"""Base module: a self-contained card with header, status pill, body, explanation.

Cada módulo de la pantalla principal hereda de `Module`. Define la "forma"
visual común (tarjeta con borde + encabezado con número + cuerpo) y el ciclo
de vida de re-render.

Ciclo de vida:
    needs_simulation: bool   — Si True, el módulo muestra un placeholder
                                hasta que el estado tenga un `sim` dict.
                                Los módulos teóricos (1, 7) lo dejan en False
                                porque pueden renderizar con sólo los
                                parámetros (no necesitan haber simulado).
    mount(state)             — llamado por la App cada vez que el estado
                                cambia; reconstruye el body desde cero.
    render(state)            — implementado por cada subclase; recibe el
                                estado ya con `sim`/`replicas_result` listos.
"""

import customtkinter as ctk

from .. import theme as t
from ..components import Card, ModuleHeader


class Module(Card):
    # Atributos de clase que las subclases sobrescriben — actúan como un
    # contrato declarativo (número, título y subtítulo del encabezado).
    number = 0
    title = "Module"
    subtitle = ""
    needs_simulation = False

    def __init__(self, master):
        # Tarjeta con borde fino: separa visualmente cada módulo del fondo
        # general (BG_SOFT) sin recurrir a sombras pesadas.
        super().__init__(master, fg_color=t.BG, border_width=1, border_color=t.BORDER)

        self.header = ModuleHeader(self, self.number, self.title, self.subtitle)
        self.header.pack(fill="x", padx=t.PAD_LG, pady=(t.PAD_LG, t.PAD_SM))

        # `body` es el contenedor que cada subclase llena en `render`. Se
        # destruye y reconstruye en cada montaje (ver `_clear_body`).
        self.body = ctk.CTkFrame(self, fg_color=t.BG)
        self.body.pack(fill="x", padx=t.PAD_LG, pady=(0, t.PAD_LG))

    def _clear_body(self):
        """Destruye recursivamente todo el contenido del body. Necesario
        antes de re-renderizar para no acumular widgets fantasma entre
        corridas."""
        for w in self.body.winfo_children():
            w.destroy()

    def _placeholder(self, text="Pendiente — pulsa Simular para calcular este bloque."):
        """Muestra un mensaje gris cuando el módulo aún no tiene datos para
        renderizar (típicamente antes de la primera corrida)."""
        self._clear_body()
        ctk.CTkLabel(
            self.body, text=text, font=t.font(t.SIZE_SMALL),
            text_color=t.TEXT_SUBTLE, anchor="w",
        ).pack(fill="x", pady=t.PAD_MD)

    def mount(self, state):
        """Punto de entrada del ciclo de re-render. La App lo llama tras
        cada simulación; decide entre placeholder y render real."""
        if self.needs_simulation and state.sim is None:
            self.header.pill.set("pending")
            self._placeholder()
            return
        self.header.pill.set("done")
        self._clear_body()
        self.render(state)

    def render(self, state):
        """Hook a implementar por subclases — recibe el estado completo y
        llena `self.body`. No debe llamar a `_clear_body` (`mount` lo hace)."""
        raise NotImplementedError
