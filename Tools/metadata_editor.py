# Tools/metadata_editor.py

from __future__ import annotations
from typing import Dict, List, Any, Tuple, Optional

from .metadata_scanner import parse_pegasus_metadata
from .metadata_writer  import dump_pegasus_metadata


def _index_games_by_key(games: List[Dict[str, Any]]) -> Dict[str, int]:
    index = {}
    for i, g in enumerate(games):
        roms = g.get("roms") or []
        for r in roms:
            index[r] = i
        # 再加一个标题兜底 key
        title = g.get("game")
        if title and title not in index:
            index[title] = i
    return index


def upsert_game(
    meta_path: str,
    rom_path: str,
    *,
    title: Optional[str] = None,
    developer: Optional[str] = None,
    description: Optional[str] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> None:
    """
    在指定 metadata.pegasus.txt 里：
    - 如果已有 rom_path 对应的 game，则更新它；
    - 否则新增一条 game。
    """
    header, games = parse_pegasus_metadata(meta_path)
    idx_map = _index_games_by_key(games)

    if rom_path in idx_map:
        g = games[idx_map[rom_path]]
        roms = g.get("roms") or []
        if rom_path not in roms:
            roms.append(rom_path)
            g["roms"] = roms
    else:
        g = {"game": title or rom_path, "roms": [rom_path]}
        games.append(g)

    # 更新字段（只覆盖非 None）
    if title is not None:
        g["game"] = title
    if developer is not None:
        g["developer"] = developer
    if description is not None:
        g["description"] = description

    if extra_fields:
        for k, v in extra_fields.items():
            if v is not None:
                g[k] = v

    dump_pegasus_metadata(meta_path, header, games)
