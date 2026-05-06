#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
scan_missing_media.py v2

Scan missing boxfront/logo/video assets for Pegasus2JSONXML jsondb.

Important:
  - This scanner is report-only. It never modifies files.
  - Use --resource-root to point at the real platform folders that contain media/.
    For TF card testing, usually:
        python .\scan_missing_media.py --resource-root F:\roms

Rules:
  - explicit assets are checked first
  - candidate media dirs are broad for scanning:
      media/<rom_parent>
      media/<rom_stem>
      media/<game>
      media/<canonical_name>
      media/<title>
      media/<firstDir> for multi-file entries
  - this broad scan is only for existence checking; metadata_writer still decides what should be emitted.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path, PurePosixPath
from typing import Any


ASSET_FILENAMES = {
    "box_front": [
        "boxfront.png", "boxfront.jpg", "boxfront.jpeg", "boxfront.webp",
        "boxFront.png", "boxFront.jpg", "boxFront.jpeg", "boxFront.webp",
        "box_front.png", "box_front.jpg", "box_front.jpeg", "box_front.webp",
        "cover.png", "cover.jpg", "cover.jpeg", "cover.webp",
        "poster.png", "poster.jpg", "poster.jpeg", "poster.webp",
    ],
    "logo": [
        "logo.png", "logo.jpg", "logo.jpeg", "logo.webp",
        "marquee.png", "marquee.jpg", "marquee.jpeg", "marquee.webp",
        "wheel.png", "wheel.jpg", "wheel.jpeg", "wheel.webp",
    ],
    "video": [
        "video.mp4", "video.webm", "preview.mp4", "preview.webm",
        "snap.mp4", "snap.webm",
    ],
}


def norm_key(s: str) -> str:
    return "".join(ch.lower() for ch in str(s) if ch.isalnum())


def norm_rel_path(p: str) -> str:
    s = str(p).replace("\\", "/").strip()
    while s.startswith("./"):
        s = s[2:]
    return str(PurePosixPath(s))


def unique_keep_order(items):
    out = []
    seen = set()
    for x in items:
        if not isinstance(x, str):
            continue
        x = x.strip()
        if not x:
            continue
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def iter_json_files(root: Path, platform: str | None = None):
    if platform:
        p = root / f"{platform}.json"
        if p.exists():
            yield p
        return
    yield from sorted(root.glob("*.json"))


def find_platform_dir(root: Path, platform_key: str, collection: str | None = None) -> Path | None:
    candidates = [platform_key]
    if collection:
        candidates.append(collection)

    for name in candidates:
        direct = root / name
        if direct.exists() and direct.is_dir():
            return direct

    targets = {norm_key(x) for x in candidates if x}
    for d in root.iterdir():
        if d.is_dir() and norm_key(d.name) in targets:
            return d

    return None


def resolve_rel_exact(base: Path, rel: str) -> Path:
    rel = norm_rel_path(rel)
    return base / Path(*PurePosixPath(rel).parts)


def resolve_rel_tolerant(base: Path, rel: str) -> Path | None:
    """
    Resolve media paths with exact, case-insensitive and normalized-name matching.
    Useful when platform folders are copied between Windows / Android / TF card.
    """
    exact = resolve_rel_exact(base, rel)
    if exact.exists():
        return exact

    cur = base
    for part in PurePosixPath(norm_rel_path(rel)).parts:
        if not cur.exists() or not cur.is_dir():
            return None

        children = list(cur.iterdir())

        # case-insensitive
        lower = part.lower()
        hit = next((c for c in children if c.name.lower() == lower), None)
        if hit:
            cur = hit
            continue

        # normalized fallback, handles spaces / underscores / hyphens / case
        nk = norm_key(part)
        hit = next((c for c in children if norm_key(c.name) == nk), None)
        if hit:
            cur = hit
            continue

        return None

    return cur if cur.exists() else None


def path_exists(base: Path, rel: str | None) -> bool:
    if not rel:
        return False
    return resolve_rel_tolerant(base, rel) is not None


def collect_assets(game: dict[str, Any]) -> dict[str, str]:
    assets: dict[str, str] = {}

    a = game.get("assets")
    if isinstance(a, dict):
        for k, v in a.items():
            if isinstance(k, str) and isinstance(v, str) and v.strip():
                assets[k] = v.strip()

    # legacy flat keys: assets.xxx
    for k, v in game.items():
        if isinstance(k, str) and k.startswith("assets.") and isinstance(v, str) and v.strip():
            sub = k.split(".", 1)[1].strip()
            if sub and sub not in assets:
                assets[sub] = v.strip()

    return assets


def all_rom_paths(game: dict[str, Any]) -> list[str]:
    out = []

    roms = game.get("roms")
    if isinstance(roms, list):
        for r in roms:
            if isinstance(r, str) and r.strip():
                out.append(norm_rel_path(r))

    files = game.get("files")
    if isinstance(files, list):
        for r in files:
            if isinstance(r, str) and r.strip():
                out.append(norm_rel_path(r))

    f = game.get("file")
    if isinstance(f, str) and f.strip():
        out.append(norm_rel_path(f))

    return unique_keep_order(out)


def first_rom_path(game: dict[str, Any]) -> str | None:
    paths = all_rom_paths(game)
    return paths[0] if paths else None


def is_multi_file(game: dict[str, Any]) -> bool:
    return len(all_rom_paths(game)) > 1


def title_bases(game: dict[str, Any]) -> list[str]:
    out = []
    for key in ("game", "canonical_name", "title", "name"):
        v = game.get(key)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return unique_keep_order(out)


def media_bases_for_game(game: dict[str, Any]) -> list[dict[str, str]]:
    """
    Candidate media directories relative to platform root.

    This scanner is intentionally broad:
      - writer rules are strict
      - scanner rules try to detect whether media exists anywhere reasonable
    """
    first = first_rom_path(game)
    if not first:
        return []

    p = PurePosixPath(first)
    stem = p.stem
    parent = p.parts[0] if len(p.parts) >= 2 else None

    candidates: list[dict[str, str]] = []

    def add(kind: str, base_name: str | None):
        if isinstance(base_name, str) and base_name.strip():
            candidates.append({"kind": kind, "base": f"media/{base_name.strip()}"})

    if is_multi_file(game):
        add("multifile_parent", parent)
        add("multifile_stem", stem)
    elif parent:
        add("nested_parent", parent)
        add("nested_stem", stem)
    else:
        add("rom_stem", stem)

    for tb in title_bases(game):
        add("title", tb)

    # In rare imported JSONs, assets might point to media/<x>/file.ext.
    # Add their parent dirs as candidates too.
    assets = collect_assets(game)
    for v in assets.values():
        if not isinstance(v, str) or not v.strip():
            continue
        parts = PurePosixPath(norm_rel_path(v)).parts
        if len(parts) >= 3 and parts[0] == "media":
            add("explicit_parent", parts[1])

    # unique by base, keep first kind
    out = []
    seen = set()
    for c in candidates:
        if c["base"] in seen:
            continue
        seen.add(c["base"])
        out.append(c)

    return out


def find_asset_in_base(platform_dir: Path, base: str, asset_key: str) -> str | None:
    base_path = resolve_rel_tolerant(platform_dir, base)
    if not base_path or not base_path.exists() or not base_path.is_dir():
        return None

    # direct common names
    for name in ASSET_FILENAMES[asset_key]:
        rel = str(PurePosixPath(base) / name)
        if path_exists(platform_dir, rel):
            return rel

    # fallback: case-insensitive and normalized-name match already handled above,
    # but also allow one file in dir whose normalized stem matches common asset words.
    acceptable_stems = {Path(x).stem.lower() for x in ASSET_FILENAMES[asset_key]}
    acceptable_exts = {Path(x).suffix.lower() for x in ASSET_FILENAMES[asset_key]}
    for child in base_path.iterdir():
        if not child.is_file():
            continue
        if child.suffix.lower() not in acceptable_exts:
            continue
        if child.stem.lower() in acceptable_stems or norm_key(child.stem) in {norm_key(x) for x in acceptable_stems}:
            return str(PurePosixPath(base) / child.name)

    return None


def inspect_game(platform_dir: Path, platform_key: str, game: dict[str, Any]) -> dict[str, Any]:
    title = str(game.get("game") or game.get("title") or game.get("canonical_name") or "<unknown>")
    file_path = first_rom_path(game)
    assets = collect_assets(game)
    candidates = media_bases_for_game(game)

    result: dict[str, Any] = {
        "platform": platform_key,
        "game": title,
        "id": game.get("id"),
        "file": file_path,
        "is_multi_file": is_multi_file(game),
        "explicit_assets": assets,
        "candidate_dirs": [],
        "found": {},
        "missing": [],
        "status": "OK",
    }

    for c in candidates:
        base = c["base"]
        result["candidate_dirs"].append({
            "kind": c["kind"],
            "base": base,
            "exists": bool(resolve_rel_tolerant(platform_dir, base)),
        })

    for asset_key in ("box_front", "logo", "video"):
        explicit = assets.get(asset_key)
        explicit_exists = path_exists(platform_dir, explicit) if explicit else False

        found_by_default = None
        if not explicit_exists:
            for c in candidates:
                hit = find_asset_in_base(platform_dir, c["base"], asset_key)
                if hit:
                    found_by_default = hit
                    break

        if explicit_exists:
            result["found"][asset_key] = {
                "source": "explicit",
                "path": explicit,
                "exists": True,
            }
        elif found_by_default:
            result["found"][asset_key] = {
                "source": "candidate",
                "path": found_by_default,
                "exists": True,
            }
        else:
            result["missing"].append(asset_key)
            result["found"][asset_key] = {
                "source": "none",
                "path": explicit or None,
                "exists": False,
            }

    if result["missing"]:
        result["status"] = "MISSING"

    return result


def inspect_json(path: Path, resource_root: Path) -> list[dict[str, Any]]:
    obj = json.loads(path.read_text(encoding="utf-8"))

    platform_key = path.stem
    collection = obj.get("collection") if isinstance(obj.get("collection"), str) else None
    platform_dir = find_platform_dir(resource_root, platform_key, collection=collection)

    if not platform_dir:
        return [{
            "platform": platform_key,
            "json_path": str(path),
            "status": "NO_PLATFORM_DIR",
            "missing": ["platform_dir"],
            "game": None,
            "file": None,
            "resource_root": str(resource_root),
        }]

    games = obj.get("games") or []
    if not isinstance(games, list):
        return []

    rows = []
    for g in games:
        if isinstance(g, dict):
            row = inspect_game(platform_dir, platform_key, g)
            row["json_path"] = str(path)
            row["platform_dir"] = str(platform_dir)
            rows.append(row)

    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "platform", "game", "file", "status", "missing",
        "box_front", "logo", "video",
        "candidate_dirs", "platform_dir",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            found = r.get("found") or {}
            w.writerow({
                "platform": r.get("platform"),
                "game": r.get("game"),
                "file": r.get("file"),
                "status": r.get("status"),
                "missing": ",".join(r.get("missing") or []),
                "box_front": (found.get("box_front") or {}).get("path"),
                "logo": (found.get("logo") or {}).get("path"),
                "video": (found.get("video") or {}).get("path"),
                "candidate_dirs": json.dumps(r.get("candidate_dirs") or [], ensure_ascii=False),
                "platform_dir": r.get("platform_dir"),
            })


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan missing media assets for jsondb games.")
    ap.add_argument("--json-root", default=Path("jsondb"), type=Path, help="jsondb root. Default: jsondb")
    ap.add_argument("--resource-root", default=Path("Resource"), type=Path, help=r"Platform root with media/. Use F:\roms for TF card.")
    ap.add_argument("--platform", help="Only scan one platform key")
    ap.add_argument("--all", action="store_true", help="Include OK games in report. Default only reports missing.")
    ap.add_argument("--report", default=Path("missing_media_report.json"), type=Path)
    ap.add_argument("--csv", default=Path("missing_media_report.csv"), type=Path)

    args = ap.parse_args()

    if not args.json_root.exists():
        raise SystemExit(f"[ERROR] json root not found: {args.json_root}")
    if not args.resource_root.exists():
        raise SystemExit(f"[ERROR] resource/platform root not found: {args.resource_root}")

    all_rows: list[dict[str, Any]] = []

    for path in iter_json_files(args.json_root, args.platform):
        all_rows.extend(inspect_json(path, args.resource_root))

    rows_out = all_rows if args.all else [r for r in all_rows if r.get("status") != "OK"]

    args.report.write_text(json.dumps(rows_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(args.csv, rows_out)

    missing_games = sum(1 for r in all_rows if r.get("status") == "MISSING")
    no_platform_dir = sum(1 for r in all_rows if r.get("status") == "NO_PLATFORM_DIR")
    total_games = sum(1 for r in all_rows if r.get("game"))

    print(f"[SUMMARY] total_games={total_games}, missing_games={missing_games}, no_platform_dir={no_platform_dir}, reported={len(rows_out)}")
    print(f"[ROOT] {args.resource_root}")
    print(f"[REPORT] {args.report}")
    print(f"[CSV] {args.csv}")

    if rows_out:
        print()
        print("[MISSING SAMPLE]")
        for r in rows_out[:30]:
            print(f"  [{r.get('platform')}] {r.get('game')} | {r.get('file')} | missing={','.join(r.get('missing') or [])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
