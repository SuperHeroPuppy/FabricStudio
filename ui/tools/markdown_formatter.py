from __future__ import annotations

import os
import re
from pathlib import Path

import customtkinter as ctk


FILE_LINK_PATTERN = re.compile(r"^\[([^\]]+)\]\((?:file:)?([^)]+)\)$")
BRACKET_FILE_PATTERN = re.compile(r"^\[\[([^\]]+)\]\]$")


def clear_content(parent) -> None:
    for widget in parent.winfo_children():
        widget.destroy()


def render_markdown(
    parent,
    content: str,
    colors: dict[str, str],
    wraplength: int = 760,
    base_path: Path | None = None,
) -> None:
    clear_content(parent)

    lines = content.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            language = stripped[3:].strip()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            render_code_block(parent, "\n".join(code_lines), colors, language)
            index += 1
            continue

        if not stripped:
            ctk.CTkLabel(parent, text="", height=8).pack(anchor="w")
            index += 1
            continue

        if stripped.startswith("# "):
            ctk.CTkLabel(
                parent,
                text=stripped[2:],
                font=("Segoe UI", 30, "bold"),
                text_color="#ffffff",
            ).pack(anchor="w", padx=20, pady=(16, 8))
            index += 1
            continue

        if stripped.startswith("## "):
            ctk.CTkLabel(
                parent,
                text=stripped[3:],
                font=("Segoe UI", 22, "bold"),
                text_color="#7aa2ff",
            ).pack(anchor="w", padx=20, pady=(14, 6))
            index += 1
            continue

        if stripped.startswith("### "):
            ctk.CTkLabel(
                parent,
                text=stripped[4:],
                font=("Segoe UI", 18, "bold"),
                text_color="#cccccc",
            ).pack(anchor="w", padx=22, pady=(10, 4))
            index += 1
            continue

        if stripped == "---":
            divider = ctk.CTkFrame(
                parent,
                height=2,
                fg_color=colors["border"],
                corner_radius=999,
            )
            divider.pack(fill="x", padx=20, pady=(14, 14))
            index += 1
            continue

        if stripped.startswith("- "):
            reference = parse_file_reference(stripped[2:])
            if reference:
                render_file_reference(parent, reference, colors, base_path, bullet=True)
                index += 1
                continue

            ctk.CTkLabel(
                parent,
                text=f"* {stripped[2:]}",
                font=("Segoe UI", 14),
                justify="left",
                wraplength=wraplength,
                anchor="w",
            ).pack(anchor="w", padx=34, pady=2)
            index += 1
            continue

        reference = parse_file_reference(stripped)
        if reference:
            render_file_reference(parent, reference, colors, base_path)
            index += 1
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
        index += 1


def render_code_block(parent, code: str, colors: dict[str, str], language: str = "") -> None:
    frame = ctk.CTkFrame(
        parent,
        fg_color=colors["panel_alt"],
        border_width=1,
        border_color=colors["border"],
        corner_radius=6,
    )
    frame.pack(fill="x", padx=20, pady=(8, 10))
    frame.grid_columnconfigure(0, weight=1)

    if language:
        ctk.CTkLabel(
            frame,
            text=language,
            text_color=colors["muted"],
            font=("Segoe UI", 12),
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 0))

    line_count = max(1, min(18, code.count("\n") + 1))
    textbox = ctk.CTkTextbox(
        frame,
        height=max(54, line_count * 20 + 16),
        fg_color=colors["panel_alt"],
        text_color=colors["text"],
        border_width=0,
        wrap="none",
        font=("Consolas", 13),
    )
    textbox.grid(row=1, column=0, sticky="ew", padx=8, pady=(6, 8))
    textbox.insert("1.0", code or " ")
    textbox.configure(state="disabled")


def render_file_reference(
    parent,
    reference: tuple[str, str],
    colors: dict[str, str],
    base_path: Path | None = None,
    bullet: bool = False,
) -> None:
    label, target = reference
    resolved_path = resolve_file_reference(target, base_path)
    exists = resolved_path.exists()

    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=34 if bullet else 22, pady=3)
    row.grid_columnconfigure(1, weight=1)

    if bullet:
        ctk.CTkLabel(row, text="*", width=14).grid(row=0, column=0, sticky="w")

    button = ctk.CTkButton(
        row,
        text=label,
        height=30,
        anchor="w",
        fg_color=colors["panel_alt"],
        hover_color=colors["accent"],
        command=lambda path=resolved_path: open_file_reference(path),
    )
    button.grid(row=0, column=1, sticky="ew", padx=(0 if not bullet else 6, 8))

    ctk.CTkLabel(
        row,
        text="found" if exists else "missing",
        width=58,
        text_color=colors["muted"] if exists else "#e08b8b",
        font=("Segoe UI", 12),
    ).grid(row=0, column=2, sticky="e")


def parse_file_reference(text: str) -> tuple[str, str] | None:
    if text.startswith("file:"):
        target = text[5:].strip()
        return (target, target) if target else None

    bracket_match = BRACKET_FILE_PATTERN.fullmatch(text)
    if bracket_match:
        target = bracket_match.group(1).strip()
        return (target, target) if target else None

    link_match = FILE_LINK_PATTERN.fullmatch(text)
    if link_match:
        label = link_match.group(1).strip()
        target = link_match.group(2).strip()
        return (label or target, target) if target else None

    return None


def resolve_file_reference(target: str, base_path: Path | None = None) -> Path:
    path = Path(target).expanduser()
    if path.is_absolute():
        return path
    return (base_path or Path.cwd()) / path


def open_file_reference(path: Path) -> None:
    if not path.exists():
        return
    os.startfile(path)
