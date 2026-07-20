import tempfile
import unittest
from pathlib import Path

from write_metadata_to_tf import build_plan, copy_with_backup


METADATA = (
    "collection: Test\n"
    "extension: zip\n"
    "\n"
    "game: Test Game\n"
    "file: Test Game.zip\n"
)


class WriteMetadataToTfTests(unittest.TestCase):
    def make_source(self, root: Path, platform: str) -> Path:
        platform_dir = root / platform
        platform_dir.mkdir(parents=True)
        metadata = platform_dir / "metadata.pegasus.txt"
        metadata.write_text(METADATA, encoding="utf-8")
        return metadata

    def test_only_existing_folder_with_rom_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_root = root / "canonical"
            tf_root = root / "roms"
            tf_root.mkdir()

            self.make_source(src_root, "with_rom")
            self.make_source(src_root, "empty")
            self.make_source(src_root, "media_only")
            self.make_source(src_root, "missing")

            with_rom = tf_root / "with rom"
            with_rom.mkdir()
            (with_rom / "Test Game.zip").write_bytes(b"rom")

            (tf_root / "empty").mkdir()

            media_only = tf_root / "media only"
            (media_only / "media" / "Test Game").mkdir(parents=True)
            (media_only / "media" / "Test Game" / "boxfront.png").write_bytes(
                b"image"
            )

            plans = {plan.key: plan for plan in build_plan(src_root, tf_root)}

            self.assertEqual(plans["withrom"].status, "READY")
            self.assertEqual(plans["withrom"].rom_files_found, 1)
            self.assertEqual(plans["empty"].status, "NO_ROMS_IN_TF_FOLDER")
            self.assertEqual(
                plans["mediaonly"].status,
                "NO_ROMS_IN_TF_FOLDER",
            )
            self.assertEqual(plans["missing"].status, "NO_MATCHING_TF_FOLDER")
            self.assertFalse((tf_root / "missing").exists())

    def test_copy_rechecks_rom_presence_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_root = root / "canonical"
            tf_root = root / "roms"
            tf_dir = tf_root / "test"
            tf_dir.mkdir(parents=True)
            self.make_source(src_root, "test")
            rom = tf_dir / "Test Game.zip"
            rom.write_bytes(b"rom")

            plan = build_plan(src_root, tf_root)[0]
            self.assertEqual(plan.status, "READY")

            rom.unlink()
            copy_with_backup(plan, root / "backup")

            self.assertEqual(plan.status, "NO_ROMS_IN_TF_FOLDER")
            self.assertFalse((tf_dir / "metadata.pegasus.txt").exists())


if __name__ == "__main__":
    unittest.main()
