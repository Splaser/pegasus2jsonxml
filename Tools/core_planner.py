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

    # 2) platform metadata default
    core = payload.get("default_core")
    if core:
        return core

    # 3) 静态平台表
    core = PLATFORM_DEFAULT_CORES.get(platform_key)
    if core:
        return core

    # 4) 看 file / roms 的扩展名兜底
    file_name = game.get("file") or ""
    import os
    _, ext = os.path.splitext(file_name)
    ext = ext.lower()

    core = EXT_CORE_MAP.get(ext)
    if core:
        return core

    return None
