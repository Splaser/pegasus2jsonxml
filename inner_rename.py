from pathlib import Path
import zipfile
import shutil
import tempfile
import os
import stat

ROOT = Path(r"f:\roms\gba")
DRY_RUN = False


def display_zip_name(name: str) -> str:
    try:
        return name.encode("cp437").decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def fix_zip(zip_path: Path):
    expected_name = zip_path.stem + ".gba"

    with zipfile.ZipFile(zip_path, "r") as zf:
        gba_entries = [
            info for info in zf.infolist()
            if not info.is_dir()
            and Path(info.filename).suffix.lower() == ".gba"
        ]

        if len(gba_entries) == 0:
            print(f"[SKIP] no GBA: {zip_path.name}")
            return

        if len(gba_entries) > 1:
            print(f"[SKIP] multiple GBA files: {zip_path.name}")
            for info in gba_entries:
                print(f"       - {display_zip_name(info.filename)}")
            return

        gba_info = gba_entries[0]
        old_name = Path(gba_info.filename).name

        if old_name == expected_name:
            print(f"[OK]   {zip_path.name}")
            return

        print(f"[FIX]  {zip_path.name}")
        print(f"       {display_zip_name(old_name)}")
        print(f"    -> {expected_name}")

        if DRY_RUN:
            return

        tmp_path = zip_path.with_suffix(".zip.tmp")

        # 清理上次失败遗留的临时文件
        if tmp_path.exists():
            tmp_path.unlink()

        with zipfile.ZipFile(tmp_path, "w") as out:
            for info in zf.infolist():
                data = zf.read(info.filename)

                if info.filename == gba_info.filename:
                    # 保留原目录层级；一般 GBA zip 应该没有目录
                    parent = Path(info.filename).parent
                    new_filename = (
                        str(parent / expected_name)
                        if str(parent) != "."
                        else expected_name
                    )

                    new_info = zipfile.ZipInfo(
                        filename=new_filename,
                        date_time=info.date_time
                    )
                    new_info.compress_type = info.compress_type
                    new_info.comment = info.comment
                    new_info.extra = info.extra
                    new_info.internal_attr = info.internal_attr
                    new_info.external_attr = info.external_attr
                    new_info.create_system = info.create_system

                    out.writestr(new_info, data)
                else:
                    out.writestr(info, data)

    # 到这里原 zip 已经关闭，避免 Windows 文件句柄占用问题

    # 清除原 ZIP 的只读属性
    try:
        os.chmod(zip_path, stat.S_IWRITE | stat.S_IREAD)
    except OSError as e:
        print(f"[WARN] chmod failed: {zip_path.name}: {e}")

    try:
        os.replace(tmp_path, zip_path)
    except PermissionError:
        print(f"[ERROR] replace denied: {zip_path}")
        print(f"        temp kept at: {tmp_path}")
        raise


def main():
    for zip_path in ROOT.rglob("*.zip"):
        fix_zip(zip_path)


if __name__ == "__main__":
    main()