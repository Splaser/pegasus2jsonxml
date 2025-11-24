#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

JSONDB_DIR = Path("jsondb")


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
                }
                f_out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"[OK] 导出完成 -> {out_path}")


if __name__ == "__main__":
    export_descriptions()
