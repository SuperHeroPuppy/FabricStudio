"""Host/join controls for LAN and Internet workspace collaboration."""

from __future__ import annotations

import threading
from tkinter import messagebox

import customtkinter as ctk

from core.collaboration import DEFAULT_PORT, CollaborationSession
from core.data_store import COLORS
from core.public_tunnel import find_cloudflared, install_cloudflared
from ui.theme import themed_entry, theme_window
from ui.window_utils import show_on_top


class CollaborationWindow(ctk.CTkToplevel):
    def __init__(self, master, session: CollaborationSession) -> None:
        super().__init__(master)
        self.session = session
        self._last_active: bool | None = None
        self._busy = False
        self._join_result: str | None = None
        self._worker_status = ""
        self.title("Workspace Collaboration")
        self.geometry("740x650")
        self.minsize(680, 580)
        theme_window(self)
        show_on_top(self, master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.body = ctk.CTkFrame(self, fg_color=COLORS["bg"])
        self.body.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        self.body.grid_columnconfigure(0, weight=1)
        self.status_var = ctk.StringVar(value="")
        self._render()
        self.after(500, self._poll)

    def _render(self) -> None:
        for widget in self.body.winfo_children():
            widget.destroy()
        self._last_active = self.session.active
        if self.session.active:
            self._render_active()
        else:
            self._render_inactive()

    def _render_inactive(self) -> None:
        ctk.CTkLabel(
            self.body,
            text="Collaborate",
            font=("Segoe UI", 24, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(
            self.body,
            text=(
                "Use a private LAN session nearby, or create an Internet invitation for a friend "
                "on another network. Files sync on save; the latest saved version wins."
            ),
            text_color=COLORS["muted"],
            anchor="w",
            justify="left",
            wraplength=630,
        ).grid(row=1, column=0, sticky="ew", pady=(0, 16))

        panels = ctk.CTkFrame(self.body, fg_color="transparent")
        panels.grid(row=2, column=0, sticky="nsew")
        panels.grid_columnconfigure((0, 1), weight=1, uniform="collaboration")

        host_panel = ctk.CTkFrame(panels, fg_color=COLORS["panel"], corner_radius=10)
        host_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        host_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(host_panel, text="Host a session", font=("Segoe UI", 17, "bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 8)
        )
        self.host_name = themed_entry(host_panel, placeholder_text="Display name")
        self.host_name.insert(0, _default_name())
        self.host_name.grid(row=1, column=0, sticky="ew", padx=14, pady=6)
        self.host_port = themed_entry(host_panel, placeholder_text="Port")
        self.host_port.insert(0, str(DEFAULT_PORT))
        self.host_port.grid(row=2, column=0, sticky="ew", padx=14, pady=6)
        ctk.CTkButton(host_panel, text="Start LAN Hosting", command=self._host).grid(
            row=3, column=0, sticky="ew", padx=14, pady=(10, 14)
        )
        ctk.CTkLabel(
            host_panel,
            text="For a friend in another location:",
            text_color=COLORS["muted"],
            anchor="w",
        ).grid(row=4, column=0, sticky="ew", padx=14, pady=(4, 4))
        ctk.CTkButton(
            host_panel,
            text="Create Internet Invitation",
            command=self._host_internet,
        ).grid(row=5, column=0, sticky="ew", padx=14, pady=(4, 14))

        join_panel = ctk.CTkFrame(panels, fg_color=COLORS["panel"], corner_radius=10)
        join_panel.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        join_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(join_panel, text="Join a session", font=("Segoe UI", 17, "bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 8)
        )
        self.join_name = themed_entry(join_panel, placeholder_text="Display name")
        self.join_name.insert(0, _default_name())
        self.join_name.grid(row=1, column=0, sticky="ew", padx=14, pady=6)
        self.invite_url = themed_entry(join_panel, placeholder_text="Internet invitation link")
        self.invite_url.grid(row=2, column=0, sticky="ew", padx=14, pady=6)
        ctk.CTkButton(
            join_panel,
            text="Join Internet Session",
            command=self._join_internet,
        ).grid(row=3, column=0, sticky="ew", padx=14, pady=(6, 10))
        ctk.CTkLabel(
            join_panel,
            text="Or join directly by address:",
            text_color=COLORS["muted"],
            anchor="w",
        ).grid(row=4, column=0, sticky="ew", padx=14, pady=(4, 2))
        self.join_host = themed_entry(join_panel, placeholder_text="Host address")
        self.join_host.grid(row=5, column=0, sticky="ew", padx=14, pady=6)
        self.join_port = themed_entry(join_panel, placeholder_text="Port")
        self.join_port.insert(0, str(DEFAULT_PORT))
        self.join_port.grid(row=6, column=0, sticky="ew", padx=14, pady=6)
        self.join_code = themed_entry(join_panel, placeholder_text="6-digit code")
        self.join_code.grid(row=7, column=0, sticky="ew", padx=14, pady=6)
        self.join_button = ctk.CTkButton(join_panel, text="Join Directly", command=self._join)
        self.join_button.grid(row=8, column=0, sticky="ew", padx=14, pady=(10, 14))

        ctk.CTkLabel(
            self.body,
            textvariable=self.status_var,
            text_color=COLORS["muted"],
            anchor="w",
            wraplength=630,
        ).grid(row=3, column=0, sticky="ew", pady=(14, 0))

    def _render_active(self) -> None:
        ctk.CTkLabel(
            self.body,
            text="Collaboration active",
            font=("Segoe UI", 24, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        panel = ctk.CTkFrame(self.body, fg_color=COLORS["panel"], corner_radius=10)
        panel.grid(row=1, column=0, sticky="ew")
        panel.grid_columnconfigure(1, weight=1)

        values = [("Role", self.session.role.title())]
        if self.session.connection_mode == "internet":
            values.append(("Connection", "Internet tunnel"))
            if self.session.role == "host":
                values.append(("Invitation", self.session.public_invite_url))
            else:
                values.append(("Host", self.session.host))
        else:
            values.append(("Address", f"{self.session.host}:{self.session.port}"))
        if self.session.role == "host" and self.session.connection_mode == "direct":
            values.append(("Pairing code", self.session.code))

        for row, (label, value) in enumerate(values):
            ctk.CTkLabel(panel, text=label, text_color=COLORS["muted"], anchor="w").grid(
                row=row, column=0, sticky="w", padx=14, pady=10
            )
            ctk.CTkLabel(
                panel,
                text=value,
                font=("Consolas", 14, "bold") if label != "Role" else ("Segoe UI", 14, "bold"),
                anchor="w",
                justify="left",
                wraplength=500,
            ).grid(row=row, column=1, sticky="ew", padx=(8, 14), pady=10)

        if self.session.role == "host" and self.session.public_invite_url:
            ctk.CTkButton(
                panel,
                text="Copy Invitation Link",
                command=self._copy_invitation,
            ).grid(row=len(values), column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 14))

        self.peer_var = ctk.StringVar()
        ctk.CTkLabel(
            self.body,
            textvariable=self.status_var,
            text_color=COLORS["muted"],
            anchor="w",
            wraplength=630,
        ).grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ctk.CTkLabel(
            self.body,
            textvariable=self.peer_var,
            text_color=COLORS["muted"],
            anchor="w",
            wraplength=630,
        ).grid(row=3, column=0, sticky="ew", pady=(6, 6))
        ctk.CTkLabel(
            self.body,
            text=(
                "Collaboration synchronizes whole files and uses last-save-wins. Only share an Internet "
                "invitation with people you trust; cursor-level co-editing is not included yet."
            ),
            text_color=COLORS["muted"],
            anchor="w",
            justify="left",
            wraplength=630,
        ).grid(row=4, column=0, sticky="ew", pady=(0, 14))
        ctk.CTkButton(
            self.body,
            text="Stop Session",
            fg_color="#a33a3a",
            hover_color="#842f2f",
            command=self._stop,
        ).grid(row=5, column=0, sticky="ew")
        self._update_peers()

    def _host(self) -> None:
        try:
            port = int(self.host_port.get().strip())
            self.session.start_host(self.host_name.get(), port)
        except (OSError, RuntimeError, ValueError) as exc:
            self.status_var.set(f"Could not host: {exc}")
            return
        self.status_var.set("")
        self._render()

    def _host_internet(self) -> None:
        if self._busy:
            return
        connector = find_cloudflared()
        download_note = (
            " FabricStudio will download and SHA-256 verify the official cloudflared connector first."
            if connector is None
            else ""
        )
        if not messagebox.askyesno(
            "Create Internet Invitation",
            (
                "This creates a temporary public HTTPS endpoint through Cloudflare Quick Tunnels."
                f"{download_note}\n\nCloudflare describes Quick Tunnels as a development service with no uptime "
                "guarantee. Installing or using cloudflared is subject to Cloudflare's license, terms, "
                "and privacy policy. Continue?"
            ),
            parent=self,
        ):
            return

        name = self.host_name.get().strip()

        def action() -> None:
            executable = connector or install_cloudflared(self._set_worker_status)
            self._set_worker_status("Creating the public invitation...")
            self.session.start_internet_host(name, executable)

        self._run_async(action, "Preparing Internet hosting...")

    def _join(self) -> None:
        if self._busy:
            return
        if not messagebox.askyesno(
            "Join Collaboration",
            "The host's workspace files will be applied to this open workspace. Continue?",
            parent=self,
        ):
            return
        try:
            port = int(self.join_port.get().strip())
        except ValueError:
            self.status_var.set("Port must be a number.")
            return

        host = self.join_host.get().strip()
        code = self.join_code.get().strip()
        name = self.join_name.get().strip()
        self._run_async(
            lambda: self.session.join(host, port, code, name),
            "Connecting directly to host...",
        )

    def _join_internet(self) -> None:
        if self._busy or not self._confirm_join():
            return
        invite_url = self.invite_url.get().strip()
        name = self.join_name.get().strip()
        self._run_async(
            lambda: self.session.join_internet(invite_url, name),
            "Connecting through the Internet tunnel...",
        )

    def _confirm_join(self) -> bool:
        return messagebox.askyesno(
            "Join Collaboration",
            "The host's workspace files will be applied to this open workspace. Continue?",
            parent=self,
        )

    def _run_async(self, action, status: str) -> None:
        self._busy = True
        self._worker_status = status
        self.status_var.set(status)

        def worker() -> None:
            try:
                action()
            except (ConnectionError, OSError, RuntimeError, ValueError) as exc:
                self._join_result = str(exc)
                return
            self._join_result = ""

        threading.Thread(target=worker, name="fabricstudio-collaboration", daemon=True).start()

    def _set_worker_status(self, message: str) -> None:
        self._worker_status = message

    def _join_finished(self, error: str) -> None:
        if not self.winfo_exists():
            return
        self._busy = False
        if error:
            self.status_var.set(f"Collaboration failed: {error}")
            self._render()
            return
        self.status_var.set("")
        self._render()

    def _copy_invitation(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.session.public_invite_url)
        self.status_var.set("Invitation link copied.")

    def _stop(self) -> None:
        self.session.stop()
        self.status_var.set("Session stopped.")
        self._render()

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        if self._join_result is not None:
            result = self._join_result
            self._join_result = None
            self._join_finished(result)
        elif self._busy and self._worker_status:
            self.status_var.set(self._worker_status)
            self.after(500, self._poll)
            return
        if self._last_active != self.session.active:
            self._render()
        elif self.session.active:
            self._update_peers()
        self.after(500, self._poll)

    def _update_peers(self) -> None:
        if not hasattr(self, "peer_var"):
            return
        names = self.session.peer_names
        if names:
            self.peer_var.set(f"Connected ({len(names)}): {', '.join(names)}")
        else:
            self.peer_var.set("Waiting for collaborators...")


def _default_name() -> str:
    return "FabricStudio User"
