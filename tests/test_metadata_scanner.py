import tempfile
import unittest
from pathlib import Path

from Tools.export_to_json import _build_game_json
from Tools.metadata_scanner import parse_pegasus_metadata


class DefaultAssetsTests(unittest.TestCase):
    def parse_games(self, text: str):
        with tempfile.TemporaryDirectory() as tmp:
            metadata_path = Path(tmp) / "metadata.pegasus.txt"
            metadata_path.write_text(text, encoding="utf-8")
            _, games = parse_pegasus_metadata(str(metadata_path))
            return games

    def test_single_file_assets_use_rom_stem_instead_of_display_name(self):
        games = self.parse_games(
            "collection: PS2\n"
            "\n"
            "game: 忍者神龟3 变种噩梦\n"
            "file: Teenage Mutant Ninja Turtles 3 - Mutant Nightmare (USA).chd\n"
        )

        self.assertEqual(
            games[0]["assets"],
            {
                "box_front": (
                    "media/Teenage Mutant Ninja Turtles 3 - "
                    "Mutant Nightmare (USA)/boxfront.png"
                ),
                "logo": (
                    "media/Teenage Mutant Ninja Turtles 3 - "
                    "Mutant Nightmare (USA)/logo.png"
                ),
                "video": (
                    "media/Teenage Mutant Ninja Turtles 3 - "
                    "Mutant Nightmare (USA)/video.mp4"
                ),
            },
        )

    def test_multifile_assets_use_common_parent_directory(self):
        games = self.parse_games(
            "collection: Saturn\n"
            "\n"
            "game: Lunar 2\n"
            "files:\n"
            "  009/Lunar 2.m3u\n"
            "  009/Lunar 2 (Disc 1).chd\n"
            "  009/Lunar 2 (Disc 2).chd\n"
        )

        self.assertEqual(
            games[0]["assets"]["box_front"],
            "media/009/boxfront.png",
        )
        exported = _build_game_json(games[0], {}, "Saturn")
        self.assertEqual(
            exported["assets"]["box_front"],
            "media/009/boxfront.png",
        )

    def test_explicit_assets_are_preserved(self):
        games = self.parse_games(
            "collection: Arcade\n"
            "\n"
            "game: 恐龙新世纪 无限保险版\n"
            "file: 恐龙新世纪 无限保险版/dino.zip\n"
            "assets.box_front: media/恐龙新世纪 无限保险版/cover.jpg\n"
        )

        self.assertEqual(
            games[0]["assets"],
            {"box_front": "media/恐龙新世纪 无限保险版/cover.jpg"},
        )

    def test_multifile_explicit_assets_are_preserved(self):
        games = self.parse_games(
            "collection: PS1 HACK\n"
            "\n"
            "game: 北欧女神 HACK\n"
            "files:\n"
            "  北欧女神 HACK/Valkyrie Profile a.chd\n"
            "  北欧女神 HACK/Valkyrie Profile b.chd\n"
            "sort-by: 007\n"
            "developer: 北欧女神 HACK\n"
            "assets.box_front: media/北欧女神 HACK/boxfront.png\n"
            "assets.logo: media/北欧女神 HACK/logo.png\n"
            "assets.video: media/北欧女神 HACK/video.mp4\n"
        )

        game = games[0]
        self.assertEqual(
            game["roms"],
            [
                "北欧女神 HACK/Valkyrie Profile a.chd",
                "北欧女神 HACK/Valkyrie Profile b.chd",
            ],
        )
        self.assertEqual(
            game["assets"],
            {
                "box_front": "media/北欧女神 HACK/boxfront.png",
                "logo": "media/北欧女神 HACK/logo.png",
                "video": "media/北欧女神 HACK/video.mp4",
            },
        )
        exported = _build_game_json(game, {}, "PS1 HACK")
        self.assertEqual(exported["roms"], game["roms"])
        self.assertEqual(exported["assets"], game["assets"])


if __name__ == "__main__":
    unittest.main()
