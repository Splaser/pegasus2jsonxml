# Tools/metadata_writer.py

from __future__ import annotations
from typing import Dict, List, Any, TextIO
from pathlib import PurePosixPath


DEFAULT_ASSET_NAMES = {
    "box_front": {
        "boxfront.png",
        "boxfront.jpg",
        "boxFront.png",
        "boxFront.jpg",
        "box_front.png",
        "box_front.jpg",
    },
    "logo": {
        "logo.png",
        "logo.jpg",
    },
    "video": {
        "video.mp4",
        "video.webm",
    },
}

def _infer_rom_stem_base_from_game(game: dict) -> str | None:
    """
    默认 media 目录按 ROM basename/stem 推断：
      mslug.zip          -> media/mslug/...
      mslugqy.zip        -> media/mslugqy/...
      mslugd/mslug.zip   -> media/mslug/...
    """
    roms = game.get("roms")
    if isinstance(roms, list) and roms:
        first = roms[0]
    else:
        first = game.get("file")

    if not isinstance(first, str) or not first.strip():
        return None

    return PurePosixPath(first.strip()).stem


def _infer_noise_title_bases_from_game(game: dict) -> set[str]:
    """
    兼容旧导出器误生成的 media/<中文游戏名>/ 三件套。
    你的实际资源库不是这种结构，所以这类 assets 不写回。
    """
    bases = set()
    for key in ("canonical_name", "game", "title"):
        v = game.get(key)
        if isinstance(v, str) and v.strip():
            bases.add(v.strip())
    return bases

def _asset_media_dir_and_filename(value: str) -> tuple[str | None, str | None]:
    p = PurePosixPath(value.strip())
    parts = p.parts

    if len(parts) < 3:
        return None, None

    if parts[0] != "media":
        return None, None

    return parts[1], parts[-1]

def _is_standard_asset_filename(key: str, filename: str | None) -> bool:
    if not filename:
        return False
    return filename in DEFAULT_ASSET_NAMES.get(key, set())

def _infer_rom_parent_base_from_game(game: dict) -> str | None:
    """
    file: mslugd/mslug.zip -> mslugd
    file: 恐龙新世纪 无限保险版/dino.zip -> 恐龙新世纪 无限保险版
    file: mslugqy.zip -> None
    """
    roms = game.get("roms")
    if isinstance(roms, list) and roms:
        first = roms[0]
    else:
        first = game.get("file")

    if not isinstance(first, str) or not first.strip():
        return None

    p = PurePosixPath(first.strip())
    parts = p.parts

    if len(parts) >= 2:
        return parts[0]

    return None


def _should_emit_asset_line(key: str, value: str, game: dict) -> bool:
    media_dir, filename = _asset_media_dir_and_filename(value)

    if not media_dir or not filename:
        # 非 media/... 结构，保守写出
        return True

    if not _is_standard_asset_filename(key, filename):
        # 非标准文件名，可能是手工指定，保守写出
        return True

    rom_stem = _infer_rom_stem_base_from_game(game)
    rom_parent = _infer_rom_parent_base_from_game(game)

    # 嵌套 ROM 的父目录 media override 必须写：
    # file: mslugd/mslug.zip -> media/mslugd/...
    # file: 恐龙新世纪 无限保险版/dino.zip -> media/恐龙新世纪 无限保险版/...
    if rom_parent and media_dir == rom_parent:
        return True

    # 默认 media/<rom_stem>/ 三件套，不写
    if rom_stem and media_dir == rom_stem:
        return False

    # 旧错误生成的 media/<中文游戏名>/ 三件套：
    # 只有在它不是 ROM 父目录时才不写
    if media_dir in _infer_noise_title_bases_from_game(game):
        return False

    # 其他 media 目录都是显式 override，要写
    return True

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
    assets = _collect_assets(game)
    media_base = _infer_media_base_from_multifiles(game)

    # ✅ 多碟 / 多文件条目：保留老逻辑，强制写 assets
    # 因为这类默认推断不可靠，需要 media/<firstDir>/ 三件套。
    if media_base:
        if not assets:
            assets = {
                "box_front": f"media/{media_base}/boxFront.png",
                "logo":      f"media/{media_base}/logo.png",
                "video":     f"media/{media_base}/video.mp4",
            }
        else:
            for k in list(assets.keys()):
                v = assets[k]
                if isinstance(v, str) and v.strip():
                    assets[k] = _rewrite_media_path_keep_filename(v, media_base)

        for key in ["box_front", "logo", "video"]:
            v = assets.get(key)
            if isinstance(v, str) and v.strip():
                f.write(f"assets.{key}: {v.strip()}\n")
        return

    # ✅ 普通单 ROM：只写真正的 assets override
    if not assets:
        return

    for key in ["box_front", "logo", "video"]:
        v = assets.get(key)
        if not (isinstance(v, str) and v.strip()):
            continue

        v = v.strip()

        if not _should_emit_asset_line(key, v, game):
            continue

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
