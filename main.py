#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目 CLI 入口

目前支持：
    python main.py              # 等价于 python main.py all
    python main.py all          # 导出所有平台
    python main.py dc           # 只导出 dc 对应的平台
"""

from __future__ import annotations
import argparse

from Tools.export_to_json import discover_platforms, export_platform


def run_export(target: str = "all", resource_root: str = "Resource"):
    platforms = discover_platforms(resource_root)

    if not platforms:
        print(f"[WARN] 在 {resource_root} 下没有发现任何 metadata.pegasus.txt")
        return

    if target == "all":
        for key, (name, meta_path) in platforms.items():
            export_platform(key, name, meta_path)
    else:
        if target not in platforms:
            print(f"[ERROR] 找不到平台 key: {target}")
            print("可用平台:")
            for k in sorted(platforms.keys()):
                print("  ", k)
            return

        name, meta_path = platforms[target]
        export_platform(target, name, meta_path)


def main():
    parser = argparse.ArgumentParser(
        description="Pegasus metadata → jsondb 导出器"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        help="平台 key（dc / fbneo_act ...）或 all（默认）",
    )
    parser.add_argument(
        "--resource-root",
        default="Resource",
        help="资源根目录，默认 ./Resource",
    )

    args = parser.parse_args()
    run_export(args.target, args.resource_root)


if __name__ == "__main__":
    main()
