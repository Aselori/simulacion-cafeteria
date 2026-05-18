# Simulación Cafetería — M/M/1 con Vacaciones Múltiples

Simulador de un sistema de colas **M/M/1 con vacaciones múltiples del servidor**, aplicado al caso de una cafetería. Proyecto de la materia de Modelado y Simulación de Sistemas Dinámicos.

## Modelo

Tres variables aleatorias, cada una con su propio PRNG implementado desde cero:

| Variable                                | Distribución | Generador                       |
| --------------------------------------- | ------------ | ------------------------------- |
| Tiempo entre llegadas                   | `Exp(λ)`     | Mersenne Twister (MT19937)      |
| Tiempo de servicio                      | `Exp(μ)`     | MRG combinado (k=2)             |
| Duración de vacación del servidor       | `Exp(θ)`     | MCG (generador de Lehmer)       |

El servidor entra en vacación cada vez que la cola queda vacía y vuelve cuando termina su vacación; si encuentra clientes, los atiende; si no, toma otra vacación (vacaciones **múltiples**).

## Estructura

```
.
├── simulacion_cafeteria.py       # Núcleo: PRNGs, generadores, simulación, analítico, reporte
├── simulacion_cafeteria_gui.py   # Entry point de la GUI
└── gui/                          # Asistente paso a paso (tkinter)
    ├── app.py                    # Ventana principal y enrutado
    ├── topbar.py                 # Barra superior con pasos
    ├── theme.py                  # Estilos
    ├── components.py             # Widgets reutilizables
    └── modules/                  # Pasos del asistente
        ├── m0_sistema.py         # Parámetros del sistema
        ├── m1_analitico.py       # Cálculo analítico
        ├── m2_prngs.py           # PRNGs y semillas
        ├── m3_eventos.py         # Trazado de eventos
        ├── m4_metricas.py        # Métricas de la corrida
        ├── m5_servidor.py        # Estado del servidor
        └── m6_replicas.py        # Réplicas y chi-cuadrado
```

## Uso

Requiere Python 3 con `tkinter` (incluido en la mayoría de distribuciones).

```bash
# GUI
python simulacion_cafeteria_gui.py

# Sólo lógica (importable)
python -c "from simulacion_cafeteria import simular, calcular_analitico"
```

## Métricas reportadas

- Comparación analítico vs simulado (`L`, `Lq`, `W`, `Wq`, utilización, fracción en vacación).
- Réplicas con intervalo de confianza.
- Prueba chi-cuadrado de bondad de ajuste exponencial sobre las series generadas.
