"""Visual language: colors, fonts, spacing.

Single source of truth — change here, propagates everywhere.
"""

import customtkinter as ctk

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# Palette — light, minimal, single accent
BG = "#ffffff"
BG_SOFT = "#f7f8fa"
BG_NARRATOR = "#f1f3f7"
BORDER = "#e5e7eb"
TEXT = "#0f172a"
TEXT_MUTED = "#64748b"
TEXT_SUBTLE = "#94a3b8"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#2563eb"
ACCENT_SOFT = "#dbeafe"
SUCCESS = "#10b981"
DANGER = "#ef4444"
WARN = "#f59e0b"

# Spacing
PAD_XS = 4
PAD_SM = 8
PAD_MD = 16
PAD_LG = 24
PAD_XL = 32


# Family names are resolved by Tk/Xft at draw time. Requires Tk built with Xft
# (system /usr/bin/python3 on Arch with `tk` package, not bundled mise Tk).
# Noto Sans: humanist, slightly heavier than Adwaita, very legible at small sizes,
# full Greek/math coverage.
SANS_FAMILY = "Noto Sans"
MONO_FAMILY = "JetBrainsMono Nerd Font"

# Body size bumped to 13 (was 12) for less strain. Hierarchy is multiplicative
# rather than fixed: use these constants so changing one cascades.
SIZE_BODY = 13
SIZE_SMALL = 12
SIZE_TINY = 11
SIZE_H1 = 23
SIZE_H2 = 15
SIZE_MONO = 12
SIZE_MONO_SMALL = 11


def font(size=SIZE_BODY, weight="normal"):
    return (SANS_FAMILY, size, weight) if weight != "normal" else (SANS_FAMILY, size)


def mono(size=SIZE_MONO, weight="normal"):
    return (MONO_FAMILY, size, weight) if weight != "normal" else (MONO_FAMILY, size)
