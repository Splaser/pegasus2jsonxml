import os


def slugify(name: str) -> str:
    # 简单一点就够用：全小写，空格 -> 下划线
    return (
        name.replace("\\", "/")
        .split("/")[-1]
        .strip()
        .lower()
        .replace(" ", "_")
    )



def discover_platforms(resource_root: str = "Resource"):
    """
    自动扫描 Resource 下所有子目录，找 metadata.pegasus.txt

    返回 dict:
        key -> (平台显示名, meta_path)
    """
    platforms = {}

    if not os.path.isdir(resource_root):
        return platforms

    for entry in os.listdir(resource_root):
        platform_dir = os.path.join(resource_root, entry)
        if not os.path.isdir(platform_dir):
            continue

        meta_path = os.path.join(platform_dir, "metadata.pegasus.txt")
        if not os.path.isfile(meta_path):
            continue

        key = slugify(entry)          # 例如 "DC" -> "dc", "FBNEO ACT" -> "fbneo_act"
        name = entry                  # 人类可读平台名，保持原文件夹名
        platforms[key] = (name, meta_path)

    return platforms