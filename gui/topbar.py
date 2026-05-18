"""Top bar: always-visible parameter strip + Simular button + live ρ indicator.

Replaces the wizard's Step 1 — parameters are editable any time, the user pushes
Simular when they want fresh results.
"""

import customtkinter as ctk

from . import theme as t
from .components import CompactField


class TopBar(ctk.CTkFrame):

    def __init__(self, master, state, on_run):
        super().__init__(master, fg_color=t.BG, height=110)
        self.state = state
        self._on_run = on_run

        self._build()
        self._sync_rho()

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

        self.f_tsim = CompactField(row1, "T", self.state.t_sim, width=90)
        self.f_tsim.pack(side="left", padx=(0, t.PAD_MD))

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
                self.lbl_rho.configure(
                    text=f"ρ = {rho:.4f}    sistema inestable",
                    text_color=t.DANGER,
                )
        except (ValueError, ZeroDivisionError):
            self.lbl_rho.configure(text="ρ = —", text_color=t.TEXT_SUBTLE)

    def _run_clicked(self):
        if not self._commit_to_state():
            self.lbl_status.configure(text="Parámetros inválidos", text_color=t.DANGER)
            return
        self.lbl_status.configure(text="")
        self._on_run()

    def _commit_to_state(self) -> bool:
        try:
            lam = float(self.f_lam.get())
            mu = float(self.f_mu.get())
            theta = float(self.f_theta.get())
            t_sim = float(self.f_tsim.get())
            assert lam > 0 and mu > 0 and theta > 0 and t_sim > 0
            self.state.lam = lam
            self.state.mu = mu
            self.state.theta = theta
            self.state.t_sim = t_sim
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
        self.btn_run.configure(
            state="disabled" if running else "normal",
            text="Ejecutando..." if running else "Simular",
        )
        self.lbl_status.configure(
            text=status,
            text_color=t.TEXT_MUTED if running else t.SUCCESS,
        )
