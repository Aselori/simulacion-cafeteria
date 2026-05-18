"""Reusable widgets: Card, FormField, ExplainBox, ModuleHeader, StatusPill."""

import customtkinter as ctk

from . import theme as t


class Card(ctk.CTkFrame):
    """Flat container with subtle background and rounded corners."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=kwargs.pop("fg_color", t.BG_SOFT),
            corner_radius=kwargs.pop("corner_radius", 10),
            border_width=kwargs.pop("border_width", 0),
            **kwargs,
        )


class FormField(ctk.CTkFrame):
    """Label + entry with optional helper text below."""

    def __init__(self, master, label, value="", helper="", width=120, on_change=None):
        super().__init__(master, fg_color="transparent")

        ctk.CTkLabel(
            self, text=label, font=t.font(t.SIZE_SMALL, "bold"),
            text_color=t.TEXT, anchor="w",
        ).pack(fill="x")

        self.var = ctk.StringVar(value=str(value))
        if on_change:
            self.var.trace_add("write", lambda *_: on_change())

        self.entry = ctk.CTkEntry(
            self, textvariable=self.var, width=width, height=34,
            fg_color=t.BG, border_color=t.BORDER, border_width=1,
            text_color=t.TEXT, font=t.mono(t.SIZE_MONO), corner_radius=6,
        )
        self.entry.pack(fill="x", pady=(4, 2))

        self.helper_lbl = ctk.CTkLabel(
            self, text=helper, font=t.font(t.SIZE_TINY - 1),
            text_color=t.TEXT_SUBTLE, anchor="w",
        )
        self.helper_lbl.pack(fill="x")

    def get(self):
        return self.var.get()

    def set_helper(self, text, color=None):
        self.helper_lbl.configure(text=text, text_color=color or t.TEXT_SUBTLE)


class CompactField(ctk.CTkFrame):
    """Inline label + entry on one line, for the top bar."""

    def __init__(self, master, label, value="", width=70, on_change=None):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(
            self, text=label, font=t.font(t.SIZE_BODY, "bold"),
            text_color=t.TEXT_MUTED,
        ).pack(side="left", padx=(0, 6))

        self.var = ctk.StringVar(value=str(value))
        if on_change:
            self.var.trace_add("write", lambda *_: on_change())

        self.entry = ctk.CTkEntry(
            self, textvariable=self.var, width=width, height=30,
            fg_color=t.BG, border_color=t.BORDER, border_width=1,
            text_color=t.TEXT, font=t.mono(t.SIZE_MONO), corner_radius=6,
            justify="center",
        )
        self.entry.pack(side="left")

    def get(self):
        return self.var.get()


class SectionTitle(ctk.CTkLabel):
    def __init__(self, master, text):
        super().__init__(
            master, text=text, font=t.font(t.SIZE_H2, "bold"),
            text_color=t.TEXT, anchor="w",
        )


class StatusPill(ctk.CTkLabel):
    """Small colored pill for module status: pendiente / computado / listo."""

    KINDS = {
        "pending":  ("Pendiente",  t.TEXT_SUBTLE, t.BG_NARRATOR),
        "live":     ("En vivo",    "white",       t.ACCENT),
        "done":     ("Ejecutado",  "white",       t.SUCCESS),
        "warn":     ("Atención",   "white",       t.WARN),
        "error":    ("Error",      "white",       t.DANGER),
    }

    def __init__(self, master, kind="pending", text=None):
        text_value, fg, bg = self.KINDS[kind]
        super().__init__(
            master, text=text or text_value,
            font=t.font(t.SIZE_TINY - 1, "bold"),
            text_color=fg, fg_color=bg, corner_radius=10,
            padx=10, pady=2, height=20,
        )
        self._kinds = dict(self.KINDS)

    def set(self, kind, text=None):
        text_value, fg, bg = self._kinds[kind]
        self.configure(text=text or text_value, text_color=fg, fg_color=bg)


class ModuleHeader(ctk.CTkFrame):
    """Header bar for a Module: number badge + title + subtitle + status pill."""

    def __init__(self, master, number, title, subtitle=""):
        super().__init__(master, fg_color="transparent")

        # Number badge (small circle)
        badge = ctk.CTkLabel(
            self, text=str(number),
            width=28, height=28, corner_radius=14,
            fg_color=t.ACCENT_SOFT, text_color=t.ACCENT,
            font=t.font(t.SIZE_SMALL, "bold"),
        )
        badge.pack(side="left", padx=(0, 12))

        # Title block
        txt = ctk.CTkFrame(self, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            txt, text=title, font=t.font(t.SIZE_H2, "bold"),
            text_color=t.TEXT, anchor="w",
        ).pack(fill="x")

        if subtitle:
            ctk.CTkLabel(
                txt, text=subtitle, font=t.font(t.SIZE_SMALL),
                text_color=t.TEXT_MUTED, anchor="w", justify="left",
                wraplength=820,
            ).pack(fill="x", pady=(1, 0))

        self.pill = StatusPill(self, "pending")
        self.pill.pack(side="right", padx=(t.PAD_MD, 0))


class ExplainBox(ctk.CTkFrame):
    """Inline explanation block: a tinted background with a label and body text.

    Lives inside a Module, next to the data it explains. Replaces the old
    bottom-of-window narrator.
    """

    def __init__(self, master, body="", title="Por qué"):
        super().__init__(master, fg_color=t.BG_NARRATOR, corner_radius=8)

        wrap = ctk.CTkFrame(self, fg_color=t.BG_NARRATOR)
        wrap.pack(fill="x", padx=t.PAD_MD, pady=t.PAD_SM)

        ctk.CTkLabel(
            wrap, text=title.upper(), font=t.font(t.SIZE_TINY - 1, "bold"),
            text_color=t.ACCENT, anchor="w",
        ).pack(fill="x")

        self.body_lbl = ctk.CTkLabel(
            wrap, text=body, font=t.font(t.SIZE_SMALL),
            text_color=t.TEXT, anchor="nw", justify="left",
            wraplength=860,
        )
        self.body_lbl.pack(fill="x", pady=(2, 0))

    def set(self, body):
        self.body_lbl.configure(text=body)


class Bullets(ctk.CTkFrame):
    """Bulleted list with hanging indentation.

    items: list of strings, or list of (label, body) tuples — in which case
    `label` is rendered bold/coloured and `body` follows on the same line.
    """

    def __init__(self, master, items, label_color=None, body_color=None,
                 mono_label=False, wraplength=820):
        super().__init__(master, fg_color="transparent")
        for it in items:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", pady=(0, 2))
            ctk.CTkLabel(
                row, text="•", font=t.font(t.SIZE_SMALL, "bold"),
                text_color=t.ACCENT, width=14, anchor="n",
            ).pack(side="left", padx=(0, 4))
            if isinstance(it, tuple):
                label, body = it
                ctk.CTkLabel(
                    row, text=label + " ",
                    font=(t.mono(t.SIZE_MONO_SMALL, "bold") if mono_label
                          else t.font(t.SIZE_SMALL, "bold")),
                    text_color=label_color or t.TEXT, anchor="nw",
                ).pack(side="left", anchor="n")
                ctk.CTkLabel(
                    row, text=body, font=t.font(t.SIZE_SMALL),
                    text_color=body_color or t.TEXT_MUTED, anchor="nw",
                    justify="left", wraplength=wraplength,
                ).pack(side="left", anchor="n", fill="x", expand=True)
            else:
                ctk.CTkLabel(
                    row, text=it, font=t.font(t.SIZE_SMALL),
                    text_color=body_color or t.TEXT, anchor="nw",
                    justify="left", wraplength=wraplength + 60,
                ).pack(side="left", anchor="n", fill="x", expand=True)


class TechBlock(Card):
    """Tinted collapsible subcard: clickable header + hidden-by-default content.

    Use as a context container — pack widgets inside `self.inner`.
    Helpers: `add_text`, `add_mono`, `add_subtitle`, `add_bullets`.
    """

    def __init__(self, master, title="Ficha técnica", collapsed=True):
        super().__init__(master, fg_color=t.BG_NARRATOR)

        self._collapsed = collapsed

        # Clickable header strip
        header = ctk.CTkFrame(self, fg_color=t.BG_NARRATOR, cursor="hand2")
        header.pack(fill="x", padx=t.PAD_MD, pady=(t.PAD_SM, 4))

        self._title_lbl = ctk.CTkLabel(
            header, text=title.upper(),
            font=t.font(t.SIZE_TINY - 1, "bold"),
            text_color=t.ACCENT, anchor="w", cursor="hand2",
        )
        self._title_lbl.pack(side="left", fill="x", expand=True)

        self._toggle_lbl = ctk.CTkLabel(
            header, text="[ ver ]",
            font=t.font(t.SIZE_TINY - 1, "bold"),
            text_color=t.ACCENT, cursor="hand2",
        )
        self._toggle_lbl.pack(side="right")

        for w in (header, self._title_lbl, self._toggle_lbl):
            w.bind("<Button-1>", lambda _e: self._toggle())

        self.inner = ctk.CTkFrame(self, fg_color=t.BG_NARRATOR)
        if not self._collapsed:
            self._show_inner()
        else:
            self._toggle_lbl.configure(text="[ ver ]")

    def _show_inner(self):
        self.inner.pack(fill="x", padx=t.PAD_MD, pady=(0, t.PAD_SM))
        self._toggle_lbl.configure(text="[ ocultar ]")

    def _toggle(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.inner.pack_forget()
            self._toggle_lbl.configure(text="[ ver ]")
        else:
            self._show_inner()

    def add_text(self, text, muted=False):
        ctk.CTkLabel(
            self.inner, text=text, font=t.font(t.SIZE_SMALL),
            text_color=t.TEXT_MUTED if muted else t.TEXT,
            anchor="w", justify="left", wraplength=860,
        ).pack(fill="x", pady=(0, 2))

    def add_mono(self, text):
        ctk.CTkLabel(
            self.inner, text=text, font=t.mono(t.SIZE_MONO_SMALL),
            text_color=t.TEXT, anchor="w", justify="left",
        ).pack(fill="x", pady=(0, 2))

    def add_subtitle(self, text):
        ctk.CTkLabel(
            self.inner, text=text, font=t.font(t.SIZE_SMALL, "bold"),
            text_color=t.TEXT, anchor="w",
        ).pack(fill="x", pady=(t.PAD_SM, 2))

    def add_bullets(self, items, mono_label=False):
        Bullets(self.inner, items, mono_label=mono_label).pack(fill="x", pady=(0, 2))
