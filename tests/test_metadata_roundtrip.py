import json
import tempfile
import unittest
from pathlib import Path

from Tools.export_to_json import export_platform_to_json
from Tools.json_to_metadata import json_to_metadata
from Tools.metadata_scanner import parse_pegasus_metadata


class MetadataRoundTripTests(unittest.TestCase):
    def test_extended_pegasus_fields_survive_jsondb_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "metadata.pegasus.txt"
            source.write_text(
                "\ufeffcollection: BennuGD\n"
                "shortname: sor\n"
                "extension: dat\n"
                "\n"
                "game: Streets of Rage Remake\n"
                "file: SORRv52/SorR.dat\n"
                "developer: Bomber Games\n"
                "publisher: Bomber Games\n"
                "release: 2020-01-01\n"
                "players: 1-2\n"
                "genre: Beat 'em up\n"
                "genres: Action, Beat 'em up\n"
                "x-scrapername: Streets of Rage Remake\n"
                "description: First line.\n"
                "A section heading:\n"
                "1. Arcade: Story mode.\n",
                encoding="utf-8",
            )

            json_path = export_platform_to_json(
                "bennugd",
                "BennuGD",
                str(source),
                out_root=str(root / "jsondb"),
            )
            payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
            self.assertEqual(payload["shortname"], "sor")
            self.assertEqual(payload["games"][0]["publisher"], "Bomber Games")
            self.assertEqual(payload["games"][0]["players"], "1-2")
            self.assertIn("1. Arcade: Story mode.", payload["games"][0]["description"])

            output = json_to_metadata(
                "bennugd",
                json_path,
                output_root=str(root / "canonical"),
            )
            header, games = parse_pegasus_metadata(output)
            self.assertEqual(header["collection"], "BennuGD")
            self.assertEqual(header["shortname"], "sor")
            self.assertEqual(games[0]["publisher"], "Bomber Games")
            self.assertEqual(games[0]["release"], "2020-01-01")
            self.assertEqual(games[0]["players"], "1-2")
            self.assertEqual(games[0]["genre"], "Beat 'em up")
            self.assertEqual(games[0]["genres"], "Action, Beat 'em up")
            self.assertEqual(
                games[0]["x_scrapername"],
                "Streets of Rage Remake",
            )
            self.assertIn("A section heading:", games[0]["description"])


if __name__ == "__main__":
    unittest.main()
