from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, cast


@dataclass
class TransparencyConfig:
    default_alpha: int
    hover_alpha: int
    hover_enabled: bool

    def clone(self) -> TransparencyConfig:
        return TransparencyConfig(self.default_alpha, self.hover_alpha, self.hover_enabled)

    def to_payload(self) -> Dict[str, int | bool]:
        return {
            "default_alpha": self.default_alpha,
            "hover_alpha": self.hover_alpha,
            "hover_enabled": self.hover_enabled,
        }

    @staticmethod
    def _is_valid_alpha(value: object) -> bool:
        return isinstance(value, int) and 0 <= value <= 255

    @classmethod
    def from_payload(cls, payload: object) -> TransparencyConfig:
        if isinstance(payload, int):
            if cls._is_valid_alpha(payload):
                return cls(default_alpha=payload, hover_alpha=payload, hover_enabled=False)
            raise ValueError("alpha must be an integer between 0 and 255")

        if isinstance(payload, dict):
            default_candidate = payload.get("default_alpha", payload.get("alpha"))
            if not cls._is_valid_alpha(default_candidate):
                raise ValueError("default_alpha is invalid")
            default_alpha = cast(int, default_candidate)

            hover_candidate = payload.get("hover_alpha", default_alpha)
            hover_alpha = cast(int, hover_candidate) if cls._is_valid_alpha(hover_candidate) else default_alpha

            hover_enabled = bool(payload.get("hover_enabled", False))

            return cls(default_alpha=default_alpha, hover_alpha=hover_alpha, hover_enabled=hover_enabled)

        raise ValueError("Unsupported payload type")


class TransparencyStore:
    """Manage per-window transparency settings persisted in JSON."""

    def __init__(self, storage_path: Path | str) -> None:
        self._path = Path(storage_path)
        self._lock = threading.RLock()
        self._data: Dict[str, TransparencyConfig] = {}
        self._load()

    @staticmethod
    def _validate_key(window_key: str) -> None:
        if not isinstance(window_key, str) or window_key == "":
            raise ValueError("window_key must be a non-empty string")

    @staticmethod
    def _validate_alpha(alpha: int) -> None:
        if not TransparencyConfig._is_valid_alpha(alpha):
            raise ValueError("alpha must be an integer between 0 and 255")

    def _load(self) -> None:
        with self._lock:
            if not self._path.exists():
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._data = {}
                return

            try:
                raw = self._path.read_text(encoding="utf-8")
                if raw.strip() == "":
                    self._data = {}
                    return

                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise ValueError("Transparency settings file must contain a JSON object")

                parsed: Dict[str, TransparencyConfig] = {}
                for key, value in payload.items():
                    if not isinstance(key, str):
                        continue
                    try:
                        parsed[key] = TransparencyConfig.from_payload(value)
                    except ValueError:
                        continue
                self._data = parsed
            except (OSError, json.JSONDecodeError, ValueError):
                backup_path = self._path.with_suffix(self._path.suffix + ".bak")
                try:
                    if self._path.exists():
                        self._path.replace(backup_path)
                except OSError:
                    pass
                self._data = {}
                self._flush_locked()

    def _flush_locked(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        serializable = {key: config.to_payload() for key, config in self._data.items()}
        temp_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        temp_path.replace(self._path)

    def set_transparency(self, window_key: str, alpha: int) -> None:
        self.set_default_alpha(window_key, alpha)

    def set_default_alpha(self, window_key: str, alpha: int) -> None:
        self._validate_key(window_key)
        self._validate_alpha(alpha)
        with self._lock:
            config = self._data.get(window_key)
            if config is None:
                config = TransparencyConfig(default_alpha=alpha, hover_alpha=alpha, hover_enabled=False)
            else:
                config.default_alpha = alpha
                if not TransparencyConfig._is_valid_alpha(config.hover_alpha):
                    config.hover_alpha = alpha
            self._data[window_key] = config
            self._flush_locked()

    def set_hover_alpha(self, window_key: str, alpha: int) -> None:
        self._validate_key(window_key)
        self._validate_alpha(alpha)
        with self._lock:
            config = self._data.get(window_key)
            if config is None:
                config = TransparencyConfig(default_alpha=alpha, hover_alpha=alpha, hover_enabled=True)
            else:
                config.hover_alpha = alpha
            self._data[window_key] = config
            self._flush_locked()

    def set_hover_enabled(self, window_key: str, enabled: bool) -> None:
        self._validate_key(window_key)
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean value")
        with self._lock:
            config = self._data.get(window_key)
            if config is None:
                config = TransparencyConfig(default_alpha=255, hover_alpha=255, hover_enabled=enabled)
            else:
                config.hover_enabled = enabled
            self._data[window_key] = config
            self._flush_locked()

    def get_transparency(self, window_key: str) -> Optional[int]:
        config = self.get_config(window_key)
        return config.default_alpha if config else None

    def get_hover_transparency(self, window_key: str) -> Optional[int]:
        config = self.get_config(window_key)
        return config.hover_alpha if config else None

    def is_hover_enabled(self, window_key: str) -> bool:
        config = self.get_config(window_key)
        return config.hover_enabled if config else False

    def get_config(self, window_key: str) -> Optional[TransparencyConfig]:
        with self._lock:
            config = self._data.get(window_key)
            return config.clone() if config else None

    def remove(self, window_key: str) -> None:
        with self._lock:
            if window_key in self._data:
                del self._data[window_key]
                self._flush_locked()

    def all(self) -> Dict[str, TransparencyConfig]:
        with self._lock:
            return {key: config.clone() for key, config in self._data.items()}
