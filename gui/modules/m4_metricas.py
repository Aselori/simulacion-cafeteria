"""Módulo 4 — Métricas de la simulación: tabla Sim vs Analítico."""

import math

import customtkinter as ctk

from .. import theme as t
from ..components import Card, ExplainBox, TechBlock, Bullets
from .base import Module


class ModMetricas(Module):
    number = 2
    title = "Métricas de la simulación vs. analítico"
    subtitle = ("Comparación punto a punto de las cinco métricas. Un error bajo "
                "indica que el simulador reproduce el modelo.")
    needs_simulation = True

    def render(self, state):
        sim, a = state.sim, state.analitico

        table = Card(self.body, fg_color=t.BG_SOFT)
        table.pack(fill="x", pady=(0, t.PAD_MD))

        headers = ("Métrica", "Simulación", "Analítico", "Error")
        widths = (240, 140, 140, 100)

        hdr = ctk.CTkFrame(table, fg_color="transparent")
        hdr.pack(fill="x", padx=t.PAD_MD, pady=(t.PAD_SM, 2))
        for h, w in zip(headers, widths):
            ctk.CTkLabel(
                hdr, text=h, font=t.font(t.SIZE_TINY, "bold"),
                text_color=t.TEXT_MUTED, width=w, anchor="w",
            ).pack(side="left", padx=2)
        ctk.CTkFrame(table, fg_color=t.BORDER, height=1).pack(fill="x", padx=t.PAD_MD)

        rows = [
            ("ρ (utilización)", sim["rho"], a["rho"]),
            ("L  (clientes en sistema)", sim["L"], a["L"]),
            ("Lq (clientes en cola)", sim["Lq"], a["Lq"]),
            ("W  (tiempo en sistema, min)", sim["W"], a["W"]),
            ("Wq (espera en cola, min)", sim["Wq"], a["Wq"]),
        ]
        errs = []
        for name, s_val, a_val in rows:
            if a_val != 0 and math.isfinite(a_val):
                err_pct = abs(s_val - a_val) / a_val * 100
                errs.append(err_pct)
                err_str = f"{err_pct:.2f} %"
                err_color = (t.SUCCESS if err_pct < 5
                             else (t.WARN if err_pct < 15 else t.DANGER))
            else:
                err_str, err_color = "—", t.TEXT_MUTED
            a_str = "∞" if math.isinf(a_val) else f"{a_val:.4f}"
            row = ctk.CTkFrame(table, fg_color="transparent")
            row.pack(fill="x", padx=t.PAD_MD)
            for (txt, col, weight), w in zip([
                (name, t.TEXT, "bold"),
                (f"{s_val:.4f}", t.TEXT, "normal"),
                (a_str, t.TEXT_MUTED, "normal"),
                (err_str, err_color, "bold"),
            ], widths):
                ctk.CTkLabel(
                    row, text=txt, font=t.mono(t.SIZE_MONO_SMALL, weight),
                    text_color=col, width=w, anchor="w",
                ).pack(side="left", padx=2)
        ctk.CTkFrame(table, fg_color="transparent", height=t.PAD_SM).pack()

        avg = sum(errs) / len(errs) if errs else 0
        avg_color = (t.SUCCESS if avg < 5 else (t.WARN if avg < 15 else t.DANGER))
        if avg < 5:
            self.header.pill.set("done", text=f"Error medio {avg:.2f}%")
        else:
            self.header.pill.set("warn", text=f"Error medio {avg:.2f}%")

        ctk.CTkLabel(
            self.body, text=f"Error promedio: {avg:.2f} %",
            font=t.mono(t.SIZE_BODY, "bold"), text_color=avg_color, anchor="w",
        ).pack(fill="x", pady=(0, t.PAD_SM))

        ExplainBox(
            self.body,
            body=("La columna 'Simulación' es un promedio ponderado por tiempo "
                  "(no por evento) sobre el tiempo total simulado. 'Analítico' "
                  "es el valor exacto del modelo M/M/1 con vacaciones múltiples. "
                  "El error porcentual baja al aumentar el tiempo simulado: con "
                  "T_sim grande converge a 0 por la ley de los grandes números."),
            title="Cómo leer esta tabla",
        ).pack(fill="x", pady=(0, t.PAD_MD))

        # ---- Convergence / interpretation ----
        tb = TechBlock(self.body, "Ficha técnica — Cómo se construye el error")
        tb.pack(fill="x")
        tb.add_subtitle("Cálculo del error porcentual")
        tb.add_mono("    error(x̂) = |x̂ − x_teórico| / x_teórico · 100 %")
        tb.add_text("donde x̂ es el estimador simulado y x_teórico el valor del "
                    "modelo M/M/1 con vacaciones múltiples.")

        tb.add_subtitle("Por qué disminuye al aumentar T_sim")
        tb.add_bullets([
            ("Para L̂, L̂q, ρ̂ (promedios temporales):", "por el teorema ergódico, "
             "el promedio temporal converge al esperado en estado estacionario "
             "cuando T → ∞. Tasa típica: O(1/√T)."),
            ("Para Ŵ, Ŵq (promedios sobre clientes):", "el número de clientes "
             "servidos crece como λ·T, así que la varianza del promedio decrece "
             "como 1/(λ·T)."),
            ("Umbrales del semáforo:", "verde si error < 5 %, ámbar si < 15 %, "
             "rojo si ≥ 15 %. Son convenciones; con T_sim ≈ 10 000 min lo típico "
             "es < 3 %."),
        ])

        tb.add_subtitle("Cuándo desconfiar de un error bajo aislado")
        tb.add_text("Un solo error bajo puede ser suerte de la semilla. La "
                    "validación robusta requiere las 10 réplicas + cobertura del "
                    "IC al 95 %, en el Módulo 4 (Réplicas).", muted=True)
