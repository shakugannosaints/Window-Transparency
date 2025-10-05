from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x02
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
COLORREF = wintypes.DWORD
GA_ROOT = 2


user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, COLORREF, wintypes.BYTE, wintypes.DWORD]
user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
user32.GetLayeredWindowAttributes.argtypes = [wintypes.HWND, ctypes.POINTER(COLORREF), ctypes.POINTER(wintypes.BYTE), ctypes.POINTER(wintypes.DWORD)]
user32.GetLayeredWindowAttributes.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HWND
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

if hasattr(kernel32, "QueryFullProcessImageNameW"):
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
else:
    psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    psapi.GetModuleFileNameExW.restype = wintypes.DWORD

@dataclass(frozen=True)
class WindowInfo:
    handle: int
    title: str
    class_name: str
    process_id: int
    process_path: Optional[str]

    @property
    def identity_key(self) -> str:
        base = (self.process_path or "UNKNOWN").replace("|", "/")
        title = (self.title or "UNTITLED").replace("|", "/")
        return f"{base}|{self.class_name}|{title}"


def _get_window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value.strip()


def _get_class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def _get_process_path(pid: int) -> Optional[str]:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        return None
    try:
        if hasattr(kernel32, "QueryFullProcessImageNameW"):
            size = wintypes.DWORD(512)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return buffer.value
        else:
            size = wintypes.DWORD(512)
            buffer = ctypes.create_unicode_buffer(size.value)
            if psapi.GetModuleFileNameExW(handle, None, buffer, size.value):
                return buffer.value
        return None
    finally:
        kernel32.CloseHandle(handle)


def enumerate_windows(filter_fn: Optional[Callable[[WindowInfo], bool]] = None) -> List[WindowInfo]:
    windows: List[WindowInfo] = []

    def callback(hwnd: int, _: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.IsIconic(hwnd):
            return True

        title = _get_window_text(hwnd)
        if title == "":
            return True

        class_name = _get_class_name(hwnd)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_path = _get_process_path(pid.value)

        info = WindowInfo(handle=hwnd, title=title, class_name=class_name, process_id=pid.value, process_path=process_path)

        if filter_fn and not filter_fn(info):
            return True

        windows.append(info)
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    windows.sort(key=lambda w: w.title.lower())
    return windows


def set_window_transparency(hwnd: int, alpha: int) -> None:
    if not (0 <= alpha <= 255):
        raise ValueError("alpha must be between 0 and 255")
    if not user32.IsWindow(hwnd):
        raise ValueError(f"Invalid window handle: {hwnd}")

    current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if current_style & WS_EX_LAYERED == 0:
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, current_style | WS_EX_LAYERED)

    if not user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA):
        raise ctypes.WinError()


def get_window_transparency(hwnd: int) -> Optional[int]:
    if not user32.IsWindow(hwnd):
        raise ValueError(f"Invalid window handle: {hwnd}")

    alpha = wintypes.BYTE()
    flags = wintypes.DWORD()
    color_key = wintypes.DWORD()

    if user32.GetLayeredWindowAttributes(hwnd, ctypes.byref(color_key), ctypes.byref(alpha), ctypes.byref(flags)):
        if flags.value & LWA_ALPHA:
            return alpha.value
    return None


def get_cursor_position() -> Tuple[int, int]:
    point = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        raise ctypes.WinError()
    return point.x, point.y


def get_root_window_from_point(x: int, y: int) -> Optional[int]:
    point = wintypes.POINT()
    point.x = x
    point.y = y
    hwnd = user32.WindowFromPoint(point)
    if not hwnd:
        return None
    root = user32.GetAncestor(hwnd, GA_ROOT)
    root = root or hwnd
    return root if user32.IsWindow(root) else None


def remove_layered_style(hwnd: int) -> None:
    if not user32.IsWindow(hwnd):
        raise ValueError(f"Invalid window handle: {hwnd}")
    current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if current_style & WS_EX_LAYERED:
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, current_style & ~WS_EX_LAYERED)
