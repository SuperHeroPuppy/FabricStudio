import customtkinter as ctk


def configure_theme() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")


COLORS = {
    "bg": "#111318",
    "panel": "#181b22",
    "panel_alt": "#20242d",
    "border": "#2b303b",
    "text": "#edf0f5",
    "muted": "#9da6b8",
    "accent": "#3b82f6",
}
