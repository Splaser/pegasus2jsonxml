#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
把某个平台的 Pegasus metadata 导出为 jsondb/{key}.json
"""

from __future__ import annotations
import hashlib
import os
import json
from pathlib import Path, PurePosixPath

from typing import Dict, Optional

from .metadata_scanner import parse_pegasus_metadata, extract_libretro_core, normalize_launch_block
from .rom_scanner import HEADER_BYTES, RomHasher


def _normalize_assets_media_dir(
    assets: Dict,
    file_name: Optional[str]
) -> Dict:
    """
    把 assets 里的 media 目录统一改成 media/<file_stem>/xxx。
    """
    if not isinstance(assets, dict) or not file_name:
        return assets

    # 取文件名最后一段，再去掉扩展名：例如 "506.chd" -> "506"
    fname = file_name.split("/")[-1]
    stem = fname.rsplit(".", 1)[0] or fname

    new_assets: Dict = {}
    for k, v in assets.items():
        if not isinstance(v, str):
            new_assets[k] = v
            continue

        p = PurePosixPath(v)
        parts = list(p.parts)

        # 只处理以 media 开头的路径：media/xxx/...
        if len(parts) >= 2 and parts[0] == "media":
            # ✅ 只有当第二段是纯数字目录时，才执行“统一到 file_stem”
            #    例如 media/001/boxfront.png → media/<stem>/boxfront.png
            if len(parts) >= 3 and parts[1].isdigit():
                rest = parts[2:]  # 去掉原来的第二段（数字目录）
                new_p = PurePosixPath("media") / stem
                for comp in rest:
                    new_p /= comp
                new_assets[k] = str(new_p)
            else:
                # ✅ 非数字目录（例如中文名/英文名）一律保持原样
                new_assets[k] = v
        else:
            new_assets[k] = v

    return new_assets


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
        raw_assets = game["assets"]
        fixed_assets = _normalize_assets_media_dir(raw_assets, file_name)
        data["assets"] = fixed_assets

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
    game_launch_str = (game_launch or "").strip()

    # 情况 A：游戏有 override → 写 launch_override + launch_info
    if game_launch_str and game_launch_str != default_launch:
        data["launch_override"] = game_launch

        info = normalize_launch_block(game_launch_str)
        data["launch_info"] = info

        core = info.get("core")
        if core:
            data["core_override"] = core


    rom_hashes = []
    for rom_path in game.get("roms", []):
        full_path = Path(rom_root) / rom_path
        if full_path.is_file():
            size, sha256_full, md5_header = hasher.hash_rom(full_path)
            rom_hashes.append({
                "rom_rel": rom_path,
                "exists": True,
                "size": size,
                "sha256_full": sha256_full,
                "md5_header": md5_header,
                "header_bytes": HEADER_BYTES,
            })
        else:
            rom_hashes.append({
                "rom_rel": rom_path,
                "exists": False,
                "size": None,
                "sha256_full": None,
                "md5_header": None,
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

    default_launch = (
        header.get("launch")
        or header.get("launch_block")
        or header.get("default_launch")
    )
    
    default_launch_info = normalize_launch_block(default_launch) if default_launch else {}

    payload["default_launch_info"] = default_launch_info
    payload["default_core"] = default_launch_info.get("core")

    # 从原始 launch 文本里再试一次提取 core（兼容老写法）
    default_core = extract_libretro_core(default_launch) if default_launch else None
    if default_core:
        payload["default_core"] = default_core

    # ------- 新增：平台元信息 platform_key / platform_type -------
    payload["platform_key"] = key

    plat_key_lower = (key or "").lower()
    collection_lower = str(header.get("collection") or "").lower()

    # 推断一个简洁的 platform_type，后续 exporter 可以直接 switch
    if plat_key_lower in ("ps2", "playstation2") or "ps2" in collection_lower:
        kind = default_launch_info.get("kind")
        emulator = default_launch_info.get("emulator")
        if kind == "android_am" and emulator in ("aethersx2_android", "nethersx2_android"):
            platform_type = "ps2_android_aethersx2"
        else:
            platform_type = "ps2"
    else:
        # 其他平台先简单兜底
        platform_type = plat_key_lower or (collection_lower or "unknown")

    payload["platform_type"] = platform_type

    # ------- 写盘 -------
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return out_path


