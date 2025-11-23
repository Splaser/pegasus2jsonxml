#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
从 jsondb/{key}.json 生成 CanonicalMetadata/{key}/metadata.pegasus.txt
"""

from __future__ import annotations

import os
import json
from typing import Any, Dict, List

from Tools.metadata_writer import dump_pegasus_metadata


def json_to_metadata(
    key: str,
    json_path: str,
    output_root: str = "CanonicalMetadata",
) -> str:
    """
    根据 jsondb/<key>.json 恢复 / 生成 Pegasus metadata：

        CanonicalMetadata/<key>/metadata.pegasus.txt

    返回写出的 metadata 路径。
    """
    with open(json_path, "r", encoding="utf-8") as f:
        payload: Dict[str, Any] = json.load(f)

    # 按现在导出的 json 结构来还原 header
    header: Dict[str, Any] = {
        "collection": payload.get("collection") or payload.get("platform_name") or key,
        "default_sort_by": payload.get("default_sort_by"),
        "launch_block": payload.get("launch_block"),
        "extensions": payload.get("extensions") or [],
        "ignore_files": payload.get("ignore_files") or [],
    }

    games: List[Dict[str, Any]] = payload.get("games", [])

    out_dir = os.path.join(output_root, key)
    os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, "metadata.pegasus.txt")
    dump_pegasus_metadata(out_path, header, games)
    return out_path
