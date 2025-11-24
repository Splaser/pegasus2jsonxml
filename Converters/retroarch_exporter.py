# Converters/retroarch_exporter.py

import json
from pathlib import Path

def export_retroarch(platform: str, json_path: Path, out_dir: Path):
    """
    生成 RetroArch 的 per-game override。
    """

    data = json.loads(json_path.read_text(encoding="utf-8"))
    games = data.get("games", [])

    for g in games:
        cfg_path = build_override(platform, g, out_dir)
        # 未来支持更多cfg字段

    print(f"[OK] RetroArch override export complete for {platform}")


def build_override(platform: str, game: dict, out_dir: Path) -> Path:
    """
    生成单文件 override。
    """
    core = game.get("core_override")
    if not core:
        return out_dir

    cfg_dir = out_dir / core
    cfg_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{game.get('id', game.get('file'))}.cfg"
    cfg_path = cfg_dir / filename

    cfg_path.write_text(
        f"# Auto-generated override\n"
        f"input_overlay_enable = \"false\"\n"
        f"# (未来更多字段…)\n",
        encoding="utf-8"
    )

    return cfg_path
