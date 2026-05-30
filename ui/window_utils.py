# window_utils.py
# developer: SuperHeroPuppy
# version: 1.0.0

from __future__ import annotations


def show_on_top(window, master=None) -> None:
    parent = master or getattr(window, "master", None)

    if parent is not None:
        try:
            window.transient(parent.winfo_toplevel())
        except Exception:
            pass

    def clear_topmost() -> None:
        try:
            window.attributes("-topmost", False)
        except Exception:
            pass

    def raise_window() -> None:
        try:
            window.lift()
            window.focus_force()
            window.attributes("-topmost", True)
            window.after(250, clear_topmost)
        except Exception:
            pass

    window.after(0, raise_window)
