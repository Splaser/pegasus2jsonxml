# Converters/esde_exporter.py

from pathlib import Path
import xml.etree.ElementTree as ET
import json

def export_esde(platform: str, json_path: Path, out_dir: Path):
    """
    jsondb/<platform>.json -> ES-DE gamelist.xml
    """

    out_platform_dir = out_dir / platform
    out_media_dir = out_platform_dir / "media"
    out_platform_dir.mkdir(parents=True, exist_ok=True)
    out_media_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    games = data.get("games", [])

    root = ET.Element("gameList")

    for g in games:
        entry = transform_to_esde(platform, g, data)
        root.append(entry)

    out_path = out_platform_dir / "gamelist.xml"
    tree = ET.ElementTree(root)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)

    print(f"[OK] ES-DE export -> {out_path}")
    return out_path


def transform_to_esde(platform: str, game: dict, payload: dict):
    """
    返回一个 <game> element。
    """
    game_elem = ET.Element("game")

    def add(tag, text):
        elem = ET.SubElement(game_elem, tag)
        elem.text = text

    add("name", game.get("game"))
    add("path", f"./roms/{game.get('file')}")

    # 媒体路径 (未来补)
    # add("image", ...)
    # add("marquee", ...)
    # add("video", ...)

    return game_elem
