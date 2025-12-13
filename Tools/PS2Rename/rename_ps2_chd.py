from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
MAPPING_JSON = HERE / "ps2_mapping_redump.json"  # { "001.chd": {cn, en}, ... }

CHD_DIRS = [
    Path(r"\\192.168.5.146\nexnasshare\tkzlm\【3】天马rom资源\【13】PS2--1077G\【汉化版，放入PS2文件夹】--276GB\PS2"),
    Path(r"\\192.168.5.146\nexnasshare\tkzlm\【3】天马rom资源\【13】PS2--1077G\【非汉化，放入PS2文件夹】--713GB\PS2"),
]

def sanitize_filename(name: str) -> str:
    """把 Redump 名转成合法的 Windows 文件名."""
    name = name.strip()

    illegal = '<>:"/\\|?*'
    name = name.replace(":", " -")
    for ch in illegal:
        if ch == ":":
            continue
        name = name.replace(ch, "")

    name = name.rstrip(" .")
    return name


def load_name_mapping() -> dict[str, str]:
    with MAPPING_JSON.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    mapping: dict[str, str] = {}
    skipped_no_en = 0

    for k, v in raw.items():
        old = k.strip()
        if not old.lower().endswith(".chd"):
            old += ".chd"

        # 只处理 dict 且 en 非空的条目
        if not isinstance(v, dict):
            skipped_no_en += 1
            continue

        en = (v.get("en") or "").strip()
        if not en:
            skipped_no_en += 1
            continue

        target = sanitize_filename(en)
        if not target.lower().endswith(".chd"):
            target += ".chd"

        mapping[old] = target

    print(f"[INFO] 仅对 en 非空条目生成 rename 计划：{len(mapping)} 条；跳过（无 en）{skipped_no_en} 条。")
    return mapping


def find_src(old_name: str) -> Path | None:
    """在多个目录中查找 old_name，返回第一个命中的完整路径。"""
    for d in CHD_DIRS:
        if not d.is_dir():
            print(f"[警告] 目录不可用：{d}")
            continue
        p = d / old_name
        if p.exists():
            return p
    return None


def rename_chd_files(dry_run: bool = True) -> None:
    mapping = load_name_mapping()

    changed = 0
    missing = 0
    conflict = 0

    for old_name, new_name in mapping.items():
        src = find_src(old_name)
        if src is None:
            print(f"[缺失] {old_name} 不在任何目录中")
            missing += 1
            continue

        dst = src.parent / new_name  # 在同一目录内重命名（最安全）

        if src.name == dst.name:
            continue

        if dst.exists():
            print(f"[冲突] 目标已存在：{dst}，跳过 {src}")
            conflict += 1
            continue

        print(f"[RENAME] {src}  ->  {dst}")
        changed += 1

        if not dry_run:
            src.rename(dst)

    print(
        f"\n准备重命名 {changed} 个文件（dry_run={dry_run}），"
        f"缺失 {missing}，冲突 {conflict}。"
    )


if __name__ == "__main__":
    # 强烈建议你第一次先 dry_run=True 看一遍输出
    rename_chd_files(dry_run=False)
