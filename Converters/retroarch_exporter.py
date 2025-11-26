# Converters/retroarch_exporter.py

import json
from pathlib import Path
from typing import Any, Dict


# 一些针对安卓 RA 的默认 per-game override，可以按需增减
DEFAULT_ANDROID_OVERRIDES: Dict[str, Any] = {
    # 典型安卓场景：不启用 overlay，避免误触
    "input_overlay_enable": False,
    # 一般不希望 per-game 自动读档
    "savestate_auto_load": False,
    "savestate_auto_index": False,
    # 按需加：比如强制全屏纵横比
    # "video_scale_integer": False,
    # "video_aspect_ratio_auto": True,
}


def export_retroarch(platform: str, json_path: Path, out_dir: Path):
    """
    从 jsondb 生成 RetroArch 的 per-game override（安卓可用版本）。

    JSON 里每个 game 支持的字段约定为：
      - id:            可选，内部 id，没则用 file 推导
      - file:          可选，原始 ROM/镜像文件名（建议带扩展名）
      - core_override: 必选（否则跳过），对应 RA config/<core_name>/ 目录名
      - ra_override:   可选 dict，用于映射到 RA 的 cfg 项，如：
                       {
                         "video_shader_enable": true,
                         "video_shader": "/storage/emulated/0/RetroArch/shaders/my.slangp"
                       }

    :param platform: 平台标识（仅写在注释里，方便 debug）
    :param json_path: jsondb 路径
    :param out_dir: RetroArch config 根目录，比如：
                    /storage/emulated/0/RetroArch/config
    """
    if not json_path.is_file():
        raise FileNotFoundError(f"json_path not found: {json_path}")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    games = data.get("games", [])
    if not isinstance(games, list):
        raise ValueError(f"json.games 必须是 list，当前类型: {type(games)}")

    generated = 0
    skipped_no_core = 0

    for g in games:
        cfg_path = build_override(platform, g, out_dir)
        if cfg_path is None:
            skipped_no_core += 1
        else:
            generated += 1

    print(
        f"[OK] RetroArch override export complete for {platform} | "
        f"generated={generated}, skipped_no_core={skipped_no_core}"
    )


def build_override(platform: str, game: dict, out_dir: Path) -> Path | None:
    """
    为单个 game 生成 per-game override cfg。

    目录结构会被生成为：
        out_dir / <core_override> / <content_name>.cfg

    其中 <content_name> 的优先级：
        game['ra_content_name'] > basename(game['file']) > game['id'] > "unknown"
    """
    core = game.get("core_override")
    if not core:
        # 没指定 core 的条目，对 RA 来说没法挂载 override，直接跳过
        return None

    cfg_dir = out_dir / core
    cfg_dir.mkdir(parents=True, exist_ok=True)

    filename_base = _infer_content_name(game)
    filename = f"{filename_base}.cfg"
    cfg_path = cfg_dir / filename

    # 1. 先合并默认安卓 override
    cfg_dict: Dict[str, Any] = dict(DEFAULT_ANDROID_OVERRIDES)

    # 2. 合并 game 级别 override（完全覆盖同名 key）
    # 支持两种字段名，方便你在 jsondb 里折腾：
    #   - "ra_override"
    #   - "retroarch_override"
    game_override = (
        game.get("ra_override")
        or game.get("retroarch_override")
        or {}
    )
    if not isinstance(game_override, dict):
        raise ValueError(
            f"game.ra_override 必须是 dict，当前类型: {type(game_override)}，game={game!r}"
        )

    cfg_dict.update(game_override)

    # 3. 写入 cfg
    lines = [
        "# Auto-generated per-game override",
        f"# platform = {platform}",
        f"# id       = {game.get('id')}",
        f"# file     = {game.get('file')}",
        "",
    ]

    for key, value in cfg_dict.items():
        ra_value = _normalize_ra_value(value)
        lines.append(f'{key} = "{ra_value}"')

    cfg_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return cfg_path


def _infer_content_name(game: dict) -> str:
    """
    RA per-game override 的文件名必须和“内容文件名”一致，
    否则 override 挂不上去，所以尽量从 file 里推导。

    优先级：
      1. game['ra_content_name'] （你手动指定的真实内容名）
      2. Path(game['file']).name 的 stem
      3. game['id']
      4. "unknown"
    再做一次简单 sanitize，去掉不适合做文件名的字符。
    """
    # 你也可以在 jsondb 里手动提供一个专门用于 cfg 的名字
    if game.get("ra_content_name"):
        name = str(game["ra_content_name"])
    else:
        file_name = game.get("file")
        if isinstance(file_name, str) and file_name.strip():
            name = Path(file_name).stem
        elif game.get("id"):
            name = str(game["id"])
        else:
            name = "unknown"

    # Android 文件名里出现 / : 之类，保险起见还是替换掉
    bad_chars = '/\\:*?"<>|'
    for ch in bad_chars:
        name = name.replace(ch, "_")
    name = name.strip()
    return name or "unknown"


def _normalize_ra_value(v: Any) -> str:
    """
    把 Python 值统一转成 RA cfg 里的字符串值。

    RA cfg 里：
      - bool 一般是 "true"/"false"
      - 数值直接字符串即可
      - 其他就按原样 str
    """
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        # 有些字段（比如 aspect_ratio）确实是浮点数
        return str(v)
    return str(v)
