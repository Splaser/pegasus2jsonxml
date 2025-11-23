#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse

from Tools.export_to_json import export_platform_to_json


def slugify(name: str) -> str:
    # 简单一点就够用：全小写，空格 -> 下划线
    return (
        name.replace("\\", "/")
        .split("/")[-1]
        .strip()
        .lower()
        .replace(" ", "_")
    )


def discover_platforms(resource_root: str = "Resource"):
    """
    自动扫描 Resource 下所有子目录，找 metadata.pegasus.txt

    返回 dict:
        key -> (平台显示名, meta_path)
    """
    platforms = {}

    if not os.path.isdir(resource_root):
        return platforms

    for entry in os.listdir(resource_root):
        platform_dir = os.path.join(resource_root, entry)
        if not os.path.isdir(platform_dir):
            continue

        meta_path = os.path.join(platform_dir, "metadata.pegasus.txt")
        if not os.path.isfile(meta_path):
            continue

        key = slugify(entry)          # 例如 "DC" -> "dc", "FBNEO ACT" -> "fbneo_act"
        name = entry                  # 人类可读平台名，保持原文件夹名
        platforms[key] = (name, meta_path)

    return platforms


def main():
    parser = argparse.ArgumentParser(description="Pegasus metadata -> jsondb exporter")
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        help="平台 key（如 dc / fbneo_act）或 all（默认：all）",
    )
    parser.add_argument(
        "--resource-root",
        default="Resource",
        help="metadata 根目录（默认 Resource）",
    )
    parser.add_argument(
        "--out-root",
        default="jsondb",
        help="json 输出目录（默认 jsondb）",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="仅列出可用平台，不导出",
    )

    args = parser.parse_args()

    platforms = discover_platforms(args.resource_root)

    if not platforms:
        print(f"[WARN] 在 {args.resource_root} 下没有找到任何 metadata.pegasus.txt")
        return

    if args.list:
        print("可用平台：")
        for key, (name, meta_path) in sorted(platforms.items()):
            print(f"  {key:15s} -> {name} ({meta_path})")
        return

    if args.target == "all":
        for key, (name, meta_path) in sorted(platforms.items()):
            print(f"[INFO] 导出 {key} ({name}) ...")
            out_path = export_platform_to_json(key, name, meta_path, out_root=args.out_root)
            print(f"       -> {out_path}")
    else:
        if args.target not in platforms:
            print(f"[ERROR] 找不到平台 key: {args.target}")
            print("可用平台（--list 查看详情）：")
            for k in sorted(platforms.keys()):
                print("  ", k)
            return

        name, meta_path = platforms[args.target]
        print(f"[INFO] 导出 {args.target} ({name}) ...")
        out_path = export_platform_to_json(args.target, name, meta_path, out_root=args.out_root)
        print(f"[OK] -> {out_path}")


if __name__ == "__main__":
    main()
