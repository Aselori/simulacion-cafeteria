"""Base module: a self-contained card with header, status pill, body, explanation.

Lifecycle:
    needs_simulation: bool   — if True, the module shows a placeholder until
                                the state has a `sim` dict.
    mount(state)             — called whenever state changes; rebuild the body.
"""

import customtkinter as ctk

from .. import theme as t
from ..components import Card, ModuleHeader


class Module(Card):
    number = 0
    title = "Module"
    subtitle = ""
    needs_simulation = False

    def __init__(self, master):
        super().__init__(master, fg_color=t.BG, border_width=1, border_color=t.BORDER)

        self.header = ModuleHeader(self, self.number, self.title, self.subtitle)
        self.header.pack(fill="x", padx=t.PAD_LG, pady=(t.PAD_LG, t.PAD_SM))

        self.body = ctk.CTkFrame(self, fg_color=t.BG)
        self.body.pack(fill="x", padx=t.PAD_LG, pady=(0, t.PAD_LG))

    def _clear_body(self):
        for w in self.body.winfo_children():
            w.destroy()

    def _placeholder(self, text="Pendiente — pulsa Simular para calcular este bloque."):
        self._clear_body()
        ctk.CTkLabel(
            self.body, text=text, font=t.font(t.SIZE_SMALL),
            text_color=t.TEXT_SUBTLE, anchor="w",
        ).pack(fill="x", pady=t.PAD_MD)

    def mount(self, state):
        if self.needs_simulation and state.sim is None:
            self.header.pill.set("pending")
            self._placeholder()
            return
        self.header.pill.set("done")
        self._clear_body()
        self.render(state)

    def render(self, state):
        raise NotImplementedError
