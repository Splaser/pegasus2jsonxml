# Tools/metadata_writer.py

from __future__ import annotations
from typing import Dict, List, Any, TextIO
from pathlib import PurePosixPath


def _write_header(f: TextIO, header: Dict[str, Any]) -> None:
    # 这里把 parse_pegasus_metadata 得到的规范字段写回 Pegasus 语法
    collection = header.get("collection")
    if collection:
        f.write(f'collection: {collection}\n')

    default_sort_by = header.get("default_sort_by")
    if default_sort_by:
        f.write(f'sort-by: {default_sort_by}\n')

    # launch_block（多行）
    launch_block = header.get("launch_block")
    if launch_block:
        lines = launch_block.splitlines()
        if len(lines) == 1:
            f.write(f'launch: {lines[0]}\n')
        else:
            f.write('launch:\n')
            for line in lines:
                f.write(f'  {line}\n')

    # ignore_files 多行输出
    ignore_files = header.get("ignore_files") or []
    if ignore_files:
        f.write('ignore-files:\n')
        for pat in ignore_files:
            f.write(f'  {pat}\n')

    # extensions 支持多行
    exts = header.get("extensions") or []
    # 兜底：如果是逗号分隔的字符串，拆成 list
    if isinstance(exts, str):
        tmp = []
        for part in exts.split(","):
            p = part.strip()
            if p:
                tmp.append(p)
        exts = tmp

    if exts:
        f.write("extension:\n")
        for ext in exts:
            f.write(f"  {ext}\n")


        f.write("\n")  # 头部和 games 之间空一行

def _is_multi_disc(game: dict) -> bool:
    # 你这边内部结构可能是 roms，也可能是 files
    roms = game.get("roms")
    if isinstance(roms, list) and len(roms) > 1:
        return True

    files = game.get("files")
    if isinstance(files, list) and len(files) > 1:
        return True

    # 有些导入器会同时存 file + roms，file不算
    return False

def _infer_media_base_from_multifiles(game: dict) -> str | None:
    """
    For multi-disc entries like:
      009/Lunar 2 Eternal Blue (Japan).m3u
      009/... (DISC 1).chd
    return "009".
    """
    lst = game.get("roms")
    if not (isinstance(lst, list) and len(lst) > 1):
        lst = game.get("files")

    if not (isinstance(lst, list) and len(lst) > 1):
        return None

    first = lst[0]
    if not isinstance(first, str) or not first.strip():
        return None

    parts = PurePosixPath(first.strip()).parts
    if len(parts) >= 2:
        return parts[0]  # <- "009" / "012"
    return None

def _collect_assets(game: dict) -> dict:
    assets = {}
    a = game.get("assets")
    if isinstance(a, dict):
        for k, v in a.items():
            if isinstance(v, str) and v.strip():
                assets[k] = v.strip()

    # legacy flat keys: assets.xxx
    for k, v in game.items():
        if isinstance(k, str) and k.startswith("assets.") and isinstance(v, str) and v.strip():
            sub = k.split(".", 1)[1].strip()
            if sub and sub not in assets:
                assets[sub] = v.strip()

    return assets

def _rewrite_media_path_keep_filename(v: str, media_base: str) -> str:
    """
    media/ANYTHING/filename -> media/<media_base>/filename
    If not starting with media/, keep unchanged.
    """
    p = PurePosixPath(v)
    parts = p.parts
    if len(parts) >= 2 and parts[0] == "media":
        return str(PurePosixPath("media") / media_base / parts[-1])
    return v

def _emit_assets_lines(f, game: dict):
    # ✅ 只在多碟时显式写回
    if not _is_multi_disc(game):
        return

    assets = _collect_assets(game)

    # ✅ 多碟但 assets 缺失：按 media/<firstDir>/ 默认补三条（可选）
    media_base = _infer_media_base_from_multifiles(game)
    if not assets and media_base:
        assets = {
            "box_front": f"media/{media_base}/boxFront.png",
            "logo":      f"media/{media_base}/logo.png",
            "video":     f"media/{media_base}/video.mp4",
        }

    if not assets:
        return

    # ✅ 关键：多碟时强制把 media 目录改成 firstDir（009/012）
    if media_base:
        for k in list(assets.keys()):
            v = assets[k]
            if isinstance(v, str) and v.strip():
                assets[k] = _rewrite_media_path_keep_filename(v, media_base)

    # 稳定输出顺序
    for key in ["box_front", "logo", "video"]:
        v = assets.get(key)
        if isinstance(v, str) and v.strip():
            f.write(f"assets.{key}: {v}\n")

def _emit_launch_block(f: TextIO, game: Dict[str, Any]) -> None:
    """
    Write Pegasus 'launch' block. Prefer raw override string if available.
    Accepts several possible keys for compatibility.
    """
    raw = None

    # ✅ 优先：你 json 已经有这个
    for key in ("launch_override", "launch_block", "launch"):
        v = game.get(key)
        if isinstance(v, str) and v.strip():
            raw = v.strip("\n")
            break

    # 兼容：如果 launch 被存成 list[str]
    if raw is None:
        v = game.get("launch")
        if isinstance(v, list) and v:
            raw = "\n".join(str(x) for x in v).strip("\n")

    if not raw:
        return

    lines = raw.splitlines()
    if len(lines) == 1:
        f.write(f"launch: {lines[0].rstrip()}\n")
    else:
        f.write("launch:\n")
        for line in lines:
            f.write(f"  {line.rstrip()}\n")



def _write_game(f: TextIO, game: Dict[str, Any]) -> None:
    # 这里用的字段名要和 parse_pegasus_metadata 产出的 dict 对齐
    title = game.get("game") or game.get("title")
    if not title:
        return

    f.write(f'game: {title}\n')

    # roms / file
    roms = game.get("roms") or []
    if roms:
        if len(roms) == 1:
            # 简单写法：file: xxx
            f.write(f'file: {roms[0]}\n')
        else:
            # 规范写法：files: 多行
            f.write('files:\n')
            for path in roms:
                f.write(f'  {path}\n')

    sort_by = game.get("sort_by")
    if sort_by:
        f.write(f'sort-by: {sort_by}\n')

    developer = game.get("developer")
    if developer:
        f.write(f'developer: {developer}\n')

    # assets.*
    _emit_assets_lines(f, game)

    # description 多行
    desc = game.get("description")
    if desc:
        lines = desc.splitlines()
        if len(lines) == 1:
            f.write(f'description: {lines[0]}\n')
        else:
            f.write('description:\n')
            for line in lines:
                f.write(f'  {line}\n')

    _emit_launch_block(f, game)

    f.write("\n")  # game block 之间空一行


def dump_pegasus_metadata(path: str, header: Dict[str, Any], games: List[Dict[str, Any]]) -> None:
    """
    把 parse_pegasus_metadata 的 (header, games) 写回 Pegasus metadata 格式。
    这是一个“规范化的写法”：排版、缩进、字段顺序都由这里统一决定。
    """
    with open(path, "w", encoding="utf-8") as f:
        _write_header(f, header or {})
        for game in games:
            _write_game(f, game)
