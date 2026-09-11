import json
import io
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path

from Converters.daijisho_exporter import export_daijisho
from main import daijisho_resource_dir


class DaijishoExporterTests(unittest.TestCase):
    def test_resolves_external_platform_media_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata = root / "Resource" / "MAME STG" / "metadata.pegasus.txt"
            external = root / "roms" / "MAME STG"
            external.mkdir(parents=True)

            self.assertEqual(
                daijisho_resource_dir(str(metadata), str(root / "roms")),
                external,
            )

    def test_exports_metadata_and_rom_named_box(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resource = root / "Resource" / "Arcade"
            source = resource / "media" / "prikura" / "boxFront.jpg"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"jpeg-data")

            json_path = root / "jsondb" / "arcade.json"
            json_path.parent.mkdir()
            json_path.write_text(
                json.dumps({
                    "games": [{
                        "game": "花小路大作战",
                        "file": "prikura.zip",
                        "sort_by": "0065",
                        "description": "第一行\\n第二行",
                        "developer": "Atlus",
                        "publisher": "Atlus",
                        "genre": "Action",
                        "players": "1-2",
                        "release": "1996-01-01",
                        # Defaults in jsondb may differ from the real file.
                        "assets": {"box_front": "media/prikura/boxfront.png"},
                    }]
                }),
                encoding="utf-8",
            )

            platform_dir = export_daijisho(
                "arcade", json_path, root / "Export_Daijisho", resource
            )

            self.assertEqual(
                (platform_dir / "box" / "prikura.jpg").read_bytes(),
                b"jpeg-data",
            )
            game = ET.parse(platform_dir / "gamelist.xml").getroot()[0]
            self.assertEqual(game.findtext("path"), "./prikura.zip")
            self.assertEqual(game.findtext("name"), "花小路大作战")
            self.assertEqual(game.findtext("desc"), "第一行\n第二行")
            self.assertEqual(game.findtext("developer"), "Atlus")
            self.assertEqual(game.findtext("publisher"), "Atlus")
            self.assertEqual(game.findtext("genre"), "Action")
            self.assertEqual(game.findtext("players"), "1-2")
            self.assertEqual(game.findtext("releasedate"), "19960101T000000")
            self.assertEqual(game.findtext("image"), "./box/prikura.jpg")

            self.assertFalse((platform_dir / "export_report.json").exists())

    def test_nested_rom_uses_explicit_media_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resource = root / "Resource" / "Hack"
            source = resource / "media" / "custom-folder" / "cover.jpg"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"nested-cover")

            json_path = root / "jsondb" / "hack.json"
            json_path.parent.mkdir()
            json_path.write_text(
                json.dumps({
                    "games": [{
                        "game": "Hack",
                        "file": "hack-folder/original.zip",
                        "assets": {
                            "box_front": "media/custom-folder/cover.jpg"
                        },
                    }]
                }),
                encoding="utf-8",
            )

            platform_dir = export_daijisho(
                "hack", json_path, root / "Export_Daijisho", resource
            )
            self.assertEqual(
                (platform_dir / "box" / "original.jpg").read_bytes(),
                b"nested-cover",
            )
            game = ET.parse(platform_dir / "gamelist.xml").getroot()[0]
            self.assertEqual(game.findtext("path"), "./hack-folder/original.zip")

    def test_multidisc_game_repeats_cover_and_metadata_for_every_rom(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resource = root / "Resource" / "PS1"
            source = resource / "media" / "Xenogears" / "boxFront.jpg"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"shared-cover")

            json_path = root / "jsondb" / "ps1.json"
            json_path.parent.mkdir()
            json_path.write_text(
                json.dumps({
                    "games": [{
                        "game": "异度装甲 汉化版",
                        "file": "Xenogears/Xenogears (Disc 1).chd",
                        "roms": [
                            "Xenogears/Xenogears (Disc 1).chd",
                            "Xenogears/Xenogears (Disc 2).chd",
                        ],
                        "description": "两张盘共用的说明",
                        "assets": {
                            "box_front": "media/Xenogears/boxfront.png"
                        },
                    }]
                }),
                encoding="utf-8",
            )

            platform_dir = export_daijisho(
                "ps1", json_path, root / "Export_Daijisho", resource
            )

            for disc in (1, 2):
                self.assertEqual(
                    (
                        platform_dir
                        / "box"
                        / f"Xenogears (Disc {disc}).jpg"
                    ).read_bytes(),
                    b"shared-cover",
                )

            games = ET.parse(platform_dir / "gamelist.xml").getroot()
            self.assertEqual(len(games), 2)
            self.assertEqual(
                [game.findtext("path") for game in games],
                [
                    "./Xenogears/Xenogears (Disc 1).chd",
                    "./Xenogears/Xenogears (Disc 2).chd",
                ],
            )
            self.assertEqual(
                [game.findtext("name") for game in games],
                ["异度装甲 汉化版", "异度装甲 汉化版"],
            )
            self.assertEqual(
                [game.findtext("desc") for game in games],
                ["两张盘共用的说明", "两张盘共用的说明"],
            )

    def test_logs_missing_and_does_not_overwrite_collision_or_export_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resource = root / "Resource" / "Disc"
            first = resource / "media" / "disc-a" / "boxfront.jpg"
            second = resource / "media" / "disc-b" / "boxfront.jpg"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_bytes(b"first")
            second.write_bytes(b"second")

            json_path = root / "jsondb" / "disc.json"
            json_path.parent.mkdir()
            json_path.write_text(
                json.dumps({
                    "games": [
                        {
                            "game": "A",
                            "file": "disc-a/game.chd",
                            "assets": {"box_front": "media/disc-a/boxfront.jpg"},
                        },
                        {
                            "game": "B",
                            "file": "disc-b/game.chd",
                            "assets": {"box_front": "media/disc-b/boxfront.jpg"},
                        },
                        {"game": "Missing", "file": "missing.zip"},
                    ]
                }),
                encoding="utf-8",
            )

            out_dir = root / "Export_Daijisho"
            platform_dir = out_dir / "disc"
            platform_dir.mkdir(parents=True)
            (out_dir / "disc.json").write_text("legacy", encoding="utf-8")
            (platform_dir / "export_report.json").write_text(
                "legacy", encoding="utf-8"
            )

            output = io.StringIO()
            with redirect_stdout(output):
                platform_dir = export_daijisho(
                    "disc", json_path, out_dir, resource
                )
            self.assertEqual(
                (platform_dir / "box" / "game.jpg").read_bytes(), b"first"
            )
            self.assertFalse((out_dir / "disc.json").exists())
            self.assertFalse((platform_dir / "export_report.json").exists())
            self.assertEqual(list(platform_dir.glob("*.json")), [])
            self.assertIn("metadata=3, covers=1, missing=1, collisions=1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
