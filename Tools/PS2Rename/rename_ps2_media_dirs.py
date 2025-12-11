#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path
from typing import Dict, Any

from rename_ps2_chd import sanitize_filename   # 和你改CHD时用的是同一个函数


def load_name_mapping(mapping_path: Path) -> Dict[str, str]:
    """
    从 ps2_mapping_redump.json 读取映射，返回：
    {"001.chd": "God of War (USA).chd", ...}
    """
    with mapping_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    result: Dict[str, str] = {}
    for key, val in raw.items():
        old = key.strip()
        if not old.lower().endswith(".chd"):
            old = old + ".chd"

        # 取 en 优先，没有就退回 cn
        if isinstance(val, dict):
            base = (val.get("en") or val.get("cn") or "").strip()
        else:
            base = str(val).strip()

        if not base:
            continue

        target = sanitize_filename(base)
        if not target.lower().endswith(".chd"):
            target += ".chd"

        result[old] = target

    return result


def rename_media_dirs(media_root: Path, mapping: Dict[str, str]) -> None:
    """
    按 mapping 把 media/<数字> 目录改成 media/<新文件名 stem>。

    例如：
    001.chd -> God of War (USA).chd
    media/001 -> media/God of War (USA)
    """
    print(f"media 根目录: {media_root}")
    if not media_root.exists():
        print("⚠ media 根目录不存在，先确认路径")
        return

    for old_chd, new_chd in mapping.items():
        old_stem = Path(old_chd).stem      # "001"
        new_stem = Path(new_chd).stem      # "God of War (USA)"

        src = media_root / old_stem
        dst = media_root / new_stem

        if not src.exists():
            # 有些编号可能没有媒体，略过
            continue

        if dst.exists():
            # 理论上不该冲突，冲突先打个 log 手工看一下
            print(f"⚠ 目标已存在，跳过: {src} -> {dst}")
            continue

        print(f"[move] {src} -> {dst}")
        src.rename(dst)

    print("✅ media 目录重命名完成")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent      # PS2Rename 目录
    proj_root = base_dir.parent.parent

    mapping_path = base_dir / "ps2_mapping_redump.json"
    media_root = Path("G:/roms/PS2/media")          # ← 把这里改成你 TF 卡上的 PS2 media 路径

    mp = load_name_mapping(mapping_path)
    rename_media_dirs(media_root, mp)
