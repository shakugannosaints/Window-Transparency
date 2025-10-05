from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

from .persistence import TransparencyConfig, TransparencyStore
from .windows_api import (
    WindowInfo,
    enumerate_windows,
    get_cursor_position,
    get_root_window_from_point,
    get_window_transparency,
    remove_layered_style,
    set_window_transparency,
)

APP_NAME = "WindowTransparencyManager"


def _default_storage_path() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        base = Path(appdata)
    else:
        base = Path.home()
    return base / APP_NAME / "settings.json"


class TransparencyApp:
    HOVER_POLL_MS = 150

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("窗口透明度管理器")
        self.root.geometry("420x520")
        self.root.resizable(False, False)

        storage_path = _default_storage_path()
        self.store = TransparencyStore(storage_path)

        self.window_cache: List[WindowInfo] = []
        self.selected_window: Optional[WindowInfo] = None
        self.default_alpha = tk.IntVar(value=255)
        self.hover_alpha = tk.IntVar(value=255)
        self.hover_enabled = tk.BooleanVar(value=False)
        self.saved_identities: List[str] = []
        self.applied_alphas: Dict[str, int] = {}

        self._build_ui()
        self._refresh_saved_list()
        self._auto_apply_saved_settings()
        self._start_hover_monitor()

    def _build_ui(self) -> None:
        header = ttk.Label(self.root, text="为不同窗口设置独立的透明度", font=("Microsoft YaHei", 12, "bold"))
        header.pack(anchor="w", padx=16, pady=8)

        select_frame = ttk.Frame(self.root)
        select_frame.pack(fill="x", padx=16, pady=8)

        self.window_label_var = tk.StringVar(value="未选择窗口")
        ttk.Label(select_frame, textvariable=self.window_label_var, width=40).pack(side="left", expand=True, fill="x")
        ttk.Button(select_frame, text="选择窗口", command=self._open_window_picker).pack(side="right")

        slider_frame = ttk.LabelFrame(self.root, text="透明度设置")
        slider_frame.pack(fill="x", padx=16, pady=12)

        ttk.Label(slider_frame, text="0 = 完全透明, 255 = 不透明").pack(anchor="w", pady=(0, 8))

        default_section = ttk.Frame(slider_frame)
        default_section.pack(fill="x", pady=(0, 12))
        ttk.Label(default_section, text="默认透明度").pack(anchor="w")
        self.default_scale = tk.Scale(
            default_section,
            from_=0,
            to=255,
            orient="horizontal",
            variable=self.default_alpha,
            command=self._on_default_alpha_change,
            showvalue=False,
            resolution=1,
        )
        self.default_scale.pack(fill="x")

        default_value_frame = ttk.Frame(default_section)
        default_value_frame.pack(fill="x", pady=4)
        ttk.Label(default_value_frame, text="当前默认值:").pack(side="left")
        self.default_value_label = ttk.Label(default_value_frame, text="255")
        self.default_value_label.pack(side="left")

        hover_section = ttk.Frame(slider_frame)
        hover_section.pack(fill="x")
        hover_toggle = ttk.Checkbutton(
            hover_section,
            text="启用鼠标悬停独立透明度",
            variable=self.hover_enabled,
            command=self._on_hover_toggle,
        )
        hover_toggle.pack(anchor="w")

        hover_controls = ttk.Frame(hover_section)
        hover_controls.pack(fill="x", pady=8)
        self.hover_scale = tk.Scale(
            hover_controls,
            from_=0,
            to=255,
            orient="horizontal",
            variable=self.hover_alpha,
            command=self._on_hover_alpha_change,
            showvalue=False,
            resolution=1,
        )
        self.hover_scale.pack(fill="x")

        hover_value_frame = ttk.Frame(hover_controls)
        hover_value_frame.pack(fill="x", pady=4)
        ttk.Label(hover_value_frame, text="悬停时的透明度:").pack(side="left")
        self.hover_value_label = ttk.Label(hover_value_frame, text="255")
        self.hover_value_label.pack(side="left")

        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", padx=16, pady=(8, 0))

        ttk.Button(button_frame, text="应用透明度", command=self._apply_transparency).pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="恢复默认", command=self._reset_transparency).pack(side="left")
        ttk.Button(self.root, text="刷新窗口列表", command=self._refresh_window_cache).pack(anchor="e", padx=16, pady=12)

        saved_frame = ttk.LabelFrame(self.root, text="已保存的窗口")
        saved_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.saved_list = tk.Listbox(saved_frame, height=8)
        self.saved_list.pack(fill="both", expand=True, padx=8, pady=8)
        self.saved_list.bind("<<ListboxSelect>>", self._on_saved_select)
        self.saved_list.bind("<Double-Button-1>", self._on_saved_activate)
        self.saved_list.bind("<Return>", self._on_saved_activate)

        self._update_hover_controls()

    def _auto_apply_saved_settings(self) -> None:
        own_pid = os.getpid()
        windows = enumerate_windows(lambda info: info.process_id != own_pid)
        self.window_cache = windows
        window_map = {info.identity_key: info for info in windows}
        for identity, config in self.store.all().items():
            info = window_map.get(identity)
            if not info:
                continue
            try:
                set_window_transparency(info.handle, config.default_alpha)
                self.applied_alphas[identity] = config.default_alpha
            except Exception:
                continue

    def _refresh_window_cache(self) -> None:
        own_pid = os.getpid()
        self.window_cache = enumerate_windows(lambda info: info.process_id != own_pid)
        if self.selected_window:
            self._update_selected_window(self.selected_window.handle)

    def _open_window_picker(self) -> None:
        self._refresh_window_cache()
        picker = tk.Toplevel(self.root)
        picker.title("选择窗口")
        picker.geometry("480x320")
        picker.transient(self.root)
        picker.grab_set()

        search_var = tk.StringVar()
        displayed_infos: List[WindowInfo] = []

        def update_list() -> None:
            listbox.delete(0, tk.END)
            displayed_infos.clear()
            keyword = search_var.get().lower()
            for info in self.window_cache:
                label = f"{info.title} ({info.process_path or '未知程序'})"
                if keyword and keyword not in label.lower():
                    continue
                listbox.insert(tk.END, label)
                displayed_infos.append(info)

        def on_select(event: tk.Event) -> None:
            selection = listbox.curselection()
            if not selection:
                return
            idx = selection[0]
            info = displayed_infos[idx]
            self._select_window(info)
            picker.destroy()

        ttk.Label(picker, text="搜索").pack(anchor="w", padx=12, pady=(12, 0))
        search_entry = ttk.Entry(picker, textvariable=search_var)
        search_entry.pack(fill="x", padx=12)
        listbox = tk.Listbox(picker)
        listbox.pack(fill="both", expand=True, padx=12, pady=12)
        listbox.bind("<Double-Button-1>", on_select)
        listbox.bind("<Return>", on_select)

        update_list()

        def on_search_change(*_: object) -> None:
            update_list()

        search_var.trace_add("write", on_search_change)
        search_entry.focus_set()

    def _select_window(self, info: WindowInfo) -> None:
        self.selected_window = info
        self.window_label_var.set(f"{info.title} ({info.process_path or '未知程序'})")

        config = self.store.get_config(info.identity_key)
        if config:
            self._apply_config_to_controls(config)
        else:
            current = get_window_transparency(info.handle)
            value = current if current is not None else 255
            self.default_alpha.set(value)
            self.hover_alpha.set(value)
            self.hover_enabled.set(False)
            self._sync_value_labels()
            self._update_hover_controls()

    def _apply_config_to_controls(self, config: TransparencyConfig) -> None:
        self.default_alpha.set(config.default_alpha)
        self.hover_alpha.set(config.hover_alpha)
        self.hover_enabled.set(config.hover_enabled)
        self._sync_value_labels()
        self._update_hover_controls()

    def _update_selected_window(self, handle: int) -> None:
        for info in self.window_cache:
            if info.handle == handle:
                self._select_window(info)
                return
        self.selected_window = None
        self.window_label_var.set("窗口已关闭")

    def _on_default_alpha_change(self, value: str) -> None:
        int_value = int(float(value))
        if not self.hover_enabled.get():
            self.hover_alpha.set(int_value)
        self._sync_value_labels()

    def _on_hover_alpha_change(self, value: str) -> None:
        self._sync_value_labels()

    def _sync_value_labels(self) -> None:
        self.default_value_label.config(text=str(self.default_alpha.get()))
        self.hover_value_label.config(text=str(self.hover_alpha.get()))

    def _on_hover_toggle(self) -> None:
        if not self.hover_enabled.get():
            self.hover_alpha.set(self.default_alpha.get())
        self._update_hover_controls()
        self._sync_value_labels()

    def _update_hover_controls(self) -> None:
        state = "normal" if self.hover_enabled.get() else "disabled"
        self.hover_scale.configure(state=state)

    def _apply_transparency(self) -> None:
        if not self.selected_window:
            messagebox.showinfo("提示", "请先选择一个窗口。")
            return

        identity = self.selected_window.identity_key
        default_alpha = int(self.default_alpha.get())
        hover_alpha = int(self.hover_alpha.get())
        hover_enabled = bool(self.hover_enabled.get())

        try:
            target_alpha = hover_alpha if hover_enabled and self._is_window_hovered(self.selected_window.handle) else default_alpha
            set_window_transparency(self.selected_window.handle, target_alpha)
            self.store.set_default_alpha(identity, default_alpha)
            self.store.set_hover_alpha(identity, hover_alpha)
            self.store.set_hover_enabled(identity, hover_enabled)
            self.applied_alphas[identity] = target_alpha
            self._refresh_saved_list()
        except Exception as exc:  # pragma: no cover - interactive error feedback
            messagebox.showerror("错误", f"无法设置透明度: {exc}")

    def _reset_transparency(self) -> None:
        if not self.selected_window:
            messagebox.showinfo("提示", "请先选择一个窗口。")
            return

        identity = self.selected_window.identity_key
        try:
            remove_layered_style(self.selected_window.handle)
        except Exception:
            pass

        self.store.remove(identity)
        self.applied_alphas.pop(identity, None)
        self.default_alpha.set(255)
        self.hover_alpha.set(255)
        self.hover_enabled.set(False)
        self._sync_value_labels()
        self._update_hover_controls()
        self._refresh_saved_list()

    def _refresh_saved_list(self) -> None:
        if not hasattr(self, "saved_list"):
            return

        saved_entries = self.store.all()
        self.saved_list.delete(0, tk.END)
        self.saved_identities.clear()

        for identity, config in sorted(saved_entries.items(), key=lambda item: item[0].lower()):
            label = self._format_saved_label(identity, config)
            self.saved_list.insert(tk.END, label)
            self.saved_identities.append(identity)

    def _format_saved_label(self, identity: str, config: TransparencyConfig) -> str:
        path, class_name, title = self._split_identity(identity)
        exe_name = Path(path).name if path not in ("", "UNKNOWN") else "未知程序"
        hover_part = f"悬停={config.hover_alpha}" if config.hover_enabled else "悬停=未启用"
        return f"{title} [{exe_name}] 默认={config.default_alpha} / {hover_part} ({class_name})"

    @staticmethod
    def _split_identity(identity: str) -> tuple[str, str, str]:
        parts = identity.split("|", 2)
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
        if len(parts) == 2:
            return parts[0], parts[1], ""
        if len(parts) == 1:
            return parts[0], "", ""
        return "", "", ""

    def _on_saved_select(self, _: tk.Event) -> None:
        self._handle_saved_selection()

    def _on_saved_activate(self, _: tk.Event) -> None:
        self._handle_saved_selection()

    def _handle_saved_selection(self) -> None:
        selection = self.saved_list.curselection()
        if not selection:
            return
        identity = self.saved_identities[selection[0]]
        self._select_saved_identity(identity)

    def _select_saved_identity(self, identity: str) -> None:
        own_pid = os.getpid()
        current_windows = enumerate_windows(lambda info: info.process_id != own_pid)
        window_map = {info.identity_key: info for info in current_windows}
        info = window_map.get(identity)
        if info:
            self.window_cache = current_windows
            self._select_window(info)
            return

        config = self.store.get_config(identity)
        if config:
            _, _, title = self._split_identity(identity)
            self.window_label_var.set(f"{title} (窗口未打开)")
            self.selected_window = None
            self._apply_config_to_controls(config)
        else:
            messagebox.showinfo("提示", "未找到对应窗口配置。")

    def _start_hover_monitor(self) -> None:
        self.root.after(self.HOVER_POLL_MS, self._hover_monitor_tick)

    def _hover_monitor_tick(self) -> None:
        try:
            self._apply_hover_states()
        finally:
            self.root.after(self.HOVER_POLL_MS, self._hover_monitor_tick)

    def _apply_hover_states(self) -> None:
        settings = self.store.all()
        if not settings:
            self.applied_alphas.clear()
            return

        own_pid = os.getpid()
        windows = enumerate_windows(lambda info: info.process_id != own_pid)
        window_map = {info.identity_key: info for info in windows}

        hovered_root = None
        if any(config.hover_enabled for config in settings.values()):
            try:
                cursor_x, cursor_y = get_cursor_position()
                hovered_root = get_root_window_from_point(cursor_x, cursor_y)
            except OSError:
                hovered_root = None

        for identity, config in settings.items():
            info = window_map.get(identity)
            if not info:
                self.applied_alphas.pop(identity, None)
                continue

            target_alpha = config.default_alpha
            if config.hover_enabled and hovered_root and info.handle == hovered_root:
                target_alpha = config.hover_alpha

            previous_alpha = self.applied_alphas.get(identity)
            if previous_alpha == target_alpha:
                continue

            try:
                set_window_transparency(info.handle, target_alpha)
                self.applied_alphas[identity] = target_alpha
            except Exception:
                continue

    def _is_window_hovered(self, hwnd: int) -> bool:
        try:
            cursor_x, cursor_y = get_cursor_position()
            hovered_root = get_root_window_from_point(cursor_x, cursor_y)
            return hovered_root == hwnd
        except OSError:
            return False


def main() -> int:
    root = tk.Tk()
    app = TransparencyApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
