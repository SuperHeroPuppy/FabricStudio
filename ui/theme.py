# theme.py
# developer: SuperHeroPuppy
# version: 1.0.0

from __future__ import annotations

import ctypes
import sys

import customtkinter as ctk

from core.data_store import COLORS


ENTRY_STYLE = {
    "fg_color": COLORS["panel_alt"],
    "border_color": COLORS["border"],
    "text_color": COLORS["text"],
    "placeholder_text_color": COLORS["muted"],
    "corner_radius": 6,
    "border_width": 1,
}

COMBO_BOX_STYLE = {
    "fg_color": COLORS["panel_alt"],
    "border_color": COLORS["border"],
    "button_color": COLORS["accent"],
    "button_hover_color": "#2563eb",
    "dropdown_fg_color": COLORS["panel_alt"],
    "dropdown_hover_color": COLORS["accent"],
    "dropdown_text_color": COLORS["text"],
    "text_color": COLORS["text"],
    "text_color_disabled": COLORS["muted"],
    "corner_radius": 6,
    "border_width": 1,
}


def themed_entry(master, **kwargs) -> ctk.CTkEntry:
    options = ENTRY_STYLE | kwargs
    return ctk.CTkEntry(master, **options)


def themed_combo_box(master, **kwargs) -> ctk.CTkComboBox:
    options = COMBO_BOX_STYLE | kwargs
    return ctk.CTkComboBox(master, **options)


def theme_menu(menu) -> None:
    menu.configure(
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        activebackground=COLORS["accent"],
        activeforeground=COLORS["text"],
        disabledforeground=COLORS["muted"],
        borderwidth=0,
        activeborderwidth=0,
        relief="flat",
    )


def theme_window(window) -> None:
    window.configure(fg_color=COLORS["bg"])
    window.after(0, lambda: _theme_windows_title_bar(window))
    window.after(200, lambda: _theme_windows_title_bar(window))


def _theme_windows_title_bar(window) -> None:
    if sys.platform != "win32":
        return

    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        value = ctypes.c_int(1)

        for attribute in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )

        caption_color = ctypes.c_int(_colorref(COLORS["panel"]))
        text_color = ctypes.c_int(_colorref(COLORS["text"]))

        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            35,
            ctypes.byref(caption_color),
            ctypes.sizeof(caption_color),
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            36,
            ctypes.byref(text_color),
            ctypes.sizeof(text_color),
        )
    except Exception:
        pass


def _colorref(hex_color: str) -> int:
    value = hex_color.lstrip("#")
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    return red | (green << 8) | (blue << 16)


def apply_tk_theme(root) -> None:
    options = {
        "*Menu.background": COLORS["panel_alt"],
        "*Menu.foreground": COLORS["text"],
        "*Menu.activeBackground": COLORS["accent"],
        "*Menu.activeForeground": COLORS["text"],
        "*Menu.disabledForeground": COLORS["muted"],
        "*Menu.borderWidth": 0,
        "*Menu.activeBorderWidth": 0,
        "*Menu.relief": "flat",
        "*background": COLORS["bg"],
        "*foreground": COLORS["text"],
        "*selectBackground": COLORS["accent"],
        "*selectForeground": COLORS["text"],
    }

    for key, value in options.items():
        root.option_add(key, value)
