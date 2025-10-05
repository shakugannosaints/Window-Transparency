import json
import os
import tempfile
import unittest
from pathlib import Path

from transparency_tool.persistence import TransparencyStore


class TransparencyStoreTests(unittest.TestCase):
    def test_store_and_retrieve_transparency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TransparencyStore(Path(tmp) / "settings.json")
            self.assertIsNone(store.get_transparency("100"))

            store.set_transparency("100", 180)
            self.assertEqual(store.get_transparency("100"), 180)
            self.assertEqual(store.get_hover_transparency("100"), 180)
            self.assertFalse(store.is_hover_enabled("100"))

            # Ensure persistence survives new instance
            store2 = TransparencyStore(Path(tmp) / "settings.json")
            self.assertEqual(store2.get_transparency("100"), 180)
            self.assertEqual(store2.get_hover_transparency("100"), 180)
            self.assertFalse(store2.is_hover_enabled("100"))

    def test_remove_transparency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            store = TransparencyStore(path)
            store.set_transparency("200", 200)
            store.remove("200")
            self.assertIsNone(store.get_transparency("200"))

            size_after_remove = path.stat().st_size
            self.assertGreater(size_after_remove, 0)

    def test_invalid_inputs_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TransparencyStore(Path(tmp) / "settings.json")
            with self.assertRaises(ValueError):
                store.set_transparency("", 100)
            with self.assertRaises(ValueError):
                store.set_transparency("hwnd", -1)
            with self.assertRaises(ValueError):
                store.set_transparency("hwnd", 256)
            with self.assertRaises(ValueError):
                store.set_hover_alpha("hwnd", 300)
            with self.assertRaises(ValueError):
                store.set_hover_enabled("hwnd", None)  # type: ignore[arg-type]

    def test_corrupted_file_resets_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("not json", encoding="utf-8")

            store = TransparencyStore(path)
            self.assertEqual(store.all(), {})
            self.assertTrue(path.exists())
            self.assertTrue((path.with_suffix(".json.bak")).exists())

    def test_non_dict_payload_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            with path.open("w", encoding="utf-8") as handle:
                json.dump([1, 2, 3], handle)

            store = TransparencyStore(path)
            self.assertEqual(store.all(), {})

    def test_hover_configuration_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            store = TransparencyStore(path)
            store.set_transparency("300", 180)
            store.set_hover_alpha("300", 240)
            store.set_hover_enabled("300", True)

            config = store.get_config("300")
            self.assertIsNotNone(config)
            assert config is not None
            self.assertEqual(config.default_alpha, 180)
            self.assertEqual(config.hover_alpha, 240)
            self.assertTrue(config.hover_enabled)

            store2 = TransparencyStore(path)
            config2 = store2.get_config("300")
            self.assertIsNotNone(config2)
            assert config2 is not None
            self.assertEqual(config2.default_alpha, 180)
            self.assertEqual(config2.hover_alpha, 240)
            self.assertTrue(config2.hover_enabled)

    def test_all_returns_clones(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            store = TransparencyStore(path)
            store.set_transparency("400", 190)
            configs = store.all()
            self.assertIn("400", configs)
            cfg = configs["400"]
            cfg.default_alpha = 10
            # Re-fetch to ensure store not mutated
            self.assertEqual(store.get_transparency("400"), 190)


if __name__ == "__main__":
    unittest.main()
