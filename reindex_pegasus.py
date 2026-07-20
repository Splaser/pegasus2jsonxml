from __future__ import annotations

import re
import shutil
from pathlib import Path


ROM_ROOT = Path(r"G:\roms")

# True：只显示改动，不真正写文件
# 第一次运行建议保持 True，确认无误后改成 False
DRY_RUN = False

# True：递归搜索平台文件夹里的 metadata.pegasus.txt
# False：只处理“平台目录\metadata.pegasus.txt”
RECURSIVE_SEARCH = True

# 是否创建 .bak 备份
CREATE_BACKUP = False

# 编号从几开始
START_INDEX = 1

# 编号宽度：001、002……
INDEX_WIDTH = 3


SORT_BY_PATTERN = re.compile(
    r"(?mi)^(?P<prefix>[ \t]*sort-by[ \t]*:[ \t]*)(?P<number>\d+)(?P<suffix>[ \t]*)$"
)


def natural_sort_key(text: str) -> list[object]:
    """让 PS2 排在 PS10 前面，而不是普通字符串排序的 PS10、PS2。"""
    return [
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", text)
    ]


def read_text_preserving_encoding(path: Path) -> tuple[str, str]:
    """
    尝试常见编码。
    返回：(文本内容, 使用的编码)
    """
    raw = path.read_bytes()

    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError(
        "unknown",
        raw,
        0,
        len(raw),
        f"无法识别文件编码：{path}",
    )


def write_text_preserving_encoding(
    path: Path,
    text: str,
    encoding: str,
) -> None:
    path.write_bytes(text.encode(encoding))


def find_metadata_files(platform_dir: Path) -> list[Path]:
    if RECURSIVE_SEARCH:
        return sorted(
            platform_dir.rglob("metadata.pegasus.txt"),
            key=lambda path: natural_sort_key(str(path)),
        )

    metadata_path = platform_dir / "metadata.pegasus.txt"
    return [metadata_path] if metadata_path.is_file() else []


def replace_sort_by(text: str, new_value: str) -> tuple[str, str | None]:
    """
    直接处理 metadata.pegasus.txt 的第二行。
    保留原文件换行符，只替换第二行冒号后的数字。
    """
    lines = text.splitlines(keepends=True)

    if len(lines) < 2:
        return text, None

    second_line = lines[1]

    # 同时兼容 sort-by、sort_by，以及半角/全角冒号
    match = re.search(
        r"(?i)(sort[-_]by\s*[:：]\s*)(\d+)",
        second_line,
    )

    if not match:
        return text, None

    old_value = match.group(2)

    lines[1] = (
        second_line[:match.start(2)]
        + new_value
        + second_line[match.end(2):]
    )

    return "".join(lines), old_value


def platform_sort_key(name: str) -> list[object]:
    # 忽略开头的 18X、18X空格、18X-、18X_
    normalized = re.sub(
        r"(?i)^18x[\s_-]*",
        "",
        name,
    )

    return natural_sort_key(normalized)


def main() -> None:
    if not ROM_ROOT.is_dir():
        raise FileNotFoundError(f"ROM 根目录不存在：{ROM_ROOT}")

    platform_dirs = sorted(
        [
            path
            for path in ROM_ROOT.iterdir()
            if path.is_dir()
        ],
        key=lambda path: platform_sort_key(path.name),
    )

    changed_count = 0
    skipped_count = 0
    missing_count = 0

    print(f"ROM 根目录：{ROM_ROOT}")
    print(f"运行模式：{'预览，不写入' if DRY_RUN else '正式写入'}")
    print()

    current_index = START_INDEX

    for platform_dir in platform_dirs:
        metadata_files = find_metadata_files(platform_dir)

        if not metadata_files:
            print(f"[无 metadata] {platform_dir.name}")
            missing_count += 1
            continue

        new_sort_by = str(current_index).zfill(INDEX_WIDTH)

        print(
            f"[平台 {new_sort_by}] "
            f"{platform_dir.name} "
            f"({len(metadata_files)} 个 metadata)"
        )

        for metadata_path in metadata_files:
            try:
                original_text, encoding = read_text_preserving_encoding(
                    metadata_path
                )
            except UnicodeDecodeError as exc:
                print(f"  [编码错误] {metadata_path}: {exc}")
                skipped_count += 1
                continue

            updated_text, old_sort_by = replace_sort_by(
                original_text,
                new_sort_by,
            )

            if old_sort_by is None:
                print(f"  [缺少 sort-by] {metadata_path}")
                skipped_count += 1
                continue

            if old_sort_by == new_sort_by:
                print(f"  [无需修改] {old_sort_by}  {metadata_path}")
                continue

            print(
                f"  [修改] {old_sort_by} -> {new_sort_by}  "
                f"{metadata_path}"
            )

            if not DRY_RUN:
                if CREATE_BACKUP:
                    backup_path = metadata_path.with_suffix(
                        metadata_path.suffix + ".bak"
                    )

                    if not backup_path.exists():
                        try:
                            shutil.copy2(metadata_path, backup_path)
                        except OSError as exc:
                            print(f"  [备份失败] {metadata_path}")
                            print(f"    {exc}")
                            skipped_count += 1
                            continue

                write_text_preserving_encoding(
                    metadata_path,
                    updated_text,
                    encoding,
                )

            changed_count += 1

        # 只有找到 metadata 的平台才占用编号
        current_index += 1

    print()
    print("=" * 60)
    print(f"需要修改：{changed_count}")
    print(f"跳过文件：{skipped_count}")
    print(f"无 metadata 的平台：{missing_count}")

    if DRY_RUN:
        print()
        print("当前只是预览。确认编号顺序后，将 DRY_RUN 改为 False。")


if __name__ == "__main__":
    main()