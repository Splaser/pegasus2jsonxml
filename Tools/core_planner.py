# Tools/core_planner.py
from __future__ import annotations
from typing import Dict, Any, Optional

# 1. 平台级默认 core 映射（兜底）
PLATFORM_DEFAULT_CORES: Dict[str, str] = {
    "ss_hack": "mednafen_saturn_hw",
    "dc": "flycast",
    "psx": "pcsx_rearmed",
    # ...
}

# 2. 扩展名 → core 的兜底映射（再兜底）
EXT_CORE_MAP: Dict[str, str] = {
    ".chd": "mednafen_saturn_hw",   # Saturn/DC 你可以按平台 key 再细分
    ".cue": "mednafen_psx_hw",
    ".iso": "mednafen_saturn",
    ".bin": "mednafen_psx_hw",
}


def choose_core_for_game(
    platform_key: str,
    payload: Dict[str, Any],
    game: Dict[str, Any],
) -> Optional[str]:
    """
    根据以下优先级选择最终 core_name:

    1) game["core_override"]
    2) payload["default_core"]
    3) PLATFORM_DEFAULT_CORES[platform_key]
    4) 根据扩展名猜一个（EXT_CORE_MAP）
    """
    # 1) per-game override
    core = game.get("core_override")
    if core:
        return core

    platform_key_lower = (platform_key or "").lower()

    # 2) 平台级默认 core（来自 export_to_json / header launch 解析）
    core = payload.get("default_core")
    if core:
        return core

    # ------- 重点：PS2 目前统一走 Android AetherSX2 / NetherSX2 standalone -------
    # 暂时不自动分配 libretro core，防止 .chd 被误绑 Saturn/DC
    if platform_key_lower in ("ps2", "playstation2"):
        return None

    # 3) 平台 key 兜底（注意用小写 key）
    core = PLATFORM_DEFAULT_CORES.get(platform_key_lower)
    if core:
        return core

    # 4) 看 file / roms 的扩展名兜底
    rom_path = None

    # 允许 game["file"] / game["rom"] / game["roms"][0] 这几种
    if isinstance(game.get("file"), str):
        rom_path = game["file"]
    elif isinstance(game.get("rom"), str):
        rom_path = game["rom"]
    else:
        roms = game.get("roms") or []
        if roms and isinstance(roms[0], str):
            rom_path = roms[0]

    if rom_path:
        _, _, ext = rom_path.rpartition(".")
        if ext:
            ext = "." + ext.lower()
            core = EXT_CORE_MAP.get(ext)
            if core:
                return core

    # 实在猜不到就 None，让上层决定是报错还是走原始 launch
    return None