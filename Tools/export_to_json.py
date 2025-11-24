#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
把某个平台的 Pegasus metadata 导出为 jsondb/{key}.json
"""

from __future__ import annotations

import os
import json
from typing import Dict, List, Tuple

from Tools.metadata_scanner import parse_pegasus_metadata, extract_libretro_core


def _build_game_json(game: Dict, header: Dict) -> Dict:
    """把解析出的 game dict 转成最终 JSON schema."""
    data = {
        "game": game.get("game"),
        "file": game.get("file"),
        "roms": game.get("roms", []),
    }

    if game.get("sort_by") is not None:
        data["sort_by"] = game["sort_by"]

    if game.get("developer"):
        data["developer"] = game["developer"]

    if game.get("description"):
        data["description"] = game["description"]

    if "assets" in game:
        data["assets"] = game["assets"]


    # 处理 per-game launch override
    game_launch = game.get("launch_block")
    default_launch = header.get("launch_block")

    if game_launch and (not default_launch or game_launch.strip() != default_launch.strip()):
        data["launch_override"] = game_launch
        core = extract_libretro_core(game_launch)
        if core:
            data["core_override"] = core

    return data


def export_platform_to_json(
    key: str,
    platform_name: str,
    meta_path: str,
    out_root: str = "jsondb",
) -> str:
    """
    读取 `meta_path`，生成 jsondb/{key}.json，返回输出文件路径。
    """
    header, games = parse_pegasus_metadata(meta_path)

    if not os.path.exists(out_root):
        os.makedirs(out_root, exist_ok=True)

    out_path = os.path.join(out_root, f"{key}.json")

    payload = {
        "schema_version": 1,
        "platform": platform_name,
        "collection": header.get("collection") or platform_name,
        "default_sort_by": header.get("default_sort_by"),
        "launch_block": header.get("launch_block"),
        "ignore_files": header.get("ignore_files", []),
        "extensions": header.get("extensions", []),
        # 可以按需暴露更多 header 字段
        "games": [_build_game_json(g, header) for g in games],
    }

    # ★ 新增 default_core
    default_launch = header.get("launch_block", "")
    default_core = extract_libretro_core(default_launch) if default_launch else None

    if default_core:
        payload["default_core"] = default_core
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return out_path


# 允许单独运行：python -m Tools.export_to_json Resource/XXX/metadata.pegasus.txt KEY "平台名"
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export one Pegasus metadata file to jsondb/*.json")
    parser.add_argument("meta_path", help="metadata.pegasus.txt 路径")
    parser.add_argument("key", help="输出 json 文件名的 key，比如 dc / mame_stg")
    parser.add_argument("name", help="平台显示名，比如 DC / MAME STG")
    parser.add_argument("--out-root", default="jsondb")
    args = parser.parse_args()

    path = export_platform_to_json(args.key, args.name, args.meta_path, out_root=args.out_root)
    print(f"[OK] 导出到 {path}")
