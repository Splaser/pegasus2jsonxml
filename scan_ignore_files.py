#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Any


def norm_rel_path(p: str) -> str:
    """
    Normalize Pegasus-style relative ROM paths:
      a\\b.zip -> a/b.zip
      ./a/b.zip -> a/b.zip
    """
    s = str(p).replace("\\", "/").strip()
    while s.startswith("./"):
        s = s[2:]
    return str(PurePosixPath(s))


def collect_game_rom_paths(games: list[dict[str, Any]]) -> set[str]:
    used: set[str] = set()

    for g in games:
        # roms: [...]
        roms = g.get("roms")
        if isinstance(roms, list):
            for r in roms:
                if isinstance(r, str) and r.strip():
                    used.add(norm_rel_path(r))

        # files: [...]
        files = g.get("files")
        if isinstance(files, list):
            for r in files:
                if isinstance(r, str) and r.strip():
                    used.add(norm_rel_path(r))

        # file: xxx
        f = g.get("file")
        if isinstance(f, str) and f.strip():
            used.add(norm_rel_path(f))

    return used


def game_titles_by_rom(games: list[dict[str, Any]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}

    for g in games:
        title = g.get("game") or g.get("title") or g.get("canonical_name") or "<unknown>"

        candidates = []

        roms = g.get("roms")
        if isinstance(roms, list):
            candidates.extend(r for r in roms if isinstance(r, str))

        files = g.get("files")
        if isinstance(files, list):
            candidates.extend(r for r in files if isinstance(r, str))

        f = g.get("file")
        if isinstance(f, str):
            candidates.append(f)

        for r in candidates:
            nr = norm_rel_path(r)
            mapping.setdefault(nr, []).append(str(title))

    return mapping


def iter_json_files(path: Path):
    if path.is_file():
        yield path
    else:
        yield from sorted(path.rglob("*.json"))


def scan_one_json(path: Path, apply: bool = False) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))

    games = obj.get("games") or []
    if not isinstance(games, list):
        games = []

    ignore_files = obj.get("ignore_files") or []
    if not isinstance(ignore_files, list):
        ignore_files = []

    used_roms = collect_game_rom_paths(games)
    titles = game_titles_by_rom(games)

    bad_items = []
    cleaned = []
    seen = set()

    for item in ignore_files:
        if not isinstance(item, str) or not item.strip():
            continue

        norm = norm_rel_path(item)

        # duplicate ignore entries should also be collapsed
        if norm in seen:
            continue
        seen.add(norm)

        if norm in used_roms:
            bad_items.append({
                "ignore": item,
                "normalized": norm,
                "games": titles.get(norm, []),
            })
            continue

        cleaned.append(item.strip())

    changed = len(cleaned) != len(ignore_files) or bool(bad_items)

    if apply and changed:
        obj["ignore_files"] = cleaned
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "path": str(path),
        "platform": obj.get("platform"),
        "changed": changed,
        "ignore_count_before": len(ignore_files),
        "ignore_count_after": len(cleaned),
        "bad_ignore_count": len(bad_items),
        "bad_items": bad_items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan jsondb ignore_files and remove entries that are real games."
    )
    parser.add_argument(
        "--json-root",
        type=Path,
        default=Path("jsondb"),
        help="JSON db root. Default: jsondb",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rewrite JSON files. Default is dry-run.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("ignore_scan_report.json"),
        help="Report output path.",
    )

    args = parser.parse_args()

    if not args.json_root.exists():
        raise SystemExit(f"[ERROR] json root not found: {args.json_root}")

    results = []
    total_bad = 0
    changed_files = 0

    for path in iter_json_files(args.json_root):
        res = scan_one_json(path, apply=args.apply)
        results.append(res)

        if res["bad_ignore_count"]:
            changed_files += 1
            total_bad += res["bad_ignore_count"]
            print(f"[BAD] {path.name}: {res['bad_ignore_count']} game ROM(s) in ignore_files")
            for item in res["bad_items"]:
                games = " / ".join(item["games"])
                print(f"      {item['ignore']}  ->  {games}")

    args.report.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print(f"[SUMMARY] changed_files={changed_files}, bad_ignore_entries={total_bad}")
    print(f"[REPORT] {args.report}")

    if args.apply:
        print("[DONE] JSON files rewritten.")
    else:
        print("[INFO] dry-run only. Add --apply to rewrite jsondb.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())