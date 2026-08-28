"""Export jsondb metadata and Pegasus media for Daijisho imports."""

from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any


BOX_FILENAMES = (
    "boxfront.jpg",
    "boxFront.jpg",
    "box_front.jpg",
    "boxfront.jpeg",
    "boxFront.jpeg",
    "box_front.jpeg",
    "boxfront.png",
    "boxFront.png",
    "box_front.png",
    "cover.jpg",
    "cover.jpeg",
    "cover.png",
)


def export_daijisho(
    platform: str,
    json_path: Path,
    out_dir: Path,
    resource_dir: Path | None = None,
) -> Path:
    """Create a Daijisho gamelist.xml and a flat box-art import folder.

    Daijisho first scans the ROM directory. Its two platform actions then
    import metadata from an EmulationStation/Skraper ``gamelist.xml`` and
    preview media from a folder whose image basenames match the ROM names.

    ``resource_dir`` is the Pegasus platform directory containing ``media``.
    It defaults to the JSON file's directory to retain compatibility with the
    original three-argument function.
    """
    json_path = Path(json_path)
    out_dir = Path(out_dir)
    resource_dir = Path(resource_dir) if resource_dir is not None else json_path.parent

    data = json.loads(json_path.read_text(encoding="utf-8"))
    games = data.get("games", [])
    platform_dir = out_dir / platform
    box_dir = platform_dir / "box"
    box_dir.mkdir(parents=True, exist_ok=True)

    copied: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    collisions: list[dict[str, str]] = []
    destinations: dict[str, Path] = {}
    game_list = ET.Element("gameList")

    for game in games:
        rom_path = _primary_rom_path(game)
        if not rom_path:
            missing.append({
                "game": _game_name(game),
                "reason": "NO_ROM_PATH",
            })
            continue

        rom_stem = PurePosixPath(rom_path.replace("\\", "/")).stem
        image_rel: str | None = None
        source = _find_box_art(resource_dir, game, rom_path)

        if not rom_stem:
            missing.append({
                "game": _game_name(game),
                "rom": rom_path,
                "reason": "NO_ROM_STEM",
            })
        elif source is None:
            missing.append({
                "game": _game_name(game),
                "rom": rom_path,
                "reason": "BOX_ART_NOT_FOUND",
            })
        else:
            destination = box_dir / f"{rom_stem}{source.suffix.lower()}"
            collision_key = destination.name.casefold()
            previous_source = destinations.get(collision_key)
            if previous_source is not None and previous_source != source:
                collisions.append({
                    "game": _game_name(game),
                    "rom": rom_path,
                    "destination": str(destination),
                    "source": str(source),
                    "conflicts_with": str(previous_source),
                })
            else:
                destinations[collision_key] = source
                shutil.copy2(source, destination)
                image_rel = f"./box/{destination.name}"
                copied.append({
                    "game": _game_name(game),
                    "rom": rom_path,
                    "source": str(source),
                    "destination": str(destination),
                })

        game_list.append(_game_to_xml(game, rom_path, image_rel))

    _indent_xml(game_list)
    gamelist_path = platform_dir / "gamelist.xml"
    ET.ElementTree(game_list).write(
        gamelist_path,
        encoding="utf-8",
        xml_declaration=True,
    )

    report_path = platform_dir / "export_report.json"
    report = {
        "platform": platform,
        "resource_dir": str(resource_dir),
        "gamelist": str(gamelist_path),
        "box_dir": str(box_dir),
        "metadata_count": len(game_list),
        "copied_count": len(copied),
        "missing_count": len(missing),
        "collision_count": len(collisions),
        "copied": copied,
        "missing": missing,
        "collisions": collisions,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"[OK] Daijisho export -> {platform_dir} "
        f"(metadata={len(game_list)}, covers={len(copied)}, "
        f"missing={len(missing)}, collisions={len(collisions)})"
    )
    return platform_dir


def _game_to_xml(
    game: dict[str, Any],
    rom_path: str,
    image_rel: str | None,
) -> ET.Element:
    item = ET.Element("game")

    def add(tag: str, value: Any) -> None:
        text = _text(value)
        if not text:
            return
        child = ET.SubElement(item, tag)
        child.text = text

    normalized_rom_path = rom_path.replace("\\", "/")
    add("path", f"./{normalized_rom_path}")
    add("name", _game_name(game))
    add("sortname", game.get("sort_by"))
    description = game.get("description")
    if isinstance(description, str):
        description = description.replace("\\n", "\n")
    add("desc", description)
    add("developer", game.get("developer"))
    add("publisher", game.get("publisher"))
    add("genre", game.get("genre") or game.get("genres"))
    add("players", game.get("players"))
    add("releasedate", _release_date(game.get("release")))
    add("image", image_rel)
    return item


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = ", ".join(str(part).strip() for part in value if str(part).strip())
    text = str(value).strip()
    return text or None


def _release_date(value: Any) -> str | None:
    """Convert common Pegasus dates to the ES/Skraper timestamp form."""
    text = _text(value)
    if not text:
        return None
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) == 4:
        return f"{digits}0101T000000"
    if len(digits) == 6:
        return f"{digits}01T000000"
    if len(digits) >= 8:
        return f"{digits[:8]}T000000"
    return text


def _primary_rom_path(game: dict[str, Any]) -> str | None:
    value = game.get("file")
    if isinstance(value, str) and value.strip():
        return value.strip()

    for key in ("roms", "files"):
        values = game.get(key)
        if isinstance(values, list):
            for candidate in values:
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
    return None


def _game_name(game: dict[str, Any]) -> str:
    return str(
        game.get("game")
        or game.get("canonical_name")
        or game.get("file")
        or ""
    )


def _find_box_art(
    resource_dir: Path,
    game: dict[str, Any],
    rom_path: str,
) -> Path | None:
    candidate_dirs: list[Path] = []
    assets = game.get("assets") or {}
    explicit = assets.get("box_front") if isinstance(assets, dict) else None

    if isinstance(explicit, str) and explicit.strip():
        explicit_path = _safe_resource_path(resource_dir, explicit)
        if explicit_path is not None:
            exact = _case_insensitive_file(explicit_path)
            if exact is not None:
                return exact
            candidate_dirs.append(explicit_path.parent)

    rom = PurePosixPath(rom_path.replace("\\", "/"))
    media_root = resource_dir / "media"
    if rom.stem:
        candidate_dirs.append(media_root / rom.stem)
    if len(rom.parts) > 1:
        candidate_dirs.append(media_root / rom.parts[0])

    seen: set[str] = set()
    for directory in candidate_dirs:
        key = str(directory).casefold()
        if key in seen:
            continue
        seen.add(key)
        found = _find_named_file(directory, BOX_FILENAMES)
        if found is not None:
            return found
    return None


def _safe_resource_path(resource_dir: Path, relative_path: str) -> Path | None:
    normalized = relative_path.strip().lstrip("./").replace("\\", "/")
    candidate = (resource_dir / PurePosixPath(normalized)).resolve()
    root = resource_dir.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _case_insensitive_file(path: Path) -> Path | None:
    if path.is_file():
        return path
    if not path.parent.is_dir():
        return None
    wanted = path.name.casefold()
    for child in path.parent.iterdir():
        if child.is_file() and child.name.casefold() == wanted:
            return child
    return None


def _find_named_file(directory: Path, names: tuple[str, ...]) -> Path | None:
    if not directory.is_dir():
        return None
    children = {
        child.name.casefold(): child
        for child in directory.iterdir()
        if child.is_file()
    }
    for name in names:
        found = children.get(name.casefold())
        if found is not None:
            return found
    return None


def _indent_xml(element: ET.Element, level: int = 0) -> None:
    space = "\n" + level * "  "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = space + "  "
        for child in element:
            _indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = space + "  "
        element[-1].tail = space
    elif level and (not element.tail or not element.tail.strip()):
        element.tail = space
