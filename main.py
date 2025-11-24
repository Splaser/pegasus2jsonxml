#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
from pathlib import Path

from Tools.export_to_json import export_platform_to_json
from Utils.helpers import discover_platforms
from Tools.base import verify_closure
from Tools.json_to_metadata import json_to_metadata

from Converters.daijisho_exporter import export_daijisho
from Converters.esde_exporter import export_esde
from Converters.retroarch_exporter import export_retroarch


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
        help="执行闭合性验证：parse → dump → parse 是否保持一致",
    )
    parser.add_argument(
        "--from-json",
        action="store_true",
        help="从 jsondb 生成 / 覆盖 CanonicalMetadata/<key>/metadata.pegasus.txt",
    )

    parser.add_argument(
        "--export-daijisho",
        action="store_true",
        help="导出 Daijisho database JSON"
    )

    parser.add_argument(
        "--export-esde",
        action="store_true",
        help="导出 ES-DE gamelist.xml + media 结构"
    )

    parser.add_argument(
        "--export-ra",
        action="store_true",
        help="导出 RetroArch per-game override 配置"
    )


    args = parser.parse_args()

    platforms = discover_platforms(args.resource_root)

    if not platforms:
        print(f"[WARN] 在 {args.resource_root} 下没有找到任何 metadata.pegasus.txt")
        return

    # 1) 仅列出平台
    if args.list:
        print("可用平台：")
        for key, (name, meta_path) in sorted(platforms.items()):
            print(f"  {key:15s} -> {name} ({meta_path})")
        return

    # 2) 闭合性验证模式（不导出 json，不写回）
    if args.verify:
        print("[TEST] 正在验证闭合性 (parse → dump → parse)...")

        if args.target == "all":
            all_ok = True
            for key, (name, meta_path) in sorted(platforms.items()):
                print(f"[TEST] 平台 {key} ({name}) ...")
                ok = verify_closure(meta_path)
                if ok:
                    print(f"[OK] {key} 闭合性成立")
                else:
                    print(f"[FAIL] {key} 闭合性失败")
                    all_ok = False
            if all_ok:
                print("[OK] 所有平台闭合性成立，可安全 round-trip")
            else:
                print("[WARN] 部分平台闭合性失败，请检查上方日志")
        else:
            if args.target not in platforms:
                print(f"[ERROR] 找不到平台 key: {args.target}")
                print("可用平台（--list 查看详情）：")
                for k in sorted(platforms.keys()):
                    print("  ", k)
                return
            name, meta_path = platforms[args.target]
            ok = verify_closure(meta_path)
            if ok:
                print(f"[OK] {args.target} ({name}) 闭合性成立")
            else:
                print(f"[FAIL] {args.target} ({name}) 闭合性失败")

        return

    # 3) 从 jsondb 写回 CanonicalMetadata
    if args.from_json:
        if args.target == "all":
            for key, (name, _) in sorted(platforms.items()):
                json_path = os.path.join(args.out_root, f"{key}.json")
                print(f"[INFO] 从 {json_path} 恢复 {key} ...")
                out_path = json_to_metadata(key, json_path, output_root="CanonicalMetadata")
                print(f"       -> {out_path}")
        else:
            key = args.target
            json_path = os.path.join(args.out_root, f"{key}.json")
            if not os.path.exists(json_path):
                print(f"[ERROR] 找不到 json: {json_path}")
                return
            print(f"[INFO] 从 {json_path} 恢复 {key} ...")
            out_path = json_to_metadata(key, json_path, output_root="CanonicalMetadata")
            print(f"[OK] -> {out_path}")
        return

    # 4) 默认行为：metadata -> jsondb 导出
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
    
    # 5) Exporter：Daijisho / ES-DE / RA
    if args.export_daijisho or args.export_esde or args.export_ra:
        if args.target == "all":
            for key, (name, _) in sorted(platforms.items()):
                json_path = Path(args.out_root) / f"{key}.json"

                if args.export_daijisho:
                    export_daijisho(key, json_path, Path("Export_Daijisho"))

                if args.export_esde:
                    export_esde(key, json_path, Path("Export_ESDE"))

                if args.export_ra:
                    export_retroarch(key, json_path, Path("Export_RetroArch"))

        else:
            key = args.target
            json_path = Path(args.out_root) / f"{key}.json"

            if args.export_daijisho:
                export_daijisho(key, json_path, Path("Export_Daijisho"))

            if args.export_esde:
                export_esde(key, json_path, Path("Export_ESDE"))

            if args.export_ra:
                export_retroarch(key, json_path, Path("Export_RetroArch"))

        return



if __name__ == "__main__":
    main()
