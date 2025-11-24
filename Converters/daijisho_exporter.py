# Converters/daijisho_exporter.py

import json
from pathlib import Path

def export_daijisho(platform: str, json_path: Path, out_dir: Path):
    """
    jsondb/<platform>.json -> daijisho/<platform>.json
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # 解析 jsondb
    data = json.loads(json_path.read_text(encoding="utf-8"))
    games = data.get("games", [])

    output = []

    for g in games:
        entry = transform_to_daijisho(platform, g, data)
        output.append(entry)

    out_path = out_dir / f"{platform}.json"
    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"[OK] Daijisho export -> {out_path}")
    return out_path


def transform_to_daijisho(platform: str, game: dict, payload: dict) -> dict:
    """
    真正的字段映射逻辑后续再补，这里先留个空壳。
    """
    return {
        "title": game.get("game"),
        "romPath": game.get("file"),
        # 待补 launchIntent / parameters / assets
    }
