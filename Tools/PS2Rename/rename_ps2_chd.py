from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
MAPPING_JSON = HERE / "ps2_mapping_redump.json"  # { "001.chd": {cn, en}, ... }


CHD_DIR = Path(r"\\192.168.5.146\nexnasshare\tkzlm\【3】天马rom资源\【13】PS2--1077G\【汉化版，放入PS2文件夹】--276GB\PS2") 


def sanitize_filename(name: str) -> str:
    """把 Redump 名转成合法的 Windows 文件名."""
    name = name.strip()

    # 冒号用破折号替换，其余非法字符直接去掉
    illegal = '<>:"/\\|?*'
    name = name.replace(":", " -")
    for ch in illegal:
        if ch == ":":
            continue
        name = name.replace(ch, "")

    # 避免末尾出现空格或点
    name = name.rstrip(" .")

    return name


def load_name_mapping() -> dict[str, str]:
    with MAPPING_JSON.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    mapping: dict[str, str] = {}
    for k, v in raw.items():
        old = k.strip()
        if not old.lower().endswith(".chd"):
            old += ".chd"

        if isinstance(v, dict):
            base = (v.get("en") or v.get("cn") or "").strip()
        else:
            base = str(v).strip()

        if not base:
            continue

        # 这里先生成目标“基名”，再做一次净化
        target = base
        target = sanitize_filename(target)
        if not target.lower().endswith(".chd"):
            target += ".chd"

        mapping[old] = target

    return mapping


def rename_chd_files(dry_run: bool = True) -> None:
    mapping = load_name_mapping()

    if not CHD_DIR.is_dir():
        raise SystemExit(f"CHD 目录不存在：{CHD_DIR}")

    changed = 0
    for old_name, new_name in mapping.items():
        src = CHD_DIR / old_name
        dst = CHD_DIR / new_name

        if not src.exists():
            # 有些条目你还没实际放进 NAS，可以忽略
            print(f"[缺失] {old_name} 不在目录中")
            continue

        if src == dst:
            continue

        if dst.exists():
            print(f"[冲突] 目标已存在：{dst.name}，跳过 {old_name}")
            continue

        print(f"[RENAME] {old_name}  ->  {new_name}")
        changed += 1

        if not dry_run:
            src.rename(dst)

    print(f"\n共准备重命名 {changed} 个文件（dry_run={dry_run}).")


if __name__ == "__main__":
    # 第一次先 dry_run 看输出
    rename_chd_files(dry_run=False)