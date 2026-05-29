# texture_viewer.py
# developer: SuperHeroPuppy
# version: 1.0.0

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw

from core.data_store import COLORS


class TextureViewer(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])

        self.current_file: Path | None = None
        self.current_image: Image.Image | None = None
        self.render_image = None

        self.zoom = 16

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(
            self,
            fg_color=COLORS["panel"],
            corner_radius=0,
            height=42,
        )

        top.grid(row=0, column=0, sticky="ew")

        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            top,
            text="Zoom",
        ).grid(
            row=0,
            column=0,
            padx=(12, 6),
            pady=8,
        )

        self.zoom_slider = ctk.CTkSlider(
            top,
            from_=1,
            to=64,
            number_of_steps=63,
            command=self._on_zoom,
            width=180,
        )

        self.zoom_slider.set(self.zoom)

        self.zoom_slider.grid(
            row=0,
            column=1,
            sticky="w",
            pady=8,
        )

        self.size_label = ctk.CTkLabel(
            top,
            text="",
            text_color=COLORS["muted"],
        )

        self.size_label.grid(
            row=0,
            column=2,
            padx=(10, 14),
        )

        self.canvas = ctk.CTkCanvas(
            self,
            bg="#111318",
            highlightthickness=0,
        )

        self.canvas.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=10,
            pady=10,
        )

        self.canvas.bind("<Configure>", lambda e: self._render())

    def open_texture(self, path: Path):
        self.current_file = path

        image = Image.open(path).convert("RGBA")

        self.current_image = image

        self.size_label.configure(
            text=f"{image.width}x{image.height}"
        )

        self._render()
        
    def _on_zoom(self, value):
        self.zoom = int(value)
        self._render()

    def _render(self):
        if self.current_image is None:
            return

        self.canvas.delete("all")

        image = self.current_image

        scaled_width = image.width * self.zoom
        scaled_height = image.height * self.zoom

        resized = image.resize(
            (scaled_width, scaled_height),
            Image.Resampling.NEAREST,
        )

        checker = self._create_checkerboard(
            scaled_width,
            scaled_height,
            16,
        )

        checker.alpha_composite(resized)

        self.render_image = ImageTk.PhotoImage(checker)

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        x = max((canvas_width - scaled_width) // 2, 0)
        y = max((canvas_height - scaled_height) // 2, 0)

        self.canvas.create_image(
            x,
            y,
            anchor="nw",
            image=self.render_image,
        )

    def _create_checkerboard(self, width, height, size):
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        draw = ImageDraw.Draw(image)

        color_a = (42, 45, 54, 255)
        color_b = (32, 35, 42, 255)

        for y in range(0, height, size):
            for x in range(0, width, size):

                color = (
                    color_a
                    if (x // size + y // size) % 2 == 0
                    else color_b
                )

                draw.rectangle(
                    (x, y, x + size, y + size),
                    fill=color,
                )

        return image