#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pegasus metadata 扫描 & 解析

暴露一个函数：
    parse_pegasus_metadata(path: str) -> (header: dict, games: list[dict])

header:
    - collection
    - ignore_files
    - extensions
    - default_sort_by
    - launch        # 单行（launch: 后面）
    - launch_block  # 整个缩进块（包括第一行 "launch:"）

games 中每一项可能包含：
    - game          # 名称
    - file          # 主 rom
    - roms          # list[str]
    - sort_by
    - developer
    - description
    - launch        # 首行（不太用）
    - launch_override # 整个缩进块
    - core_override   # 从 launch_override 里解析出的 core.so 文件名
"""

from __future__ import annotations
import os
from typing import Tuple, Dict, Any, List


def parse_pegasus_metadata(path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    header: Dict[str, Any] = {}
    games: List[Dict[str, Any]] = []

    current: Dict[str, Any] | None = None
    in_global_launch = False
    in_game_launch = False
    in_files = False
    scratch_lines: List[str] = []

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            stripped = line.strip()

            # -----------------------
            # Global launch block
            # -----------------------
            if in_global_launch:
                if line.startswith("  "):
                    scratch_lines.append(line.rstrip())
                    continue
                else:
                    # end global launch
                    in_global_launch = False
                    header["launch_block"] = "\n".join(scratch_lines)

            # -----------------------
            # game launch override
            # -----------------------
            if in_game_launch:
                if line.startswith("  "):
                    scratch_lines.append(line.rstrip())
                    continue
                else:
                    # end game launch
                    in_game_launch = False
                    if current is not None:
                        current["launch_override"] = "\n".join(scratch_lines)

            # 空行：结束 files 区
            if stripped == "":
                in_files = False
                continue

            # -----------------------
            # new game block
            # -----------------------
            if line.startswith("game:"):
                # 收尾前一个 game
                if current is not None:
                    if "roms" not in current and "file" in current:
                        current["roms"] = [current["file"]]
                    games.append(current)

                name = line.split(":", 1)[1].strip()
                current = {"game": name}
                continue

            # -----------------------
            # header zone
            # -----------------------
            if current is None:
                if line.startswith("collection:"):
                    header["collection"] = line.split(":", 1)[1].strip()

                elif line.startswith("ignore-files:"):
                    header["ignore_files"] = []

                elif "ignore_files" in header and line.startswith("  "):
                    header["ignore_files"].append(stripped)

                elif line.startswith("extension:"):
                    header["extensions"] = [
                        x.strip()
                        for x in stripped.split(":", 1)[1].split(",")
                    ]

                elif line.startswith("sort-by:"):
                    header["default_sort_by"] = line.split(":", 1)[1].strip()

                elif line.startswith("launch:"):
                    in_global_launch = True
                    scratch_lines = [line.rstrip()]
                    header["launch"] = line.split(":", 1)[1].strip()

                continue

            # -----------------------
            # game zone
            # -----------------------
            if line.startswith("file:"):
                val = line.split(":", 1)[1].strip()
                current["file"] = val
                current["roms"] = [val]

            elif line.startswith("files:"):
                in_files = True
                current["roms"] = []

            elif in_files and line.startswith("  "):
                current["roms"].append(stripped)

            elif line.startswith("sort-by:"):
                current["sort_by"] = line.split(":", 1)[1].strip()

            elif line.startswith("developer:"):
                current["developer"] = line.split(":", 1)[1].strip()

            elif line.startswith("description:"):
                current["description"] = line.split(":", 1)[1].strip()

            elif line.startswith("launch:"):
                in_game_launch = True
                scratch_lines = [line.rstrip()]
                current["launch"] = line.split(":", 1)[1].strip()

    # finalize last game
    if current is not None:
        if "roms" not in current and "file" in current:
            current["roms"] = [current["file"]]
        games.append(current)

    # 额外处理：从 launch_override 里提取 core 覆盖
    for g in games:
        lo = g.get("launch_override")
        if not lo:
            continue
        for ln in lo.split("\n"):
            if "-e LIBRETRO" in ln:
                core = ln.split()[-1]
                g["core_override"] = os.path.basename(core)

    return header, games
