#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析 Pegasus metadata.txt，抽象成 header + games 结构。

支持：
- 头部字段：collection, sort-by, launch, ignore-files, extension 等
- game block：game, file(多次), sort-by, developer, description, launch 等
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple, Optional


def _finalize_multiline_prop(
    target: Dict,
    key: Optional[str],
    buf: List[str],
    is_header: bool,
) -> None:
    """把正在累积的多行属性收尾写入 target."""
    if not key:
        return
    text = "\n".join(buf).rstrip("\n")

    if is_header:
        if key == "launch":
            target["launch_block"] = text
        elif key == "sort-by":
            target["default_sort_by"] = text
        elif key == "ignore-files":
            # 多行 ignore-files 列表
            items = [ln.strip() for ln in buf if ln.strip()]
            target["ignore_files"] = items
        elif key == "extension":
            # "7z, zip" -> ["7z", "zip"]
            exts = []
            for ln in buf:
                for part in ln.split(","):
                    p = part.strip()
                    if p:
                        exts.append(p)
            target["extensions"] = exts
        else:
            target[key.replace("-", "_")] = text
    else:
        # game block 内
        if key == "launch":
            target["launch_block"] = text
        elif key == "sort-by":
            target["sort_by"] = text
        elif key == "description":
            target["description"] = text
        else:
            target[key.replace("-", "_")] = text


def parse_pegasus_metadata(path: str) -> Tuple[Dict, List[Dict]]:
    """
    解析 Pegasus metadata 文件，返回 (header, games)。

    header 大致结构：
        {
          "collection": "...",
          "default_sort_by": "004",
          "launch_block": "launch:\\n  ...",
          "ignore_files": [...],
          "extensions": [...]
        }

    games 元素结构：
        {
          "game": "标题",
          "roms": ["xx.chd", ...],
          "file": "xx.chd",    # roms[0] 方便前端用
          "sort_by": "001",
          "developer": "...",
          "description": "...",
          "launch_block": "launch:\\n  ...",   # 仅 per-game override 时存在
        }
    """
    header: Dict = {}
    games: List[Dict] = []

    current_game: Optional[Dict] = None
    in_header = True

    # 当前正在累积的多行属性
    current_key: Optional[str] = None
    buf: List[str] = []

    def flush_multiline():
        nonlocal current_key, buf
        if in_header:
            _finalize_multiline_prop(header, current_key, buf, is_header=True)
        else:
            if current_game is not None:
                _finalize_multiline_prop(current_game, current_key, buf, is_header=False)
        current_key = None
        buf = []

    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")

            # 跳过空行 / 纯注释行
            if not line.strip() or line.lstrip().startswith("#"):
                continue

            # 顶层 key（不缩进）
            if not line.startswith(" "):
                # 先收尾上一段多行属性
                flush_multiline()

                # 解析 "key: value"
                if ":" not in line:
                    continue

                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()

                # game: 开启新游戏块
                if key == "game":
                    in_header = False
                    # 收尾上一 game
                    if current_game is not None:
                        # 统一 file / roms
                        roms = current_game.get("roms", [])
                        if not roms:
                            # 兼容 file: 只有一个
                            fpath = current_game.get("file")
                            if isinstance(fpath, str) and fpath:
                                roms = [fpath]
                        current_game["roms"] = roms
                        if roms and "file" not in current_game:
                            current_game["file"] = roms[0]
                        _ensure_default_assets(current_game)
                        games.append(current_game)


                    current_game = {"game": value}
                    current_key = None
                    buf = []
                    continue

                # 其他 header/game 属性
                # file: 特殊处理，多次出现 -> roms 列表
                if key == "file":
                    if in_header:
                        # header 不应该出现 file
                        continue
                    if current_game is None:
                        continue
                    roms = current_game.setdefault("roms", [])
                    roms.append(value)
                    # 不把 "file" 作为多行字段继续累积
                    continue

                # 启动多行属性（launch, description, ignore-files, extension 等）
                if key in ("launch", "description", "ignore-files", "extension"):
                    current_key = key
                    # 把当前行也记录进去（保持原始格式：launch: + 缩进行）
                    if value:
                        buf = [f"{key}: {value}"]
                    else:
                        buf = [f"{key}:"]
                else:
                    # 单行属性，直接写入
                    target = header if in_header else current_game
                    if target is None:
                        continue
                    if key == "sort-by":
                        if in_header:
                            header["default_sort_by"] = value
                        else:
                            current_game["sort_by"] = value
                    else:
                        target[key.replace("-", "_")] = value
            else:
                # 缩进行：多行属性的 continuation
                if current_key is not None:
                    buf.append(line.strip("\n"))
                else:
                    # 没有 current_key，当作 description 的一部分可能比较合理
                    # 但为了简单我们这里直接丢弃，或者你可以根据需要补逻辑
                    pass

    # 文件结束后收尾
    flush_multiline()
    if current_game is not None:
        roms = current_game.get("roms", [])
        if not roms:
            fpath = current_game.get("file")
            if isinstance(fpath, str) and fpath:
                roms = [fpath]
        current_game["roms"] = roms
        if roms and "file" not in current_game:
            current_game["file"] = roms[0]
            
        _ensure_default_assets(current_game)
        games.append(current_game)

    # header 里保证 default_sort_by 存在（哪怕 None）
    if "default_sort_by" not in header:
        header["default_sort_by"] = None

    return header, games


def extract_libretro_core(launch_block: str) -> Optional[str]:
    """
    从 launch block 里解析出 cores/xxx_libretro_android.so 这段，方便前端 override 用。
    """
    if not launch_block:
        return None
    m = re.search(r"/cores/([^/\s]+_libretro_android\.so)", launch_block)
    if not m:
        return None
    return m.group(1)


def _ensure_default_assets(game_dict):
    """
    确保每个 game 都有 assets 字段。
    如果 metadata 里没写 assets，就按照约定：
        media/{game_name}/boxfront.png / logo.png / video.mp4
    自动补上。
    """
    # 已经有 assets，就不动
    if "assets" in game_dict and game_dict["assets"]:
        return

    title = game_dict.get("game") or game_dict.get("title")
    if not title:
        return

    game_dict["assets"] = {
        "box_front": f"media/{title}/boxfront.png",
        "logo":      f"media/{title}/logo.png",
        "video":     f"media/{title}/video.mp4",
    }
