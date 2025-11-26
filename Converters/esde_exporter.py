# Converters/esde_exporter.py

from pathlib import Path
import xml.etree.ElementTree as ET
import json
import shutil


def export_esde(platform: str, json_path: Path, out_dir: Path, roms_subdir: str = "roms"):
    """
    jsondb/<platform>.json -> ES-DE gamelist.xml

    out_dir/
      <platform>/
        gamelist.xml
        media/  (可选，在这里复制封面 / logo / 视频)

    roms_subdir:
      - 默认 "./roms/<file>"，你也可以传空字符串让 path 直接指向 "./<file>"。
    """

    data = json.loads(json_path.read_text(encoding="utf-8"))
    games = data.get("games", [])
    assets_base = data.get("assets_base", "media")

    out_platform_dir = out_dir / platform
    out_platform_dir.mkdir(parents=True, exist_ok=True)

    root = ET.Element("gameList")

    for g in games:
        game_elem = transform_to_esde(
            platform=platform,
            game=g,
            assets_base=assets_base,
        )
        root.append(game_elem)

        # === 可选：顺手复制 media 资源 ===
        assets = g.get("assets") or {}
        for key in ("box_front", "logo", "video"):
            rel = assets.get(key)
            if not rel:
                continue
            _copy_asset(json_path.parent, out_platform_dir, rel)

    out_path = out_platform_dir / "gamelist.xml"
    tree = ET.ElementTree(root)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)

    print(f"[OK] ES-DE export -> {out_path}")
    return out_path


def _copy_asset(src_root: Path, dst_root: Path, rel_path: str):
    """
    把 jsondb 里记录的 media/<xxx> 复制到 ES 平台目录下，保持相对路径一致：
      src: src_root / rel_path
      dst: dst_root / rel_path
    """
    rel = rel_path.lstrip("./").replace("\\", "/")
    src = (src_root / rel).resolve()
    dst = (dst_root / rel)

    if not src.is_file():
        # 不存在就算了，后面有需要可以加日志
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def transform_to_esde(platform: str, game: dict, assets_base: str) -> ET.Element:
    """
    构造一个 <game> element。
    目前字段：
      - name
      - path
      - sortname
      - desc
      - developer
      - image / marquee / video
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
        # 如果你不想强制 "./roms"，可以在 export_esde 里把 roms_subdir 传进来
        add("path", f"./roms/{file_name}")

    # sortname：用你的 sort_by 保证排序稳定
    sort_by = game.get("sort_by")
    if sort_by:
        add("sortname", f"{sort_by} {name}")

    # desc：把 \n 还原成真正换行
    desc = game.get("description")
    if desc:
        add("desc", desc.replace("\\n", "\n"))

    # developer / publisher（先都写成 developer，后续你分开再改）
    dev = game.get("developer")
    if dev:
        add("developer", dev)
        add("publisher", dev)

    # === 媒体：image / marquee / video ===
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
