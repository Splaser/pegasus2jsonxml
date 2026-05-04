#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


DEFAULT_SRC_ROOT = Path("CanonicalMetadata")
DEFAULT_TF_ROMS_ROOT = Path(r"F:\roms")
DEFAULT_BACKUP_ROOT = Path("TF_Metadata_Backup")


@dataclass
class CopyPlan:
    key: str
    src_dir: str
    src_metadata: str
    tf_dir: str | None
    tf_metadata: str | None
    status: str
    backed_up_to: str | None = None


def normalize_name(name: str) -> str:
    """
    Match project keys like:
      fbneo_act_hack
      mame_stg_v
      18x_cdr

    To TF folders like:
      FBNEO ACT hack
      MAME STG V
      18X CDR
    """
    s = name.strip().lower()
    s = s.replace("&", "and")
    s = re.sub(r"[_\-\s]+", "", s)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def find_metadata_sources(src_root: Path) -> dict[str, Path]:
    """
    Returns normalized_key -> metadata path.
    Supports both:
      CanonicalMetadata/fbneo_act/metadata.pegasus.txt
      CanonicalMetadata/FBNEO ACT/metadata.pegasus.txt
    """
    result: dict[str, Path] = {}

    for p in src_root.rglob("metadata.pegasus.txt"):
        platform_dir = p.parent.name
        key = normalize_name(platform_dir)

        # If duplicate normalized names appear, keep first and warn by suffix key.
        if key in result:
            print(f"[WARN] duplicate source normalized key: {platform_dir} -> {key}")
            print(f"       keep: {result[key]}")
            print(f"       skip: {p}")
            continue

        result[key] = p

    return result


def find_tf_platform_dirs(tf_roms_root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}

    for d in tf_roms_root.iterdir():
        if not d.is_dir():
            continue

        key = normalize_name(d.name)

        if key in result:
            print(f"[WARN] duplicate TF normalized key: {d.name} -> {key}")
            print(f"       keep: {result[key]}")
            print(f"       skip: {d}")
            continue

        result[key] = d

    return result


def build_plan(src_root: Path, tf_roms_root: Path) -> list[CopyPlan]:
    sources = find_metadata_sources(src_root)
    tf_dirs = find_tf_platform_dirs(tf_roms_root)

    plans: list[CopyPlan] = []

    for key, src_meta in sorted(sources.items()):
        tf_dir = tf_dirs.get(key)

        if not tf_dir:
            plans.append(CopyPlan(
                key=key,
                src_dir=str(src_meta.parent),
                src_metadata=str(src_meta),
                tf_dir=None,
                tf_metadata=None,
                status="NO_MATCHING_TF_FOLDER",
            ))
            continue

        plans.append(CopyPlan(
            key=key,
            src_dir=str(src_meta.parent),
            src_metadata=str(src_meta),
            tf_dir=str(tf_dir),
            tf_metadata=str(tf_dir / "metadata.pegasus.txt"),
            status="READY",
        ))

    return plans


def copy_with_backup(plan: CopyPlan, backup_root: Path) -> CopyPlan:
    if plan.status != "READY" or not plan.tf_metadata:
        return plan

    src = Path(plan.src_metadata)
    dst = Path(plan.tf_metadata)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if dst.exists():
        # Backup path mirrors TF folder name.
        backup_dir = backup_root / Path(plan.tf_dir).name
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"metadata.pegasus.{timestamp}.bak.txt"
        shutil.copy2(dst, backup_path)
        plan.backed_up_to = str(backup_path)

    shutil.copy2(src, dst)
    plan.status = "UPDATED"
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy CanonicalMetadata metadata.pegasus.txt back to TF card rom folders."
    )

    parser.add_argument(
        "--src-root",
        type=Path,
        default=DEFAULT_SRC_ROOT,
        help="Source metadata root. Default: CanonicalMetadata",
    )
    parser.add_argument(
        "--tf-roms-root",
        type=Path,
        default=DEFAULT_TF_ROMS_ROOT,
        help=r"TF roms root. Default: F:\roms",
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        default=DEFAULT_BACKUP_ROOT,
        help="Backup root for old TF metadata files.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually copy files. Without this flag, dry-run only.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("tf_metadata_write_report.json"),
        help="Write JSON report.",
    )

    args = parser.parse_args()

    if not args.src_root.exists():
        raise SystemExit(f"[ERROR] source root not found: {args.src_root}")

    if not args.tf_roms_root.exists():
        raise SystemExit(f"[ERROR] TF roms root not found: {args.tf_roms_root}")

    plans = build_plan(args.src_root, args.tf_roms_root)

    updated = 0
    ready = 0
    missing = 0

    for plan in plans:
        if plan.status == "READY":
            ready += 1
            if args.apply:
                copy_with_backup(plan, args.backup_root)
                updated += 1
                print(f"[UPDATED] {Path(plan.tf_dir).name}")
            else:
                print(f"[DRY] {Path(plan.src_dir).name} -> {Path(plan.tf_dir).name}")
        else:
            missing += 1
            print(f"[SKIP] {Path(plan.src_dir).name}: {plan.status}")

    report = [asdict(p) for p in plans]
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"[SUMMARY] ready={ready}, updated={updated}, missing_tf_folder={missing}")
    print(f"[REPORT] {args.report}")

    if not args.apply:
        print("[INFO] dry-run only. Add --apply to write to TF card.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())