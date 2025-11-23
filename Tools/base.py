# Tools/base.py
import unicodedata
import re
import os
import json
from typing import Dict, Any, List, Tuple

from .metadata_scanner import parse_pegasus_metadata
from .metadata_writer import dump_pegasus_metadata


def _clean_text(s: str) -> str:
    if not isinstance(s, str):
        return s

    # 1) Unicode normalization NFKC（全角/半角 + 合字规范化）
    s = unicodedata.normalize("NFKC", s)

    # 2) 去掉所有零宽字符
    s = re.sub(r"[\u200B\u200C\u200D\uFEFF]", "", s)

    # 3) 去掉 unicode 中隐形换行符
    s = s.replace("\u2028", "").replace("\u2029", "")

    # 4) 标准化换行（全部变成 \n）
    s = s.replace("\r\n", "\n").replace("\r", "\n")

    # 5) 去掉末尾空行和末尾空白
    lines = [ln.rstrip() for ln in s.split("\n")]
    return "\n".join(lines).strip()


def _normalize_header(h: Dict[str, Any]) -> Dict[str, Any]:
    """用于闭合性测试的 header 语义归一化。"""
    if h is None:
        return {}

    h2 = dict(h)

    # 1) extensions：缺省 ≈ []，字符串/逗号分隔都拆成 list
    exts = h2.get("extensions")
    if exts is None:
        exts = []
    if isinstance(exts, str):
        tmp = []
        for part in exts.split(","):
            p = part.strip()
            if p:
                tmp.append(p)
        exts = tmp
    h2["extensions"] = exts

    # 2) ignore_files：缺省当成 []
    ig = h2.get("ignore_files")
    if ig is None:
        ig = []
    h2["ignore_files"] = ig

    # 3) launch_block：去掉行首缩进差异
    lb = h2.get("launch_block")
    if lb:
        lines = lb.splitlines()
        lines = [ln.lstrip() for ln in lines]
        h2["launch_block"] = "\n".join(lines)

    return h2


def _normalize_game(g: Dict[str, Any]) -> Dict[str, Any]:
    """用于闭合性测试的 game 语义归一化。"""
    norm: Dict[str, Any] = {}

    # 基本字段：只保留非空的
    for key in ("game", "title", "sort_by", "developer", "year"):
        val = g.get(key)
        if val not in (None, "", []):
            norm[key] = val

    # ===== roms：统一成 strip + 去空 + 去重 + 排序 =====
    roms = g.get("roms") or []
    if isinstance(roms, str):
        roms = [roms]

    cleaned_roms = []
    for r in roms:
        if not r:
            continue
        s = r.strip()
        if not s:
            continue
        cleaned_roms.append(s)

    # 去重 + 排序
    cleaned_roms = []
    for r in roms:
        if not r: continue
        s = _clean_text(r.strip())
        if s:
            cleaned_roms.append(s)
    norm["roms"] = sorted(set(cleaned_roms))

    # description：去掉行末空格 & 首尾空行
    desc = g.get("description")
    if desc:
        desc2 = _clean_text(desc)
        norm["description"] = desc2

    # per-game launch_block：去掉行首缩进
    lb = g.get("launch_block")
    if lb:
        lines = [ln.lstrip() for ln in lb.splitlines()]
        norm["launch_block"] = "\n".join(lines)

    # 一些额外字段（比如 core_override），你有的话也可以保留
    extra_keys = ("core_override", )
    for k in extra_keys:
        v = g.get(k)
        if v not in (None, "", []):
            norm[k] = v

    return norm

# 用 game 名 + roms 作为排序 key，确保顺序不影响比较
def _game_key(g: Dict[str, Any]) -> Tuple[str, str]:
    name = g.get("game") or g.get("title") or ""
    rom0 = ""
    roms = g.get("roms") or []
    if isinstance(roms, list) and roms:
        rom0 = roms[0]
    elif isinstance(roms, str):
        rom0 = roms
    return (name, rom0)


def verify_closure(meta_path: str, keep_temp: bool = False) -> bool:
    """
    闭合集合验证：
      1. parse 原始 metadata → (h1, g1)
      2. dump 到一个临时规范文件
      3. 再 parse → (h2, g2)
      4. 在“语义归一化”后比较是否一致

    keep_temp = False 时，验证完成后自动删除临时文件；
                   True 时保留临时文件，便于调试。
    """

    # 1) parse 原始
    h1, g1 = parse_pegasus_metadata(meta_path)

    # 2) 生成临时路径：同级目录 / _norm_test / metadata.txt.norm
    base_dir = os.path.dirname(meta_path)
    norm_dir = os.path.join(base_dir, "_norm_test")
    os.makedirs(norm_dir, exist_ok=True)

    temp_name = os.path.basename(meta_path) + ".norm"
    temp_path = os.path.join(norm_dir, temp_name)

    # 写入临时文件
    dump_pegasus_metadata(temp_path, h1, g1)

    # 3) 再 parse 回来
    h2, g2 = parse_pegasus_metadata(temp_path)

    # ==== header 归一化后比较 ====
    nh1 = _normalize_header(h1 or {})
    nh2 = _normalize_header(h2 or {})
    is_header_same = (nh1 == nh2)

    # ==== games 归一化后比较 ====
    g1_norm = [_normalize_game(g) for g in g1]
    g2_norm = [_normalize_game(g) for g in g2]

    g1_sorted = sorted(g1_norm, key=_game_key)
    g2_sorted = sorted(g2_norm, key=_game_key)

    is_games_same = (g1_sorted == g2_sorted)

    if not is_games_same:
        print("[DEBUG] 找第一条不相等的 game：")
        for a, b in zip(g1_sorted, g2_sorted):
            if a != b:
                print("game1 =", json.dumps(a, ensure_ascii=False, indent=2))
                print("game2 =", json.dumps(b, ensure_ascii=False, indent=2))
                break

    # 输出结果
    print("---- 闭合性检查 ----")
    print("header 相同：", is_header_same)
    print("games  相同：", is_games_same)

    ok = is_header_same and is_games_same

    # 4) 自动删除临时文件（除非 keep_temp=True）
    if not keep_temp:
        try:
            os.remove(temp_path)
            # 如果目录空了可以顺带清理掉
            if not os.listdir(norm_dir):
                os.rmdir(norm_dir)
        except Exception:
            pass

    # 差异提示
    if not ok:
        print("\n[DIFF] 发现差异，可前往调试：")
        print("header1 =", json.dumps(h1, indent=2, ensure_ascii=False))
        print("header2 =", json.dumps(h2, indent=2, ensure_ascii=False))
        print("games1_count =", len(g1))
        print("games2_count =", len(g2))

    return ok
