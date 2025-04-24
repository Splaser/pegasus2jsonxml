import os
import xml.etree.ElementTree as ET


def parse_pegasus_config(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    games = []
    current_game = {}
    ignore_files = set()
    allowed_extensions = set()
    in_ignore_block = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("ignore-files:"):
            in_ignore_block = True
            continue
        if in_ignore_block:
            if line.startswith("-"):
                ignore_files.add(line[1:].strip())
                continue
            else:
                in_ignore_block = False

        if line.startswith("extension:"):
            exts = line.split(":", 1)[1].strip()
            allowed_extensions = set(ext.strip().lower() for ext in exts.split(","))
            continue

        if line.startswith("game:"):
            if current_game:
                games.append(current_game)
            current_game = {"name": line.split(":", 1)[1].strip()}
        elif ':' in line and current_game is not None:
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip()
            current_game[key] = val

    if current_game:
        games.append(current_game)

    return games, ignore_files, allowed_extensions


def media_path(file_base, subfile):
    return f"./media/{file_base}/{subfile}"

def build_esde_gamelist(parsed_result, base_path=".", output_file="gamelist.xml"):
    games, ignore_files, allowed_extensions = parsed_result
    root = ET.Element("gameList")

    count = 0
    for game in games:
        file_name = game.get("file", "")
        if not file_name:
            continue
        if file_name in ignore_files:
            continue
        ext = os.path.splitext(file_name)[1].lower().lstrip(".")
        if allowed_extensions and ext not in allowed_extensions:
            continue

        file_base = os.path.splitext(file_name)[0]
        game_el = ET.SubElement(root, "game")

        ET.SubElement(game_el, "path").text = f"./{file_name}"
        ET.SubElement(game_el, "name").text = game.get("name", "")
        ET.SubElement(game_el, "desc").text = game.get("description", "")
        ET.SubElement(game_el, "developer").text = game.get("developer", "")
        ET.SubElement(game_el, "sortname").text = game.get("sort-by", "")

        media_dir = os.path.join(base_path, "media", file_base)

        image_path = os.path.join(media_dir, "boxFront.jpg")
        if os.path.isfile(image_path):
            ET.SubElement(game_el, "image").text = f"./media/{file_base}/boxFront.jpg"

        marquee_path = os.path.join(media_dir, "logo.png")
        if os.path.isfile(marquee_path):
            ET.SubElement(game_el, "marquee").text = f"./media/{file_base}/logo.png"

        video_path = os.path.join(media_dir, "video.mp4")
        if os.path.isfile(video_path):
            ET.SubElement(game_el, "video").text = f"./media/{file_base}/video.mp4"

        count += 1

    ET.ElementTree(root).write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"✅ gamelist.xml written with {count} games. Ignored: {len(ignore_files)}, Extensions allowed: {', '.join(allowed_extensions) if allowed_extensions else 'all'}")


if __name__ == "__main__":
    input_file = "pegasus_collection.txt"  # 替换为你的 Pegasus 配置路径
    build_esde_gamelist(parse_pegasus_config(input_file))
