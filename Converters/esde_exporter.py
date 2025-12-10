# Converters/esde_exporter.py

from pathlib import Path
import xml.etree.ElementTree as ET
import json
import shutil


def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i + "  "
        if not elem[-1].tail or not elem[-1].tail.strip():
            elem[-1].tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def export_esde(
    platform: str,
    json_path: Path,
    esde_root: Path,
    roms_subdir: str | None = None,
):
    """
    jsondb/<platform>.json -> ES-DE 结构：

    esde_root/
      gamelists/<platform>/gamelist.xml
      downloaded_media/<platform>/
        covers/
        marquees/
        videos/

    roms_subdir:
      - None 或 ""  -> <path> = "./<file>"
      - "roms"      -> <path> = "./roms/<file>"
    """

    data = json.loads(json_path.read_text(encoding="utf-8"))
    games = data.get("games", [])
    assets_base = data.get("assets_base", "media")

    # 1) gamelist 输出目录
    gamelist_dir = esde_root / "gamelists" / platform
    gamelist_dir.mkdir(parents=True, exist_ok=True)

    # 2) downloaded_media 输出目录
    media_root = esde_root / "downloaded_media" / platform
    covers_dir = media_root / "covers"
    marquees_dir = media_root / "marquees"
    videos_dir = media_root / "videos"

    root = ET.Element("gameList")

    for g in games:
        game_elem = transform_to_esde(
            platform=platform,
            game=g,
            assets_base=assets_base,
            roms_subdir=roms_subdir,
        )
        root.append(game_elem)

        # === 拷贝媒体到 downloaded_media 目录 ===
        assets = g.get("assets") or {}
        rom_file = g.get("file") or ""
        rom_stem = Path(rom_file).stem if rom_file else None

        if not rom_stem:
            continue

        # 封面 -> covers/<ROM名>.<原后缀>
        box_front = assets.get("box_front")
        if box_front:
            _copy_asset_to_named(
                src_root=json_path.parent,
                rel_path=box_front,
                dst_dir=covers_dir,
                out_basename=rom_stem,
            )

        # logo -> marquees/<ROM名>.<原后缀>
        logo = assets.get("logo")
        if logo:
            _copy_asset_to_named(
                src_root=json_path.parent,
                rel_path=logo,
                dst_dir=marquees_dir,
                out_basename=rom_stem,
            )

        # 视频 -> videos/<ROM名>.<原后缀>
        video = assets.get("video")
        if video:
            _copy_asset_to_named(
                src_root=json_path.parent,
                rel_path=video,
                dst_dir=videos_dir,
                out_basename=rom_stem,
            )

        # === 可选：保持一份相对 gamelist 的 media 结构（兼容其他前端） ===
        for key in ("box_front", "logo", "video"):
            rel = assets.get(key)
            if not rel:
                continue
            _copy_asset_relative(
                src_root=json_path.parent,
                dst_root=gamelist_dir,
                rel_path=rel,
            )

    indent(root)

    out_path = gamelist_dir / "gamelist.xml"
    tree = ET.ElementTree(root)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)

    print(f"[OK] ES-DE export -> {out_path}")
    return out_path


def _copy_asset_relative(src_root: Path, dst_root: Path, rel_path: str):
    """
    老逻辑：按 jsondb 里记录的相对路径复制到平台 gamelist 目录下，
    比如 ./media/xxx -> gamelists/<platform>/media/xxx
    """
    rel = rel_path.lstrip("./").replace("\\", "/")
    src = (src_root / rel).resolve()
    dst = dst_root / rel

    if not src.is_file():
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_asset_to_named(
    src_root: Path,
    rel_path: str,
    dst_dir: Path,
    out_basename: str,
):
    """
    ES-DE 正式用的 copy：
      src: jsondb 里的资源路径
      dst: downloaded_media/<platform>/<type>/<out_basename>.<原后缀>

    例如：
      ROM:  MHP3rd.iso   -> out_basename = "MHP3rd"
      封面: box_front.png -> copied to covers/MHP3rd.png
    """
    rel = rel_path.lstrip("./").replace("\\", "/")
    src = (src_root / rel).resolve()
    if not src.is_file():
        return

    dst_dir.mkdir(parents=True, exist_ok=True)
    ext = src.suffix.lower()
    dst = dst_dir / f"{out_basename}{ext}"
    shutil.copy2(src, dst)


def transform_to_esde(
    platform: str,
    game: dict,
    assets_base: str,
    roms_subdir: str | None = None,
) -> ET.Element:
    """
    构造一个 <game> element。
      - name
      - path
      - sortname
      - desc
      - developer / publisher
      - image / marquee / video（兼容用，ES-DE 主用 downloaded_media）
    """
    game_elem = ET.Element("game")

    def add(tag: str, text):
        if text is None:
            return
        s = str(text).strip()
        if not s:
            return
        elem = ET.SubElement(game_elem, tag)
        elem.text = s

    # name：优先 game，其次 canonical_name，再不行用 file 顶上
    name = game.get("game") or game.get("canonical_name") or game.get("file")
    add("name", name)

    # path：ES-DE 的 ROM 相对路径
    file_name = game.get("file")
    if file_name:
        file_name_only = Path(file_name).name
        sub = (roms_subdir or "").strip().replace("\\", "/")
        if sub:
            rel_path = f"./{sub}/{file_name_only}"
        else:
            rel_path = f"./{file_name_only}"
        add("path", rel_path)

    # sortname：用 sort_by 保证排序稳定
    sort_by = game.get("sort_by")
    if sort_by:
        add("sortname", f"{sort_by} {name}")

    # desc：把 \n 还原成真正换行
    desc = game.get("description")
    if desc:
        add("desc", desc.replace("\\n", "\n"))

    # developer / publisher
    dev = game.get("developer")
    if dev:
        add("developer", dev)
        add("publisher", dev)

    # === 媒体 tag（兼容） ===
    assets = game.get("assets") or {}

    def norm_rel(path: str | None):
        if not path:
            return None
        p = path.replace("\\", "/")
        if not p.startswith("./") and not p.startswith("/"):
            p = "./" + p
        return p

    image = norm_rel(assets.get("box_front"))
    marquee = norm_rel(assets.get("logo"))
    video = norm_rel(assets.get("video"))

    if image:
        add("image", image)
    if marquee:
        add("marquee", marquee)
    if video:
        add("video", video)

    return game_elem
