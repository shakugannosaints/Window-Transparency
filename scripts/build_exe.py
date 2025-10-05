from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

try:
    import PyInstaller.__main__  # type: ignore
except ModuleNotFoundError as exc:
    raise SystemExit(
        "PyInstaller 未安装。请先运行 'pip install -r requirements-build.txt' 或 'pip install pyinstaller' 再执行此脚本。"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "WindowTransparencyManager.spec"
ENTRY_POINT = PROJECT_ROOT / "main.py"
APP_NAME = "WindowTransparencyManager"


def clean_previous_builds() -> None:
    for path in (DIST_DIR, BUILD_DIR, SPEC_FILE):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def build() -> None:
    if not ENTRY_POINT.exists():
        raise SystemExit(f"未找到入口脚本: {ENTRY_POINT}")

    PyInstaller.__main__.run(
        [
            str(ENTRY_POINT),
            "--name",
            APP_NAME,
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--distpath",
            str(DIST_DIR),
            "--workpath",
            str(BUILD_DIR),
        ]
    )


if __name__ == "__main__":
    clean_flag = "--clean-only"
    if clean_flag in sys.argv:
        clean_previous_builds()
        sys.exit(0)

    if "--no-clean" not in sys.argv:
        clean_previous_builds()

    build()
