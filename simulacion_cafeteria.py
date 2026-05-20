"""
Simulación de un Sistema de Colas M/M/1 con Vacaciones Múltiples del Servidor.
Cafetería — Modelado y Simulación de Sistemas Dinámicos.

Tres variables aleatorias gobiernan el sistema, cada una con su propio PRNG
implementado desde cero (sin usar `random` de la biblioteca estándar):

  1. Tiempo entre llegadas individuales ~ Exp(λ)   [Mersenne Twister MT19937]
  2. Tiempo de servicio por persona     ~ Exp(μ)   [MRG/FMRG k=2]
  3. Duración de vacación del servidor  ~ Exp(θ)   [MCG — Generador de Lehmer]

Asignar un PRNG distinto a cada variable garantiza independencia estadística
entre los flujos: ningún número uniforme se reutiliza entre procesos.

La simulación usa el esquema "next-event time advance" (avance al próximo
evento) con un heap binario como agenda de eventos: en lugar de avanzar el
reloj en pasos fijos Δt, salta directamente al instante del siguiente evento
programado, lo que evita simular tiempo muerto.
"""

import math
import heapq
from collections import deque

# ============================================================================
# PRNG 1: Mersenne Twister (MT19937) — Matsumoto y Nishimura (1998)
# ============================================================================

class MersenneTwister:
    """Generador Mersenne Twister de 32 bits (MT19937).

    Período: 2^19937 − 1 (de ahí el nombre). Equidistribución probada en
    623 dimensiones a 32 bits, lo que lo hace muy superior a cualquier LCG
    para simulaciones que consumen muchos uniformes por unidad de tiempo.

    Estado interno: un vector `mt` de N=624 enteros de 32 bits, que se
    "tuerce" (twist) en bloque cada vez que se han consumido los 624.
    """

    # Parámetros estructurales del MT19937 (NO modificar — definen el período).
    N = 624                       # tamaño del vector de estado
    M = 397                       # offset del "middle word" en la recurrencia
    MATRIX_A = 0x9908B0DF         # coeficientes de la matriz de torsión
    UPPER_MASK = 0x80000000       # bit más significativo (separa "upper" word)
    LOWER_MASK = 0x7FFFFFFF       # 31 bits inferiores (separa "lower" word)
    MASK32 = 0xFFFFFFFF           # máscara para forzar aritmética de 32 bits

    def __init__(self, seed: int):
        # Inicialización por la recurrencia lineal estándar de Knuth/MT19937,
        # que difunde los bits de la semilla por todo el vector de estado.
        self.mt = [0] * self.N
        self.index = self.N       # `index >= N` fuerza un twist en la 1ª llamada
        self.mt[0] = seed & self.MASK32
        for i in range(1, self.N):
            # Constante 1812433253 = ajuste de Knuth para buena difusión inicial.
            self.mt[i] = (1812433253 * (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) + i) & self.MASK32

    def _generate(self):
        # "Twist": regenera los 624 enteros del vector de estado en una sola
        # pasada usando la recurrencia matricial del MT. Una vez hecho, el
        # generador puede entregar 624 enteros antes del próximo twist.
        for i in range(self.N):
            # `y` combina el bit superior de mt[i] con los 31 inferiores de
            # mt[i+1] — esto introduce la dependencia "cross-word".
            y = (self.mt[i] & self.UPPER_MASK) | (self.mt[(i + 1) % self.N] & self.LOWER_MASK)
            self.mt[i] = self.mt[(i + self.M) % self.N] ^ (y >> 1)
            if y & 1:                          # si el bit más bajo de y es 1,
                self.mt[i] ^= self.MATRIX_A    # aplica los coeficientes de A.
        self.index = 0

    def next_int(self) -> int:
        """Devuelve el siguiente entero pseudoaleatorio de 32 bits."""
        if self.index >= self.N:
            self._generate()
        y = self.mt[self.index]
        self.index += 1
        # Tempering: cuatro XOR-shift que descorrelacionan los bits de salida.
        # Sin esto el MT pasa peor las pruebas de aleatoriedad pese al período.
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= y >> 18
        return y & self.MASK32

    def random(self) -> float:
        """Uniforme en [0, 1). Divide entre 2^32 (no entre 2^32 − 1) para
        conservar la equidistribución entera."""
        return self.next_int() / 4294967296.0


# ============================================================================
# PRNG 2: Generador Congruencial Multiplicativo (MCG / Lehmer) — Deng-Lin (2000)
# Caso multiplicativo (C=0) del congruencial lineal X_{i+1} = (A·X_i) mod M.
# Período: M − 1 = 2^31 − 2 cuando A es raíz primitiva de M (primo).
# ============================================================================

class MCG:
    """Generador de Lehmer / Park-Miller — multiplicativo puro.

    Asignado a las duraciones de vacación. Su período (~2·10^9) es más que
    suficiente para esta variable, que se consume sólo una vez por vacación
    (mucho menos frecuentemente que llegadas o servicios).
    """

    A = 16807                   # 7^5 — multiplicador de Park-Miller (1988)
    M = 2147483647              # 2^31 − 1, primo de Mersenne

    def __init__(self, seed: int):
        # Seed must be in (0, M). El estado cero es absorbente: si X_i = 0,
        # todos los siguientes son cero. Por eso se fuerza a 1 si llegara 0.
        self.x = seed % self.M
        if self.x == 0:
            self.x = 1

    def next_int(self) -> int:
        self.x = (self.A * self.x) % self.M
        return self.x

    def random(self) -> float:
        return self.next_int() / self.M


# Alias histórico: en el reporte académico el generador aparece como LCG, pero
# técnicamente es MCG (C=0). Se conserva el alias para compatibilidad.
LCG = MCG


# ============================================================================
# PRNG 3: Generador Recursivo Múltiple (MRG/FMRG k=2) — Deng y Lin (2000)
# ============================================================================

class MRG:
    """MRG de orden k=2 — combina dos retardos para obtener un período mucho
    mayor que un MCG de un solo retardo.

    Recurrencia:  X_i = (α₁ · X_{i-1} + α₂ · X_{i-2}) mod p

    Período máximo: p² − 1 ≈ 4.6 × 10^18 cuando los coeficientes α₁, α₂ son
    apropiados (Deng-Lin, 2000). Asignado a tiempos de servicio porque es la
    variable que más se consume después de los arribos.
    """

    P = 2147483647              # mismo primo que el MCG: 2^31 − 1
    ALPHA1 = 1071064            # coeficiente del retardo 1 (Deng-Lin)
    ALPHA2 = 2113664            # coeficiente del retardo 2 (Deng-Lin)

    def __init__(self, seed1: int, seed2: int):
        # Dos semillas independientes; ambas deben ser no-cero por la misma
        # razón que en el MCG (estado cero absorbente).
        self.x_prev = seed1 % self.P
        self.x_prev2 = seed2 % self.P
        if self.x_prev == 0:
            self.x_prev = 1
        if self.x_prev2 == 0:
            self.x_prev2 = 1

    def next_int(self) -> int:
        x_new = (self.ALPHA1 * self.x_prev + self.ALPHA2 * self.x_prev2) % self.P
        # Desplaza la "ventana" de dos retardos: x_{-2} ← x_{-1},  x_{-1} ← nuevo.
        self.x_prev2 = self.x_prev
        self.x_prev = x_new
        return x_new

    def random(self) -> float:
        return self.next_int() / self.P


# ============================================================================
# Generación de variables aleatorias por transformada inversa.
# Para X ~ Exp(λ), F⁻¹(U) = −ln(1−U)/λ ; como 1−U también es uniforme en (0,1),
# se usa la forma equivalente más simple:  X = −ln(U)/λ.
# ============================================================================

def gen_interarrival(rng: MersenneTwister, lam: float) -> float:
    """Tiempo entre dos llegadas consecutivas ~ Exp(λ)."""
    u = rng.random()
    if u == 0.0:                  # ln(0) = −∞ ; protección numérica.
        u = 1e-15
    return -math.log(u) / lam


def gen_service_time(rng: MRG, mu: float) -> float:
    """Duración de un servicio individual ~ Exp(μ)."""
    u = rng.random()
    if u == 0.0:
        u = 1e-15
    return -math.log(u) / mu


def gen_vacation_time(rng: MCG, theta: float) -> float:
    """Duración de una vacación del servidor ~ Exp(θ)."""
    u = rng.random()
    if u == 0.0:
        u = 1e-15
    return -math.log(u) / theta


# ============================================================================
# Fórmulas analíticas del modelo M/M/1 con vacaciones múltiples.
# Referencia: Haviv (2013), "Queues: A Course in Queueing Theory", Teorema 4.9
# (descomposición exponencial para vacaciones múltiples exhaustivas).
# ============================================================================

def calcular_analitico(lam: float, mu: float, theta: float):
    """Devuelve un diccionario con ρ, L, Lq, W, Wq y Wq_mm1 según la teoría.

    Cuando ρ ≥ 1 el sistema es inestable: las cinco métricas divergen y se
    devuelven como infinito. La GUI usa esto para mostrar una advertencia.
    """
    rho = lam / mu

    if rho >= 1.0:
        return {
            "rho": rho, "L": float("inf"), "Lq": float("inf"),
            "W": float("inf"), "Wq": float("inf"),
            "Wq_mm1": float("inf"),
            "estable": False,
        }

    # Wq del M/M/1 puro (sin vacaciones).
    wq_mm1 = rho / (mu * (1 - rho))
    # Descomposición de Takine-Hasegawa: la vacación añade en promedio
    # E[V_res] = 1/θ a la espera, porque la propiedad sin memoria garantiza
    # que el tiempo residual de una Exp(θ) también es Exp(θ).
    wq = wq_mm1 + 1.0 / theta
    w = wq + 1.0 / mu             # añadir el servicio medio para obtener W
    lq = lam * wq                 # ley de Little aplicada a la cola
    l = lam * w                   # ley de Little aplicada al sistema

    return {
        "rho": rho, "L": l, "Lq": lq, "W": w, "Wq": wq,
        "Wq_mm1": wq_mm1,
        "estable": True,
    }


# ============================================================================
# Motor de Simulación de Eventos Discretos (DES).
# ============================================================================

# Códigos de evento. Se usan enteros (no strings) porque el heap los compara
# como desempate cuando dos eventos ocurren en el mismo instante; usar enteros
# evita comparaciones de cadena y es más rápido.
EVENTO_LLEGADA = 0
EVENTO_FIN_SERVICIO = 1
EVENTO_FIN_VACACION = 2

# Estados posibles del servidor.
ESTADO_LIBRE = 0      # esperando, cola vacía y aún no salió de vacación
ESTADO_OCUPADO = 1    # atendiendo a un cliente
ESTADO_VACACION = 2   # fuera del mostrador (reponiendo, descanso, etc.)


def simular(lam, mu, theta, t_sim, seed_mt, seed_mcg, seed_mrg1, seed_mrg2,
            t_warmup=0.0, trace_eventos=0):
    """Ejecuta una corrida de la simulación de duración `t_sim` (minutos).

    Parámetros
    ----------
    lam, mu, theta : tasas de llegada / servicio / retorno de vacación.
    t_sim          : duración total simulada.
    seed_*         : semillas independientes para cada PRNG.
    t_warmup       : si > 0, las primeras `t_warmup` unidades se descartan
                     para las estadísticas (no para los eventos en sí).
    trace_eventos  : cuántos eventos detallar en la traza para depuración.

    Devuelve un diccionario con las métricas observadas y, opcionalmente, la
    traza inicial y snapshots periódicos para gráficas de convergencia.
    """
    # Un PRNG por flujo aleatorio — independencia entre llegadas, servicios y
    # vacaciones.
    rng_llegadas = MersenneTwister(seed_mt)
    rng_servicio = MRG(seed_mrg1, seed_mrg2)
    rng_vacacion = MCG(seed_mcg)

    # Estado del sistema.
    reloj = 0.0
    estado_servidor = ESTADO_LIBRE
    cola = deque()                   # FIFO; almacena el instante de llegada
                                     # de cada cliente para calcular su espera
    cliente_actual_llegada = 0.0     # instante de llegada del cliente que se
                                     # está sirviendo (para calcular su W)

    # Agenda de eventos (heap binario). Cada entrada es la tupla
    # (instante, contador, tipo). El contador asegura un orden FIFO estable
    # cuando dos eventos coinciden en el mismo instante.
    eventos = []
    contador_eventos = 0

    # Acumuladores para estadísticas integrales en el tiempo.
    # "Time-average" estimators: el promedio de cualquier variable de estado
    # X(t) sobre [0,T] es (1/T) ∫₀ᵀ X(t) dt. Como X(t) es constante a trozos
    # entre eventos, la integral es Σ X · Δt — eso es lo que acumulan las
    # áreas siguientes.
    num_en_cola = 0
    num_en_sistema = 0
    area_cola = 0.0          # ∫ Lq(t) dt
    area_sistema = 0.0       # ∫ L(t)  dt
    area_ocupado = 0.0       # ∫ 1{servidor ocupado} dt  → ρ_sim
    area_vacacion = 0.0      # ∫ 1{servidor en vacación} dt
    total_espera = 0.0       # Σ tiempos de espera por cliente atendido
    total_tiempo_sistema = 0.0
    clientes_servidos = 0
    clientes_llegados = 0
    total_vacaciones = 0

    t_inicio_stats = t_warmup        # antes de este instante no se cuenta
    traza = []                       # registro humano-legible de los primeros
                                     # eventos (para inspección/debug)

    # Snapshots periódicos: capturan métricas acumuladas a lo largo de la
    # corrida para que la GUI dibuje la curva de convergencia hacia el régimen
    # estacionario.
    snapshots = []
    snapshot_interval = t_sim / 20   # 20 puntos sobre la corrida

    # Sembrar la agenda con la primera llegada — sin ella el bucle no
    # arrancaría (sólo procesamos eventos que ya estén en el heap).
    t_primera = gen_interarrival(rng_llegadas, lam)
    heapq.heappush(eventos, (t_primera, contador_eventos, EVENTO_LLEGADA))
    contador_eventos += 1

    next_snapshot = snapshot_interval
    total_eventos_procesados = 0

    # ----- Bucle principal de eventos -----
    while eventos:
        t_evento, _, tipo = heapq.heappop(eventos)
        if t_evento > t_sim:
            break                    # paramos al cruzar el horizonte

        # Antes de avanzar el reloj, acumulamos el "área bajo la curva" de las
        # variables de estado durante el intervalo [reloj, t_evento). Sólo se
        # cuenta lo que ocurre después del warm-up.
        if reloj >= t_inicio_stats:
            dt = t_evento - max(reloj, t_inicio_stats)
            if reloj < t_inicio_stats:
                # Caso borde: el intervalo cruza el final del warm-up.
                dt = t_evento - t_inicio_stats
            area_cola += num_en_cola * dt
            area_sistema += num_en_sistema * dt
            area_ocupado += (1.0 if estado_servidor == ESTADO_OCUPADO else 0.0) * dt
            area_vacacion += (1.0 if estado_servidor == ESTADO_VACACION else 0.0) * dt

        reloj = t_evento
        total_eventos_procesados += 1

        # ---- LLEGADA de un cliente ----
        if tipo == EVENTO_LLEGADA:
            if reloj >= t_inicio_stats:
                clientes_llegados += 1

            # Guardar evento en la traza si todavía hay cupo.
            if trace_eventos > 0 and len(traza) < trace_eventos:
                estado_str = {ESTADO_LIBRE: "Libre", ESTADO_OCUPADO: "Ocupado", ESTADO_VACACION: "Vacación"}
                traza.append({
                    "t": reloj, "tipo": "LLEGADA",
                    "cola_antes": num_en_cola,
                    "servidor": estado_str[estado_servidor],
                })

            if estado_servidor == ESTADO_LIBRE:
                # Servidor disponible → servicio inmediato, espera = 0.
                estado_servidor = ESTADO_OCUPADO
                cliente_actual_llegada = reloj
                num_en_sistema += 1
                s = gen_service_time(rng_servicio, mu)
                heapq.heappush(eventos, (reloj + s, contador_eventos, EVENTO_FIN_SERVICIO))
                contador_eventos += 1
                if reloj >= t_inicio_stats:
                    total_espera += 0.0  # explícito: este cliente no espera
            else:
                # Servidor ocupado o de vacaciones → el cliente se forma.
                cola.append(reloj)
                num_en_cola += 1
                num_en_sistema += 1

            # Programar la próxima llegada (las llegadas son independientes
            # del estado del servidor).
            t_sig = reloj + gen_interarrival(rng_llegadas, lam)
            heapq.heappush(eventos, (t_sig, contador_eventos, EVENTO_LLEGADA))
            contador_eventos += 1

        # ---- FIN DE SERVICIO ----
        elif tipo == EVENTO_FIN_SERVICIO:
            if reloj >= t_inicio_stats:
                clientes_servidos += 1
                # W del cliente = momento de salida − momento de llegada.
                total_tiempo_sistema += reloj - cliente_actual_llegada

            num_en_sistema -= 1

            if trace_eventos > 0 and len(traza) < trace_eventos:
                traza.append({
                    "t": reloj, "tipo": "FIN_SERV",
                    "cola_antes": num_en_cola,
                    "servidor": "->Siguiente" if cola else "->Vacación",
                })

            if cola:
                # Sigue habiendo gente → atender al primero de la fila.
                t_llegada_sig = cola.popleft()
                num_en_cola -= 1
                cliente_actual_llegada = t_llegada_sig
                if reloj >= t_inicio_stats:
                    total_espera += reloj - t_llegada_sig
                s = gen_service_time(rng_servicio, mu)
                heapq.heappush(eventos, (reloj + s, contador_eventos, EVENTO_FIN_SERVICIO))
                contador_eventos += 1
            else:
                # Cola vacía → servidor se va de vacación (modelo exhaustivo).
                estado_servidor = ESTADO_VACACION
                v = gen_vacation_time(rng_vacacion, theta)
                heapq.heappush(eventos, (reloj + v, contador_eventos, EVENTO_FIN_VACACION))
                contador_eventos += 1

        # ---- FIN DE VACACIÓN ----
        elif tipo == EVENTO_FIN_VACACION:
            if reloj >= t_inicio_stats:
                total_vacaciones += 1

            if trace_eventos > 0 and len(traza) < trace_eventos:
                traza.append({
                    "t": reloj, "tipo": "FIN_VAC",
                    "cola_antes": num_en_cola,
                    "servidor": "->Atender" if cola else "->Otra Vac.",
                })

            if cola:
                # El servidor regresa y encuentra fila → atiende.
                estado_servidor = ESTADO_OCUPADO
                t_llegada_sig = cola.popleft()
                num_en_cola -= 1
                cliente_actual_llegada = t_llegada_sig
                if reloj >= t_inicio_stats:
                    total_espera += reloj - t_llegada_sig
                s = gen_service_time(rng_servicio, mu)
                heapq.heappush(eventos, (reloj + s, contador_eventos, EVENTO_FIN_SERVICIO))
                contador_eventos += 1
            else:
                # Cola vacía al volver → otra vacación. ESTO es lo que define
                # "vacaciones MÚLTIPLES" (vs. una sola vacación al vaciarse).
                v = gen_vacation_time(rng_vacacion, theta)
                heapq.heappush(eventos, (reloj + v, contador_eventos, EVENTO_FIN_VACACION))
                contador_eventos += 1

        # Snapshot periódico para la curva de convergencia.
        if reloj >= t_inicio_stats and reloj >= next_snapshot:
            t_eff = reloj - t_inicio_stats
            if t_eff > 0 and clientes_servidos > 0:
                snapshots.append({
                    "t": reloj,
                    "L": area_sistema / t_eff,
                    "Lq": area_cola / t_eff,
                    "rho": area_ocupado / t_eff,
                    "W": total_tiempo_sistema / clientes_servidos,
                    "Wq": total_espera / clientes_servidos,
                })
            next_snapshot += snapshot_interval

    # ----- Cierre: convertir áreas en promedios temporales -----
    t_efectivo = reloj - t_inicio_stats
    if t_efectivo <= 0:
        t_efectivo = 1.0          # evita división por cero en corridas muy
                                  # cortas (defensivo; no debería pasar en uso
                                  # normal).

    l_sim = area_sistema / t_efectivo
    lq_sim = area_cola / t_efectivo
    rho_sim = area_ocupado / t_efectivo
    rho_vac = area_vacacion / t_efectivo
    # W y Wq son promedios "por cliente", no integrales temporales — por eso
    # se dividen por el número de clientes servidos, no por t_efectivo.
    w_sim = total_tiempo_sistema / clientes_servidos if clientes_servidos > 0 else 0
    wq_sim = total_espera / clientes_servidos if clientes_servidos > 0 else 0

    return {
        "rho": rho_sim, "L": l_sim, "Lq": lq_sim, "W": w_sim, "Wq": wq_sim,
        "clientes_servidos": clientes_servidos,
        "clientes_llegados": clientes_llegados,
        "total_vacaciones": total_vacaciones,
        "rho_vacacion": rho_vac,
        "t_efectivo": t_efectivo,
        "traza": traza, "snapshots": snapshots,
        "total_eventos": total_eventos_procesados,
    }


# ============================================================================
# Ejecución de múltiples réplicas con intervalos de confianza.
# ============================================================================

# Valor crítico t-Student para n=10 réplicas, α=0.05 a dos colas (gl=9).
# Se pre-hardcodea porque no se quiere depender de scipy en este proyecto.
T_CRIT_9_0025 = 2.262


def ejecutar_replicas(lam, mu, theta, t_sim, t_warmup, n_replicas=10,
                      base_seed=42, trace_eventos=0):
    """Corre `n_replicas` simulaciones independientes y calcula intervalos
    de confianza al 95% para cada métrica.

    Cada réplica usa un cuádruple de semillas distinto, derivado de un MT19937
    "maestro" alimentado por `base_seed`. Esto da independencia entre réplicas
    a la vez que mantiene la corrida reproducible: con la misma `base_seed`,
    los mismos números salen siempre.
    """
    master = MersenneTwister(base_seed)
    resultados = []

    for r in range(n_replicas):
        # Generamos cuatro semillas — una por PRNG de la réplica. El módulo en
        # MCG y MRG asegura que la semilla cae en el rango admisible (1..M−1).
        s_mt = master.next_int()
        s_mcg = master.next_int() % (MCG.M - 1) + 1
        s_mrg1 = master.next_int() % (MRG.P - 1) + 1
        s_mrg2 = master.next_int() % (MRG.P - 1) + 1

        # Sólo la primera réplica produce traza (la GUI la usa para mostrar
        # el detalle paso a paso; las demás sólo aportan números).
        sim = simular(lam, mu, theta, t_sim, s_mt, s_mcg, s_mrg1, s_mrg2,
                      t_warmup, trace_eventos if r == 0 else 0)
        resultados.append(sim)

    # Estadísticos por métrica: media muestral, desviación estándar muestral
    # (denominador n-1) y semiamplitud del IC al 95% (t · s / √n).
    metricas_nombres = ["rho", "L", "Lq", "W", "Wq"]
    stats = {}

    for m in metricas_nombres:
        vals = [r[m] for r in resultados]
        media = sum(vals) / n_replicas
        var = sum((v - media) ** 2 for v in vals) / (n_replicas - 1)
        s = math.sqrt(var)
        margen = T_CRIT_9_0025 * s / math.sqrt(n_replicas)
        stats[m] = {
            "media": media, "std": s,
            "ci_lower": media - margen, "ci_upper": media + margen,
            "valores": vals,
        }

    # Validación: pruebas universales (Little) + pruebas de estado estacionario
    # (cobertura de Wq, precisión de ρ) que sólo aplican cuando la ventana de
    # observación es lo suficientemente larga.
    analitico = calcular_analitico(lam, mu, theta)
    validacion = {}

    t_obs = t_sim - t_warmup
    clientes_medio = sum(r["clientes_servidos"] for r in resultados) / n_replicas
    es_estacionario = t_obs >= 500 and clientes_medio >= 150

    validacion["es_estacionario"] = es_estacionario
    validacion["t_obs"] = t_obs
    validacion["clientes_medio"] = clientes_medio

    if analitico["estable"]:
        # --- Pruebas universales (siempre aplican) ---

        # Ley de Little aplicada al sistema completo: |L − λ·W|/L < 5%.
        l_media = stats["L"]["media"]
        w_media = stats["W"]["media"]
        if l_media > 0:
            little_L = abs(l_media - lam * w_media) / l_media
        else:
            little_L = 0
        validacion["Little_L"] = little_L < 0.05

        # Ley de Little aplicada a la cola: |Lq − λ·Wq|/Lq < 5%.
        lq_media = stats["Lq"]["media"]
        wq_media = stats["Wq"]["media"]
        if lq_media > 0:
            little_Lq = abs(lq_media - lam * wq_media) / lq_media
        else:
            little_Lq = 0
        validacion["Little_Lq"] = little_Lq < 0.05

        validacion["Little_L_valor"] = little_L
        validacion["Little_Lq_valor"] = little_Lq

        # --- Pruebas de estado estacionario (sólo cuando hay suficientes datos) ---

        wq_a = analitico["Wq"]
        validacion["Wq_en_IC"] = stats["Wq"]["ci_lower"] <= wq_a <= stats["Wq"]["ci_upper"]

        rho_media = stats["rho"]["media"]
        validacion["rho_precision"] = abs(rho_media - lam / mu) < 0.02
        validacion["rho_diff"] = abs(rho_media - lam / mu)

    return {
        "resultados": resultados,
        "stats": stats,
        "validacion": validacion,
        "analitico": analitico,
        "n_replicas": n_replicas,
    }


# ============================================================================
# Prueba Chi-Cuadrado de bondad de ajuste para Exp(tasa).
# ============================================================================

def chi_cuadrado_exp(datos, tasa, num_bins=6):
    """Prueba χ² con bins **equiprobables** para H₀: datos ~ Exp(tasa).

    La estrategia de bins equiprobables (no equiespaciados) es estándar en
    Walpole/Myers: garantiza que el conteo esperado en cada bin sea n/k, lo
    que estabiliza la varianza del estadístico y mejora la aproximación a χ².

    Devuelve (chi2, chi2_crit, acepta, observados, esperados, edges).
    """
    n = len(datos)
    if n == 0:
        return 0, 0, False, [], 0, []

    # Construir los k bordes de bin como cuantiles de la exponencial:
    #   F(x) = 1 − e^(−λx)  →  x_i = −ln(1 − i/k)/λ
    bin_edges = [0.0]
    for i in range(1, num_bins):
        bin_edges.append(-math.log(1 - i / num_bins) / tasa)
    bin_edges.append(float("inf"))

    # Contar observaciones por bin.
    observados = [0] * num_bins
    for x in datos:
        for b in range(num_bins):
            if x < bin_edges[b + 1]:
                observados[b] += 1
                break

    esperados = n / num_bins                 # constante por construcción
    chi2 = sum((o - esperados) ** 2 / esperados for o in observados)

    # Grados de libertad: k − 1 (por la suma fija) − 1 (parámetro λ estimado).
    # Aquí λ está dado por el usuario, así que estrictamente serían k−1; se
    # deja k−2 por convención conservadora del curso.
    gl = num_bins - 1 - 1

    # Tabla de χ² críticos al 95% (α=0.05). Se incluyen hasta gl=15 porque la
    # GUI permite ajustar el número de bins; basta con eso para uso típico.
    chi2_criticos = {
        1: 3.841, 2: 5.991, 3: 7.815, 4: 9.488, 5: 11.070,
        6: 12.592, 7: 14.067, 8: 15.507, 9: 16.919, 10: 18.307,
        11: 19.675, 12: 21.026, 13: 22.362, 14: 23.685, 15: 24.996,
    }
    chi2_crit = chi2_criticos.get(gl, 16.919)

    return chi2, chi2_crit, chi2 <= chi2_crit, observados, esperados, bin_edges


# ============================================================================
# Reporte académico detallado en texto plano.
# `print_fn` permite redirigir la salida (la GUI lo usa para escribir a un
# StringIO en vez de a stdout).
# ============================================================================

def reporte_completo(sim, analitico, lam, mu, theta, t_sim, t_warmup, seeds,
                     replicas_result=None, print_fn=None):
    _print = print_fn or print

    # Helpers locales para que cada sección tenga el mismo formato visual.
    def linea(c="═", n=72):
        _print(c * n)

    def titulo_seccion(num, texto):
        _print()
        linea("─")
        _print(f"  SECCIÓN {num}: {texto}")
        linea("─")
        _print()

    def pct_error(s, a):
        # Para métricas con valor analítico cero o infinito el porcentaje no
        # tiene sentido — devolvemos "N/A" para no contaminar la tabla.
        if a == 0 or not math.isfinite(a):
            return "N/A"
        return f"{abs(s - a) / a * 100:.2f}%"

    # ENCABEZADO
    _print()
    linea()
    _print("  SIMULACIÓN DE COLA M/M/1 CON VACACIONES MÚLTIPLES DEL SERVIDOR")
    _print("  Cafetería Universitaria — UANL")
    _print("  Modelado y Simulación de Sistemas Dinámicos")
    linea()

    # ====================================================================
    # SECCIÓN 1: DESCRIPCIÓN DEL SISTEMA
    # ====================================================================
    titulo_seccion(1, "DESCRIPCIÓN DEL SISTEMA")

    _print("  Modelo: M/M/1 con vacaciones múltiples del servidor")
    _print()
    _print("  En notación de Kendall:")
    _print("    M       → Llegadas individuales siguen proceso de Poisson")
    _print("    M       → Tiempos de servicio individuales son exponenciales")
    _print("    1       → Un solo servidor")
    _print("    + Vac.  → Vacaciones múltiples i.i.d. del servidor")
    _print()
    _print("  Flujo del sistema:")
    _print("    Cliente llega → Si servidor libre: servicio inmediato")
    _print("                  → Si servidor ocupado o de vacación: espera en cola (FIFO)")
    _print("    Fin servicio  → Si cola no vacía: atiende siguiente")
    _print("                  → Si cola vacía: servidor inicia vacación")
    _print("    Fin vacación  → Si cola no vacía: atiende primer cliente")
    _print("                  → Si cola vacía: otra vacación")
    _print()
    _print("  Componentes estructurales (3 variables independientes):")
    _print("    ┌──────────────────────────────────────────────────────────────┐")
    _print("    │  CUÁNDO llegan    →  Tiempo entre llegadas  ~ Exp(λ)       │")
    _print("    │  CUÁNTO TARDA     →  Tiempo de servicio     ~ Exp(μ)       │")
    _print("    │  CUÁNTO DESCANSA  →  Duración de vacación   ~ Exp(θ)       │")
    _print("    └──────────────────────────────────────────────────────────────┘")
    _print()

    # ====================================================================
    # SECCIÓN 2: PARÁMETROS DE ENTRADA
    # ====================================================================
    titulo_seccion(2, "PARÁMETROS DE ENTRADA")

    _print(f"  λ (tasa de llegada individual)     = {lam:.4f} clientes/min  ({lam*60:.1f} clientes/hora)")
    _print(f"  μ (tasa de servicio individual)     = {mu:.4f} clientes/min ({mu*60:.1f} clientes/hora)")
    _print(f"  θ (tasa de retorno de vacación)     = {theta:.4f} retornos/min ({theta*60:.1f} retornos/hora)")
    _print(f"  1/λ (tiempo medio entre llegadas)   = {1/lam:.4f} min")
    _print(f"  1/μ (tiempo medio de servicio)      = {1/mu:.4f} min")
    _print(f"  1/θ (duración media de vacación)    = {1/theta:.4f} min")
    _print(f"  ρ = λ / μ                           = {analitico['rho']:.4f}")
    _print()
    _print(f"  Tiempo de simulación               = {t_sim:,.0f} min ({t_sim/60:.1f} horas)")
    _print(f"  Período de calentamiento           = {t_warmup:,.0f} min ({t_warmup/60:.1f} horas)")
    _print(f"  Tiempo efectivo para estadísticas  = {t_sim - t_warmup:,.0f} min")
    _print()

    if analitico["rho"] < 1:
        _print(f"  Condición de estabilidad: ρ = {analitico['rho']:.4f} < 1  ✓  Sistema ESTABLE")
    else:
        _print(f"  Condición de estabilidad: ρ = {analitico['rho']:.4f} >= 1  ✗  Sistema INESTABLE")
    _print()

    # ====================================================================
    # SECCIÓN 3: GENERADORES DE NÚMEROS PSEUDOALEATORIOS (PRNGs)
    # ====================================================================
    titulo_seccion(3, "GENERADORES DE NÚMEROS PSEUDOALEATORIOS (PRNGs)")

    _print("  ┌─ PRNG 1: Mersenne Twister (MT19937) ─────────────────────────┐")
    _print("  │  Fuente: Matsumoto y Nishimura (1998)                        │")
    _print("  │  Asignado a: Tiempo entre llegadas individuales              │")
    _print("  │  Período: 2^19937 - 1 ≈ 4.3 × 10^6001                      │")
    _print("  │  Equidistribución: 623 dimensiones a 32 bits                 │")
    _print(f"  │  Semilla: {seeds['mt']:<50d}│")
    _print("  │                                                              │")
    _print("  │  Recurrencia:                                                │")
    _print("  │  x_{k+n} = x_{k+m} ⊕ (x_k^u ‖ x_{k+1}^l) · A             │")
    _print("  └──────────────────────────────────────────────────────────────┘")
    _print()

    # Demostración: regeneramos el PRNG con la misma semilla para imprimir los
    # primeros 10 enteros que produciría — útil para verificar contra el
    # reporte y reproducir paso a paso.
    mt_demo = MersenneTwister(seeds["mt"])
    _print("  Primeros 10 números uniformes U ~ (0,1) generados:")
    _print("  ┌──────┬──────────────┬──────────────────┐")
    _print("  │  i   │  Entero X_i  │  U_i = X_i/2^32  │")
    _print("  ├──────┼──────────────┼──────────────────┤")
    for i in range(10):
        xi = mt_demo.next_int()
        ui = xi / 4294967296.0
        _print(f"  │  {i+1:2d}  │ {xi:>12d} │     {ui:.10f}   │")
    _print("  └──────┴──────────────┴──────────────────┘")
    _print()

    _print("  ┌─ PRNG 2: Generador Recursivo Múltiple (MRG, k=2) ──────────┐")
    _print("  │  Fuente: Deng y Lin (2000)                                   │")
    _print("  │  Asignado a: Tiempo de servicio por persona                  │")
    _print("  │  Período máximo: p^2 - 1 = 4,611,686,014,132,420,608        │")
    _print(f"  │  Semillas: X_0 = {seeds['mrg1']}, X_{{-1}} = {seeds['mrg2']:<28d}│")
    _print("  │                                                              │")
    _print("  │  Recurrencia:                                                │")
    _print(f"  │  X_i = ({MRG.ALPHA1} · X_{{i-1}} + {MRG.ALPHA2} · X_{{i-2}}) mod p      │")
    _print("  │  U_i = X_i / p                                               │")
    _print("  └──────────────────────────────────────────────────────────────┘")
    _print()

    mrg_demo = MRG(seeds["mrg1"], seeds["mrg2"])
    _print("  Primeros 10 números uniformes generados:")
    _print("  ┌──────┬──────────────────┬──────────────────┐")
    _print("  │  i   │     X_i          │     U_i          │")
    _print("  ├──────┼──────────────────┼──────────────────┤")
    for i in range(10):
        xi = mrg_demo.next_int()
        ui = xi / MRG.P
        _print(f"  │  {i+1:2d}  │  {xi:>14d}  │     {ui:.10f}   │")
    _print("  └──────┴──────────────────┴──────────────────┘")
    _print()

    _print("  ┌─ PRNG 3: Generador Congruencial Multiplicativo (MCG / Lehmer) ┐")
    _print("  │  Fuente: Deng y Lin (2000)                                   │")
    _print("  │  Asignado a: Duración de vacación del servidor               │")
    _print("  │  Período: 2^31 - 2 = 2,147,483,646                          │")
    _print(f"  │  Semilla: {seeds['mcg']:<50d}│")
    _print("  │                                                              │")
    _print("  │  Recurrencia (multiplicativo puro, C=0):                     │")
    _print("  │  X_i = (16807 · X_{i-1}) mod (2^31 - 1)                     │")
    _print("  │  U_i = X_i / (2^31 - 1)                                     │")
    _print("  └──────────────────────────────────────────────────────────────┘")
    _print()

    mcg_demo = MCG(seeds["mcg"])
    _print("  Primeros 10 números uniformes generados:")
    _print("  ┌──────┬──────────────────┬──────────────────┐")
    _print("  │  i   │     X_i          │     U_i          │")
    _print("  ├──────┼──────────────────┼──────────────────┤")
    for i in range(10):
        xi = mcg_demo.next_int()
        ui = xi / MCG.M
        _print(f"  │  {i+1:2d}  │  {xi:>14d}  │     {ui:.10f}   │")
    _print("  └──────┴──────────────────┴──────────────────┘")
    _print()

    # ====================================================================
    # SECCIÓN 4: TRANSFORMADA INVERSA — GENERACIÓN DE VARIABLES
    # ====================================================================
    titulo_seccion(4, "TRANSFORMADA INVERSA — GENERACIÓN DE VARIABLES ALEATORIAS")

    _print("  Las tres variables se generan con la transformada inversa de la")
    _print("  distribución exponencial: X = -(1/tasa) · ln(U)")
    _print()

    _print("  VARIABLE 1: Tiempo entre llegadas ~ Exp(λ)")
    _print(f"  Fórmula: T = -(1/λ) · ln(U) = -(1/{lam}) · ln(U)")
    _print()
    _print("  Ejemplo paso a paso con los primeros 5 valores del MT19937:")
    _print("  ┌──────┬──────────────┬────────────────────────────┬────────────┐")
    _print("  │  i   │  U_i (MT)    │  Cálculo                   │  T_i (min) │")
    _print("  ├──────┼──────────────┼────────────────────────────┼────────────┤")

    mt_demo2 = MersenneTwister(seeds["mt"])
    for i in range(5):
        u = mt_demo2.random()
        t = -math.log(u) / lam
        _print(f"  │  {i+1:2d}  │  {u:.10f}│  -(1/{lam})·ln({u:.6f})  │  {t:8.4f}   │")
    _print("  └──────┴──────────────┴────────────────────────────┴────────────┘")
    _print()

    _print("  VARIABLE 2: Tiempo de servicio ~ Exp(μ)")
    _print(f"  Fórmula: S = -(1/μ) · ln(U) = -(1/{mu}) · ln(U)")
    _print()
    _print("  Ejemplo paso a paso con los primeros 5 valores del MRG:")
    _print("  ┌──────┬──────────────┬────────────────────────────┬────────────┐")
    _print("  │  i   │  U_i (MRG)   │  Cálculo                   │  S_i (min) │")
    _print("  ├──────┼──────────────┼────────────────────────────┼────────────┤")

    mrg_demo2 = MRG(seeds["mrg1"], seeds["mrg2"])
    for i in range(5):
        u = mrg_demo2.random()
        s = -math.log(u) / mu
        _print(f"  │  {i+1:2d}  │  {u:.10f}│  -(1/{mu})·ln({u:.6f})  │  {s:8.4f}   │")
    _print("  └──────┴──────────────┴────────────────────────────┴────────────┘")
    _print()

    _print("  VARIABLE 3: Duración de vacación ~ Exp(θ)")
    _print(f"  Fórmula: V = -(1/θ) · ln(U) = -(1/{theta}) · ln(U)")
    _print()
    _print("  Ejemplo paso a paso con los primeros 5 valores del MCG:")
    _print("  ┌──────┬──────────────┬────────────────────────────┬────────────┐")
    _print("  │  i   │  U_i (MCG)   │  Cálculo                   │  V_i (min) │")
    _print("  ├──────┼──────────────┼────────────────────────────┼────────────┤")

    mcg_demo2 = MCG(seeds["mcg"])
    for i in range(5):
        u = mcg_demo2.random()
        v = -math.log(u) / theta
        _print(f"  │  {i+1:2d}  │  {u:.10f}│  -(1/{theta})·ln({u:.6f})  │  {v:8.4f}   │")
    _print("  └──────┴──────────────┴────────────────────────────┴────────────┘")
    _print()

    # ====================================================================
    # SECCIÓN 5: TRAZA DE EVENTOS
    # ====================================================================
    titulo_seccion(5, "TRAZA DE EVENTOS — PRIMEROS PASOS DE LA SIMULACIÓN")

    _print("  La simulación avanza de evento en evento (next-event time advance).")
    _print("  Tipos de evento: LLEGADA | FIN_SERVICIO | FIN_VACACIÓN")
    _print()

    traza = sim["traza"]
    if traza:
        _print(f"  Primeros {len(traza)} eventos procesados:")
        _print("  ┌────────┬──────────┬──────────────┬───────────┬───────────────────────┐")
        _print("  │ Evento │ Reloj    │ Tipo         │ En cola   │ Detalle               │")
        _print("  ├────────┼──────────┼──────────────┼───────────┼───────────────────────┤")
        for i, ev in enumerate(traza):
            if ev["tipo"] == "LLEGADA":
                det = f"Servidor: {ev['servidor']}"
            else:
                det = f"Servidor {ev['servidor']}"
            _print(f"  │  {i+1:4d}  │ {ev['t']:8.3f} │ {ev['tipo']:<12s} │    {ev['cola_antes']:3d}    │ {det:<21s} │")
        _print("  └────────┴──────────┴──────────────┴───────────┴───────────────────────┘")
        _print()
    _print(f"  Total de eventos procesados en la simulación: {sim['total_eventos']:,}")
    _print()

    # ====================================================================
    # SECCIÓN 6: RESULTADOS DE LA SIMULACIÓN
    # ====================================================================
    titulo_seccion(6, "RESULTADOS DE LA SIMULACIÓN")

    _print(f"  Clientes llegados                  = {sim['clientes_llegados']:>10,}")
    _print(f"  Clientes atendidos completamente   = {sim['clientes_servidos']:>10,}")
    _print(f"  Total de vacaciones tomadas         = {sim['total_vacaciones']:>10,}")
    _print(f"  Fracción de tiempo en vacación      = {sim['rho_vacacion']:>10.4f}")
    _print(f"  Fracción de tiempo ocupado (ρ)      = {sim['rho']:>10.4f}  (teórico: {analitico['rho']:.4f})")
    _print(f"  Fracción de tiempo libre            = {1 - sim['rho'] - sim['rho_vacacion']:>10.4f}")
    _print()

    # ====================================================================
    # SECCIÓN 7: PRUEBAS DE BONDAD DE AJUSTE (Chi-Cuadrado)
    # ====================================================================
    titulo_seccion(7, "PRUEBAS DE BONDAD DE AJUSTE — CHI-CUADRADO")

    _print("  Se aplica la prueba χ² para verificar que las variables generadas")
    _print("  siguen las distribuciones teóricas especificadas.")
    _print()

    # 5000 muestras es suficiente para que el χ² sea sensible sin ser caro.
    n_test = 5000

    mt_test = MersenneTwister(seeds["mt"])
    llegadas_test = [gen_interarrival(mt_test, lam) for _ in range(n_test)]
    chi2, chi2_c, acepta, obs_bins, esp, edges = chi_cuadrado_exp(llegadas_test, lam)

    _print(f"  PRUEBA 1: Tiempo entre llegadas ~ Exp(λ={lam})")
    _print(f"  Muestra: {n_test} valores generados con MT19937")
    _print(f"  Media teórica: {1/lam:.4f} min | Media observada: {sum(llegadas_test)/len(llegadas_test):.4f} min")
    _print(f"  Bins equiprobables: 6 | Grados de libertad: 4")
    _print(f"  χ² calculado = {chi2:.4f}")
    _print(f"  χ² crítico (α=0.05, gl=4) = {chi2_c:.4f}")
    _print(f"  Resultado: {'NO SE RECHAZA H₀ ✓' if acepta else 'SE RECHAZA H₀ ✗'} — ", end="")
    _print(f"{'La distribución exponencial es un buen ajuste' if acepta else 'El ajuste no es adecuado'}")
    _print()

    mrg_test = MRG(seeds["mrg1"], seeds["mrg2"])
    servicio_test = [gen_service_time(mrg_test, mu) for _ in range(n_test)]
    chi2_s, chi2_cs, acepta_s, _, _, _ = chi_cuadrado_exp(servicio_test, mu)

    _print(f"  PRUEBA 2: Tiempo de servicio ~ Exp(μ={mu})")
    _print(f"  Muestra: {n_test} valores generados con MRG/FMRG")
    _print(f"  Media teórica: {1/mu:.4f} min | Media observada: {sum(servicio_test)/len(servicio_test):.4f} min")
    _print(f"  χ² calculado = {chi2_s:.4f}")
    _print(f"  χ² crítico (α=0.05, gl=4) = {chi2_cs:.4f}")
    _print(f"  Resultado: {'NO SE RECHAZA H₀ ✓' if acepta_s else 'SE RECHAZA H₀ ✗'}")
    _print()

    mcg_test = MCG(seeds["mcg"])
    vacacion_test = [gen_vacation_time(mcg_test, theta) for _ in range(n_test)]
    chi2_v, chi2_cv, acepta_v, _, _, _ = chi_cuadrado_exp(vacacion_test, theta)

    _print(f"  PRUEBA 3: Duración de vacación ~ Exp(θ={theta})")
    _print(f"  Muestra: {n_test} valores generados con MCG")
    _print(f"  Media teórica: {1/theta:.4f} min | Media observada: {sum(vacacion_test)/len(vacacion_test):.4f} min")
    _print(f"  χ² calculado = {chi2_v:.4f}")
    _print(f"  χ² crítico (α=0.05, gl=4) = {chi2_cv:.4f}")
    _print(f"  Resultado: {'NO SE RECHAZA H₀ ✓' if acepta_v else 'SE RECHAZA H₀ ✗'}")
    _print()

    # ====================================================================
    # SECCIÓN 8: CONVERGENCIA AL ESTADO ESTACIONARIO
    # ====================================================================
    titulo_seccion(8, "CONVERGENCIA AL ESTADO ESTACIONARIO")

    _print("  Evolución de las métricas a lo largo del tiempo simulado.")
    _print("  Las métricas deben estabilizarse conforme la simulación avanza.")
    _print()

    snapshots = sim["snapshots"]
    if snapshots:
        _print("  ┌──────────┬─────────┬─────────┬─────────┬─────────┬─────────┐")
        _print("  │ Tiempo   │   ρ     │   L     │   Lq    │  W(min) │ Wq(min) │")
        _print("  ├──────────┼─────────┼─────────┼─────────┼─────────┼─────────┤")
        for s in snapshots:
            _print(f"  │ {s['t']:>7.0f}  │ {s['rho']:7.4f} │ {s['L']:7.4f} │ {s['Lq']:7.4f} │ {s['W']:7.4f} │ {s['Wq']:7.4f} │")
        _print("  ├──────────┼─────────┼─────────┼─────────┼─────────┼─────────┤")
        a = analitico
        _print(f"  │ Analítico│ {a['rho']:7.4f} │ {a['L']:7.4f} │ {a['Lq']:7.4f} │ {a['W']:7.4f} │ {a['Wq']:7.4f} │")
        _print("  └──────────┴─────────┴─────────┴─────────┴─────────┴─────────┘")
        _print()

        # Gráfica ASCII de convergencia: cada línea es un snapshot, la barra '│'
        # marca el valor teórico y '●' el observado en ese instante. Permite ver
        # visualmente cómo la simulación se acerca al estacionario.
        _print("  Convergencia de ρ (utilización del servidor):")
        rho_teo = analitico["rho"]
        for s in snapshots:
            pos = int((s["rho"] / (rho_teo * 1.5)) * 50) if rho_teo > 0 else 0
            pos = max(0, min(49, pos))
            teo_pos = int((rho_teo / (rho_teo * 1.5)) * 50) if rho_teo > 0 else 0
            teo_pos = min(teo_pos, 49)
            line = list("·" * 50)
            line[teo_pos] = "│"
            line[pos] = "●"
            _print(f"  t={s['t']:>5.0f} {''.join(line)} {s['rho']:.4f}")
        _print(f"  {'':>8s} {'':>{teo_pos}}▲ ρ_teórico = {rho_teo:.4f}")
    _print()

    # ====================================================================
    # SECCIÓN 9: MODELO ANALÍTICO M/M/1 CON VACACIONES
    # ====================================================================
    titulo_seccion(9, "MODELO ANALÍTICO M/M/1 CON VACACIONES — TEOREMA 4.9")

    _print("  Fuente: Haviv (2013), Queues: A Course in Queueing Theory")
    _print("  Teorema 4.9 — Descomposición con vacaciones múltiples")
    _print()
    _print("  Paso 1: Intensidad de tráfico")
    _print(f"    ρ = λ / μ = {lam} / {mu} = {analitico['rho']:.4f}")
    _print()
    _print("  Paso 2: Tiempo de espera en cola del M/M/1 estándar")
    _print(f"    Wq_MM1 = ρ / (μ(1-ρ)) = {analitico['rho']:.4f} / ({mu}×{1-analitico['rho']:.4f})")
    _print(f"           = {analitico['Wq_mm1']:.4f} min")
    _print()
    _print("  Paso 3: Vida residual media de la vacación")
    _print(f"    Para V ~ Exp(θ): E[V²]/(2·E[V]) = 1/θ = 1/{theta} = {1/theta:.4f} min")
    _print("    (por la propiedad sin memoria de la exponencial)")
    _print()
    _print("  Paso 4: Descomposición (Teorema 4.9)")
    _print(f"    Wq = Wq_MM1 + 1/θ = {analitico['Wq_mm1']:.4f} + {1/theta:.4f} = {analitico['Wq']:.4f} min")
    _print()
    _print("  Paso 5: Tiempo promedio en el sistema")
    _print(f"    W = Wq + 1/μ = {analitico['Wq']:.4f} + {1/mu:.4f} = {analitico['W']:.4f} min")
    _print()
    _print("  Paso 6: Ley de Little")
    _print(f"    Lq = λ · Wq = {lam} × {analitico['Wq']:.4f} = {analitico['Lq']:.4f} clientes")
    _print(f"    L  = λ · W  = {lam} × {analitico['W']:.4f}  = {analitico['L']:.4f} clientes")
    _print()

    # ====================================================================
    # SECCIÓN 10: COMPARACIÓN FINAL — SIMULACIÓN vs ANALÍTICO
    # ====================================================================
    titulo_seccion(10, "COMPARACIÓN FINAL — SIMULACIÓN vs MODELO ANALÍTICO")

    _print("  ┌────────────────┬────────────────┬────────────────┬──────────────┐")
    _print("  │ Métrica        │   Simulación   │   Analítico    │  Error (%)   │")
    _print("  ├────────────────┼────────────────┼────────────────┼──────────────┤")

    metricas = [
        ("ρ (utilización)", sim["rho"], analitico["rho"]),
        ("L  (en sistema)", sim["L"], analitico["L"]),
        ("Lq (en cola)", sim["Lq"], analitico["Lq"]),
        ("W  (min)", sim["W"], analitico["W"]),
        ("Wq (min)", sim["Wq"], analitico["Wq"]),
    ]

    for nombre, s_val, a_val in metricas:
        err = pct_error(s_val, a_val)
        _print(f"  │ {nombre:<14s} │    {s_val:10.4f}  │    {a_val:10.4f}  │    {err:>8s}  │")

    _print("  └────────────────┴────────────────┴────────────────┴──────────────┘")
    _print()

    # Error promedio entre simulación y teoría — un solo número para resumir
    # la calidad de la corrida. <5% se considera buena en este curso.
    errores = []
    for _, s_val, a_val in metricas:
        if a_val != 0 and math.isfinite(a_val):
            errores.append(abs(s_val - a_val) / a_val * 100)
    if errores:
        err_promedio = sum(errores) / len(errores)
        _print(f"  Error promedio entre simulación y modelo: {err_promedio:.2f}%")
        if err_promedio < 5:
            _print("  Los resultados de la simulación validan el modelo analítico.")
        else:
            _print("  Considere aumentar el tiempo de simulación para mejor convergencia.")
    _print()

    # ====================================================================
    # SECCIÓN 11: RÉPLICAS E INTERVALOS DE CONFIANZA
    # ====================================================================
    if replicas_result:
        titulo_seccion(11, "RÉPLICAS E INTERVALOS DE CONFIANZA AL 95%")

        rr = replicas_result
        n_rep = rr["n_replicas"]
        stats = rr["stats"]

        _print(f"  Número de réplicas: {n_rep}")
        _print(f"  Valor crítico t_({{n-1}}, 0.025) = t_(9, 0.025) = {T_CRIT_9_0025}")
        _print(f"  IC: X̄ ± {T_CRIT_9_0025} · s / √{n_rep}")
        _print()

        _print("  RESULTADOS POR RÉPLICA")
        _print("  ┌─────────┬──────────┬──────────┬──────────┬──────────┬──────────┐")
        _print("  │ Réplica │    ρ     │    L     │    Lq    │  W (min) │ Wq (min) │")
        _print("  ├─────────┼──────────┼──────────┼──────────┼──────────┼──────────┤")
        for r in range(n_rep):
            res = rr["resultados"][r]
            _print(f"  │   {r+1:2d}    │ {res['rho']:8.4f} │ {res['L']:8.4f} │ {res['Lq']:8.4f} │ {res['W']:8.4f} │ {res['Wq']:8.4f} │")
        _print("  ├─────────┼──────────┼──────────┼──────────┼──────────┼──────────┤")
        _print(f"  │  Media  │ {stats['rho']['media']:8.4f} │ {stats['L']['media']:8.4f} │ {stats['Lq']['media']:8.4f} │ {stats['W']['media']:8.4f} │ {stats['Wq']['media']:8.4f} │")
        _print(f"  │  Std    │ {stats['rho']['std']:8.4f} │ {stats['L']['std']:8.4f} │ {stats['Lq']['std']:8.4f} │ {stats['W']['std']:8.4f} │ {stats['Wq']['std']:8.4f} │")
        _print("  └─────────┴──────────┴──────────┴──────────┴──────────┴──────────┘")
        _print()

        _print("  INTERVALOS DE CONFIANZA AL 95%")
        _print("  ┌────────────────┬──────────────┬──────────────────────────┬──────────────┬──────────┐")
        _print("  │ Métrica        │   Analítico  │    IC 95% [lower,upper]  │  Media sim.  │ Contiene │")
        _print("  ├────────────────┼──────────────┼──────────────────────────┼──────────────┼──────────┤")

        a = rr["analitico"]
        for nombre_corto, clave, a_val in [
            ("ρ (utilización)", "rho", a["rho"]),
            ("L  (en sistema)", "L", a["L"]),
            ("Lq (en cola)", "Lq", a["Lq"]),
            ("W  (min)", "W", a["W"]),
            ("Wq (min)", "Wq", a["Wq"]),
        ]:
            st = stats[clave]
            contiene = st["ci_lower"] <= a_val <= st["ci_upper"]
            _print(f"  │ {nombre_corto:<14s} │   {a_val:8.4f}   │  [{st['ci_lower']:8.4f}, {st['ci_upper']:8.4f}]  │   {st['media']:8.4f}   │   {'✓' if contiene else '✗'}      │")

        _print("  └────────────────┴──────────────┴──────────────────────────┴──────────────┴──────────┘")
        _print()

        _print("  VALIDACIÓN (§8.4)")
        val = rr["validacion"]
        _print(f"  1. Wq analítico dentro del IC 95%:           {'PASA ✓' if val.get('Wq_en_IC') else 'FALLA ✗'}")
        _print(f"  2. Ley de Little (L = λ·W), error relativo:  {val.get('Little_L_valor', 0)*100:.2f}%  {'PASA ✓' if val.get('Little_L') else 'FALLA ✗'}")
        _print(f"  3. Ley de Little (Lq = λ·Wq), error relativo: {val.get('Little_Lq_valor', 0)*100:.2f}%  {'PASA ✓' if val.get('Little_Lq') else 'FALLA ✗'}")
        _print(f"  4. |ρ_sim - λ/μ| < 0.02:                    {val.get('rho_diff', 0):.4f}  {'PASA ✓' if val.get('rho_precision') else 'FALLA ✗'}")
        _print()

    # RESUMEN DE PRNGs
    _print("  RESUMEN DE GENERADORES UTILIZADOS")
    _print("  ┌────────────────────────────┬──────────────────────────┬────────────────────┐")
    _print("  │ Variable                   │ PRNG                     │ Fuente             │")
    _print("  ├────────────────────────────┼──────────────────────────┼────────────────────┤")
    _print("  │ Tiempo entre llegadas      │ Mersenne Twister MT19937 │ Matsumoto (1998)   │")
    _print("  │ Tiempo de servicio         │ MRG/FMRG (k=2)          │ Deng y Lin (2000)  │")
    _print("  │ Duración de vacación       │ MCG (Lehmer)             │ Deng y Lin (2000)  │")
    _print("  └────────────────────────────┴──────────────────────────┴────────────────────┘")
    _print()

    linea()
    _print("  FIN DEL REPORTE")
    linea()
    _print()


# ============================================================================
# Punto de entrada principal — corrida desde línea de comandos.
# La GUI no usa este bloque; tiene su propio entry point en
# `simulacion_cafeteria_gui.py`.
# ============================================================================

if __name__ == "__main__":
    # Parámetros del sistema (§3.2: cafetería en hora pico 12:30–14:30).
    LAM = 0.5      # llegadas/min  (1 cliente cada 2 min en promedio)
    MU = 0.67      # servicios/min (1.49 min de servicio en promedio)
    THETA = 0.2    # retornos/min  (5 min de vacación en promedio)

    # Estrategia de simulación: turno de 12 horas (8am–8pm), ventana de
    # observación de 1pm a 2pm (minuto 300 a 420). Los primeros 300 min se
    # simulan normalmente (llegan clientes, se atienden, hay vacaciones) pero
    # las estadísticas sólo se recolectan dentro de la ventana de observación.
    T_SIM = 120      # 2 horas de grabación observada
    T_WARMUP = 0     # observar desde el inicio de la grabación

    # Semillas — fijas para reproducibilidad de los reportes académicos. Cambiar
    # cualquiera produce una corrida distinta pero igualmente válida.
    SEED_MT = 19937
    SEED_MCG = 48271
    SEED_MRG1 = 31415
    SEED_MRG2 = 92653

    seeds = {"mt": SEED_MT, "mcg": SEED_MCG, "mrg1": SEED_MRG1, "mrg2": SEED_MRG2}

    analitico = calcular_analitico(LAM, MU, THETA)

    print()
    print(f"  Verificando estabilidad: ρ = {analitico['rho']:.4f}", end="")
    if analitico["estable"]:
        print(" < 1 ✓ — Sistema estable")
    else:
        print(" ≥ 1 ✗ — SISTEMA INESTABLE")

    print(f"  Ejecutando simulación individual ({T_SIM:,} minutos simulados)...")
    resultado = simular(LAM, MU, THETA, T_SIM, SEED_MT, SEED_MCG, SEED_MRG1, SEED_MRG2,
                        T_WARMUP, trace_eventos=20)
    print("  Simulación completada.")

    print(f"\n  Ejecutando {10} réplicas independientes...")
    replicas = ejecutar_replicas(LAM, MU, THETA, T_SIM, T_WARMUP,
                                n_replicas=10, base_seed=42, trace_eventos=20)
    print("  Réplicas completadas.")

    reporte_completo(resultado, analitico, LAM, MU, THETA, T_SIM, T_WARMUP, seeds,
                     replicas_result=replicas)
