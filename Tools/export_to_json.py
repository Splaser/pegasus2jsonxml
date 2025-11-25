#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
把某个平台的 Pegasus metadata 导出为 jsondb/{key}.json
"""

from __future__ import annotations
import hashlib
import os
import json
from pathlib import Path 

from typing import Dict, Optional

from .metadata_scanner import parse_pegasus_metadata, extract_libretro_core
from .rom_scanner import HEADER_BYTES, RomHasher


def _build_game_json(
    game: Dict,
    header: Dict,
    platform: str,
    rom_root: Optional[str] = None,
    hasher: Optional[RomHasher] = None,
) -> Dict:
    """把解析出的 game dict 转成最终 JSON schema."""

    title = game.get("game")
    file_name = game.get("file")

    data = {
        "game": title,
        "file": file_name,
        "roms": game.get("roms", []),
    }

    # ---- sort_by / developer / description / assets ----
    if game.get("sort_by") is not None:
        data["sort_by"] = game["sort_by"]

    if game.get("developer"):
        data["developer"] = game["developer"]

    if game.get("description"):
        data["description"] = game["description"]

    if "assets" in game:
        data["assets"] = game["assets"]

    # =====================================================
    # 🔥 新增: canonical_name（短期先等于 game）
    # =====================================================
    data["canonical_name"] = title or ""

    # =====================================================
    # 🔥 新增: 游戏唯一 ID（platform + file 的 sha256 截断）
    # =====================================================
    sig_source = f"{platform}:{file_name}".encode("utf-8")
    digest = hashlib.sha256(sig_source).hexdigest()
    # 截为 16 字符，更优雅；你要 full hash 也可以另外输出
    data["id"] = f"{platform}_{digest[:16]}"

    # =====================================================
    # 🔥 per-game launch override（保持你原有逻辑）
    # =====================================================
    game_launch = game.get("launch_block")
    default_launch = header.get("launch_block")

    if game_launch and (not default_launch or game_launch.strip() != default_launch.strip()):
        data["launch_override"] = game_launch

        core = extract_libretro_core(game_launch)
        if core:
            data["core_override"] = core


    # 新增：如果 rom_root 提供，则扫描
    if rom_root and hasher is not None:
        rom_hashes = []
        for rom_path in game.get("roms", []):
            full_path = Path(rom_root) / rom_path
            if full_path.is_file():
                size, sha256_full, md5_header = hasher.hash_rom(full_path)
                rom_hashes.append({
                    "rom_rel": rom_path,
                    "size": size,
                    "sha256_full": sha256_full,
                    "md5_header": md5_header,
                    "header_bytes": HEADER_BYTES,
                })

        if rom_hashes:
            data["rom_hashes"] = rom_hashes
            
    return data

def export_platform_to_json(
    key: str,
    platform_name: str,
    meta_path: str,
    out_root: str = "jsondb",
    rom_root: str | None = None,
) -> str:
    """
    读取 `meta_path`，生成 jsondb/{key}.json，返回输出文件路径。
    """
    header, games = parse_pegasus_metadata(meta_path)

    hasher = RomHasher(header_bytes=HEADER_BYTES) if rom_root else None
    if not os.path.exists(out_root):
        os.makedirs(out_root, exist_ok=True)

    out_path = os.path.join(out_root, f"{key}.json")

    # export_to_json.py 里：
    ignore_files = header.get("ignore_files")
    if ignore_files is None:
        # 兼容老写法 ignore_file: xxx
        single = header.get("ignore_file")
        if isinstance(single, str) and single.strip():
            ignore_files = [single.strip()]
        else:
            ignore_files = []

    payload = {
        "schema_version": 1,
        "platform": platform_name,
        "collection": header.get("collection") or platform_name,
        "assets_base": "media",  # 新增：约定所有媒体路径都在 media/ 下
        "default_sort_by": header.get("default_sort_by"),
        "launch_block": header.get("launch_block"),
        "ignore_files": ignore_files,
        "extensions": header.get("extensions", []),
        # 可以按需暴露更多 header 字段
        "games": [
            _build_game_json(
                g,
                header,
                platform_name,
                rom_root=rom_root,
                hasher=hasher,
            )
            for g in games
        ],
        
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
