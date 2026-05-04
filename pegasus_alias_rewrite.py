#!/usr/bin/env python3
"""
Rewrite Pegasus JSON launch_block LIBRETRO values from RetroArch Android .so paths
into alias/core-id form, e.g.:

  /data/data/com.retroarch.aarch64/cores/snes9x_libretro_android.so -> snes9x
  /data/data/com.retroarch.aarch64/cores/mame_libretro_android.so   -> mamearcade

Default behavior is conservative: preserve the existing launch_block structure and only
replace the value after `-e LIBRETRO` / `--es LIBRETRO`, plus optionally quote ROM.
Use --minimal to rebuild a clean Daijisho-like block with only ROM/LIBRETRO/CONFIGFILE.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable


RA_ACTIVITY = "com.retroarch.aarch64/com.retroarch.browser.retroactivity.RetroActivityFuture"
DEFAULT_CONFIG = "/storage/emulated/0/Android/data/com.retroarch.aarch64/files/retroarch.cfg"

# Known practical override from Odin3/RetroArch Android/Daijisho testing.
# Most aliases are simply basename minus `_libretro_android.so`; current MAME is the exception.
CORE_OVERRIDES = {
    "mame_libretro_android.so": "mamearcade",
    "mamearcade_libretro_android.so": "mamearcade",
}

LIBRETRO_EXTRA_RE = re.compile(
    r'((?:-e|--es)\s+LIBRETRO\s+)(?P<q>["\']?)(?P<core>[^\s"\']+)(?P=q)'
)

ROM_PLACEHOLDER_RE = re.compile(
    r'((?:-e|--es)\s+ROM\s+)(?!["\'])\{file\.path\}'
)


@dataclass
class RewriteResult:
    path: str
    platform: str | None
    old_core: str | None
    new_core: str | None
    changed: bool
    mode: str
    game_overrides_changed: int = 0


def core_to_alias(core: str | None) -> str | None:
    if not core:
        return core

    core = core.strip()

    # Already alias
    if "/" not in core and not core.endswith(".so"):
        return core

    name = core.replace("\\", "/").split("/")[-1]

    special = {
        "mame_libretro_android.so": "mamearcade",
        "mamearcade_libretro_android.so": "mamearcade",
    }
    if name in special:
        return special[name]

    suffix = "_libretro_android.so"
    if name.endswith(suffix):
        return name[:-len(suffix)]

    if name.endswith(".so"):
        return name[:-3]

    return core


CORE_PATH_RE = re.compile(
    r"(/data/data/com\.retroarch\.aarch64/cores/)?([A-Za-z0-9_]+)_libretro_android\.so"
)

def alias_from_match(m: re.Match) -> str:
    core_file = m.group(2)
    if core_file in ("mame", "mamearcade"):
        return "mamearcade"
    return core_file

def rewrite_core_refs_in_text(text: str) -> tuple[str, bool]:
    if not text:
        return text, False

    new = CORE_PATH_RE.sub(alias_from_match, text)

    # Quote Pegasus ROM placeholder
    new = re.sub(r"(-e\s+ROM\s+)\{file\.path\}", r'\1"{file.path}"', new)

    return new, new != text


def rewrite_launch_text(text: str) -> tuple[str, str | None, str | None, bool]:
    """
    Rewrite only:
      - LIBRETRO <core path> -> LIBRETRO <alias>
      - ROM {file.path} -> ROM "{file.path}"

    Return:
      new_text, old_core, new_core, changed
    """
    if not text:
        return text, None, None, False

    old_core: str | None = None
    new_core: str | None = None
    changed = False

    def repl_libretro(m: re.Match) -> str:
        nonlocal old_core, new_core, changed

        prefix = m.group(1)
        quote = m.group("q") or ""
        core = m.group("core")

        alias = core_to_alias(core)

        if old_core is None:
            old_core = core
            new_core = alias

        if alias != core:
            changed = True

        # Keep existing quoting style if present.
        return f"{prefix}{quote}{alias}{quote}"

    new = LIBRETRO_EXTRA_RE.sub(repl_libretro, text)

    quoted = ROM_PLACEHOLDER_RE.sub(r'\1"{file.path}"', new)
    if quoted != new:
        changed = True
        new = quoted

    return new, old_core, new_core, changed


def rewrite_token_list(tokens: list[Any]) -> tuple[list[Any], bool]:
    """
    Helper metadata only. Runtime uses raw launch_block.
    """
    changed = False
    out = list(tokens)

    i = 0
    while i < len(out):
        if (
            isinstance(out[i], str)
            and out[i] in ("-e", "--es")
            and i + 2 < len(out)
            and out[i + 1] == "LIBRETRO"
            and isinstance(out[i + 2], str)
        ):
            old = out[i + 2]
            new = core_to_alias(old)
            if new != old:
                out[i + 2] = new
                changed = True
            i += 3
            continue

        if (
            isinstance(out[i], str)
            and out[i] in ("-e", "--es")
            and i + 2 < len(out)
            and out[i + 1] == "ROM"
            and out[i + 2] == "{file.path}"
        ):
            out[i + 2] = '"{file.path}"'
            changed = True
            i += 3
            continue

        i += 1

    return out, changed


def rewrite_launch_info(info: dict[str, Any]) -> tuple[bool, str | None, str | None]:
    changed = False
    old_core = None
    new_core = None

    if not isinstance(info, dict):
        return False, None, None

    if isinstance(info.get("raw"), str):
        new_raw, oc, nc, ch = rewrite_launch_text(info["raw"])
        if ch:
            info["raw"] = new_raw
            changed = True
        old_core = old_core or oc
        new_core = new_core or nc

    if isinstance(info.get("tokens"), list):
        new_tokens, ch = rewrite_token_list(info["tokens"])
        if ch:
            info["tokens"] = new_tokens
            changed = True

    if isinstance(info.get("core"), str):
        oc = info["core"]
        nc = core_to_alias(oc)
        if nc != oc:
            info["core"] = nc
            changed = True
        old_core = old_core or oc
        new_core = new_core or nc

    return changed, old_core, new_core


def rewrite_game_overrides(game: dict[str, Any]) -> bool:
    changed = False

    if isinstance(game.get("launch_override"), str):
        new_raw, _, _, ch = rewrite_launch_text(game["launch_override"])
        if ch:
            game["launch_override"] = new_raw
            changed = True

    if isinstance(game.get("launch_info"), dict):
        ch, _, _ = rewrite_launch_info(game["launch_info"])
        if ch:
            changed = True

    if isinstance(game.get("core_override"), str):
        old = game["core_override"]
        new = core_to_alias(old)
        if new != old:
            game["core_override"] = new
            changed = True

    return changed

def iter_json_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
    else:
        yield from sorted(path.rglob("*.json"))


def rewrite_json_obj(obj: dict[str, Any]) -> RewriteResult:
    platform = obj.get("platform")
    changed = False

    old_core: str | None = None
    new_core: str | None = None

    # Top-level launch_block
    if isinstance(obj.get("launch_block"), str):
        new_raw, oc, nc, ch = rewrite_launch_text(obj["launch_block"])
        if ch:
            obj["launch_block"] = new_raw
            changed = True
        old_core = old_core or oc
        new_core = new_core or nc

    # default_launch_info
    if isinstance(obj.get("default_launch_info"), dict):
        info = obj["default_launch_info"]

        # Keep helper raw aligned with top-level launch_block when present.
        if isinstance(obj.get("launch_block"), str):
            info["raw"] = obj["launch_block"]

        ch, oc, nc = rewrite_launch_info(info)
        if ch:
            changed = True
        old_core = old_core or oc
        new_core = new_core or nc

        # Rebuild helper tokens from raw if possible.
        if isinstance(info.get("raw"), str):
            try:
                info["tokens"] = shlex.split(info["raw"], posix=True)
            except Exception:
                pass

        info["kind"] = info.get("kind") or "android_am"
        info["emulator"] = info.get("emulator") or "retroarch"

    # default_core
    if isinstance(obj.get("default_core"), str):
        oc = obj["default_core"]
        nc = core_to_alias(oc)
        if nc != oc:
            obj["default_core"] = nc
            changed = True
        old_core = old_core or oc
        new_core = new_core or nc

    # If top-level LIBRETRO was found, keep default_core aligned.
    if new_core:
        obj["default_core"] = new_core
        if isinstance(obj.get("default_launch_info"), dict):
            obj["default_launch_info"]["core"] = new_core

    # Per-game overrides
    game_overrides_changed = 0
    for game in obj.get("games", []):
        if isinstance(game, dict) and rewrite_game_overrides(game):
            game_overrides_changed += 1

    if game_overrides_changed:
        changed = True

    return RewriteResult(
        path="",
        platform=platform,
        old_core=old_core,
        new_core=new_core,
        changed=changed,
        mode="alias_only",
        game_overrides_changed=game_overrides_changed,
    )

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Rewrite Pegasus JSON RetroArch cores to alias form."
    )

    # Project defaults
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print report; do not write files"
    )

    args = ap.parse_args()

    project_root = Path(__file__).resolve().parent
    input_dir = project_root / "jsondb"
    out_dir = project_root / "jsondb"
    report_path = project_root / "alias_report.json"

    if not input_dir.exists():
        raise SystemExit(f"input dir not found: {input_dir}")

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []

    for src in iter_json_files(input_dir):
        try:
            obj = json.loads(src.read_text(encoding="utf-8"))
        except Exception as e:
            results.append({"path": str(src), "error": str(e)})
            continue

        res = rewrite_json_obj(obj)
        res.path = str(src)
        results.append(asdict(res))

        if args.dry_run:
            continue

        text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
        dst = out_dir / src.name
        dst.write_text(text, encoding="utf-8")

    report_text = json.dumps(results, ensure_ascii=False, indent=2) + "\n"

    if not args.dry_run:
        report_path.write_text(report_text, encoding="utf-8")

    print(report_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
