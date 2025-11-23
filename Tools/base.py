import json
from .metadata_scanner import parse_pegasus_metadata
from .metadata_writer import dump_pegasus_metadata


def verify_closure(meta_path: str) -> bool:
    """
    闭合集合验证：
      1. parse 原始 metadata → (h1, g1)
      2. dump 到一个临时规范文件
      3. 再 parse → (h2, g2)
      4. 判断语义是否一致

    返回 True = 闭合（幂等）; False = 有差异
    """

    h1, g1 = parse_pegasus_metadata(meta_path)

    temp_path = meta_path + ".norm_test"
    dump_pegasus_metadata(temp_path, h1, g1)

    h2, g2 = parse_pegasus_metadata(temp_path)

    # 可选：按 game 名排序，避免输出顺序影响比较
    g1_sorted = sorted(g1, key=lambda x: x.get("game") or "")
    g2_sorted = sorted(g2, key=lambda x: x.get("game") or "")

    is_header_same = (h1 == h2)
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
