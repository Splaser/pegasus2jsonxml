import json
from pathlib import Path, PurePosixPath
from rename_ps2_chd import load_name_mapping


def _infer_media_stem(game: dict) -> str | None:
    # 1) 优先从 file 推（仅当是纯数字）
    old_file = game.get("file")
    if isinstance(old_file, str) and old_file:
        fname = old_file.split("/")[-1]
        stem = fname.rsplit(".", 1)[0]
        if stem.isdigit():
            return stem

    # 2) 否则从 assets 路径推（media/<stem>/xxx）
    assets = game.get("assets")
    if isinstance(assets, dict):
        for v in assets.values():
            if isinstance(v, str):
                p = PurePosixPath(v)
                parts = list(p.parts)
                if len(parts) >= 2 and parts[0] == "media" and parts[1].isdigit():
                    return parts[1]

    return None




def _fix_assets_paths(game: dict, media_stem: str | None) -> None:
    """
    按“数字编号目录”规范矫正 assets：
    一律改成 media/<old_stem>/xxx，而不跟随新的 file 名字。
    """
    if not media_stem:
        return

    assets = game.get("assets")
    if not isinstance(assets, dict):
        return

    for k, v in list(assets.items()):
        if not isinstance(v, str):
            continue

        p = PurePosixPath(v)
        parts = list(p.parts)

        # 只处理以 "media/..." 开头的路径
        if len(parts) >= 2 and parts[0] == "media":
            rest = parts[2:]  # 去掉原来的第二段（无论是中文名还是数字）
            new_p = PurePosixPath("media") / media_stem
            for comp in rest:
                new_p /= comp
            new_path = str(new_p)
            if new_path != v:
                assets[k] = new_path
                print(f"[assets] {v} -> {new_path}")


def apply_to_jsondb(jsondb_path: Path, mapping: dict[str, str]) -> None:
    """
    按 mapping 重写 jsondb 中的 file / roms / rom_hashes[*].rom_rel，
    同时把 assets 目录统一矫正为 media/<数字编号>/xxx。
    """
    with jsondb_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    games = data.get("games", [])
    changed = 0

    for g in games:
        # 保存旧的 file 名（用来提取数字编号）
        old_file = g.get("file")
        old_stem = _infer_media_stem(g)
        if isinstance(old_file, str) and old_file:
            # 只取文件名最后一段，然后去掉扩展名
            fname = old_file.split("/")[-1]
            old_stem = fname.rsplit(".", 1)[0]  # 例如 "506.chd" -> "506"

        # 1) file 字段
        if old_file in mapping:
            new_file = mapping[old_file]
            if new_file != old_file:
                g["file"] = new_file
                changed += 1
                print(f"[file] {old_file} -> {new_file}")

        # 2) roms 数组
        roms = g.get("roms")
        if isinstance(roms, list):
            new_roms = []
            updated = False
            for r in roms:
                if r in mapping:
                    nr = mapping[r]
                    new_roms.append(nr)
                    updated = True
                    print(f"[roms] {r} -> {nr}")
                else:
                    new_roms.append(r)
            if updated:
                g["roms"] = new_roms

        # 3) rom_hashes 数组
        rh_list = g.get("rom_hashes")
        if isinstance(rh_list, list):
            for rh in rh_list:
                rrel = rh.get("rom_rel")
                if rrel in mapping:
                    nr = mapping[rrel]
                    rh["rom_rel"] = nr
                    print(f"[rom_hashes] {rrel} -> {nr}")

        # 4) 统一矫正 assets 路径 -> media/<old_stem>/xxx
        _fix_assets_paths(g, old_stem)

    # 先备份（仅第一次备份，不覆盖老备份）
    bak_path = jsondb_path.with_suffix(jsondb_path.suffix + ".bak")
    if not bak_path.exists():
        bak_path.write_bytes(jsondb_path.read_bytes())
        print(f"🧷 已备份：{bak_path}")
    
    # 直接覆盖写回原文件
    with jsondb_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已写回 {jsondb_path.name}，共修改 {changed} 条 game.file")



if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent          # PS2Rename
    proj_root = base_dir.parent.parent                  # 项目根
    jsondb_ps2 = proj_root / "jsondb" / "ps2.json"
    # jsondb_ps2_hack = proj_root / "jsondb" / "ps2_hack.json"

    mp = load_name_mapping()
    apply_to_jsondb(jsondb_ps2, mp)
    # apply_to_jsondb(jsondb_ps2_hack, mp)
