# PS2 Rename

该目录把可执行脚本、本地映射数据和原始说明分开：

```text
PS2Rename/
├── scripts/   # 可执行 Python 脚本
├── data/      # 生成及人工补全的 JSON 映射（本地数据）
└── docs/      # 原始中文/非中文说明（本地数据）
```

## 建议流程

1. `python Tools/PS2Rename/scripts/build_raw_mapping.py`
2. `python Tools/PS2Rename/scripts/build_redump_template.py`
3. 在 `data/ps2_mapping_redump.json` 中补全 Redump 英文名。
4. `python Tools/PS2Rename/scripts/rename_ps2_chd.py` 预览 CHD 重命名计划。
5. 确认无误后使用 `python Tools/PS2Rename/scripts/rename_ps2_chd.py --apply`。
6. 按需运行 `apply_rename_to_jsondb.py` 和 `rename_ps2_media_dirs.py`。

`data/*.json` 和 `docs/*.txt` 仍按项目现有规则作为本地数据，不提交到 Git。CHD 重命名默认是 dry-run，只有显式传入 `--apply` 才会写入。
