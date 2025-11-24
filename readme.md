
# Pegasus2JSONXML

一个用于将 Pegasus 的 `metadata.pegasus.txt` 统一转换为结构化 JSON（jsondb）的轻量工具，并支持从 JSON 反向生成规范化 metadata 文件。

## 功能特性

- Pegasus metadata ➜ JSON（jsondb）
- JSON ➜ Canonical Pegasus metadata
- 保证解析与回写的 **闭合性（round‑trip）**
- 自动处理 launch_block、default_core、assets、rom 列表等
- 统一平台扫描、批量导出、批量验证
- 多前端导出（Daijisho / ES-DE / RetroArch）

## 目录结构

```
PEGASUS2JSONXML/
├── CanonicalMetadata/       # 从 jsondb 反向生成的 metadata
├── jsondb/                  # 导出的 JSON 数据库
├── Resource/                # 原始 metadata.pegasus.txt
├── Tools/                   # 解析/写入/导出工具
├── Utils/                   # 辅助函数
└── main.py                  # CLI 入口
```

## 使用说明

### 查看所有平台

```
python main.py --list
```

### 导出所有 metadata ➜ jsondb

```
python main.py
# 或
python main.py all
```

### 仅导出单个平台

```
python main.py dc
python main.py wii_official
```

### 闭合性验证（parse ➜ dump ➜ parse）

所有平台：

```
python main.py --verify all
```

单个平台：

```
python main.py --verify dc
```

---

## 从 jsondb 反向生成 CanonicalMetadata

所有平台：

```
python main.py --export-pegasus all
```

单个平台：

```
python main.py --export-pegasus dc
```

---

## 自定义目录

```
python main.py --resource-root MyMeta --out-root MyJson all
```

---

## JSON Schema 示例

```
{
  "schema_version": 1,
  "platform": "wii official",
  "collection": "WII",
  "default_sort_by": "032",
  "launch_block": "...",
  "default_core": "dolphin_libretro",
  "assets_base": "media",
  "games": [
    {
      "id": "dc_7fa2b31c9f1a2c3d",
      "canonical_name": "蓝海豚",
      "game": "蓝海豚",
      "file": "蓝海豚.cdi",
      "roms": ["蓝海豚.cdi"],
      "sort_by": "001",
      "developer": "蓝海豚",
      "description": "...",
      "assets": {
        "box_front": "media/蓝海豚/boxfront.png",
        "logo": "media/蓝海豚/logo.png",
        "video": "media/蓝海豚/video.mp4"
      }
    }
  ]
}
```

---

## AI 重写 JSONL Prompt 模板

下面是一批 JSON Lines，每行是一个游戏记录。  
请按照这些规则批量修改其中的 `description` 字段，并输出结构完全相同的 JSON Lines：

1. 除 `description` 外，不要修改、删除或新增任何字段（包括 `platform_key`、`platform`、`id`、`game`、`developer`、`file`、`is_hack` 等都保持原样）。
2. `is_hack == false`：可以对 `description` 做适度重写，要求：
   - 中文、简洁客观
   - 不要编造不存在的系统或剧情
   - 尽量保留原文提到的关键信息
3. `is_hack == true`：视为改版 / Hack / Mod 版本：
   - 只允许轻度润色
   - 不删除任何描述改动/特性的信息
4. 输出时：
   - 保持 JSON Lines，每行一个 JSON
   - 顺序与输入一致
   - 不要输出解释文字

---

如需更多功能可继续扩展。
