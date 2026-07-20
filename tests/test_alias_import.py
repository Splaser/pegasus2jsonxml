import json
import tempfile
import unittest
from pathlib import Path

from pegasus_alias_rewrite import rewrite_json_obj
from Tools.export_to_json import export_platform_to_json


class AliasImportTests(unittest.TestCase):
    def export(self, launch_core: str, game_core: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata_path = root / "metadata.pegasus.txt"
            metadata_path.write_text(
                "collection: TEST\n"
                "launch:\n"
                "  am start -n "
                "com.retroarch.aarch64/"
                "com.retroarch.browser.retroactivity.RetroActivityFuture\n"
                "  -e ROM {file.path}\n"
                f"  -e LIBRETRO {launch_core}\n"
                "\n"
                "game: Test Game\n"
                "file: Test Game.zip\n"
                "launch:\n"
                "  am start -n "
                "com.retroarch.aarch64/"
                "com.retroarch.browser.retroactivity.RetroActivityFuture\n"
                "  -e ROM {file.path}\n"
                f"  -e LIBRETRO {game_core}\n",
                encoding="utf-8",
            )

            output_path = export_platform_to_json(
                "test",
                "TEST",
                str(metadata_path),
                out_root=str(root / "jsondb"),
            )
            return json.loads(Path(output_path).read_text(encoding="utf-8"))

    def test_import_rewrites_core_paths_and_keeps_helper_fields_aligned(self):
        payload = self.export(
            "/data/data/com.retroarch.aarch64/cores/"
            "snes9x_libretro_android.so",
            "/data/data/com.retroarch.aarch64/cores/"
            "mame_libretro_android.so",
        )

        self.assertIn("-e LIBRETRO snes9x", payload["launch_block"])
        self.assertIn('-e ROM "{file.path}"', payload["launch_block"])
        self.assertEqual(payload["default_core"], "snes9x")
        self.assertEqual(payload["default_launch_info"]["core"], "snes9x")
        self.assertEqual(
            payload["default_launch_info"]["raw"],
            payload["launch_block"],
        )

        game = payload["games"][0]
        self.assertIn("-e LIBRETRO mamearcade", game["launch_override"])
        self.assertEqual(game["core_override"], "mamearcade")
        self.assertEqual(game["launch_info"]["core"], "mamearcade")
        self.assertEqual(game["launch_info"]["raw"], game["launch_override"])
        self.assertFalse(rewrite_json_obj(payload).changed)

    def test_import_populates_core_fields_when_source_already_uses_aliases(self):
        payload = self.export("fbneo", "mame2003_plus")

        self.assertEqual(payload["default_core"], "fbneo")
        self.assertEqual(payload["default_launch_info"]["core"], "fbneo")
        game = payload["games"][0]
        self.assertEqual(game["core_override"], "mame2003_plus")
        self.assertEqual(game["launch_info"]["core"], "mame2003_plus")
        self.assertFalse(rewrite_json_obj(payload).changed)


if __name__ == "__main__":
    unittest.main()
