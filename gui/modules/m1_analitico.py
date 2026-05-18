"""Módulo 1 — Modelo analítico: fórmulas cerradas + sustitución + valores.

Renderiza las cinco métricas teóricas (ρ, Wq, W, Lq, L) con su fórmula,
sustitución numérica y resultado. Si el sistema es inestable (ρ ≥ 1), muestra
una advertencia y omite el cuerpo: las fórmulas divergen.
"""

import math

import customtkinter as ctk

from .. import theme as t
from ..components import Card, ExplainBox, TechBlock, Bullets
from .base import Module


class ModAnalitico(Module):
    """Primer módulo visible. No necesita simulación — se calcula al vuelo
    con `calcular_analitico` y sirve como referencia para validar la
    simulación más abajo en la página.
    """

    number = 1
    title = "Modelo analítico (M/M/1 con vacaciones múltiples)"
    subtitle = ("Antes de simular, calculamos los valores exactos que predice la teoría. "
                "Servirán de referencia para validar la simulación.")
    needs_simulation = False

    def render(self, state):
        # La App pre-computa `analitico` antes de montar cualquier módulo, así
        # que aquí ya está listo sin necesidad de recalcularlo.
        a = state.analitico

        # Top summary strip
        summary = Card(self.body, fg_color=t.BG_SOFT)
        summary.pack(fill="x", pady=(0, t.PAD_MD))
        ctk.CTkLabel(
            summary,
            text=(f"λ = {state.lam:g}    μ = {state.mu:g}    θ = {state.theta:g}    "
                  f"ρ = λ/μ = {a['rho']:.4f}"),
            font=t.mono(t.SIZE_BODY, "bold"), text_color=t.TEXT, anchor="w",
        ).pack(fill="x", padx=t.PAD_MD, pady=t.PAD_SM)

        if not a["estable"]:
            self.header.pill.set("warn")
            ctk.CTkLabel(
                self.body,
                text=("Sistema inestable (ρ ≥ 1). Las métricas analíticas divergen; "
                      "la simulación mostrará una cola que crece sin cota."),
                font=t.font(t.SIZE_SMALL), text_color=t.DANGER,
                anchor="w", justify="left", wraplength=860,
            ).pack(fill="x", pady=(0, t.PAD_MD))
            return

        # Formula rows
        rows = [
            ("Wq (M/M/1)",
             "ρ / [μ · (1 − ρ)]",
             f"{a['rho']:.4f} / [{state.mu:g} · (1 − {a['rho']:.4f})]",
             a["Wq_mm1"], "min",
             "Tiempo medio de espera en cola para el M/M/1 clásico (sin vacaciones)."),
            ("Wq (con vacaciones)",
             "Wq(M/M/1) + 1/θ",
             f"{a['Wq_mm1']:.4f} + {1/state.theta:.4f}",
             a["Wq"], "min",
             ("Las vacaciones añaden, en promedio, 1/θ minutos a la espera, porque "
              "todo cliente que llega con el servidor de vacaciones debe esperar el "
              "tiempo restante de esa vacación (Haviv, 2013, Teorema 4.9).")),
            ("W",
             "Wq + 1/μ",
             f"{a['Wq']:.4f} + {1/state.mu:.4f}",
             a["W"], "min",
             "Tiempo total en el sistema = espera en cola + tiempo medio de servicio."),
            ("Lq",
             "λ · Wq    (ley de Little)",
             f"{state.lam:g} · {a['Wq']:.4f}",
             a["Lq"], "clientes",
             "Número promedio de clientes en cola, por la ley de Little."),
            ("L",
             "λ · W     (ley de Little)",
             f"{state.lam:g} · {a['W']:.4f}",
             a["L"], "clientes",
             "Número promedio de clientes en el sistema (cola + en servicio)."),
        ]

        for r in rows:
            self._formula_row(*r)

        # --- Derivation / origin of formulas ---
        tb = TechBlock(self.body, "Ficha técnica — de dónde salen las fórmulas")
        tb.pack(fill="x", pady=(t.PAD_MD, 0))

        tb.add_subtitle("Teorema de descomposición (Takine & Hasegawa; Haviv 2013, §4.3)")
        tb.add_text("En un M/M/1 con vacaciones múltiples exhaustivas:")
        tb.add_mono("    Wq  =  Wq(M/M/1)  +  E[V_res]")
        tb.add_text("donde V_res es el tiempo residual de la vacación en curso al "
                    "llegar el cliente. Si V ~ Exp(θ), por la propiedad sin memoria "
                    "V_res también es Exp(θ) y por lo tanto:")
        tb.add_mono("    E[V_res]  =  1/θ")

        tb.add_subtitle("Pasos a las cinco métricas")
        tb.add_bullets([
            ("(1)", "Para el M/M/1 clásico, Wq = ρ / [μ·(1−ρ)] con ρ = λ/μ."),
            ("(2)", "Sumar el término de vacación:  Wq_V = Wq + 1/θ."),
            ("(3)", "W = Wq + 1/μ  (tiempo en cola más servicio medio)."),
            ("(4)", "Lq = λ · Wq  por la ley de Little aplicada a la cola."),
            ("(5)", "L  = λ · W   por la ley de Little aplicada al sistema."),
        ], mono_label=True)

        tb.add_subtitle("Condición de estabilidad")
        tb.add_text("Se requiere ρ = λ/μ < 1. Si no, la cola crece sin cota y las "
                    "cinco métricas son infinitas. Notar que θ no aparece en la "
                    "condición: por más cortas que sean las vacaciones, no pueden "
                    "compensar un servidor que llega tarde por sobrecarga.")

        tb.add_subtitle("Interpretación operacional de los recíprocos")
        tb.add_bullets([
            ("1/λ", f"= {1/state.lam:.2f} min — tiempo medio entre llegadas consecutivas."),
            ("1/μ", f"= {1/state.mu:.2f} min — duración media de un servicio."),
            ("1/θ", f"= {1/state.theta:.2f} min — duración media de una vacación."),
        ], mono_label=True)

        ExplainBox(
            self.body,
            body=("Estos valores son la 'verdad teórica' contra la que se compara la "
                  "simulación. Cuando ejecutes Simular abajo, las métricas observadas "
                  "deberían acercarse a estas a medida que crezca el tiempo simulado."),
            title="Por qué este módulo",
        ).pack(fill="x", pady=(t.PAD_MD, 0))

    def _formula_row(self, name, formula, subst, value, unit, note):
        """Renderiza una fila visual: nombre · fórmula simbólica · sustitución
        numérica · valor calculado · nota explicativa.

        Mantener las cuatro piezas (símbolo, fórmula, sustitución, número) en
        la misma línea ayuda al lector a seguir el cálculo paso a paso sin
        tener que cruzar referencias entre secciones.
        """
        card = Card(self.body, fg_color=t.BG_SOFT)
        card.pack(fill="x", pady=(0, t.PAD_SM))

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=t.PAD_MD, pady=(t.PAD_SM, 0))

        ctk.CTkLabel(
            top, text=name, font=t.font(t.SIZE_SMALL, "bold"),
            text_color=t.TEXT, anchor="w", width=180,
        ).pack(side="left")

        ctk.CTkLabel(
            top, text=f"=  {formula}", font=t.mono(t.SIZE_MONO_SMALL),
            text_color=t.TEXT_MUTED, anchor="w",
        ).pack(side="left", padx=(0, t.PAD_MD))

        val_str = "∞" if math.isinf(value) else f"{value:.4f}"
        ctk.CTkLabel(
            top, text=f"{val_str} {unit}", font=t.mono(t.SIZE_BODY, "bold"),
            text_color=t.ACCENT, anchor="e",
        ).pack(side="right")

        ctk.CTkLabel(
            card, text=f"     {subst}",
            font=t.mono(t.SIZE_MONO_SMALL), text_color=t.TEXT_SUBTLE, anchor="w",
        ).pack(fill="x", padx=t.PAD_MD)

        ctk.CTkLabel(
            card, text=note, font=t.font(t.SIZE_TINY),
            text_color=t.TEXT_MUTED, anchor="w", justify="left", wraplength=820,
        ).pack(fill="x", padx=t.PAD_MD, pady=(2, t.PAD_SM))
