"""Módulo (apéndice) — Descripción formal del sistema simulado.

Apéndice teórico: vive al final del scroll. Todo su contenido es colapsable
por defecto para no robar espacio al resultado principal. No depende de la
simulación — se renderiza igual antes y después de pulsar Simular.
"""

from .. import theme as t
from ..components import ExplainBox, TechBlock
from .base import Module


class ModSistema(Module):
    """Módulo 7 (último en orden visual): ficha académica del modelo.

    Responde la pregunta "¿qué sistema estás simulando?" para la rúbrica:
    mapeo cafetería↔modelo, notación de Kendall, supuestos y justificación
    de por qué todas las variables son exponenciales.
    """

    number = 7
    title = "Descripción del sistema (apéndice)"
    subtitle = ("Mapeo cafetería ↔ modelo, notación Kendall y supuestos. "
                "Aquí van las respuestas al '¿qué modelo es esto?'.")
    needs_simulation = False

    def render(self, state):
        # Cuatro bloques colapsables independientes — el usuario abre el que
        # le interese sin obligarse a leer todo el bloque teórico.
        # --- Mapeo (colapsable) ---
        tb_map = TechBlock(self.body, "Mapeo cafetería ↔ modelo")
        tb_map.pack(fill="x", pady=(0, t.PAD_SM))
        tb_map.add_bullets([
            ("Cliente:", "estudiante o profesor que llega al mostrador."),
            ("Servidor:", "el cajero/cocinero único que atiende la fila."),
            ("Cola:", "fila física frente al mostrador, capacidad ilimitada, FIFO."),
            ("Servicio:", "tiempo desde que toma el pedido hasta entregarlo y cobrar."),
            ("Vacación:", "el servidor abandona el mostrador (preparar bebidas, "
             "reponer insumos, descanso) cuando no hay nadie en fila; al volver, "
             "si la fila sigue vacía, se va de nuevo (vacaciones múltiples)."),
        ])

        # --- Kendall (colapsable) ---
        tb_k = TechBlock(self.body, "Notación de Kendall extendida")
        tb_k.pack(fill="x", pady=(0, t.PAD_SM))
        tb_k.add_mono("    M / M / 1 / ∞ / ∞ / FIFO   +   vacaciones múltiples")
        tb_k.add_bullets([
            ("M (arribos):", "proceso de llegada markoviano — tiempos entre "
             "llegadas i.i.d. exponenciales con tasa λ. Equivale a llegadas "
             "según un proceso de Poisson(λ)."),
            ("M (servicio):", "tiempos de servicio i.i.d. exponenciales con tasa μ."),
            ("1 (servidores):", "un único servidor."),
            ("∞ (capacidad):", "la fila no rechaza a nadie (no hay límite)."),
            ("∞ (población):", "fuente de clientes infinita; las llegadas no se "
             "agotan."),
            ("FIFO:", "disciplina de atención por orden de llegada."),
            ("+ V múltiples:", "cuando la fila se vacía, el servidor toma una "
             "vacación Exp(θ); si al volver la fila sigue vacía, toma OTRA "
             "vacación (Haviv 2013, §4.3)."),
        ])

        # --- Supuestos (colapsable) ---
        tb_s = TechBlock(self.body, "Supuestos del modelo")
        tb_s.pack(fill="x", pady=(0, t.PAD_SM))
        tb_s.add_bullets([
            ("Independencia:", "los tres procesos (llegadas, servicios, "
             "vacaciones) son mutuamente independientes."),
            ("Sin abandonos:", "ningún cliente se va de la fila (no reneging, "
             "no balking)."),
            ("Servicio exhaustivo:", "el servidor no interrumpe un servicio a "
             "medias; sólo toma vacación cuando termina y la cola está vacía."),
            ("Estado estacionario:", "todas las métricas son de largo plazo; se "
             "asumen alcanzados cuando t → ∞. Estabilidad requiere ρ = λ/μ < 1."),
            ("Sin warm-up:", "se inicia con sistema vacío y servidor en LIBRE. "
             "En un M/M/1 estable el efecto del estado inicial se desvanece "
             "exponencialmente; se confía en T_sim ≫ tiempo característico."),
        ])

        # --- Por qué Exponencial (colapsable) ---
        tb_e = TechBlock(self.body, "Por qué Exponencial en los tres procesos")
        tb_e.pack(fill="x", pady=(0, t.PAD_SM))
        tb_e.add_text(
            "La distribución exponencial es la única continua sin memoria: "
            "P(X > s+t | X > s) = P(X > t). Tres consecuencias clave:"
        )
        tb_e.add_bullets([
            ("Llegadas:", "necesario para que las llegadas formen un proceso "
             "de Poisson, cuya tasa instantánea es constante e independiente "
             "del pasado."),
            ("Servicio:", "el tiempo restante para terminar al cliente en "
             "curso es siempre Exp(μ), sin importar cuánto lleva ya."),
            ("Vacaciones:", "el tiempo residual de una vacación Exp(θ) es "
             "también Exp(θ). De ahí E[residual] = 1/θ que da el término +1/θ "
             "en Wq (ver Módulo 1)."),
        ])
        tb_e.add_text("Si los datos reales no fueran exponenciales habría que "
                      "usar G/G/1 o M/G/1 con vacaciones, donde las fórmulas "
                      "son más complejas (Pollaczek-Khinchine, etc.).", muted=True)

        ExplainBox(
            self.body,
            body=("Este módulo responde la primera pregunta de cualquier "
                  "evaluación: '¿qué sistema modelaste?'. Define la clase de "
                  "modelo, los supuestos que validan las fórmulas cerradas, y la "
                  "frontera entre lo que el simulador captura y lo que no (por "
                  "ejemplo, abandonos o servicios no exponenciales)."),
            title="Por qué este módulo",
        ).pack(fill="x", pady=(t.PAD_SM, 0))
