#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
从 jsondb/{key}.json 生成 CanonicalMetadata/{key}/metadata.pegasus.txt
"""

from __future__ import annotations

import os
import json
from typing import Any, Dict, List
from pathlib import PurePosixPath
from Tools.metadata_writer import dump_pegasus_metadata


def _norm_rel_path(p: str) -> str:
    return str(PurePosixPath(str(p).replace("\\", "/").strip()))


def _collect_game_rom_paths(games: list[dict]) -> set[str]:
    used = set()

    for g in games:
        # roms
        roms = g.get("roms")
        if isinstance(roms, list):
            for r in roms:
                if isinstance(r, str) and r.strip():
                    used.add(_norm_rel_path(r))

        # files
        files = g.get("files")
        if isinstance(files, list):
            for r in files:
                if isinstance(r, str) and r.strip():
                    used.add(_norm_rel_path(r))

        # file
        f = g.get("file")
        if isinstance(f, str) and f.strip():
            used.add(_norm_rel_path(f))

    return used

def _sanitize_ignore_files(ignore_files, games: list[dict]) -> list[str]:
    if not ignore_files:
        return []

    used_roms = _collect_game_rom_paths(games)

    result = []
    seen = set()

    for item in ignore_files:
        if not isinstance(item, str) or not item.strip():
            continue

        norm = _norm_rel_path(item)

        # 关键：如果 ignore 项其实是一个入库游戏，不能再 ignore
        if norm in used_roms:
            continue

        if norm in seen:
            continue

        seen.add(norm)
        result.append(item.strip())

    return result

def json_to_metadata(
    key: str,
    json_path: str,
    output_root: str = "CanonicalMetadata",
) -> str:
    """
    根据 jsondb/<key>.json 恢复 / 生成 Pegasus metadata：

        CanonicalMetadata/<key>/metadata.pegasus.txt

    返回写出的 metadata 路径。
    """
    with open(json_path, "r", encoding="utf-8") as f:
        payload: Dict[str, Any] = json.load(f)

    games: List[Dict[str, Any]] = payload.get("games", [])

    header: Dict[str, Any] = {
        "collection": payload.get("collection") or payload.get("platform_name") or key,
        "shortname": payload.get("shortname"),
        "default_sort_by": payload.get("default_sort_by"),
        "launch_block": payload.get("launch_block"),
        "extensions": payload.get("extensions") or [],
        "ignore_files": payload.get("ignore_files") or [],
    }

    header["ignore_files"] = _sanitize_ignore_files(header["ignore_files"], games)
    
    out_dir = os.path.join(output_root, key)
    os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, "metadata.pegasus.txt")
    dump_pegasus_metadata(out_path, header, games)
    return out_path
