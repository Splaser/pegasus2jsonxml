#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

JSONDB_DIR = Path("jsondb")
AI_DIR = Path("descriptions_ai")   # 你放 *_out.jsonl 的目录

def load_patches() -> dict:
    """
    从 descriptions_ai/*.jsonl 读取所有改写后的 description。
    返回 dict[(platform_key, id)] = new_description
    """
    patches: dict[tuple[str, str], str] = {}

    for path in sorted(AI_DIR.glob("batch_*_out.jsonl")):
        print(f"[LOAD] {path}")
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)

                platform_key = obj.get("platform_key")
                gid = obj.get("id")
                desc = obj.get("description", "")

                if not platform_key or not gid:
                    continue

                patches[(platform_key, gid)] = desc

    print(f"[INFO] 共加载补丁条目: {len(patches)}")
    return patches


def apply_patches(patches: dict[tuple[str, str], str]):
    """
    遍历 jsondb/*.json，按 (platform_key, id) 回写 description。
    """
    total_updated = 0

    for json_path in sorted(JSONDB_DIR.glob("*.json")):
        platform_key = json_path.stem
        with json_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        changed = False
        games = payload.get("games", [])

        for g in games:
            gid = g.get("id")
            if not gid:
                continue

            key = (platform_key, gid)
            if key in patches:
                new_desc = patches[key]
                old_desc = g.get("description", "")

                if new_desc != old_desc:
                    g["description"] = new_desc
                    changed = True
                    total_updated += 1

        if changed:
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"[WRITE] 更新 {json_path}")

    print(f"[DONE] 总共更新 description 条目: {total_updated}")


def main():
    patches = load_patches()
    apply_patches(patches)


if __name__ == "__main__":
    main()
