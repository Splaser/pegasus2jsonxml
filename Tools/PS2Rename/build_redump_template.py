from pathlib import Path
import json
import re
from collections import OrderedDict

def chd_sort_key(k: str):
    """
    PS2 CHD 专用排序规则：
    1. 按主数字编号排序
    2. 同编号下：主盘 -> Disc -> 变体
    """

    # 提取主编号
    m = re.match(r"(\d+)", k)
    if m:
        num = int(m.group(1))
    else:
        num = 10_000  # 极端兜底

    lk = k.lower()

    # 类型权重
    if re.fullmatch(r"\d+\.chd", lk):
        kind = 0
    elif "disc" in lk:
        kind = 1
    elif "_" in lk:
        kind = 2
    else:
        kind = 9

    return (num, kind, lk)

def main():
    base_dir = Path(__file__).parent
    raw_path = base_dir / "ps2_raw_mapping.json"
    out_path = base_dir / "ps2_mapping_redump.json"

    if not raw_path.is_file():
        raise SystemExit(f"找不到 ps2_raw_mapping.json: {raw_path}")

    with raw_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    # 关键：如果已有 ps2_mapping_redump.json，就读进来当“人工权威缓存”
    existing = {}
    if out_path.is_file():
        with out_path.open("r", encoding="utf-8") as f:
            existing = json.load(f)

    changed = 0
    for k in sorted(raw.keys()):
        cn = raw[k]

        if k in existing and isinstance(existing[k], dict):
            existing[k].setdefault("cn", "")
            existing[k].setdefault("en", "")
            if not existing[k]["cn"] and isinstance(cn, str) and cn.strip():
                existing[k]["cn"] = cn.strip()
                changed += 1
        else:
            if isinstance(cn, str) and cn.strip():
                existing[k] = {"cn": cn.strip(), "en": ""}
                changed += 1

    sorted_existing = OrderedDict(
        (k, existing[k])
        for k in sorted(existing.keys(), key=chd_sort_key)
    )
    
    # 写回：不会把你手工 en 清空
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(sorted_existing, f, ensure_ascii=False, indent=2)

    print(f"增量补齐 {changed} 条。")


if __name__ == "__main__":
    main()
