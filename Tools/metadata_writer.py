# Tools/metadata_writer.py

from __future__ import annotations
from typing import Dict, List, Any, TextIO

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

    # launch（per-game override）
    launch_block = game.get("launch_block")
    if launch_block:
        lines = launch_block.splitlines()
        if len(lines) == 1:
            f.write(f'launch: {lines[0]}\n')
        else:
            f.write('launch:\n')
            for line in lines:
                f.write(f'  {line}\n')

    # 你如果想把 core_override 映射回 launch 里的 -L cores/xxx_libretro_android.so
    # 也可以在这里反向构造一行
    # core = game.get("core_override")
    # if core and not launch_block:
    #     f.write(f'launch: retroarch -L "{core}" "{{file}}"\n')

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
