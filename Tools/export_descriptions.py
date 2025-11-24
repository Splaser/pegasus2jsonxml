#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

JSONDB_DIR = Path("jsondb")


def detect_hack(platform_key, game):
    # 1) Platform 级别 hack → 100% hack
    if platform_key.endswith("_hack"):
        return True

    # 2) 文件夹里明确 hack 的目录
    # 如果未来你想扩展，例如：
    # if "hack" in platform_display_name.lower(): return True

    # 3)（可选）再用轻量级关键词辅助
    name = (game.get("game") or "").lower()
    file = (game.get("file") or "").lower()
    keywords = ["hack", "改版", "修正版"]

    if any(k in name or k in file for k in keywords):
        return True

    return False


def export_descriptions(out_path: Path = Path("descriptions_raw.jsonl")):
    """
    扫描 jsondb/*.json，把所有游戏的描述导出到 JSONL：
    每行一个对象：
    {
      "platform_key": "fbneo_act_v",
      "platform": "FBNEO ACT V",
      "id": "...",
      "game": "城市快打",
      "developer": "城市快打",
      "description": "...",
      "file": "downtown.zip"
    }
    """
    with out_path.open("w", encoding="utf-8") as f_out:
        for json_path in sorted(JSONDB_DIR.glob("*.json")):
            with json_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            platform_key = json_path.stem
            platform_name = payload.get("platform", platform_key)

            for g in payload.get("games", []):
                rec = {
                    "platform_key": platform_key,
                    "platform": platform_name,
                    "id": g.get("id"),
                    "game": g.get("game"),
                    "developer": g.get("developer"),
                    "file": g.get("file"),
                    "description": g.get("description", ""),
                    "is_hack": detect_hack(platform_key, g),
                }
                f_out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"[OK] 导出完成 -> {out_path}")


if __name__ == "__main__":
    export_descriptions()
