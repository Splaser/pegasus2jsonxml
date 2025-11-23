import json
from Tools.metadata_scanner import parse_pegasus_metadata
from Tools.metadata_writer import dump_pegasus_metadata


def _normalize_header(h: dict) -> dict:
    """用于闭合性测试的 header 语义归一化：
    - 没有 extensions 当成 []
    - 如果 extensions 是字符串就按逗号拆
    - launch_block 去掉行首多余空格，只比真实指令内容
    """
    if h is None:
        return {}

    h2 = dict(h)

    # 1) extensions：缺省 ≈ []
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

    # 2) launch_block：去掉行首缩进差异
    lb = h2.get("launch_block")
    if lb:
        lines = lb.splitlines()
        # 行内内容不变，只剥掉左侧空白
        lines = [ln.lstrip() for ln in lines]
        h2["launch_block"] = "\n".join(lines)

    return h2


def verify_closure(meta_path: str) -> bool:
    h1, g1 = parse_pegasus_metadata(meta_path)

    temp_path = meta_path + ".norm_test"
    dump_pegasus_metadata(temp_path, h1, g1)

    h2, g2 = parse_pegasus_metadata(temp_path)

    g1_sorted = sorted(g1, key=lambda x: x.get("game") or "")
    g2_sorted = sorted(g2, key=lambda x: x.get("game") or "")

    # ✨ 用归一化后的 header 比较
    nh1 = _normalize_header(h1)
    nh2 = _normalize_header(h2)

    is_header_same = (nh1 == nh2)
    is_games_same = (g1_sorted == g2_sorted)

    print("---- 闭合性检查 ----")
    print("header 相同：", is_header_same)
    print("games  相同：", is_games_same)

    if not (is_header_same and is_games_same):
        print("\n[DIFF] 发现差异，可前往调试：")
        print("header1 =", json.dumps(h1, indent=2, ensure_ascii=False))
        print("header2 =", json.dumps(h2, indent=2, ensure_ascii=False))
        print("games1_count =", len(g1))
        print("games2_count =", len(g2))

    return is_header_same and is_games_same
