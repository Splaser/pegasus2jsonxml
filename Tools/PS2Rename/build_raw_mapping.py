from pathlib import Path
import json


def parse_mapping_from_txt(txt_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}

    with txt_path.open("r", encoding="utf-8-sig") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#") or line.startswith("//"):
                continue

            # 跳过表头/噪音行：例如 "chd\tXXXX"
            low = line.lower()
            if low.startswith("chd") and ("\t" in line or " " in line):
                continue

            # 优先用 TAB 分割（更像“字段”）
            if "\t" in line:
                key_raw, desc_raw = line.split("\t", 1)
                key_raw = key_raw.strip()
                desc_raw = desc_raw.strip()
                if not key_raw or not desc_raw:
                    continue
                tokens = [key_raw] + desc_raw.split()
            else:
                tokens = line.split()

            if len(tokens) < 2:
                print(f"[跳过] 解析不到描述: {line!r}")
                continue

            key_raw = tokens[0]
            desc_tokens = tokens[1:]

            # 特判：数字 + Disc + A/B/1/2 这种多碟 key
            if (
                len(tokens) >= 3
                and tokens[0].isdigit()
                and tokens[1].lower() == "disc"
                and tokens[2].upper() in {"A", "B", "1", "2"}
            ):
                key_raw = " ".join(tokens[:3])          # "043 Disc A"
                desc_tokens = tokens[3:] or [""]

            desc_raw = " ".join(desc_tokens).strip()
            if not desc_raw:
                continue

            key = key_raw.strip()

            # 允许 key 只有数字：033 -> 033.chd
            if key.isdigit():
                key = f"{key}.chd"

            # 普通 key：补 .chd 后缀
            if not key.lower().endswith(".chd"):
                key = key + ".chd"

            if key in mapping:
                print(f"[警告] 重复条目 {key}，将覆盖之前的值。")
            mapping[key] = desc_raw

    return mapping


def main():
    base_dir = Path(__file__).parent
    txt_paths = [
        base_dir / "PS2 汉化版说明.txt",
        base_dir / "PS2 非汉化说明.txt",
    ]
    out_path = base_dir / "ps2_raw_mapping.json"

    merged: dict[str, str] = {}
    total = 0

    for p in txt_paths:
        if not p.is_file():
            print(f"[跳过] 找不到说明文件: {p.name}")
            continue
        m = parse_mapping_from_txt(p)
        total += len(m)
        # 合并：后读的覆盖先读的（你也可以反过来）
        merged.update(m)

    mapping_sorted = dict(sorted(merged.items(), key=lambda kv: kv[0]))

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(mapping_sorted, f, ensure_ascii=False, indent=2)

    print(f"✅ 已生成 raw mapping，共 {len(mapping_sorted)} 条记录（源合计 {total}）。")
    print(out_path)


if __name__ == "__main__":
    main()
