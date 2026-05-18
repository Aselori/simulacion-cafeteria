"""Main app shell: sticky top bar + scrollable column of self-contained modules.

No wizard. Inputs live in the top bar; pressing Simular re-runs the simulation
and remounts every module. Modules 1 and 2 don't need a simulation and render
their content from the parameters alone.
"""

import threading
from dataclasses import dataclass, field

import customtkinter as ctk

from simulacion_cafeteria import simular, ejecutar_replicas, calcular_analitico

from . import theme as t
from .topbar import TopBar
from .modules.m0_sistema import ModSistema
from .modules.m1_analitico import ModAnalitico
from .modules.m2_prngs import ModPRNGs
from .modules.m3_eventos import ModEventos
from .modules.m4_metricas import ModMetricas
from .modules.m5_servidor import ModServidor
from .modules.m6_replicas import ModReplicas


@dataclass
class SimulationState:
    lam: float = 0.5
    mu: float = 0.67
    theta: float = 0.2
    t_sim: float = 10000.0
    t_warmup: float = 0.0
    seed_mt: int = 19937
    seed_lcg: int = 48271
    seed_mrg1: int = 31415
    seed_mrg2: int = 92653
    run_replicas: bool = True

    analitico: dict | None = None
    sim: dict | None = None
    replicas_result: dict | None = None
    prng_samples: dict[str, list[float]] = field(default_factory=dict)


# Order shown to the user — results-first; theory at the bottom as appendix.
MODULE_CLASSES = (
    ModAnalitico,   # 1 — referencia
    ModMetricas,    # 2 — resultado principal (Sim vs Analítico)
    ModServidor,    # 3 — estados del servidor
    ModReplicas,    # 4 — validación
    ModEventos,     # 5 — detalle del proceso
    ModPRNGs,       # 6 — auditoría de generadores
    ModSistema,     # 7 — apéndice teórico
)


class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=t.BG)
        self.title("Simulación M/M/1 con vacaciones — Cafetería UANL")
        self.geometry("1100x820")
        self.minsize(960, 700)

        self.sim_state = SimulationState()
        self._running = False
        self._build()
        self._refresh_modules()

    def _build(self):
        self.topbar = TopBar(self, self.sim_state, on_run=self._run_simulation)
        self.topbar.pack(fill="x", side="top")

        ctk.CTkFrame(self, fg_color=t.BORDER, height=1).pack(fill="x")

        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=t.BG_SOFT,
            scrollbar_button_color=t.BORDER,
            scrollbar_button_hover_color=t.TEXT_SUBTLE,
        )
        self.scroll.pack(fill="both", expand=True)
        self._wire_mousewheel(self.scroll)

        self.modules = []
        for cls in MODULE_CLASSES:
            mod = cls(self.scroll)
            mod.pack(fill="x", padx=t.PAD_LG, pady=(t.PAD_MD, 0))
            self.modules.append(mod)

        ctk.CTkFrame(self.scroll, fg_color=t.BG_SOFT, height=t.PAD_LG).pack(fill="x")

    def _wire_mousewheel(self, scrollable):
        """CTkScrollableFrame only binds wheel on its canvas; children steal the
        event. Forward all wheel events on this window to the canvas's yview.
        Linux uses Button-4/5; Windows/macOS use MouseWheel with delta."""
        canvas = scrollable._parent_canvas

        def on_wheel(event):
            if event.num == 4 or getattr(event, "delta", 0) > 0:
                canvas.yview_scroll(-3, "units")
            elif event.num == 5 or getattr(event, "delta", 0) < 0:
                canvas.yview_scroll(3, "units")

        self.bind_all("<MouseWheel>", on_wheel)
        self.bind_all("<Button-4>", on_wheel)
        self.bind_all("<Button-5>", on_wheel)

    def _refresh_modules(self):
        # Pre-compute the analytic reference so any module can read it,
        # regardless of mount order.
        s = self.sim_state
        s.analitico = calcular_analitico(s.lam, s.mu, s.theta)
        for mod in self.modules:
            mod.mount(s)

    def _run_simulation(self):
        if self._running:
            return
        self._running = True
        s = self.sim_state
        self.topbar.set_running(True, "Ejecutando simulación...")

        def worker():
            sim = simular(
                s.lam, s.mu, s.theta, s.t_sim,
                s.seed_mt, s.seed_lcg, s.seed_mrg1, s.seed_mrg2,
                t_warmup=s.t_warmup, trace_eventos=25,
            )
            replicas_result = None
            if s.run_replicas:
                replicas_result = ejecutar_replicas(
                    s.lam, s.mu, s.theta, s.t_sim, s.t_warmup,
                    n_replicas=10, base_seed=42, trace_eventos=0,
                )
            self.after(0, lambda: self._on_finish(sim, replicas_result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_finish(self, sim, replicas_result):
        self.sim_state.sim = sim
        self.sim_state.replicas_result = replicas_result
        self._running = False
        self.topbar.set_running(
            False,
            f"Listo: {sim['clientes_servidos']:,} clientes servidos, "
            f"{sim['total_eventos']:,} eventos.",
        )
        self._refresh_modules()
