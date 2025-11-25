#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析 Pegasus metadata.txt，抽象成 header + games 结构。

支持：
- 头部字段：collection, sort-by, launch, ignore-files, extension 等
- game block：game, file(多次), sort-by, developer, description, launch 等
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple, Optional, Any
import shlex
import os

def normalize_launch_block(launch_block: str) -> Dict[str, Any]:
    """
    把一段 Pegasus launch 命令“正则化”，返回结构化信息：

    {
      "raw": "... 原始 launch ...",
      "emulator": "retroarch",
      "binary": "E:/Emu/RetroArch/retroarch.exe",
      "core": "mednafen_saturn_hw",
      "rom_arg_index": 3,   # 第几个 token 是 ROM 占位符
      "tokens": [...]       # 可选：完整 tokens 列表，方便 debug
    }

    - 不改写原始命令，只做解析。
    - 如果不是 RA / 没法识别，至少会带上 raw / tokens。
    """
    result: Dict[str, Any] = {
        "raw": (launch_block or "").strip(),
    }
    text = result["raw"]
    if not text:
        return result

    # 用 shlex 粗略拆 token（对大部分 Windows/Unix 命令都够用）
    try:
        tokens = shlex.split(text, posix=False)
    except ValueError:
        # 命令里有奇怪的引号，至少保留原文
        result["tokens"] = []
        return result

    result["tokens"] = tokens

    # 1) 尝试识别 emulator / binary
    for t in tokens:
        base = os.path.basename(t).lower()
        if "retroarch" in base:
            result["emulator"] = "retroarch"
            result["binary"] = t
            break

    # 2) 提取 core 名（沿用你现有的提取逻辑）
    from .metadata_scanner import extract_libretro_core  # 如果在同文件，直接调用即可
    core = extract_libretro_core(text)
    if core:
        result["core"] = core

    # 3) 找 ROM 占位符所在位置（%ROM%、{file}、%file% 之类）
    rom_index: Optional[int] = None
    for idx, t in enumerate(tokens):
        if ("%ROM%" in t) or ("%rom%" in t) or ("{file}" in t) or ("%file%" in t):
            rom_index = idx
            break
    if rom_index is not None:
        result["rom_arg_index"] = rom_index

    return result

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
            # 去掉开头多余的 "launch:" 前缀（兼容 "launch: xxx" 和 "launch:" 两种写法）
            txt = text
            if txt.startswith("launch:"):
                txt = txt[len("launch:"):].lstrip()
            target["launch_block"] = txt
        elif key == "sort-by":
            target["default_sort_by"] = text
        elif key == "ignore-files":
            # buf[0] 是 "ignore-files:"，要去掉
            items = [ln.strip() for ln in buf[1:] if ln.strip()]
            target["ignore_files"] = items
        elif key in ("extension", "extensions"):
            # 多行写法：
            # extension:
            #   7z
            #   zip
            lines = buf[1:] if len(buf) > 1 else []
            exts: List[str] = []
            for ln in lines:
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
            txt = text
            if txt.startswith("launch:"):
                txt = txt[len("launch:"):].lstrip()
            target["launch_block"] = txt
        elif key == "sort-by":
            target["sort_by"] = text
        elif key == "description":
            text = "\n".join(buf).rstrip("\n")
            # 如果开头是 "description:" 就砍掉这一段
            if text.startswith("description:"):
                text = text[len("description:"):].lstrip()
            target["description"] = text

        elif key == "files":
            # 多行 files:
            #   path1
            #   path2
            # 注意：防止 "files:"/空行 混进来
            lines: List[str] = []
            for ln in buf:
                s = ln.strip()
                if not s:
                    continue
                # 万一哪天 buf 里真的混进 "files:"，这里直接跳过
                if s.lower().startswith("files:"):
                    continue
                lines.append(s)

            roms = target.setdefault("roms", [])
            roms.extend(lines)

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

                        # 先把意外的 "files:" 之类的占位符滤掉
                        roms = [
                            r for r in roms
                            if isinstance(r, str)
                            and r.strip()
                            and not r.strip().lower().startswith("files:")
                        ]

                        # 如果之前误写了 file = "files:"，这里也顺手清理掉
                        fval = current_game.get("file")
                        if isinstance(fval, str) and fval.strip().lower().startswith("files:"):
                            current_game.pop("file", None)

                        if not roms:
                            # 兼容只有 file: 的写法
                            fpath = current_game.get("file")
                            if isinstance(fpath, str) and fpath.strip():
                                roms = [fpath]

                        current_game["roms"] = roms

                        # 优先保证 file 和 roms[0] 对齐
                        if roms:
                            if "file" not in current_game or not current_game["file"]:
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
                if key in ("launch", "description", "ignore-files", "extension", "extensions", "files"):
                    current_key = key
                    if key == "files":
                        # files: 是纯多行列表，不需要把首行带进去
                        buf = []
                        continue


                    # ---- 特殊处理 extension：支持单行写法 "extension: 7z, zip" ----
                    if key in ("extension", "extensions") and in_header:
                        if value:
                            # 单行：直接解析 value → ["7z", "zip"]
                            exts = []
                            for part in value.split(","):
                                p = part.strip()
                                if p:
                                    exts.append(p)
                            header["extensions"] = exts
                            # ★ 关键：既然是单行解析完成，就不要再进入多行流程了
                            current_key = None
                            buf = []
                            continue
                        else:
                            # 真·多行 extension:
                            # extension:
                            #   7z
                            #   zip
                            current_key = key
                            buf = [f"{key}:"]
                    else:
                        # 其他多行字段（launch / description / ignore-files）
                        current_key = key
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

        roms = [
            r for r in roms
            if isinstance(r, str)
            and r.strip()
            and not r.strip().lower().startswith("files:")
        ]

        fval = current_game.get("file")
        if isinstance(fval, str) and fval.strip().lower().startswith("files:"):
            current_game.pop("file", None)

        if not roms:
            fpath = current_game.get("file")
            if isinstance(fpath, str) and fpath.strip():
                roms = [fpath]

        current_game["roms"] = roms

        if roms:
            if "file" not in current_game or not current_game["file"]:
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
