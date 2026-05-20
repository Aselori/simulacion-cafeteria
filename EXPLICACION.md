# Guía completa del simulador — Para explicar ante el profesor

Este documento explica **todo** lo que hace el proyecto, por qué lo hace, y cómo funciona por dentro. Está escrito para que cualquier miembro del equipo pueda leerlo, entenderlo y explicarlo con confianza.

---

## 1. ¿Qué estamos simulando?

Imagínense la cafetería de la universidad a la hora pico. Hay **un solo cajero** (servidor) y **una fila** (cola). Los estudiantes llegan de a uno, hacen fila si el cajero está ocupado, y cuando los atienden se van.

Lo que hace especial a nuestro modelo es lo siguiente: cuando la fila se vacía, el cajero **no se queda parado esperando**. Se va a hacer otra cosa (reponer insumos, preparar bebidas, tomar un descanso). A esto le llamamos **vacación**. Cuando termina su vacación, regresa y revisa la fila: si hay alguien esperando, lo atiende; si la fila sigue vacía, **se va de vacación otra vez**. Por eso se llaman **vacaciones múltiples**: puede tomar varias seguidas hasta que alguien llegue.

En notación formal, esto es un sistema **M/M/1 con vacaciones múltiples exhaustivas**:

- **M** (primero): las llegadas siguen un proceso de Poisson — los tiempos entre llegadas son exponenciales con tasa λ.
- **M** (segundo): los tiempos de servicio son exponenciales con tasa μ.
- **1**: hay un solo servidor.
- **Vacaciones múltiples**: cuando la cola se vacía, el servidor toma vacaciones Exp(θ) repetidas hasta encontrar clientes al regresar.

### Los tres parámetros del sistema

| Parámetro | Significado | Valor por defecto | En palabras |
|-----------|-------------|-------------------|-------------|
| λ = 0.5 | Tasa de llegada | 0.5 clientes/min | Llega 1 cliente cada 2 minutos en promedio |
| μ = 0.67 | Tasa de servicio | 0.67 clientes/min | Cada servicio tarda ~1.49 minutos en promedio |
| θ = 0.2 | Tasa de retorno de vacación | 0.2 retornos/min | Cada vacación dura 5 minutos en promedio |

### ¿Cuándo es estable el sistema?

El sistema es estable cuando **llegan clientes más lento de lo que se pueden atender**: ρ = λ/μ < 1. Con nuestros valores: ρ = 0.5/0.67 ≈ 0.746 < 1, así que sí es estable.

Si ρ ≥ 1, la fila crecería infinitamente y todas las métricas explotarían.

Noten que θ (las vacaciones) **no aparece en la condición de estabilidad**. Esto tiene sentido: no importa qué tan largas o cortas sean las vacaciones, si el servidor no puede con la carga de trabajo (ρ ≥ 1), las vacaciones sólo empeoran las cosas pero no son la causa del problema.

---

## 2. ¿Por qué todo es exponencial?

La distribución exponencial tiene una propiedad única llamada **falta de memoria** (memorylessness):

> La probabilidad de que falten más de *t* minutos para el siguiente evento es la misma sin importar cuánto tiempo ya haya pasado.

Matemáticamente: P(X > s+t | X > s) = P(X > t).

Esto es crucial para tres cosas:

1. **Llegadas**: para que las llegadas formen un proceso de Poisson (tasa constante, sin "rachas"), los tiempos entre llegadas **deben** ser exponenciales. Es la única distribución que da esa propiedad.

2. **Servicio**: la falta de memoria significa que si llegamos a la mitad de un servicio, el tiempo restante sigue siendo Exp(μ). Esto simplifica enormemente las fórmulas analíticas.

3. **Vacaciones**: aquí es donde más importa. La falta de memoria implica que si un cliente llega cuando el servidor está a la mitad de una vacación, **el tiempo que falta de esa vacación es también Exp(θ)**. Por eso el término que las vacaciones añaden a la espera es simplemente 1/θ (la media de la exponencial). Si usáramos otra distribución, habría que calcular la *vida residual* con fórmulas mucho más complicadas.

---

## 3. Los tres generadores de números aleatorios (PRNGs)

Necesitamos números aleatorios para generar los tres tipos de tiempos (llegadas, servicios, vacaciones). Usamos **tres generadores completamente separados**, cada uno con su propia semilla. ¿Por qué? Porque si usáramos uno solo, los números consecutivos que produce podrían crear correlaciones espurias entre procesos que deberían ser independientes. Con tres generadores independientes, la llegada no tiene nada que ver con el servicio ni con la vacación — por construcción.

### PRNG 1: Mersenne Twister (MT19937)

**Asignado a:** tiempos entre llegadas (la variable que más se consume).

Este es el generador "bueno" del proyecto. Fue inventado por Matsumoto y Nishimura en 1998 y es el estándar de facto en simulación.

**¿Cómo funciona?** Internamente mantiene un vector de 624 enteros de 32 bits. Cada vez que pedimos un número:
1. Si ya consumimos los 624, hace un "twist": recalcula todo el vector aplicando operaciones de bits (XOR, shifts, multiplicación por una matriz).
2. Toma el siguiente entero del vector.
3. Le aplica cuatro operaciones de "tempering" (XOR-shifts con constantes mágicas) para mejorar la calidad estadística de la salida.
4. Divide entre 2³² para obtener un número decimal entre 0 y 1.

**Período:** 2¹⁹⁹³⁷ − 1 ≈ 10⁶⁰⁰¹. Es un número absurdamente grande — más grande que el número de átomos en el universo observable elevado a la 150ava potencia. Nunca vamos a agotar la secuencia.

**Equidistribución:** demostrada en 623 dimensiones. Esto significa que si tomamos bloques de 623 números consecutivos, se distribuyen uniformemente en el hipercubo [0,1)⁶²³. Ningún LCG simple puede hacer eso.

**¿Por qué lo asignamos a las llegadas?** Porque es el proceso que más números consume (una llegada por cada cliente que entra al sistema). Queremos el generador de mayor calidad para la variable de mayor volumen.

### PRNG 2: Generador Congruencial Multiplicativo (MCG / Lehmer)

**Asignado a:** duraciones de vacación.

Es el generador más simple de los tres. La fórmula es:

```
X_{i+1} = (16807 × X_i) mod (2³¹ − 1)
U_i = X_i / (2³¹ − 1)
```

Donde 16807 = 7⁵ es el multiplicador de Park-Miller, y 2³¹ − 1 = 2,147,483,647 es un primo de Mersenne.

**¿Cómo funciona?** Multiplica el estado actual por 16807 y toma el residuo módulo 2³¹−1. Eso es todo. Un solo estado, una sola operación.

**Período:** 2³¹ − 2 ≈ 2.15 × 10⁹. Mucho más corto que el MT, pero suficiente para las vacaciones: como el servidor sólo toma una vacación cada vez que la cola se vacía, consume muchos menos números que las llegadas o los servicios.

**¿Por qué funciona?** El multiplicador 16807 es raíz primitiva del primo 2³¹−1. Esto garantiza que la secuencia recorre todos los enteros de 1 hasta 2³¹−2 antes de repetirse.

**Nota sobre el nombre:** en el código aparece como `MCG` (Multiplicative Congruential Generator) y tiene un alias `LCG`. Técnicamente es un MCG porque la constante aditiva C es cero. Un LCG tendría C ≠ 0.

**Dato importante:** si la semilla fuera 0, el generador se "muere" — todos los siguientes serían 0 (porque 16807 × 0 mod cualquier cosa = 0). Por eso el código fuerza la semilla a 1 si llega un 0.

### PRNG 3: Generador Recursivo Múltiple (MRG, k=2)

**Asignado a:** tiempos de servicio.

Es un paso intermedio entre el MCG simple y el MT. La fórmula es:

```
X_i = (1071064 × X_{i-1} + 2113664 × X_{i-2}) mod (2³¹ − 1)
U_i = X_i / (2³¹ − 1)
```

**¿Cómo funciona?** En vez de depender sólo del estado anterior (como el MCG), depende de los **dos estados anteriores**. Necesita dos semillas iniciales.

**Período:** hasta p² − 1 ≈ 4.6 × 10¹⁸ cuando los coeficientes son apropiados (los nuestros vienen de Deng y Lin, 2000). Mucho mejor que el MCG simple.

**¿Por qué lo asignamos a los servicios?** Los tiempos de servicio son la segunda variable más consumida (un número por cada cliente atendido). El MRG ofrece mejor calidad que el MCG pero es más simple que el MT.

### Resumen de asignación

| Variable | PRNG | Período | Referencia |
|----------|------|---------|------------|
| Tiempo entre llegadas | Mersenne Twister MT19937 | 2¹⁹⁹³⁷ − 1 | Matsumoto & Nishimura, 1998 |
| Tiempo de servicio | MRG k=2 | ~p² ≈ 4.6 × 10¹⁸ | Deng & Lin, 2000 |
| Duración de vacación | MCG (Lehmer) | 2³¹ − 2 | Park-Miller, 1988 |

---

## 4. ¿Cómo convertimos uniformes en exponenciales? (Transformada inversa)

Los tres generadores producen números **uniformes** U entre 0 y 1. Pero nosotros necesitamos tiempos **exponenciales**. La conversión se llama **método de la transformada inversa**.

La idea es sencilla:

1. La CDF (función de distribución acumulada) de una Exp(λ) es: F(x) = 1 − e^(−λx)
2. Si U es uniforme en (0,1), entonces F⁻¹(U) tiene distribución F.
3. Despejando: x = −ln(1 − U) / λ
4. Pero como U es uniforme, (1 − U) también es uniforme. Entonces simplificamos a: **x = −ln(U) / λ**

Esta última línea es exactamente lo que hace el código:

```python
def gen_interarrival(rng, lam):
    u = rng.random()          # U ~ Uniforme(0,1)
    return -math.log(u) / lam # X ~ Exp(λ)
```

**La protección numérica:** si U = 0 (probabilidad 2⁻³², prácticamente imposible), ln(0) = −∞ y el programa truena. Por eso hay un `if u == 0.0: u = 1e-15`. Es un parche defensivo que nunca se activa en la práctica.

---

## 5. Las fórmulas analíticas (la "verdad teórica")

Antes de simular, calculamos los valores **exactos** que predice la teoría. Esto nos da la referencia contra la cual comparar la simulación.

La referencia es el **Teorema 4.9 de Haviv (2013)**, que dice algo muy elegante:

> En un M/M/1 con vacaciones múltiples exponenciales, la espera en cola se descompone en dos partes independientes: la espera del M/M/1 puro + el tiempo residual de la vacación.

### Paso a paso

**Paso 1: Utilización**
```
ρ = λ / μ = 0.5 / 0.67 = 0.7463
```

**Paso 2: Espera en cola del M/M/1 sin vacaciones**
```
Wq(M/M/1) = ρ / [μ × (1 − ρ)] = 0.7463 / [0.67 × 0.2537] = 4.3896 min
```
Esto es cuánto esperaría un cliente si el cajero nunca tomara vacaciones.

**Paso 3: El efecto de las vacaciones**

Aquí es donde entra la propiedad sin memoria. Cuando un cliente llega y el servidor está de vacación, ¿cuánto falta para que regrese? Como la vacación es Exp(θ), la falta de memoria dice que el tiempo restante **también es Exp(θ)**, con media 1/θ.

```
Tiempo residual medio = 1/θ = 1/0.2 = 5.0 min
```

**Paso 4: Descomposición (el teorema)**
```
Wq = Wq(M/M/1) + 1/θ = 4.3896 + 5.0 = 9.3896 min
```

Las vacaciones le suman **5 minutos de espera** en promedio a cada cliente. Es un impacto enorme.

**Paso 5: Tiempo total en el sistema**
```
W = Wq + 1/μ = 9.3896 + 1.4925 = 10.8821 min
```
(Añadimos el tiempo de servicio medio.)

**Paso 6: Ley de Little**

La ley de Little es una identidad universal de teoría de colas: L = λ × W, Lq = λ × Wq. No necesita supuestos sobre distribuciones — funciona para cualquier sistema en estado estacionario.

```
Lq = λ × Wq = 0.5 × 9.3896 = 4.6948 clientes en cola
L  = λ × W  = 0.5 × 10.8821 = 5.4410 clientes en el sistema
```

### ¿Por qué importa la descomposición?

Porque nos dice que el efecto de las vacaciones es **aditivo** y se puede calcular por separado. No necesitamos resolver un sistema complicado de ecuaciones: tomamos la fórmula del M/M/1 clásico (que está en cualquier libro) y le sumamos 1/θ. Esto sólo funciona gracias a que las vacaciones son exponenciales — con otra distribución, el término sería E[V²]/(2·E[V]) en vez de 1/θ.

---

## 6. El motor de simulación (cómo funciona el simulador)

El simulador usa la técnica de **simulación de eventos discretos** (DES, Discrete Event Simulation) con avance al próximo evento (next-event time advance).

### ¿Qué significa "avance al próximo evento"?

En vez de avanzar el reloj de a poquitos (Δt = 0.01 minutos, por ejemplo), el simulador **salta directamente al instante del siguiente evento**. Entre eventos no pasa nada interesante — el estado del sistema no cambia — así que no tiene sentido simular esos intervalos vacíos.

### La agenda de eventos (FEL)

El corazón del simulador es una **cola de prioridad** (heap binario) llamada FEL (Future Event List). Cada entrada es una tupla `(instante, contador, tipo)`:

- **instante:** cuándo ocurrirá el evento.
- **contador:** desempate FIFO cuando dos eventos coinciden en el mismo instante.
- **tipo:** LLEGADA (0), FIN_SERVICIO (1), o FIN_VACACION (2).

### Los tres tipos de evento

**LLEGADA** — un cliente entra al sistema:
- Si el servidor está libre → lo atiende de inmediato (programa un FIN_SERVICIO).
- Si el servidor está ocupado o de vacaciones → el cliente se forma en la cola.
- **Siempre** programa la próxima LLEGADA (las llegadas no dependen del estado del servidor).

**FIN_SERVICIO** — el servidor termina de atender a un cliente:
- Si hay gente en la cola → atiende al siguiente (programa otro FIN_SERVICIO).
- Si la cola está vacía → se va de vacaciones (programa un FIN_VACACION).

**FIN_VACACION** — el servidor regresa de una vacación:
- Si hay gente en la cola → la atiende (programa un FIN_SERVICIO).
- Si la cola está vacía → toma **otra** vacación (programa otro FIN_VACACION). **Este es el paso que define las vacaciones múltiples.**

### El bucle principal

```
mientras haya eventos en la FEL:
    sacar el evento con el tiempo más pequeño
    si el tiempo excede T_sim → parar
    acumular las áreas (estadísticas) desde el reloj anterior hasta este evento
    avanzar el reloj al tiempo de este evento
    procesar el evento según su tipo (LLEGADA / FIN_SERVICIO / FIN_VACACION)
```

### ¿Cómo se calculan las métricas? (Las áreas)

Las métricas como L (clientes promedio en el sistema) son **promedios ponderados por tiempo**. Como el número de clientes en el sistema es constante a trozos (sólo cambia en los eventos), el promedio es:

```
L = (1/T) × ∫₀ᵀ N(t) dt = (1/T) × Σ [N_i × Δt_i]
```

Donde N_i es el número de clientes durante el intervalo i, y Δt_i es la duración de ese intervalo. Eso es lo que hacen las variables `area_sistema`, `area_cola`, `area_ocupado` y `area_vacacion` en el código: acumulan la integral rectangularmente entre evento y evento.

Las métricas W y Wq, en cambio, son **promedios por cliente**: suman los tiempos individuales de cada cliente y dividen entre el número de clientes servidos. Por eso no se calculan con áreas sino con acumuladores directos (`total_espera`, `total_tiempo_sistema`).

---

## 7. Las semillas — por qué las elegimos así

El profesor nos advirtió sobre usar `time()` como semilla. ¿Por qué es peligroso?

Si hacemos `seed = int(time.time())` para cada generador, y los tres se inicializan en el mismo milisegundo, **los tres generadores arrancan con la misma semilla**. Esto rompe la independencia entre flujos: llegadas, servicios y vacaciones producirían secuencias correlacionadas.

**Nuestra estrategia:**

1. **Para la corrida individual:** las semillas son constantes fijas (`19937`, `48271`, `31415`, `92653`). Esto hace la simulación **reproducible**: cada vez que corremos con los mismos parámetros obtenemos exactamente los mismos resultados. El profesor puede verificar nuestros números.

2. **Para las 10 réplicas:** un MT19937 "maestro" (con semilla 42) genera las cuatro semillas de cada réplica. Así cada réplica usa un cuádruple distinto de semillas, derivado de una sola fuente. Esto da independencia entre réplicas y a la vez es determinista.

3. **No usamos `time()` en ningún lado.** No hay dependencia de la hora, del sistema operativo ni del hardware.

---

## 8. Las réplicas e intervalos de confianza

Una sola corrida da **un** resultado. Pero ese resultado depende de la semilla — otra semilla daría números ligeramente diferentes. ¿Cómo sabemos si nuestro resultado es confiable?

Corremos **10 réplicas independientes** (cada una con semillas diferentes) y construimos un **intervalo de confianza al 95%** para cada métrica.

### La fórmula

```
IC₉₅% = x̄ ± t_(α/2, n−1) × s / √n
```

Donde:
- x̄ = media de las 10 medias replicadas
- s = desviación estándar muestral (con divisor n−1)
- n = 10 réplicas
- t_(0.025, 9) = 2.262 (valor crítico de la t de Student con 9 grados de libertad)

**¿Por qué t de Student y no z (normal)?** Porque no conocemos la desviación verdadera σ — la estimamos con s. Cuando n es pequeño (10), esa estimación tiene incertidumbre y la distribución del estadístico no es normal exacta: es una t de Student con n−1 grados de libertad. Si tuviéramos 30+ réplicas la diferencia sería mínima, pero con 10 importa.

### Las cuatro pruebas de validación

1. **Cobertura:** ¿el valor analítico de Wq cae dentro del IC al 95%? Si sí, no hay sesgo detectable.

2. **Ley de Little (L):** ¿se cumple que L ≈ λ × W? Esto es una identidad universal — si falla, hay un error de implementación.

3. **Ley de Little (Lq):** ¿se cumple que Lq ≈ λ × Wq? Misma verificación para la cola.

4. **Precisión de ρ:** ¿es |ρ_sim − λ/μ| < 0.02? La utilización es la métrica que más rápido converge; si no coincide hay un problema serio.

Si las cuatro pasan, el simulador está validado: es coherente con la teoría, consigo mismo (Little) y en su estimador más básico (ρ).

---

## 9. La prueba chi-cuadrado

Verificamos que los números generados por cada PRNG realmente siguen una distribución exponencial. Usamos la **prueba χ² de bondad de ajuste con bins equiprobables**.

### ¿Cómo funciona?

1. Generamos 1000 valores con cada generador (ya transformados a exponencial).
2. Dividimos el rango en 6 **bins equiprobables**: calculamos los bordes como cuantiles de la exponencial teórica, de modo que cada bin debería contener 1000/6 ≈ 167 observaciones si la distribución fuera perfecta.
3. Contamos cuántas observaciones cayeron en cada bin (observados).
4. Calculamos el estadístico:

```
χ² = Σ (O_i − E_i)² / E_i
```

5. Comparamos con el valor crítico χ²(4, 0.05) = 9.488.
6. Si χ² ≤ 9.488 → **no rechazamos H₀** (no hay evidencia de que no sea exponencial).

**¿Por qué bins equiprobables y no equiespaciados?** Porque los bins equiprobables garantizan que el conteo esperado en cada bin sea el mismo (n/k), lo que estabiliza la varianza del estadístico y mejora la aproximación a χ². Con bins equiespaciados, los bins de la cola tendrían muy pocas observaciones esperadas y el test perdería potencia.

**Grados de libertad:** usamos gl = k − 1 − 1 = 4 (6 bins − 1 por la suma fija − 1 por convención conservadora del curso).

---

## 10. La GUI — cómo está organizada

La interfaz gráfica usa **customtkinter** (una versión moderna de tkinter) y está organizada como una página web vertical scrollable:

```
┌─────────────────────────────────────────┐
│  TOP BAR: λ  μ  θ  T  [Simular]  ρ=... │ ← siempre visible
├─────────────────────────────────────────┤
│  Módulo 1: Modelo analítico             │ ← no necesita sim
│  Módulo 2: Métricas sim vs analítico    │ ← necesita sim
│  Módulo 3: Estadísticas del servidor    │ ← necesita sim
│  Módulo 4: Réplicas e IC               │ ← necesita sim + réplicas
│  Módulo 5: Motor de eventos (traza)     │ ← necesita sim
│  Módulo 6: Generadores (PRNGs + χ²)    │ ← no necesita sim
│  Módulo 7: Descripción del sistema      │ ← no necesita sim
└─────────────────────────────────────────┘
```

### Ciclo de vida

1. Al abrir la app, los módulos que **no** necesitan simulación (1, 6, 7) se renderizan con los parámetros por defecto.
2. Los demás muestran "Pendiente — pulsa Simular".
3. Al pulsar Simular, la simulación corre en un **hilo aparte** (para no congelar la ventana).
4. Al terminar, se re-montan **todos** los módulos con los nuevos resultados.

### Cada módulo tiene:
- Un **encabezado** con número, título y pill de estado (Pendiente / Ejecutado / Atención).
- Un **cuerpo** que se destruye y reconstruye en cada montaje.
- **TechBlocks** plegables con la ficha técnica detallada.
- Un **ExplainBox** que explica por qué ese módulo existe.

---

## 11. Estructura del código

```
simulacion_cafeteria.py       ← TODA la lógica: PRNGs, generadores, simulación,
                                 analítico, réplicas, chi², reporte en texto
simulacion_cafeteria_gui.py   ← Entry point de la GUI (2 líneas útiles)
gui/
  app.py                      ← Ventana principal, estado compartido, orquestación
  topbar.py                   ← Barra de parámetros + botón Simular
  theme.py                    ← Colores, fuentes, espaciado (source of truth)
  components.py               ← Widgets reutilizables (Card, FormField, etc.)
  modules/
    base.py                   ← Clase base Module (ciclo de vida mount/render)
    m0_sistema.py             ← Apéndice teórico (Kendall, supuestos)
    m1_analitico.py           ← Fórmulas cerradas
    m2_prngs.py               ← Histogramas + chi² de los 3 generadores
    m3_eventos.py             ← Traza paso a paso + pseudocódigo DES
    m4_metricas.py            ← Tabla sim vs analítico
    m5_servidor.py            ← Fracciones ocupado/vacación/ocioso
    m6_replicas.py            ← IC al 95% + validación
```

La separación clave es: `simulacion_cafeteria.py` se puede usar **sin GUI** (desde línea de comandos o importándolo). La GUI sólo es una capa de presentación que llama a las mismas funciones.

---

## 12. Preguntas que podría hacer el profesor

**"¿Por qué no usan `random` de Python?"**
Porque la materia pide implementar los generadores desde cero para demostrar que los entendemos. Además, saber qué generador produce qué variable permite auditar la independencia.

**"¿Por qué usan semillas fijas y no `time()`?"**
Para reproducibilidad: misma semilla = mismo resultado. Si usáramos `time()`, las réplicas lanzadas en el mismo milisegundo compartirían semilla y perderían independencia.

**"¿Por qué tres generadores y no uno?"**
Para garantizar independencia estadística entre los flujos de llegada, servicio y vacación. Con un solo generador, los números consecutivos podrían correlacionar procesos que deberían ser independientes.

**"¿Cómo verifican que la simulación es correcta?"**
Cuatro pruebas: (1) el valor analítico de Wq cae en el IC al 95%, (2-3) la ley de Little se cumple para L y Lq, (4) ρ simulado coincide con λ/μ.

**"¿De dónde sale el +1/θ en Wq?"**
Del Teorema 4.9 de Haviv. La descomposición dice que Wq = Wq(M/M/1) + E[tiempo residual de la vacación]. Como la vacación es Exp(θ), su tiempo residual también es Exp(θ) por la propiedad sin memoria, con media 1/θ.

**"¿Qué pasa con el warm-up?"**
Lo dejamos en 0 porque el objetivo es medir el turno completo de hora pico (la fila empieza vacía, igual que en la realidad). No necesitamos "calentar" el sistema porque no estamos intentando medir sólo el régimen estacionario.

**"¿Cómo saben que los generadores producen buenas exponenciales?"**
Con la prueba χ² de bondad de ajuste usando bins equiprobables. Las tres pruebas no rechazan H₀ al nivel α=0.05.

---

## 13. Glosario rápido

| Término | Significado |
|---------|-------------|
| ρ | Utilización del servidor = λ/μ. Fracción del tiempo que está atendiendo. |
| L | Número promedio de clientes en el sistema (cola + en servicio). |
| Lq | Número promedio de clientes en cola (esperando, no en servicio). |
| W | Tiempo promedio que un cliente pasa en el sistema (espera + servicio). |
| Wq | Tiempo promedio que un cliente espera en cola (sin contar el servicio). |
| FEL | Future Event List. La cola de prioridad con los eventos programados. |
| DES | Discrete Event Simulation. Técnica de avance por eventos. |
| IC | Intervalo de confianza. |
| PRNG | Pseudo-Random Number Generator. Generador de números pseudoaleatorios. |
| Transformada inversa | Método para convertir U~Uniforme(0,1) en X~F cualquiera, aplicando F⁻¹(U). |
| Vacaciones múltiples | El servidor toma vacaciones repetidas hasta encontrar cola al regresar. |
| Exhaustivo | El servidor termina todo el servicio actual antes de tomar vacación. |
| PASTA | Poisson Arrivals See Time Averages — los clientes que llegan ven el sistema en proporciones iguales a los promedios temporales. |
