from pathlib import Path
import json


def parse_mapping_from_txt(txt_path: Path) -> dict[str, str]:
    """
    从《PS2 汉化版说明.txt》解析出原始映射表：
    支持：
      001           战神1 D9和谐 汉化版
      043 Disc A    影之心2 导演剪辑版（DISK A）
      043 Disc B    影之心2 导演剪辑版（DISK B）
    生成：
      { "001.chd": "战神1 D9和谐 汉化版",
        "043 Disc A.chd": "影之心2 导演剪辑版（DISK A）",
        "043 Disc B.chd": "影之心2 导演剪辑版（DISK B）", ... }
    """
    mapping: dict[str, str] = {}

    with txt_path.open("r", encoding="utf-8-sig") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#") or line.startswith("//"):
                continue

            tokens = line.split()
            if len(tokens) < 2:
                print(f"[跳过] 解析不到描述: {line!r}")
                continue

            # 默认：第一个 token 为 key，其余为描述
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
                desc_tokens = tokens[3:] or [""]        # 之后才是描述

            desc_raw = " ".join(desc_tokens).strip()

            key = key_raw.strip()
            if not key.lower().endswith(".chd"):
                key = key + ".chd"

            if not desc_raw:
                print(f"[警告] {key} 描述为空")
                continue

            if key in mapping:
                print(f"[警告] 重复条目 {key}，将覆盖之前的值。")
            mapping[key] = desc_raw

    return mapping


def main():
    base_dir = Path(__file__).parent
    txt_path = base_dir / "PS2 汉化版说明.txt"
    out_path = base_dir / "ps2_raw_mapping.json"

    if not txt_path.is_file():
        raise SystemExit(f"找不到说明文件: {txt_path}")

    mapping = parse_mapping_from_txt(txt_path)
    mapping_sorted = dict(sorted(mapping.items(), key=lambda kv: kv[0]))

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(mapping_sorted, f, ensure_ascii=False, indent=2)

    print(f"✅ 已生成 raw mapping，共 {len(mapping_sorted)} 条记录：")
    print(out_path)


if __name__ == "__main__":
    main()
