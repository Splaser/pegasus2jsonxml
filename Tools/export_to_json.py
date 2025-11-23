#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pegasus metadata → JSONDB 导出工具（库）

提供几个核心函数：

- discover_platforms(resource_root="Resource") -> dict[key] = (platform_name, meta_path)
- build_platform_data(platform_name, meta_path) -> dict  # 用于写入 json
- export_platform(key, platform_name, meta_path, out_dir="jsondb") -> str  # 返回写入路径

真正的 CLI 放在项目根的 main.py 里，这里只负责逻辑。
"""

from __future__ import annotations
import os
import json
from typing import Dict, Tuple

from Tools.metadata_scanner import parse_pegasus_metadata


def discover_platforms(resource_root: str = "Resource") -> Dict[str, Tuple[str, str]]:
    """
    自动扫描 Resource 下所有子目录，
    找到里面带 metadata.pegasus.txt 的目录。

    返回:
        dict:
            key -> (平台目录名, metadata 文件路径)
        默认 key = 子目录名全部小写 + 下划线替换空格，
        比较适合拿来当命令行参数，例如 dc / fbneo_act 等。
    """
    platforms: Dict[str, Tuple[str, str]] = {}

    if not os.path.isdir(resource_root):
        return platforms

    for entry in os.listdir(resource_root):
        platform_dir = os.path.join(resource_root, entry)
        if not os.path.isdir(platform_dir):
            continue

        meta_path = os.path.join(platform_dir, "metadata.pegasus.txt")
        if os.path.exists(meta_path):
            key = entry.lower().replace(" ", "_")
            platforms[key] = (entry, meta_path)

    return platforms


def build_platform_data(platform_name: str, meta_path: str) -> dict:
    """
    从 pegasus metadata 文件构造一个可直接 json.dump 的数据结构。
    """
    header, games = parse_pegasus_metadata(meta_path)

    data = {
        "platform": platform_name,                     # 比如 "DC" / "FBNEO ACT"
        "collection": header.get("collection"),
        "default_sort_by": header.get("default_sort_by"),
        "launch_block": header.get("launch_block"),
        "games": games,
    }
    return data


def export_platform(
    key: str,
    platform_name: str,
    meta_path: str,
    out_dir: str = "jsondb",
    preview: int = 2,
) -> str:
    """
    导出单个平台为 jsondb/{key}.json

    Args:
        key: 用于文件名，比如 dc / fbneo_act
        platform_name: 人类可读平台名（目录名）
        meta_path: metadata.pegasus.txt 的路径
        out_dir: 输出目录，默认 'jsondb'
        preview: 预览打印前几条（如果你在 CLI 里想用）

    Returns:
        写入的 json 文件路径
    """
    print(f"\n==== [{key}] {platform_name} ====")
    print(f"[INFO] 读取: {meta_path}")

    data = build_platform_data(platform_name, meta_path)
    games = data.get("games") or []

    # --- 清理无意义空字段 ---
    for g in games:
        # 删除空 launch
        if not g.get("launch"):
            g.pop("launch", None)
        # 如果 launch_override 是空，也删
        if "launch_override" in g and not g["launch_override"].strip():
            g.pop("launch_override", None)

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{key}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[OK] 写入: {out_path}  (共 {len(games)} 游戏)")

    # 简单预览
    if preview and games:
        print(f"[PREVIEW] 前 {min(preview, len(games))} 条：")
        for idx, g in enumerate(games[:preview], start=1):
            print(f"  [{idx}] {g.get('game')}")
            print(f"       roms : {g.get('roms')}")
        print("-" * 60)

    return out_path
