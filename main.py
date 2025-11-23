#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse

from Tools.export_to_json import export_platform_to_json
from Utils.helpers import discover_platforms
from Tools.base import verify_closure



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
    parser.add_argument(
        "--verify",
        action="store_true",
        help="执行闭合性验证：parse → dump → parse 是否保持一致"
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
    if args.verify:
        print("[TEST] 正在验证闭合性 (parse → dump → parse)...")
        ok = verify_closure(meta_path)
        if ok:
            print("[OK] 闭合性成立，此平台可安全 round-trip")
        else:
            print("[FAIL] 闭合性失败，需要检查 parser/writer")
        return
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
