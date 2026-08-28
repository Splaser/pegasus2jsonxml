import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from Converters.daijisho_exporter import export_daijisho


class DaijishoExporterTests(unittest.TestCase):
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

            report = json.loads(
                (platform_dir / "export_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["metadata_count"], 1)
            self.assertEqual(report["copied_count"], 1)
            self.assertEqual(report["missing_count"], 0)

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

    def test_reports_missing_and_does_not_overwrite_collision(self):
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

            platform_dir = export_daijisho(
                "disc", json_path, root / "Export_Daijisho", resource
            )
            self.assertEqual(
                (platform_dir / "box" / "game.jpg").read_bytes(), b"first"
            )
            report = json.loads(
                (platform_dir / "export_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["metadata_count"], 3)
            self.assertEqual(report["copied_count"], 1)
            self.assertEqual(report["missing_count"], 1)
            self.assertEqual(report["collision_count"], 1)


if __name__ == "__main__":
    unittest.main()
