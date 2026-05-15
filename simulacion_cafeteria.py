"""
Simulación de un Sistema de Colas M/M/1 con Vacaciones Múltiples del Servidor
Cafetería Universitaria — UANL

Modelado y Simulación de Sistemas Dinámicos

Tres variables estocásticas:
  1. Tiempo entre llegadas individuales ~ Exp(λ)   [Mersenne Twister MT19937]
  2. Tiempo de servicio por persona     ~ Exp(μ)   [MRG/FMRG k=2]
  3. Duración de vacación del servidor   ~ Exp(θ)   [LCG]
"""

import math
import heapq
from collections import deque


# ============================================================================
# PRNG 1: Mersenne Twister (MT19937) — Matsumoto y Nishimura (1998)
# ============================================================================

class MersenneTwister:
    N = 624
    M = 397
    MATRIX_A = 0x9908B0DF
    UPPER_MASK = 0x80000000
    LOWER_MASK = 0x7FFFFFFF
    MASK32 = 0xFFFFFFFF

    def __init__(self, seed: int):
        self.mt = [0] * self.N
        self.index = self.N
        self.mt[0] = seed & self.MASK32
        for i in range(1, self.N):
            self.mt[i] = (1812433253 * (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) + i) & self.MASK32

    def _generate(self):
        for i in range(self.N):
            y = (self.mt[i] & self.UPPER_MASK) | (self.mt[(i + 1) % self.N] & self.LOWER_MASK)
            self.mt[i] = self.mt[(i + self.M) % self.N] ^ (y >> 1)
            if y & 1:
                self.mt[i] ^= self.MATRIX_A
        self.index = 0

    def next_int(self) -> int:
        if self.index >= self.N:
            self._generate()
        y = self.mt[self.index]
        self.index += 1
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= y >> 18
        return y & self.MASK32

    def random(self) -> float:
        return self.next_int() / 4294967296.0


# ============================================================================
# PRNG 2: Generador Congruencial Lineal (LCG) — Deng y Lin (2000)
# ============================================================================

class LCG:
    A = 16807
    M = 2147483647

    def __init__(self, seed: int):
        self.x = seed % self.M
        if self.x == 0:
            self.x = 1

    def next_int(self) -> int:
        self.x = (self.A * self.x) % self.M
        return self.x

    def random(self) -> float:
        return self.next_int() / self.M


# ============================================================================
# PRNG 3: Generador Recursivo Múltiple (MRG/FMRG k=2) — Deng y Lin (2000)
# ============================================================================

class MRG:
    P = 2147483647
    ALPHA1 = 1071064
    ALPHA2 = 2113664

    def __init__(self, seed1: int, seed2: int):
        self.x_prev = seed1 % self.P
        self.x_prev2 = seed2 % self.P
        if self.x_prev == 0:
            self.x_prev = 1
        if self.x_prev2 == 0:
            self.x_prev2 = 1

    def next_int(self) -> int:
        x_new = (self.ALPHA1 * self.x_prev + self.ALPHA2 * self.x_prev2) % self.P
        self.x_prev2 = self.x_prev
        self.x_prev = x_new
        return x_new

    def random(self) -> float:
        return self.next_int() / self.P


# ============================================================================
# Generación de variables aleatorias (transformada inversa)
# ============================================================================

def gen_interarrival(rng: MersenneTwister, lam: float) -> float:
    u = rng.random()
    if u == 0.0:
        u = 1e-15
    return -math.log(u) / lam


def gen_service_time(rng: MRG, mu: float) -> float:
    u = rng.random()
    if u == 0.0:
        u = 1e-15
    return -math.log(u) / mu


def gen_vacation_time(rng: LCG, theta: float) -> float:
    u = rng.random()
    if u == 0.0:
        u = 1e-15
    return -math.log(u) / theta


# ============================================================================
# Fórmulas analíticas del modelo M/M/1 con vacaciones múltiples
# Fuente: Haviv (2013), Teorema 4.9
# ============================================================================

def calcular_analitico(lam: float, mu: float, theta: float):
    rho = lam / mu

    if rho >= 1.0:
        return {
            "rho": rho, "L": float("inf"), "Lq": float("inf"),
            "W": float("inf"), "Wq": float("inf"),
            "Wq_mm1": float("inf"),
            "estable": False,
        }

    wq_mm1 = rho / (mu * (1 - rho))
    wq = wq_mm1 + 1.0 / theta
    w = wq + 1.0 / mu
    lq = lam * wq
    l = lam * w

    return {
        "rho": rho, "L": l, "Lq": lq, "W": w, "Wq": wq,
        "Wq_mm1": wq_mm1,
        "estable": True,
    }


# ============================================================================
# Motor de Simulación de Eventos Discretos (DES)
# ============================================================================

EVENTO_LLEGADA = 0
EVENTO_FIN_SERVICIO = 1
EVENTO_FIN_VACACION = 2

ESTADO_LIBRE = 0
ESTADO_OCUPADO = 1
ESTADO_VACACION = 2


def simular(lam, mu, theta, t_sim, seed_mt, seed_lcg, seed_mrg1, seed_mrg2,
            t_warmup=0.0, trace_eventos=0):
    rng_llegadas = MersenneTwister(seed_mt)
    rng_servicio = MRG(seed_mrg1, seed_mrg2)
    rng_vacacion = LCG(seed_lcg)

    reloj = 0.0
    estado_servidor = ESTADO_LIBRE
    cola = deque()
    cliente_actual_llegada = 0.0

    eventos = []
    contador_eventos = 0

    num_en_cola = 0
    num_en_sistema = 0
    area_cola = 0.0
    area_sistema = 0.0
    area_ocupado = 0.0
    area_vacacion = 0.0
    total_espera = 0.0
    total_tiempo_sistema = 0.0
    clientes_servidos = 0
    clientes_llegados = 0
    total_vacaciones = 0

    t_inicio_stats = t_warmup
    traza = []

    snapshots = []
    snapshot_interval = t_sim / 20

    t_primera = gen_interarrival(rng_llegadas, lam)
    heapq.heappush(eventos, (t_primera, contador_eventos, EVENTO_LLEGADA))
    contador_eventos += 1

    next_snapshot = snapshot_interval
    total_eventos_procesados = 0

    while eventos:
        t_evento, _, tipo = heapq.heappop(eventos)
        if t_evento > t_sim:
            break

        if reloj >= t_inicio_stats:
            dt = t_evento - max(reloj, t_inicio_stats)
            if reloj < t_inicio_stats:
                dt = t_evento - t_inicio_stats
            area_cola += num_en_cola * dt
            area_sistema += num_en_sistema * dt
            area_ocupado += (1.0 if estado_servidor == ESTADO_OCUPADO else 0.0) * dt
            area_vacacion += (1.0 if estado_servidor == ESTADO_VACACION else 0.0) * dt

        reloj = t_evento
        total_eventos_procesados += 1

        if tipo == EVENTO_LLEGADA:
            if reloj >= t_inicio_stats:
                clientes_llegados += 1

            if trace_eventos > 0 and len(traza) < trace_eventos:
                estado_str = {ESTADO_LIBRE: "Libre", ESTADO_OCUPADO: "Ocupado", ESTADO_VACACION: "Vacación"}
                traza.append({
                    "t": reloj, "tipo": "LLEGADA",
                    "cola_antes": num_en_cola,
                    "servidor": estado_str[estado_servidor],
                })

            if estado_servidor == ESTADO_LIBRE:
                estado_servidor = ESTADO_OCUPADO
                cliente_actual_llegada = reloj
                num_en_sistema += 1
                s = gen_service_time(rng_servicio, mu)
                heapq.heappush(eventos, (reloj + s, contador_eventos, EVENTO_FIN_SERVICIO))
                contador_eventos += 1
                if reloj >= t_inicio_stats:
                    total_espera += 0.0
            else:
                cola.append(reloj)
                num_en_cola += 1
                num_en_sistema += 1

            t_sig = reloj + gen_interarrival(rng_llegadas, lam)
            heapq.heappush(eventos, (t_sig, contador_eventos, EVENTO_LLEGADA))
            contador_eventos += 1

        elif tipo == EVENTO_FIN_SERVICIO:
            if reloj >= t_inicio_stats:
                clientes_servidos += 1
                total_tiempo_sistema += reloj - cliente_actual_llegada

            num_en_sistema -= 1

            if trace_eventos > 0 and len(traza) < trace_eventos:
                traza.append({
                    "t": reloj, "tipo": "FIN_SERV",
                    "cola_antes": num_en_cola,
                    "servidor": "->Siguiente" if cola else "->Vacación",
                })

            if cola:
                t_llegada_sig = cola.popleft()
                num_en_cola -= 1
                cliente_actual_llegada = t_llegada_sig
                if reloj >= t_inicio_stats:
                    total_espera += reloj - t_llegada_sig
                s = gen_service_time(rng_servicio, mu)
                heapq.heappush(eventos, (reloj + s, contador_eventos, EVENTO_FIN_SERVICIO))
                contador_eventos += 1
            else:
                estado_servidor = ESTADO_VACACION
                v = gen_vacation_time(rng_vacacion, theta)
                heapq.heappush(eventos, (reloj + v, contador_eventos, EVENTO_FIN_VACACION))
                contador_eventos += 1

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
                v = gen_vacation_time(rng_vacacion, theta)
                heapq.heappush(eventos, (reloj + v, contador_eventos, EVENTO_FIN_VACACION))
                contador_eventos += 1

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

    t_efectivo = reloj - t_inicio_stats
    if t_efectivo <= 0:
        t_efectivo = 1.0

    l_sim = area_sistema / t_efectivo
    lq_sim = area_cola / t_efectivo
    rho_sim = area_ocupado / t_efectivo
    rho_vac = area_vacacion / t_efectivo
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
# Ejecución de múltiples réplicas con intervalos de confianza
# ============================================================================

T_CRIT_9_0025 = 2.262


def ejecutar_replicas(lam, mu, theta, t_sim, t_warmup, n_replicas=10,
                      base_seed=42, trace_eventos=0):
    master = MersenneTwister(base_seed)
    resultados = []

    for r in range(n_replicas):
        s_mt = master.next_int()
        s_lcg = master.next_int() % (LCG.M - 1) + 1
        s_mrg1 = master.next_int() % (MRG.P - 1) + 1
        s_mrg2 = master.next_int() % (MRG.P - 1) + 1

        sim = simular(lam, mu, theta, t_sim, s_mt, s_lcg, s_mrg1, s_mrg2,
                      t_warmup, trace_eventos if r == 0 else 0)
        resultados.append(sim)

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

    analitico = calcular_analitico(lam, mu, theta)
    validacion = {}

    if analitico["estable"]:
        wq_a = analitico["Wq"]
        validacion["Wq_en_IC"] = stats["Wq"]["ci_lower"] <= wq_a <= stats["Wq"]["ci_upper"]

        l_media = stats["L"]["media"]
        w_media = stats["W"]["media"]
        if l_media > 0:
            little_L = abs(l_media - lam * w_media) / l_media
        else:
            little_L = 0
        validacion["Little_L"] = little_L < 0.05

        lq_media = stats["Lq"]["media"]
        wq_media = stats["Wq"]["media"]
        if lq_media > 0:
            little_Lq = abs(lq_media - lam * wq_media) / lq_media
        else:
            little_Lq = 0
        validacion["Little_Lq"] = little_Lq < 0.05

        rho_media = stats["rho"]["media"]
        validacion["rho_precision"] = abs(rho_media - lam / mu) < 0.02

        validacion["Little_L_valor"] = little_L
        validacion["Little_Lq_valor"] = little_Lq
        validacion["rho_diff"] = abs(rho_media - lam / mu)

    return {
        "resultados": resultados,
        "stats": stats,
        "validacion": validacion,
        "analitico": analitico,
        "n_replicas": n_replicas,
    }


# ============================================================================
# Prueba Chi-Cuadrado de bondad de ajuste
# ============================================================================

def chi_cuadrado_exp(datos, tasa, num_bins=10):
    n = len(datos)
    if n == 0:
        return 0, 0, False, [], 0, []

    bin_edges = [0.0]
    for i in range(1, num_bins):
        bin_edges.append(-math.log(1 - i / num_bins) / tasa)
    bin_edges.append(float("inf"))

    observados = [0] * num_bins
    for x in datos:
        for b in range(num_bins):
            if x < bin_edges[b + 1]:
                observados[b] += 1
                break

    esperados = n / num_bins
    chi2 = sum((o - esperados) ** 2 / esperados for o in observados)
    gl = num_bins - 1 - 1

    chi2_criticos = {
        1: 3.841, 2: 5.991, 3: 7.815, 4: 9.488, 5: 11.070,
        6: 12.592, 7: 14.067, 8: 15.507, 9: 16.919, 10: 18.307,
        11: 19.675, 12: 21.026, 13: 22.362, 14: 23.685, 15: 24.996,
    }
    chi2_crit = chi2_criticos.get(gl, 16.919)

    return chi2, chi2_crit, chi2 <= chi2_crit, observados, esperados, bin_edges


# ============================================================================
# Reporte detallado académico
# ============================================================================

def reporte_completo(sim, analitico, lam, mu, theta, t_sim, t_warmup, seeds,
                     replicas_result=None, print_fn=None):
    _print = print_fn or print

    def linea(c="═", n=72):
        _print(c * n)

    def titulo_seccion(num, texto):
        _print()
        linea("─")
        _print(f"  SECCIÓN {num}: {texto}")
        linea("─")
        _print()

    def pct_error(s, a):
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

    _print("  ┌─ PRNG 3: Generador Congruencial Lineal (LCG) ───────────────┐")
    _print("  │  Fuente: Deng y Lin (2000)                                   │")
    _print("  │  Asignado a: Duración de vacación del servidor               │")
    _print("  │  Período: m - 1 = 2,147,483,646                             │")
    _print(f"  │  Semilla: {seeds['lcg']:<50d}│")
    _print("  │                                                              │")
    _print("  │  Recurrencia (multiplicativo, C=0):                          │")
    _print("  │  X_i = (16807 · X_{i-1}) mod (2^31 - 1)                     │")
    _print("  │  U_i = X_i / (2^31 - 1)                                     │")
    _print("  └──────────────────────────────────────────────────────────────┘")
    _print()

    lcg_demo = LCG(seeds["lcg"])
    _print("  Primeros 10 números uniformes generados:")
    _print("  ┌──────┬──────────────────┬──────────────────┐")
    _print("  │  i   │     X_i          │     U_i          │")
    _print("  ├──────┼──────────────────┼──────────────────┤")
    for i in range(10):
        xi = lcg_demo.next_int()
        ui = xi / LCG.M
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
    _print("  Ejemplo paso a paso con los primeros 5 valores del LCG:")
    _print("  ┌──────┬──────────────┬────────────────────────────┬────────────┐")
    _print("  │  i   │  U_i (LCG)   │  Cálculo                   │  V_i (min) │")
    _print("  ├──────┼──────────────┼────────────────────────────┼────────────┤")

    lcg_demo2 = LCG(seeds["lcg"])
    for i in range(5):
        u = lcg_demo2.random()
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

    n_test = 5000

    mt_test = MersenneTwister(seeds["mt"])
    llegadas_test = [gen_interarrival(mt_test, lam) for _ in range(n_test)]
    chi2, chi2_c, acepta, obs_bins, esp, edges = chi_cuadrado_exp(llegadas_test, lam)

    _print(f"  PRUEBA 1: Tiempo entre llegadas ~ Exp(λ={lam})")
    _print(f"  Muestra: {n_test} valores generados con MT19937")
    _print(f"  Media teórica: {1/lam:.4f} min | Media observada: {sum(llegadas_test)/len(llegadas_test):.4f} min")
    _print(f"  Bins equiprobables: 10 | Grados de libertad: 8")
    _print(f"  χ² calculado = {chi2:.4f}")
    _print(f"  χ² crítico (α=0.05, gl=8) = {chi2_c:.4f}")
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
    _print(f"  χ² crítico (α=0.05, gl=8) = {chi2_cs:.4f}")
    _print(f"  Resultado: {'NO SE RECHAZA H₀ ✓' if acepta_s else 'SE RECHAZA H₀ ✗'}")
    _print()

    lcg_test = LCG(seeds["lcg"])
    vacacion_test = [gen_vacation_time(lcg_test, theta) for _ in range(n_test)]
    chi2_v, chi2_cv, acepta_v, _, _, _ = chi_cuadrado_exp(vacacion_test, theta)

    _print(f"  PRUEBA 3: Duración de vacación ~ Exp(θ={theta})")
    _print(f"  Muestra: {n_test} valores generados con LCG")
    _print(f"  Media teórica: {1/theta:.4f} min | Media observada: {sum(vacacion_test)/len(vacacion_test):.4f} min")
    _print(f"  χ² calculado = {chi2_v:.4f}")
    _print(f"  χ² crítico (α=0.05, gl=8) = {chi2_cv:.4f}")
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
    _print("  │ Duración de vacación       │ LCG multiplicativo       │ Deng y Lin (2000)  │")
    _print("  └────────────────────────────┴──────────────────────────┴────────────────────┘")
    _print()

    linea()
    _print("  FIN DEL REPORTE")
    linea()
    _print()


# ============================================================================
# Punto de entrada principal
# ============================================================================

if __name__ == "__main__":
    LAM = 0.5
    MU = 0.67
    THETA = 0.2
    T_SIM = 10_000
    T_WARMUP = 500

    SEED_MT = 19937
    SEED_LCG = 48271
    SEED_MRG1 = 31415
    SEED_MRG2 = 92653

    seeds = {"mt": SEED_MT, "lcg": SEED_LCG, "mrg1": SEED_MRG1, "mrg2": SEED_MRG2}

    analitico = calcular_analitico(LAM, MU, THETA)

    print()
    print(f"  Verificando estabilidad: ρ = {analitico['rho']:.4f}", end="")
    if analitico["estable"]:
        print(" < 1 ✓ — Sistema estable")
    else:
        print(" ≥ 1 ✗ — SISTEMA INESTABLE")

    print(f"  Ejecutando simulación individual ({T_SIM:,} minutos simulados)...")
    resultado = simular(LAM, MU, THETA, T_SIM, SEED_MT, SEED_LCG, SEED_MRG1, SEED_MRG2,
                        T_WARMUP, trace_eventos=20)
    print("  Simulación completada.")

    print(f"\n  Ejecutando {10} réplicas independientes...")
    replicas = ejecutar_replicas(LAM, MU, THETA, T_SIM, T_WARMUP,
                                n_replicas=10, base_seed=42, trace_eventos=20)
    print("  Réplicas completadas.")

    reporte_completo(resultado, analitico, LAM, MU, THETA, T_SIM, T_WARMUP, seeds,
                     replicas_result=replicas)
