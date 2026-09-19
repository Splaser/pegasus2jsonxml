# Tools

`Tools` 根目录保留主程序会导入的 Python 模块，避免打断 `Tools.*` 公共路径。

## 核心模块

- `export_to_json.py`：Pegasus metadata 转 `jsondb`。
- `json_to_metadata.py`：`jsondb` 转回 CanonicalMetadata。
- `metadata_scanner.py` / `metadata_writer.py`：metadata 解析与写回。
- `base.py`：往返转换的闭合性检查。
- `rom_scanner.py`：ROM 大小与哈希扫描。
- `metadata_editor.py`：小范围编辑 metadata 游戏条目。

## 独立工具

- `export_descriptions.py`：导出描述 JSONL。
- `core_planner.py`：核心选择规则的实验性模块。
- `PS2Rename/`：PS2 CHD 名称映射和重命名工具，具体顺序见其 README。

`__pycache__` 和 `*.pyc` 是运行时产物，已由项目 `.gitignore` 排除，不属于源码。
