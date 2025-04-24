import os
import json
import re


def parse_pegasus_config(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    games = []
    current_game = {}
    launch_lines = []
    ignore_files = set()
    in_ignore_block = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检查 ignore-files 段
        if line.startswith("ignore-files:"):
            in_ignore_block = True
            continue
        if in_ignore_block and line.startswith("-"):
            ignore_files.add(line[1:].strip())
            continue
        if in_ignore_block and not line.startswith("-"):
            in_ignore_block = False

        # launch 块
        if line.startswith("launch:"):
            launch_lines = []
        elif launch_lines or line.startswith("-e ") or line.startswith("am start"):
            launch_lines.append(line)

        # 游戏块
        elif line.startswith("game:"):
            if current_game:
                games.append(current_game)
            current_game = {"title": line.split(":", 1)[1].strip()}
        elif ':' in line and current_game is not None:
            key, val = line.split(":", 1)
            current_game[key.strip().lower()] = val.strip()

    if current_game:
        games.append(current_game)

    return games, launch_lines, ignore_files


def parse_launch_block(launch_lines):
    package = ""
    activity = ""
    intent = {}

    for line in launch_lines:
        if "-n " in line:
            parts = line.split("-n ")[1].strip().split("/")
            package, activity = parts[0], parts[1]
        elif line.startswith("-e "):
            parts = line.split(" ", 2)
            if len(parts) == 3:
                key, value = parts[1], parts[2]
                intent[key] = value
    return package, activity, intent


def make_daijisho_json(game, media_root, rom_root, package, activity, base_intent, output_dir):
    file_name = game.get("file", "")
    file_base = os.path.splitext(file_name)[0]

    rom_path = f"{rom_root}/{file_name}"
    media_path = f"{media_root}/{file_base}"

    intent = base_intent.copy()
    if "ROM" in intent:
        intent["ROM"] = rom_path  # 替换 ROM 参数为实际路径

    game_json = {
        "title": game.get("title", ""),
        "rom": rom_path,
        "description": game.get("description", ""),
        "developer": game.get("developer", ""),
        "sorttitle": game.get("sort-by", ""),
        "image": f"{media_path}/boxFront.jpg" if os.path.exists(f"{media_path}/boxFront.jpg") else "",
        "marquee": f"{media_path}/logo.png" if os.path.exists(f"{media_path}/logo.png") else "",
        "video": f"{media_path}/video.mp4" if os.path.exists(f"{media_path}/video.mp4") else "",
        "package": package,
        "activity": activity,
        "intent": intent
    }

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, f"{file_base}.json"), 'w', encoding='utf-8') as f:
        json.dump(game_json, f, indent=2, ensure_ascii=False)


def main():
    config_file = "pegasus_collection.txt"
    rom_root = "/storage/emulated/0/Emu/Arcade"
    media_root = f"{rom_root}/media"
    output_dir = "daijisho_output"

    games, launch_lines, ignore_files = parse_pegasus_config(config_file)
    package, activity, base_intent = parse_launch_block(launch_lines)

    count = 0
    for game in games:
        file_name = game.get("file", "")
        if file_name in ignore_files:
            continue
        make_daijisho_json(game, media_root, rom_root, package,
                           activity, base_intent, output_dir)
        count += 1

    print(f"✅ 转换完成，共生成 {count} 个 Daijisho 游戏配置文件。输出目录：{output_dir}")


if __name__ == "__main__":
    main()
