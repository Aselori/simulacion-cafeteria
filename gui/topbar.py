"""Top bar: always-visible parameter strip + Simular button + live ρ indicator.

Replaces the wizard's Step 1 — parameters are editable any time, the user pushes
Simular when they want fresh results.
"""

import customtkinter as ctk

from . import theme as t
from .components import CompactField


class TopBar(ctk.CTkFrame):
    """Cinta superior con dos filas: parámetros + botón de simular en la
    primera, semillas + indicador de ρ en la segunda.

    El indicador de ρ se actualiza en vivo conforme el usuario edita λ y μ,
    sin necesidad de pulsar Simular — sirve como retroalimentación inmediata
    de si el sistema sería estable con esos valores.
    """

    def __init__(self, master, state, on_run):
        super().__init__(master, fg_color=t.BG, height=110)
        self.state = state
        self._on_run = on_run            # callback que dispara la simulación

        self._build()
        self._sync_rho()                 # render inicial del indicador ρ

    def _build(self):
        # Row 1: rates + T_sim + run button
        row1 = ctk.CTkFrame(self, fg_color=t.BG)
        row1.pack(fill="x", padx=t.PAD_LG, pady=(t.PAD_MD, t.PAD_SM))

        self.f_lam = CompactField(row1, "λ", self.state.lam,
                                  width=70, on_change=self._sync_rho)
        self.f_lam.pack(side="left", padx=(0, t.PAD_MD))

        self.f_mu = CompactField(row1, "μ", self.state.mu,
                                 width=70, on_change=self._sync_rho)
        self.f_mu.pack(side="left", padx=(0, t.PAD_MD))

        self.f_theta = CompactField(row1, "θ", self.state.theta,
                                    width=70, on_change=self._sync_rho)
        self.f_theta.pack(side="left", padx=(0, t.PAD_MD))

        ctk.CTkLabel(
            row1, text="|", font=t.font(t.SIZE_BODY),
            text_color=t.BORDER,
        ).pack(side="left", padx=(0, t.PAD_SM))

        ctk.CTkLabel(
            row1, text="Turno", font=t.font(t.SIZE_SMALL, "bold"),
            text_color=t.TEXT_MUTED,
        ).pack(side="left", padx=(0, 4))

        self.f_turno = CompactField(row1, "", self.state.turno, width=60)
        self.f_turno.pack(side="left", padx=(0, t.PAD_SM))

        self.f_obs_desde = CompactField(row1, "Obs.", self.state.obs_desde, width=60)
        self.f_obs_desde.pack(side="left", padx=(0, 4))

        ctk.CTkLabel(
            row1, text="a", font=t.font(t.SIZE_SMALL),
            text_color=t.TEXT_MUTED,
        ).pack(side="left", padx=(0, 4))

        self.f_obs_hasta = CompactField(row1, "", self.state.obs_hasta, width=60)
        self.f_obs_hasta.pack(side="left", padx=(0, t.PAD_MD))

        self.var_replicas = ctk.BooleanVar(value=self.state.run_replicas)
        ctk.CTkCheckBox(
            row1, text="10 réplicas (IC 95%)",
            variable=self.var_replicas, font=t.font(t.SIZE_SMALL),
            fg_color=t.ACCENT, hover_color=t.ACCENT_HOVER,
            text_color=t.TEXT, border_color=t.BORDER, border_width=2,
            checkbox_height=18, checkbox_width=18,
        ).pack(side="left", padx=(t.PAD_MD, 0))

        # Right side: run button
        self.btn_run = ctk.CTkButton(
            row1, text="Simular", command=self._run_clicked,
            fg_color=t.ACCENT, hover_color=t.ACCENT_HOVER,
            text_color="white", font=t.font(t.SIZE_BODY, "bold"),
            corner_radius=8, height=36, width=130,
        )
        self.btn_run.pack(side="right")

        self.lbl_status = ctk.CTkLabel(
            row1, text="", font=t.font(t.SIZE_SMALL),
            text_color=t.TEXT_MUTED, anchor="e",
        )
        self.lbl_status.pack(side="right", padx=(0, t.PAD_MD))

        # Row 2: seeds + rho indicator
        row2 = ctk.CTkFrame(self, fg_color=t.BG)
        row2.pack(fill="x", padx=t.PAD_LG, pady=(0, t.PAD_SM))

        ctk.CTkLabel(
            row2, text="Semillas", font=t.font(t.SIZE_SMALL, "bold"),
            text_color=t.TEXT_MUTED,
        ).pack(side="left", padx=(0, t.PAD_SM))

        self.f_mt = CompactField(row2, "MT", self.state.seed_mt, width=70)
        self.f_mt.pack(side="left", padx=(0, t.PAD_SM))
        self.f_lcg = CompactField(row2, "LCG", self.state.seed_lcg, width=70)
        self.f_lcg.pack(side="left", padx=(0, t.PAD_SM))
        self.f_mrg1 = CompactField(row2, "MRG₁", self.state.seed_mrg1, width=70)
        self.f_mrg1.pack(side="left", padx=(0, t.PAD_SM))
        self.f_mrg2 = CompactField(row2, "MRG₂", self.state.seed_mrg2, width=70)
        self.f_mrg2.pack(side="left", padx=(0, t.PAD_SM))

        self.lbl_rho = ctk.CTkLabel(
            row2, text="", font=t.mono(t.SIZE_BODY, "bold"),
            text_color=t.SUCCESS,
        )
        self.lbl_rho.pack(side="right")

    # --------------------------------------------------------------

    def _sync_rho(self):
        """Recalcula ρ = λ/μ en vivo y actualiza el color del indicador.

        Llamado por las trace callbacks de λ, μ y θ; tolera entradas
        inválidas (texto incompleto, división por cero) mostrando un guion.
        """
        try:
            lam = float(self.f_lam.get())
            mu = float(self.f_mu.get())
            rho = lam / mu
            if rho < 1:
                self.lbl_rho.configure(
                    text=f"ρ = {rho:.4f}    sistema estable",
                    text_color=t.SUCCESS,
                )
            else:
                # ρ ≥ 1: la cola explotaría — avisamos en rojo.
                self.lbl_rho.configure(
                    text=f"ρ = {rho:.4f}    sistema inestable",
                    text_color=t.DANGER,
                )
        except (ValueError, ZeroDivisionError):
            # El usuario está editando y el campo está temporalmente vacío
            # o no es número — mostramos un placeholder neutro.
            self.lbl_rho.configure(text="ρ = —", text_color=t.TEXT_SUBTLE)

    def _run_clicked(self):
        """Handler del botón Simular. Valida y, si pasa, delega al callback."""
        if not self._commit_to_state():
            self.lbl_status.configure(text="Parámetros inválidos", text_color=t.DANGER)
            return
        self.lbl_status.configure(text="")
        self._on_run()

    def _commit_to_state(self) -> bool:
        """Lee los widgets, valida y vuelca al `SimulationState` compartido.

        Devuelve True si todo es válido; False si algún campo no parsea o si
        algún parámetro no es estrictamente positivo (λ=0, etc., no tienen
        sentido en este modelo).
        """
        try:
            lam = float(self.f_lam.get())
            mu = float(self.f_mu.get())
            theta = float(self.f_theta.get())
            turno = float(self.f_turno.get())
            obs_desde = float(self.f_obs_desde.get())
            obs_hasta = float(self.f_obs_hasta.get())
            assert lam > 0 and mu > 0 and theta > 0
            assert turno > 0 and obs_hasta > obs_desde >= 0
            assert obs_hasta <= turno
            self.state.lam = lam
            self.state.mu = mu
            self.state.theta = theta
            self.state.turno = turno
            self.state.obs_desde = obs_desde
            self.state.obs_hasta = obs_hasta
            self.state.seed_mt = int(self.f_mt.get())
            self.state.seed_lcg = int(self.f_lcg.get())
            self.state.seed_mrg1 = int(self.f_mrg1.get())
            self.state.seed_mrg2 = int(self.f_mrg2.get())
            self.state.run_replicas = bool(self.var_replicas.get())
            return True
        except (ValueError, AssertionError):
            return False

    # --------------------------------------------------------------

    def set_running(self, running: bool, status: str = ""):
        """Cambia visualmente el estado de la barra entre "listo" y
        "ejecutando". Llamado por la App al inicio y fin de cada corrida."""
        self.btn_run.configure(
            state="disabled" if running else "normal",
            text="Ejecutando..." if running else "Simular",
        )
        self.lbl_status.configure(
            text=status,
            text_color=t.TEXT_MUTED if running else t.SUCCESS,
        )
