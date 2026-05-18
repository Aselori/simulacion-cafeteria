"""Módulo 5 — Estadísticas del servidor: fracciones ocupado / vacación / ocioso.

Visualiza las tres áreas temporales acumuladas por la simulación:
  - ρ      (área_ocupado / t_efectivo)
  - 1 − ρ  típicamente equivale a fracción en vacación
  - idle   debería ser ~0 en este modelo (servidor nunca está despierto sin
            atender y sin haber salido de vacación)
"""

import customtkinter as ctk

from .. import theme as t
from ..components import Card, ExplainBox, TechBlock
from .base import Module


class ModServidor(Module):
    """Tres "stat cards" lado a lado + ficha técnica con el invariante y
    PASTA. Sirve para auditar visualmente que la simulación cumple el
    invariante ρ + ρ_vac + ρ_idle = 1."""

    number = 3
    title = "Estadísticas del servidor"
    subtitle = "Cómo distribuye el servidor su tiempo entre los tres estados posibles."
    needs_simulation = True

    def render(self, state):
        sim = state.sim
        # `max(0, ...)` protege contra errores de redondeo que pudieran dar
        # un idle ligeramente negativo (ρ_sim + ρ_vac ≈ 1 con jitter de float).
        idle = max(0.0, 1 - sim["rho"] - sim["rho_vacacion"])

        wrap = ctk.CTkFrame(self.body, fg_color="transparent")
        wrap.pack(fill="x", pady=(0, t.PAD_MD))

        for label, value, color, note in [
            ("Ocupado (atendiendo)",
             f"{sim['rho']*100:.2f} %", t.ACCENT,
             "Fracción del tiempo con un cliente en servicio."),
            ("En vacaciones",
             f"{sim['rho_vacacion']*100:.2f} %", t.WARN,
             "Tras vaciarse la cola, el servidor toma una vacación Exp(θ); "
             "si al volver no hay nadie, toma otra (vacaciones múltiples)."),
            ("Ocioso (cola vacía sin vacación)",
             f"{idle*100:.2f} %", t.TEXT_MUTED,
             "Debe ser 0 en este modelo: el servidor nunca está ocioso despierto. "
             "Si > 0, hubo error numérico."),
        ]:
            box = Card(wrap, fg_color=t.BG_SOFT)
            box.pack(side="left", expand=True, fill="x", padx=t.PAD_XS)
            ctk.CTkLabel(
                box, text=label, font=t.font(t.SIZE_TINY, "bold"),
                text_color=t.TEXT_MUTED, anchor="w",
            ).pack(fill="x", padx=t.PAD_MD, pady=(t.PAD_SM, 0))
            ctk.CTkLabel(
                box, text=value, font=t.mono(22, "bold"),
                text_color=color, anchor="w",
            ).pack(fill="x", padx=t.PAD_MD)
            ctk.CTkLabel(
                box, text=note, font=t.font(t.SIZE_TINY),
                text_color=t.TEXT_SUBTLE, anchor="w", justify="left", wraplength=240,
            ).pack(fill="x", padx=t.PAD_MD, pady=(0, t.PAD_SM))

        ExplainBox(
            self.body,
            body=("La utilización ρ_obs debería coincidir con λ/μ. La fracción de "
                  "vacaciones (1 − ρ) sale del hecho de que cuando el servidor no "
                  "está atendiendo, está siempre de vacación: este es el invariante "
                  "que define al modelo M/M/1 con vacaciones múltiples."),
            title="Por qué este módulo",
        ).pack(fill="x", pady=(0, t.PAD_MD))

        # ---- Invariant + PASTA ----
        tb = TechBlock(self.body, "Ficha técnica — Invariante del servidor y PASTA")
        tb.pack(fill="x")
        tb.add_subtitle("Identidad invariante en estado estacionario")
        tb.add_mono("    ρ_ocupado  +  ρ_vacación  +  ρ_ocioso  =  1")
        tb.add_text("En el modelo M/M/1 con vacaciones múltiples exhaustivas, "
                    "ρ_ocioso = 0 por construcción: si el servidor no está "
                    "atendiendo a alguien, está siempre de vacación. Entonces:")
        tb.add_mono("    ρ_vacación  =  1  −  ρ")
        tb.add_text("Si la simulación reporta ρ_ocioso > 0, hubo un error de "
                    "implementación.")

        tb.add_subtitle("Cálculo (consistente con el Módulo 5: Eventos)")
        tb.add_bullets([
            ("ρ̂ =", "area_ocupado / t_efectivo"),
            ("ρ̂_vacación =", "area_vacacion / t_efectivo"),
            ("ρ̂_ocioso =", "1 − ρ̂ − ρ̂_vacación   (debería tender a 0)"),
        ], mono_label=True)

        tb.add_subtitle("PASTA (Poisson Arrivals See Time Averages)")
        tb.add_text("Como las llegadas son Poisson(λ), los clientes 'ven' el "
                    "sistema en proporciones idénticas a los promedios temporales. "
                    "Es decir, la probabilidad de que un cliente llegue con el "
                    "servidor de vacaciones es exactamente ρ_vacación = 1 − ρ. "
                    "De ahí nace el término +1/θ en Wq: una fracción (1−ρ) de "
                    "clientes encara la espera por vacación residual.")
