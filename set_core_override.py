#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
set_core_override.py

Platform-level / game-level RetroArch core override editor for Pegasus2JSONXML jsondb.

Examples:

  # Dry-run: change an entire platform default core
  python .\set_core_override.py --platform ps1 --core swanstation

  # Apply: change an entire platform default core
  python .\set_core_override.py --platform ps1 --core swanstation --apply

  # Apply: change one game by file
  python .\set_core_override.py --platform fbneo_ftg_hack --file "hxs1/powerins.zip" --core fbneo --apply

  # Apply: change one game by exact title
  python .\set_core_override.py --platform mame_stg --game "花小路大作战" --core mame2003_plus --apply

  # Apply: change one game by id
  python .\set_core_override.py --platform fbneo_ftg_hack --id "FBNEO FTG hack_xxxxxxxx" --core fbneo --apply
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath
from typing import Any


RA_ACTIVITY = "com.retroarch.aarch64/com.retroarch.browser.retroactivity.RetroActivityFuture"
DEFAULT_CONFIGFILE = "/storage/emulated/0/Android/data/com.retroarch.aarch64/files/retroarch.cfg"

LIBRETRO_EXTRA_RE = re.compile(
    r'((?:-e|--es)\s+LIBRETRO\s+)(?P<q>["\']?)(?P<core>[^\s"\']+)(?P=q)'
)
ROM_PLACEHOLDER_RE = re.compile(
    r'((?:-e|--es)\s+ROM\s+)(?!["\'])\{file\.path\}'
)


@dataclass
class Change:
    kind: str
    platform: str
    json_path: str
    target: str
    old_core: str | None
    new_core: str
    changed: bool


def norm_rel_path(p: str) -> str:
    s = str(p).replace("\\", "/").strip()
    while s.startswith("./"):
        s = s[2:]
    return str(PurePosixPath(s))


def core_to_alias(core: str | None) -> str | None:
    if not core:
        return core

    core = core.strip()
    name = core.replace("\\", "/").split("/")[-1]

    special = {
        "mame_libretro_android.so": "mamearcade",
        "mame_libretro_android": "mamearcade",
        "mamearcade_libretro_android.so": "mamearcade",
        "mamearcade_libretro_android": "mamearcade",

        "fbneo_libretro_old_android.so": "fbneo",
        "fbneo_libretro_old_android": "fbneo",
        "fbalpha_libretro_old_android.so": "fbalpha",
        "fbalpha_libretro_old_android": "fbalpha",
    }
    if name in special:
        return special[name]

    # Already clean alias
    if "/" not in core and not name.endswith(".so") and "_libretro_" not in name:
        return core

    suffixes = [
        "_libretro_android.so",
        "_libretro_android",
        "_libretro_old_android.so",
        "_libretro_old_android",
    ]

    for suffix in suffixes:
        if name.endswith(suffix):
            base = name[:-len(suffix)]
            if base == "mame":
                return "mamearcade"
            return base

    if name.endswith(".so"):
        return name[:-3]

    return core


def default_launch_block(core: str, configfile: str = DEFAULT_CONFIGFILE) -> str:
    return (
        "am start --user 0\n"
        f"  -n {RA_ACTIVITY}\n"
        '  -e ROM "{file.path}"\n'
        f"  -e LIBRETRO {core}\n"
        f"  -e CONFIGFILE {configfile}\n"
        "  -e IME com.android.inputmethod.latin/.LatinIME\n"
        "  -e DATADIR /data/data/com.retroarch.aarch64\n"
        "  -e APK /data/app/com.retroarch.aarch64-1/base.apk\n"
        "  -e SDCARD /storage/emulated/0\n"
        "  -e EXTERNAL /storage/emulated/0/Android/data/com.retroarch.aarch64/files\n"
        "  --activity-clear-top"
    )


def extract_configfile(raw: str | None) -> str:
    if not raw:
        return DEFAULT_CONFIGFILE
    try:
        tokens = shlex.split(raw, posix=True)
        for i in range(len(tokens) - 2):
            if tokens[i] in ("-e", "--es") and tokens[i + 1] == "CONFIGFILE":
                return tokens[i + 2]
    except Exception:
        pass
    m = re.search(r'(?:-e|--es)\s+CONFIGFILE\s+([^\s"\']+)', raw)
    if m:
        return m.group(1)
    return DEFAULT_CONFIGFILE


def rewrite_launch_text(raw: str | None, core: str) -> tuple[str, str | None, bool]:
    """
    Replace LIBRETRO in an existing launch text. If no LIBRETRO exists, build a default block.
    Return: new_raw, old_core, changed
    """
    core = core_to_alias(core) or core
    if not raw or not raw.strip():
        return default_launch_block(core), None, True

    old_core: str | None = None
    changed = False

    def repl(m: re.Match) -> str:
        nonlocal old_core, changed
        prefix = m.group(1)
        quote = m.group("q") or ""
        old = m.group("core")
        old_core = old
        if old != core:
            changed = True
        return f"{prefix}{quote}{core}{quote}"

    new = LIBRETRO_EXTRA_RE.sub(repl, raw)

    if old_core is None:
        # Existing block is weird; rebuild with same configfile.
        cfg = extract_configfile(raw)
        return default_launch_block(core, cfg), None, True

    quoted = ROM_PLACEHOLDER_RE.sub(r'\1"{file.path}"', new)
    if quoted != new:
        changed = True
        new = quoted

    return new, old_core, changed


def tokens_for(raw: str) -> list[str]:
    try:
        return shlex.split(raw, posix=True)
    except Exception:
        return raw.replace("\n", " ").split()


def update_launch_info(info: dict[str, Any], raw: str, core: str) -> None:
    info["raw"] = raw
    info["tokens"] = tokens_for(raw)
    info["kind"] = info.get("kind") or "android_am"
    info["binary"] = info.get("binary") or RA_ACTIVITY
    info["emulator"] = info.get("emulator") or "retroarch"
    info["core"] = core


def get_platform_launch_raw(obj: dict[str, Any]) -> str | None:
    if isinstance(obj.get("launch_block"), str) and obj["launch_block"].strip():
        return obj["launch_block"]
    info = obj.get("default_launch_info")
    if isinstance(info, dict) and isinstance(info.get("raw"), str):
        return info["raw"]
    return None


def set_platform_core(obj: dict[str, Any], platform: str, json_path: Path, core: str) -> Change:
    new_core = core_to_alias(core) or core
    raw = get_platform_launch_raw(obj)
    new_raw, old_core, changed_raw = rewrite_launch_text(raw, new_core)

    old_default = obj.get("default_core")
    changed = changed_raw or old_default != new_core

    obj["launch_block"] = new_raw
    obj["default_core"] = new_core

    info = obj.get("default_launch_info")
    if not isinstance(info, dict):
        info = {}
        obj["default_launch_info"] = info
    update_launch_info(info, new_raw, new_core)

    return Change(
        kind="platform",
        platform=platform,
        json_path=str(json_path),
        target=platform,
        old_core=old_core or old_default,
        new_core=new_core,
        changed=changed,
    )


def game_rom_paths(game: dict[str, Any]) -> set[str]:
    out: set[str] = set()

    f = game.get("file")
    if isinstance(f, str) and f.strip():
        out.add(norm_rel_path(f))

    roms = game.get("roms")
    if isinstance(roms, list):
        for r in roms:
            if isinstance(r, str) and r.strip():
                out.add(norm_rel_path(r))

    files = game.get("files")
    if isinstance(files, list):
        for r in files:
            if isinstance(r, str) and r.strip():
                out.add(norm_rel_path(r))

    return out


def match_games(
    obj: dict[str, Any],
    file: str | None = None,
    game: str | None = None,
    id_: str | None = None,
    contains: bool = False,
) -> list[dict[str, Any]]:
    games = obj.get("games") or []
    if not isinstance(games, list):
        return []

    if file:
        nf = norm_rel_path(file)
        return [g for g in games if isinstance(g, dict) and nf in game_rom_paths(g)]

    if id_:
        return [g for g in games if isinstance(g, dict) and g.get("id") == id_]

    if game:
        if contains:
            return [
                g for g in games
                if isinstance(g, dict) and game in str(g.get("game") or g.get("title") or g.get("canonical_name") or "")
            ]
        return [
            g for g in games
            if isinstance(g, dict)
            and str(g.get("game") or g.get("title") or g.get("canonical_name") or "") == game
        ]

    return []


def set_game_core(
    obj: dict[str, Any],
    platform: str,
    json_path: Path,
    target_game: dict[str, Any],
    core: str,
) -> Change:
    new_core = core_to_alias(core) or core

    base_raw = None
    if isinstance(target_game.get("launch_override"), str):
        base_raw = target_game["launch_override"]
    elif isinstance(target_game.get("launch_info"), dict) and isinstance(target_game["launch_info"].get("raw"), str):
        base_raw = target_game["launch_info"]["raw"]
    else:
        base_raw = get_platform_launch_raw(obj)

    new_raw, old_core, changed_raw = rewrite_launch_text(base_raw, new_core)

    old_override = target_game.get("core_override")
    changed = changed_raw or old_override != new_core

    target_game["launch_override"] = new_raw
    target_game["core_override"] = new_core

    info = target_game.get("launch_info")
    if not isinstance(info, dict):
        info = {}
        target_game["launch_info"] = info
    update_launch_info(info, new_raw, new_core)

    title = str(target_game.get("game") or target_game.get("title")
                or target_game.get("canonical_name") or target_game.get("id"))

    return Change(
        kind="game",
        platform=platform,
        json_path=str(json_path),
        target=title,
        old_core=old_core or old_override,
        new_core=new_core,
        changed=changed,
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False,
                               indent=2) + "\n", encoding="utf-8")


def find_libretro_core(raw: str | None) -> str | None:
    if not raw:
        return None
    m = LIBRETRO_EXTRA_RE.search(raw)
    if not m:
        return None
    return m.group("core")

def clear_game_override(
    platform: str,
    json_path: Path,
    target_game: dict[str, Any],
) -> Change:
    title = str(
        target_game.get("game")
        or target_game.get("title")
        or target_game.get("canonical_name")
        or target_game.get("id")
    )

    old_core = target_game.get("core_override")

    if not old_core:
        info = target_game.get("launch_info")
        if isinstance(info, dict):
            old_core = info.get("core")

    if not old_core:
        for key in ("launch_override", "launch_block", "launch"):
            v = target_game.get(key)
            if isinstance(v, str) and v.strip():
                old_core = find_libretro_core(v)
                break

    keys_to_remove = [
        "launch_override",
        "launch_block",
        "launch",
        "launch_info",
        "core_override",
    ]

    existed = {}
    for key in keys_to_remove:
        if key in target_game:
            existed[key] = target_game.get(key)

    for key in keys_to_remove:
        target_game.pop(key, None)

    return Change(
        kind="clear_game_override",
        platform=platform,
        json_path=str(json_path),
        target=title,
        old_core=old_core,
        new_core="INHERIT_PLATFORM",
        changed=bool(existed),
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Set platform-level or game-level RetroArch core override in jsondb.")
    ap.add_argument("--json-root", default="jsondb", type=Path,
                    help="jsondb root. Default: jsondb")
    ap.add_argument("--platform", required=True,
                    help="Platform key, e.g. ps1 / fbneo_act_hack")
    ap.add_argument(
        "--core", help="Core alias or old core filename/path. It will be normalized.")
    ap.add_argument(
        "--clear-override",
        action="store_true",
        help="Remove game-level launch/core override and let the game inherit platform default."
    )
    ap.add_argument(
        "--file", help="Game ROM path selector, e.g. hxs1/powerins.zip")
    ap.add_argument("--game", help="Exact game title selector")
    ap.add_argument("--id", dest="id_", help="Exact game id selector")
    ap.add_argument("--contains", action="store_true",
                    help="Use substring match for --game")
    ap.add_argument("--allow-multiple", action="store_true",
                    help="Allow updating multiple matched games")
    ap.add_argument("--apply", action="store_true",
                    help="Actually rewrite JSON. Default is dry-run.")
    ap.add_argument(
        "--report", default=Path("set_core_override_report.json"), type=Path)

    args = ap.parse_args()

    if args.clear_override:
        if args.core:
            print("[WARN] --core is ignored when --clear-override is used.")

        if not (args.file or args.game or args.id_):
            raise SystemExit("[ERROR] --clear-override requires --file, --game, or --id.")

    else:
        if not args.core:
            raise SystemExit("[ERROR] --core is required unless --clear-override is used.")

    json_path = args.json_root / f"{args.platform}.json"
    if not json_path.exists():
        raise SystemExit(f"[ERROR] JSON not found: {json_path}")

    obj = load_json(json_path)
    changes: list[Change] = []

    is_game_mode = bool(args.file or args.game or args.id_)

    if is_game_mode:
        matches = match_games(obj, file=args.file, game=args.game, id_=args.id_, contains=args.contains)
        if not matches:
            raise SystemExit("[ERROR] No matching game found.")

        if len(matches) > 1 and not args.allow_multiple:
            print(f"[ERROR] Matched {len(matches)} games. Add --allow-multiple or use --file/--id.")
            for g in matches:
                print("  -", g.get("game"), "|", g.get("file") or g.get("roms"), "|", g.get("id"))
            return 2

        for g in matches:
            if args.clear_override:
                changes.append(clear_game_override(args.platform, json_path, g))
            else:
                changes.append(set_game_core(obj, args.platform, json_path, g, args.core))

    else:
        if args.clear_override:
            raise SystemExit("[ERROR] --clear-override only supports game-level override. Use --file, --game, or --id.")
        changes.append(set_platform_core(obj, args.platform, json_path, args.core))

    report = {
        "json_path": str(json_path),
        "apply": args.apply,
        "core_normalized": core_to_alias(args.core) if args.core else None,
        "clear_override": args.clear_override,
        "changes": [asdict(c) for c in changes],
    }

    args.report.write_text(json.dumps(
        report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for c in changes:
        status = "CHANGE" if c.changed else "NOCHANGE"
        print(f"[{status}] {c.kind} {c.platform} :: {c.target} :: {c.old_core} -> {c.new_core}")

    print(f"[REPORT] {args.report}")

    if args.apply:
        write_json(json_path, obj)
        print(f"[DONE] rewritten: {json_path}")
    else:
        print("[INFO] dry-run only. Add --apply to rewrite JSON.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
