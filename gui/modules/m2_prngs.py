"""Módulo 2 — Generadores pseudoaleatorios: 3 sub-cards con muestras y chi²."""

import math
import tkinter as tk

import customtkinter as ctk

from simulacion_cafeteria import (
    MersenneTwister, MCG, MRG,
    gen_interarrival, gen_service_time, gen_vacation_time,
    chi_cuadrado_exp,
)

from .. import theme as t
from ..components import Card, ExplainBox, TechBlock, Bullets
from .base import Module


N_MUESTRAS = 1000
N_PREVIEW = 8


class ModPRNGs(Module):
    number = 6
    title = "Generadores pseudoaleatorios"
    subtitle = ("Tres generadores independientes alimentan los tres procesos del modelo. "
                "Verificamos con chi² que cada serie sigue una distribución exponencial.")
    needs_simulation = False

    def render(self, state):
        rng_lleg = MersenneTwister(state.seed_mt)
        rng_serv = MRG(state.seed_mrg1, state.seed_mrg2)
        rng_vac = MCG(state.seed_lcg)

        muestras_lleg = [gen_interarrival(rng_lleg, state.lam) for _ in range(N_MUESTRAS)]
        muestras_serv = [gen_service_time(rng_serv, state.mu) for _ in range(N_MUESTRAS)]
        muestras_vac = [gen_vacation_time(rng_vac, state.theta) for _ in range(N_MUESTRAS)]
        state.prng_samples = {
            "llegadas": muestras_lleg, "servicio": muestras_serv, "vacacion": muestras_vac,
        }

        all_pass = True
        for spec in [
            ("MT19937 (Mersenne Twister)", "Matsumoto & Nishimura, 1998",
             "Tiempo entre llegadas, distribución Exp(λ)",
             "λ", state.lam, muestras_lleg, f"semilla = {state.seed_mt}"),
            ("MRG (k=2)", "Deng & Lin, 2000",
             "Tiempo de servicio, distribución Exp(μ)",
             "μ", state.mu, muestras_serv,
             f"semillas = ({state.seed_mrg1}, {state.seed_mrg2})"),
            ("LCG / MCG (Lehmer)", "A = 16807, M = 2³¹ − 1",
             "Duración de vacación, distribución Exp(θ)",
             "θ", state.theta, muestras_vac, f"semilla = {state.seed_lcg}"),
        ]:
            ok = self._sub_card(*spec)
            all_pass = all_pass and ok

        self.header.pill.set("done" if all_pass else "warn")

        # ---- Inverse transform derivation ----
        tb1 = TechBlock(self.body, "Ficha técnica — Transformada inversa para Exp(λ)")
        tb1.pack(fill="x", pady=(t.PAD_MD, t.PAD_SM))
        tb1.add_text("La función de distribución acumulada de Exp(λ) es:")
        tb1.add_mono("    F(x) = 1 − exp(−λ·x),    x ≥ 0")
        tb1.add_text("Si U ~ Uniforme(0,1), entonces F⁻¹(U) tiene distribución F. "
                     "Despejando x de U = 1 − exp(−λx):")
        tb1.add_mono("    x = −ln(1 − U) / λ")
        tb1.add_text("Como U y (1−U) son ambas Uniforme(0,1), simplificamos a:")
        tb1.add_mono("    x = −ln(U) / λ        (forma usada en el código)")
        tb1.add_text("Esta sustitución vale por el teorema de la transformada de "
                     "probabilidad (probability integral transform).", muted=True)

        # ---- Generator periods & properties ----
        tb2 = TechBlock(self.body, "Ficha técnica — Propiedades de los tres generadores")
        tb2.pack(fill="x", pady=(0, t.PAD_SM))
        tb2.add_bullets([
            ("MT19937:", "período = 2¹⁹⁹³⁷ − 1 (~10⁶⁰⁰¹), equidistribución 623-D, "
             "estándar de facto. Producción de uniformes muy uniforme en (0,1)."),
            ("LCG (Park-Miller, A=16807, M=2³¹−1):", "período = 2³¹ − 2 ≈ 2.15·10⁹. "
             "Suficiente para vacaciones (poco numerosas); fácil de auditar; "
             "estructura reticular limita sub-muestras de alta dimensión."),
            ("MRG k=2:", "Xₙ = (α₁·Xₙ₋₁ + α₂·Xₙ₋₂) mod p,  p = 2³¹−1. "
             "Período ≈ p² ≈ 4.6·10¹⁸. Mejor independencia de varias dimensiones "
             "que un LCG simple."),
        ], mono_label=True)

        # ---- Chi-square test formal statement ----
        tb3 = TechBlock(self.body, "Ficha técnica — Prueba χ² de bondad de ajuste")
        tb3.pack(fill="x", pady=(0, t.PAD_SM))
        tb3.add_bullets([
            ("H₀:", "las muestras provienen de Exp con la tasa indicada."),
            ("H₁:", "las muestras no provienen de esa Exp."),
            ("Estadístico:", "χ² = Σ (Oᵢ − Eᵢ)² / Eᵢ  sobre k bins equiprobables."),
            ("Bins:", f"k = 6 bins equiprobables (cuantiles de Exp): cada bin "
             f"tiene Eᵢ = n/k = {N_MUESTRAS/6:.0f} esperados."),
            ("Grados de libertad:", "gl = k − 1 − m, con m=1 parámetro asumido "
             "conocido (la tasa). Entonces gl = 4."),
            ("Nivel de significancia:", "α = 0.05; valor crítico = 9.488."),
            ("Decisión:", "rechazar H₀ si χ² > 9.488. De lo contrario, no se "
             "tiene evidencia para rechazar la hipótesis exponencial."),
        ], mono_label=True)

        # ---- Why three independent streams ----
        tb4 = TechBlock(self.body, "Ficha técnica — Por qué tres streams independientes")
        tb4.pack(fill="x", pady=(0, 0))
        tb4.add_text(
            "Si un único generador produjera todos los tiempos (llegadas, "
            "servicios y vacaciones), una sub-secuencia de muestras consecutivas "
            "podría introducir correlación espuria entre procesos lógicamente "
            "independientes — por ejemplo, sincronizar 'llegada larga' con "
            "'servicio largo'. Usar tres streams con semillas distintas las "
            "desacopla por construcción y permite reproducir cada flujo por "
            "separado (útil para depurar)."
        )

        ExplainBox(
            self.body,
            body=("Se usan tres generadores distintos para evitar correlaciones entre "
                  "los procesos de llegada, servicio y vacaciones. Las muestras Exp se "
                  "obtienen por la transformada inversa X = −ln(U)/tasa, donde U es "
                  "uniforme en (0,1). El test χ² compara la distribución empírica con "
                  "la exponencial teórica."),
            title="Por qué este módulo",
        ).pack(fill="x", pady=(t.PAD_MD, 0))

    def _sub_card(self, name, ref, uses, tasa_name, tasa, muestras, seed_text):
        card = Card(self.body, fg_color=t.BG_SOFT)
        card.pack(fill="x", pady=(0, t.PAD_SM))

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=t.PAD_MD, pady=(t.PAD_SM, 2))

        ctk.CTkLabel(
            top, text=name, font=t.font(t.SIZE_SMALL, "bold"),
            text_color=t.TEXT, anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            top, text=ref, font=t.font(t.SIZE_TINY),
            text_color=t.TEXT_MUTED, anchor="w",
        ).pack(side="left", padx=(t.PAD_SM, 0))
        ctk.CTkLabel(
            top, text=seed_text, font=t.mono(t.SIZE_MONO_SMALL),
            text_color=t.TEXT_SUBTLE, anchor="e",
        ).pack(side="right")

        ctk.CTkLabel(
            card, text=uses, font=t.font(t.SIZE_SMALL),
            text_color=t.ACCENT, anchor="w",
        ).pack(fill="x", padx=t.PAD_MD)

        preview = "  ".join(f"{x:.3f}" for x in muestras[:N_PREVIEW])
        ctk.CTkLabel(
            card, text=f"Primeras {N_PREVIEW} muestras:  {preview}  …",
            font=t.mono(t.SIZE_MONO_SMALL), text_color=t.TEXT, anchor="w",
            justify="left", wraplength=820,
        ).pack(fill="x", padx=t.PAD_MD, pady=(t.PAD_XS, 0))

        media = sum(muestras) / len(muestras)
        teorica = 1.0 / tasa
        err_pct = abs(media - teorica) / teorica * 100
        ctk.CTkLabel(
            card,
            text=(f"Media muestral = {media:.4f}     "
                  f"Media teórica (1/{tasa_name}) = {teorica:.4f}     "
                  f"Error = {err_pct:.2f} %"),
            font=t.mono(t.SIZE_MONO_SMALL), text_color=t.TEXT_MUTED, anchor="w",
        ).pack(fill="x", padx=t.PAD_MD)

        self._histogram(card, muestras, tasa).pack(
            fill="x", padx=t.PAD_MD, pady=(t.PAD_XS, t.PAD_XS),
        )

        chi2, chi2_crit, ok, *_ = chi_cuadrado_exp(muestras, tasa, num_bins=6)
        chi_color = t.SUCCESS if ok else t.DANGER
        ctk.CTkLabel(
            card,
            text=(f"χ² = {chi2:.3f}    crítico (gl=4, α=0.05) = {chi2_crit:.3f}    "
                  f"{'pasa (acepta exponencial)' if ok else 'falla'}"),
            font=t.mono(t.SIZE_MONO_SMALL, "bold"),
            text_color=chi_color, anchor="w",
        ).pack(fill="x", padx=t.PAD_MD, pady=(0, t.PAD_SM))

        return ok

    def _histogram(self, master, muestras, tasa, n_bins=20):
        w, h = 820, 70
        canvas = tk.Canvas(master, width=w, height=h, bg=t.BG_SOFT, highlightthickness=0)
        if not muestras:
            return canvas

        sorted_m = sorted(muestras)
        x_cap = sorted_m[int(0.95 * len(sorted_m))] or max(muestras)
        if x_cap <= 0:
            return canvas

        bin_w = x_cap / n_bins
        counts = [0] * n_bins
        for x in muestras:
            b = min(int(x / bin_w), n_bins - 1)
            counts[b] += 1
        max_count = max(counts) or 1

        bar_w = w / n_bins
        for i, c in enumerate(counts):
            bar_h = (c / max_count) * (h - 4)
            canvas.create_rectangle(
                i * bar_w, h - bar_h, (i + 1) * bar_w - 1, h,
                fill=t.ACCENT_SOFT, outline="",
            )

        points = []
        for px in range(0, int(w), 2):
            x_val = (px / w) * x_cap
            expected = tasa * math.exp(-tasa * x_val) * bin_w * len(muestras)
            py = h - (expected / max_count) * (h - 4)
            points.extend([px, py])
        if len(points) >= 4:
            canvas.create_line(*points, fill=t.ACCENT, width=2, smooth=True)
        return canvas
