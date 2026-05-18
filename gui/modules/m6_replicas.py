"""Módulo 6 — Réplicas e intervalos de confianza al 95 %.

Renderiza la tabla de IC para las cinco métricas y las cuatro pruebas de
validación: cobertura de Wq, ley de Little (L y Lq) y precisión de ρ.

Este módulo sobrescribe `mount` (en vez de `render`) porque tiene tres
estados visuales posibles: pendiente, desactivado (cuando run_replicas=False)
y renderizado.
"""

import customtkinter as ctk

from .. import theme as t
from ..components import Card, ExplainBox, TechBlock, Bullets
from .base import Module


class ModReplicas(Module):
    """Validación estadística del simulador con 10 réplicas independientes.

    La pill del header muestra "X/4 pruebas pasan" — feedback inmediato del
    estado de la validación sin tener que leer la tabla completa.
    """

    number = 4
    title = "Réplicas e intervalos de confianza (95 %)"
    subtitle = ("Diez ejecuciones independientes producen una distribución de cada "
                "métrica. Validamos cobertura, ley de Little y precisión de ρ.")
    needs_simulation = True

    def mount(self, state):
        # Tres estados: (1) sin simulación → placeholder genérico, (2) con
        # simulación pero usuario desactivó réplicas → mensaje explicativo,
        # (3) con réplicas → render completo.
        if state.sim is None:
            self.header.pill.set("pending")
            self._placeholder()
            return
        if not state.run_replicas or state.replicas_result is None:
            self._clear_body()
            self.header.pill.set("pending", text="Desactivado")
            ctk.CTkLabel(
                self.body,
                text=("Las réplicas están desactivadas. Marca '10 réplicas (IC 95%)' "
                      "en la barra superior y vuelve a simular para activar este módulo."),
                font=t.font(t.SIZE_SMALL), text_color=t.TEXT_MUTED,
                anchor="w", justify="left", wraplength=860,
            ).pack(fill="x", pady=t.PAD_MD)
            return
        self._clear_body()
        self.render(state)

    def render(self, state):
        rr = state.replicas_result
        stats, a = rr["stats"], rr["analitico"]

        # --- IC table ---
        table = Card(self.body, fg_color=t.BG_SOFT)
        table.pack(fill="x", pady=(0, t.PAD_MD))

        headers = ("Métrica", "Media", "IC inferior", "IC superior", "Analítico", "Cobertura")
        widths = (140, 100, 100, 100, 100, 100)

        hdr = ctk.CTkFrame(table, fg_color="transparent")
        hdr.pack(fill="x", padx=t.PAD_MD, pady=(t.PAD_SM, 2))
        for h, w in zip(headers, widths):
            ctk.CTkLabel(
                hdr, text=h, font=t.font(t.SIZE_TINY, "bold"),
                text_color=t.TEXT_MUTED, width=w, anchor="w",
            ).pack(side="left", padx=2)
        ctk.CTkFrame(table, fg_color=t.BORDER, height=1).pack(fill="x", padx=t.PAD_MD)

        for name, key in [("ρ", "rho"), ("L", "L"), ("Lq", "Lq"),
                          ("W", "W"), ("Wq", "Wq")]:
            st = stats[key]
            a_val = a[key]
            contains = st["ci_lower"] <= a_val <= st["ci_upper"]
            cov_color = t.SUCCESS if contains else t.DANGER
            row = ctk.CTkFrame(table, fg_color="transparent")
            row.pack(fill="x", padx=t.PAD_MD)
            for (txt, col, weight), w in zip([
                (name, t.TEXT, "bold"),
                (f"{st['media']:.4f}", t.TEXT, "normal"),
                (f"{st['ci_lower']:.4f}", t.TEXT_MUTED, "normal"),
                (f"{st['ci_upper']:.4f}", t.TEXT_MUTED, "normal"),
                (f"{a_val:.4f}", t.TEXT, "normal"),
                ("Sí" if contains else "No", cov_color, "bold"),
            ], widths):
                ctk.CTkLabel(
                    row, text=txt, font=t.mono(t.SIZE_MONO_SMALL, weight),
                    text_color=col, width=w, anchor="w",
                ).pack(side="left", padx=2)
        ctk.CTkFrame(table, fg_color="transparent", height=t.PAD_SM).pack()

        # --- Validation checks ---
        ctk.CTkLabel(
            self.body, text="Validación del modelo (§ 8.4)",
            font=t.font(t.SIZE_SMALL, "bold"), text_color=t.TEXT, anchor="w",
        ).pack(fill="x", pady=(0, t.PAD_XS))

        v = rr["validacion"]
        checks = [
            ("Wq analítico cae dentro del IC 95 %",
             v.get("Wq_en_IC", False), "",
             "Si el IC cubre el valor teórico, el simulador no presenta sesgo "
             "estadísticamente detectable en Wq."),
            ("Ley de Little:  L ≈ λ·W",
             v.get("Little_L", False),
             f"error {v.get('Little_L_valor', 0)*100:.2f} %",
             "Verificación interna: independiente del modelo teórico, L debe ser "
             "λ·W por la ley de Little. Si falla, algo está mal en el conteo."),
            ("Ley de Little:  Lq ≈ λ·Wq",
             v.get("Little_Lq", False),
             f"error {v.get('Little_Lq_valor', 0)*100:.2f} %",
             "Idéntica verificación para la cola."),
            ("Precisión de ρ:  |ρ_sim − λ/μ| < 0.02",
             v.get("rho_precision", False),
             f"|Δ| = {v.get('rho_diff', 0):.4f}",
             "La utilización converge exactamente a λ/μ por la condición de "
             "estabilidad del modelo."),
        ]

        passes = 0
        for label, ok, detail, note in checks:
            if ok:
                passes += 1
            self._check_row(label, ok, detail, note)

        self.header.pill.set(
            "done" if passes == 4 else "warn",
            text=f"{passes}/4 pruebas pasan",
        )

        ExplainBox(
            self.body,
            body=("Los IC al 95 % se construyen con la t de Student (gl=9, t=2.262) "
                  "sobre las 10 medias replicadas, usando semillas independientes "
                  "generadas a partir de la semilla maestra. La cobertura del IC y "
                  "las dos pruebas de Little son condiciones suficientes para "
                  "considerar validado el simulador."),
            title="Cómo se construye este módulo",
        ).pack(fill="x", pady=(t.PAD_MD, t.PAD_MD))

        # ---- IC formula + replicas justification ----
        tb1 = TechBlock(self.body, "Ficha técnica — Construcción del intervalo de confianza")
        tb1.pack(fill="x", pady=(0, t.PAD_SM))
        tb1.add_subtitle("Fórmula del IC al 95 %")
        tb1.add_mono("    IC₉₅ %  =  x̄  ±  t_(α/2, n−1) · s / √n")
        tb1.add_bullets([
            ("x̄", "media muestral de las n medias replicadas."),
            ("s",  "desviación estándar muestral (con divisor n−1)."),
            ("n",  "número de réplicas = 10."),
            ("α",  "1 − 0.95 = 0.05."),
            ("t_(0.025, 9)", "= 2.262  (valor crítico de la t de Student con 9 gl)."),
        ], mono_label=True)
        tb1.add_subtitle("Por qué t de Student y no z")
        tb1.add_text("La desviación verdadera σ es desconocida; al estimarla con s "
                     "sobre n pequeño (10), el estadístico (x̄ − μ)/(s/√n) sigue "
                     "exactamente una t de Student con n−1 gl si las medias "
                     "replicadas son aproximadamente normales (lo son por TCL).")

        tb2 = TechBlock(self.body, "Ficha técnica — Por qué 10 réplicas independientes")
        tb2.pack(fill="x", pady=(0, t.PAD_SM))
        tb2.add_bullets([
            "Cada réplica corre la misma simulación pero con un cuarteto de "
            "semillas distinto, derivado de una semilla maestra (42) vía un "
            "MT19937 — garantiza independencia estadística entre réplicas.",
            "n = 10 es el mínimo común en simulación didáctica: pequeño "
            "suficiente para correr rápido, grande suficiente para que la t de "
            "Student tenga gl=9 (valores críticos razonables).",
            "El semi-ancho del IC decrece como 1/√n: pasar de 10 a 40 réplicas "
            "reduce el semi-ancho a la mitad. Es un trade-off costo/precisión.",
        ])

        tb3 = TechBlock(self.body, "Ficha técnica — Las cuatro pruebas como condición suficiente")
        tb3.pack(fill="x", pady=(0, 0))
        tb3.add_bullets([
            ("Cobertura (1):", "valida el simulador contra el modelo teórico — "
             "si el IC cubre el valor analítico, no hay sesgo detectable."),
            ("Little L (2):", "verificación interna independiente del modelo: "
             "L = λ·W es identidad universal de teoría de colas. Detecta errores "
             "de conteo aunque el modelo teórico estuviera mal."),
            ("Little Lq (3):", "idéntica para la cola; refuerza la (2)."),
            ("Precisión ρ (4):", "ρ_sim debe coincidir con λ/μ en cualquier "
             "modelo M/M/1 (con o sin vacaciones). Detecta errores en el conteo "
             "del tiempo ocupado del servidor."),
        ])
        tb3.add_text("Las cuatro juntas chequean: (a) coherencia con el modelo "
                     "teórico, (b) coherencia interna del simulador (Little), y "
                     "(c) coherencia del estimador más básico (ρ). Si las cuatro "
                     "pasan, el profesor no tiene base estadística para dudar.",
                     muted=True)

    def _check_row(self, label, ok, detail, note):
        """Fila visual de una prueba: badge pasa/falla + label + detalle
        numérico + nota explicativa debajo. Usado para las cuatro pruebas
        de validación."""
        card = Card(self.body, fg_color=t.BG_SOFT)
        card.pack(fill="x", pady=(0, t.PAD_XS))

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=t.PAD_MD, pady=(t.PAD_SM, 0))

        badge = "pasa" if ok else "falla"
        ctk.CTkLabel(
            top, text=badge, font=t.mono(t.SIZE_MONO_SMALL, "bold"),
            text_color=t.SUCCESS if ok else t.DANGER,
            width=50, anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            top, text=label, font=t.font(t.SIZE_SMALL),
            text_color=t.TEXT, anchor="w",
        ).pack(side="left", padx=t.PAD_SM)
        if detail:
            ctk.CTkLabel(
                top, text=detail, font=t.mono(t.SIZE_MONO_SMALL),
                text_color=t.TEXT_MUTED, anchor="e",
            ).pack(side="right")

        ctk.CTkLabel(
            card, text=note, font=t.font(t.SIZE_TINY),
            text_color=t.TEXT_SUBTLE, anchor="w", justify="left", wraplength=820,
        ).pack(fill="x", padx=t.PAD_MD, pady=(2, t.PAD_SM))
