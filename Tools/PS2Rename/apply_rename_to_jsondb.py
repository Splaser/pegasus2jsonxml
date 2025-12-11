import json
from pathlib import Path, PurePosixPath
from rename_ps2_chd import sanitize_filename 


def load_name_mapping(mapping_path: Path) -> dict[str, str]:
    """
    从 ps2_mapping_redump.json 读取映射，返回：
    {"001.chd": "God of War (USA).chd", ...}
    """
    with mapping_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    result: dict[str, str] = {}
    for key, val in raw.items():
        old = key.strip()
        if not old.lower().endswith(".chd"):
            old = old + ".chd"

        if isinstance(val, dict):
            base = (val.get("en") or val.get("cn") or "").strip()
        else:
            base = str(val).strip()

        if not base:
            continue
        
        target = sanitize_filename(base)

        if not target.lower().endswith(".chd"):
            target += ".chd"

        result[old] = target

    return result


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
        old_stem = None
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

    out_path = jsondb_path.with_name(jsondb_path.stem + "_renamed.json")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已处理完 {jsondb_path.name}，共修改 {changed} 条 game.file")
    print(f"输出文件：{out_path}")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent          # PS2Rename
    proj_root = base_dir.parent.parent                  # 项目根
    mapping_path = base_dir / "ps2_mapping_redump.json"
    jsondb_ps2 = proj_root / "jsondb" / "ps2.json"
    # jsondb_ps2_hack = proj_root / "jsondb" / "ps2_hack.json"
    
    mp = load_name_mapping(mapping_path)
    apply_to_jsondb(jsondb_ps2, mp)
    # apply_to_jsondb(jsondb_ps2_hack, mp)
