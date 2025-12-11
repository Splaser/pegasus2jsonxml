from pathlib import Path
import json


def main():
    base_dir = Path(__file__).parent
    raw_path = base_dir / "ps2_raw_mapping.json"
    out_path = base_dir / "ps2_mapping_redump.json"

    if not raw_path.is_file():
        raise SystemExit(f"找不到 ps2_raw_mapping.json: {raw_path}")

    with raw_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    result = {}
    # 按 key 排序，方便你手工填 en
    for k in sorted(raw.keys()):
        cn = raw[k]
        result[k] = {
            "cn": cn,
            "en": ""   # 这里等会儿我们/你填 Redump 英文名
        }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 已生成模板: {out_path} （共 {len(result)} 条）")


if __name__ == "__main__":
    main()
