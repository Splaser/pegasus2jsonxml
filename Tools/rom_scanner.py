#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROM 扫描与哈希工具

用途：
- 给定一个 jsondb/<platform>.json
- 给定实际 ROM 根目录（该 json 里的 file / roms 相对路径均从此处出发）
- 扫描所有实际存在的 ROM 文件
- 计算 sha256 / 文件大小
- 生成一个独立的 romhash db（后续可挂回 jsondb 或单独使用）

示例：
    python -m Tools.rom_scanner dc \
        --json jsondb/dc.json \
        --rom-root /mnt/roms/DC \
        --out romdb/dc_romhash.json
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


HEADER_BYTES = 65536

class RomHasher:
    """
    统一的 ROM Hash 工具：
      - 一个实例可复用多次计算（减少 hashlib init 开销）
      - 单次 read 完成 size / sha256_full / md5_header
    """

    def __init__(self, header_bytes: int = HEADER_BYTES):
        self.header_bytes = header_bytes
        self.sha_factory = hashlib.sha256   # 缓存构造函数
        self.md5_factory = hashlib.md5      # 缓存构造函数

    def hash_rom(self, path: Path) -> Tuple[int, str, Optional[str]]:
        """
        返回: (size, sha256_full, md5_header)
        """
        sha = self.sha_factory()
        md5 = self.md5_factory()

        size = 0
        remaining = self.header_bytes

        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                if not chunk:
                    break

                size += len(chunk)
                sha.update(chunk)

                # 前 header_bytes bytes 给 md5_header 用
                if remaining > 0:
                    if len(chunk) <= remaining:
                        md5.update(chunk)
                        remaining -= len(chunk)
                    else:
                        md5.update(chunk[:remaining])
                        remaining = 0

        sha256_full = sha.hexdigest()
        md5_header = md5.hexdigest() if self.header_bytes > 0 else None
        return size, sha256_full, md5_header



def scan_roms_for_platform(
    platform: str,
    json_path: Path,
    rom_root: Path,
) -> Dict[str, Any]:
    """
    从指定 jsondb 平台文件扫描实际 ROM 文件，返回一个结构化 romhash 结果。

    约定：
    - json["games"][i]["roms"] 里的每一条，都是相对 rom_root 的路径
      （可以包含子目录，比如 "机动战士高达/.../Disc 1.chd"）
    - 如果 json 里没有 "roms"，fallback 用 "file"
    """
    with json_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    hasher = RomHasher(header_bytes=HEADER_BYTES)

    games: List[Dict[str, Any]] = payload.get("games", [])

    results: Dict[str, Any] = {
        "platform": platform,
        "json_source": str(json_path),
        "rom_root": str(rom_root),
        "roms": [],   # 每个元素是一个 dict
    }

    for idx, game in enumerate(games):
        game_title: str = game.get("game", "") or ""
        game_id: Optional[str] = game.get("id")  # 若你后面已加 id，这里顺带带上

        rom_list: List[str] = game.get("roms") or []
        if not rom_list:
            # 兼容旧 schema，roms 为空时用 file 字段
            file_name = game.get("file")
            if file_name:
                rom_list = [file_name]

        for rom_rel in rom_list:
            rom_rel = rom_rel.strip()
            if not rom_rel:
                continue

            full_path = rom_root / rom_rel
            entry: Dict[str, Any] = {
                "platform": platform,
                "game_title": game_title,
                "game_id": game_id,
                "rom_rel": rom_rel,
                "rom_path": str(full_path),
                "exists": full_path.is_file(),
                "size": None,
                "sha256_full": None,
                "md5_header": None,
                "header_bytes": HEADER_BYTES,
            }


            if full_path.is_file():
                size, sha256_full, md5_header = hasher.hash_rom(full_path)
                entry["size"] = size
                entry["sha256_full"] = sha256_full
                entry["md5_header"] = md5_header

            results["roms"].append(entry)

    return results


def save_romhash_db(data: Dict[str, Any], out_path: Path) -> None:
    """保存 rom 扫描结果为 json."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="扫描实际 ROM 文件并生成 sha256 romhash db"
    )
    parser.add_argument(
        "platform",
        help="平台 key（例如 dc / fbneo_act / mame_fly_v）",
    )
    parser.add_argument(
        "--json",
        required=True,
        help="对应平台的 jsondb 路径，例如 jsondb/dc.json",
    )
    parser.add_argument(
        "--rom-root",
        required=True,
        help="该平台 ROM 的根目录，例如 /mnt/roms/DC",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="输出 romhash db 路径（默认：romdb/<platform>_romhash.json）",
    )

    args = parser.parse_args()

    platform = args.platform
    json_path = Path(args.json)
    rom_root = Path(args.rom_root)

    if not json_path.is_file():
        print(f"[ERROR] 找不到 jsondb 文件: {json_path}")
        return

    if not rom_root.is_dir():
        print(f"[WARN] ROM 根目录不存在: {rom_root}")

    print(f"[INFO] 平台: {platform}")
    print(f"[INFO] jsondb: {json_path}")
    print(f"[INFO] rom_root: {rom_root}")

    results = scan_roms_for_platform(platform, json_path, rom_root)

    # 统计一下命中情况
    total = len(results["roms"])
    found = sum(1 for r in results["roms"] if r["exists"])
    print(f"[INFO] 共 {total} 条 rom 记录，找到实际文件 {found} 条")

    # 输出路径
    if args.out:
        out_path = Path(args.out)
    else:
        out_path = Path("romdb") / f"{platform}_romhash.json"

    save_romhash_db(results, out_path)
    print(f"[OK] romhash db 已保存 -> {out_path}")


if __name__ == "__main__":
    main()
