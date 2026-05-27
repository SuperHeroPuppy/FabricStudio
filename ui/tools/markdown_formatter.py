from __future__ import annotations

import customtkinter as ctk


def clear_content(parent) -> None:
    for widget in parent.winfo_children():
        widget.destroy()


def render_markdown(parent, content: str, colors: dict[str, str], wraplength: int = 760) -> None:
    clear_content(parent)

    for line in content.splitlines():
        stripped = line.strip()

        if not stripped:
            ctk.CTkLabel(parent, text="", height=8).pack(anchor="w")
            continue

        if stripped.startswith("# "):
            ctk.CTkLabel(
                parent,
                text=stripped[2:],
                font=("Segoe UI", 30, "bold"),
                text_color="#ffffff",
            ).pack(anchor="w", padx=20, pady=(16, 8))
            continue

        if stripped.startswith("## "):
            ctk.CTkLabel(
                parent,
                text=stripped[3:],
                font=("Segoe UI", 22, "bold"),
                text_color="#7aa2ff",
            ).pack(anchor="w", padx=20, pady=(14, 6))
            continue

        if stripped.startswith("### "):
            ctk.CTkLabel(
                parent,
                text=stripped[4:],
                font=("Segoe UI", 18, "bold"),
                text_color="#cccccc",
            ).pack(anchor="w", padx=22, pady=(10, 4))
            continue

        if stripped == "---":
            divider = ctk.CTkFrame(
                parent,
                height=2,
                fg_color=colors["border"],
                corner_radius=999,
            )
            divider.pack(fill="x", padx=20, pady=(14, 14))
            continue

        if stripped.startswith("- "):
            ctk.CTkLabel(
                parent,
                text=f"* {stripped[2:]}",
                font=("Segoe UI", 14),
                justify="left",
                wraplength=wraplength,
                anchor="w",
            ).pack(anchor="w", padx=34, pady=2)
            continue

        ctk.CTkLabel(
            parent,
            text=stripped,
            font=("Segoe UI", 14),
            justify="left",
            wraplength=wraplength,
            anchor="w",
            text_color="#d0d0d0",
        ).pack(anchor="w", padx=22, pady=2)
