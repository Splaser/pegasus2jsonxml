# Pegasus2JSONXML

Pegasus2JSONXML 是一个面向复古掌机 / Android 前端的 **ROM 元数据治理与配置分发工具链**。

它的核心目标不是只把 `metadata.pegasus.txt` 转成 JSON，而是把 Pegasus、RetroArch Android、TF 卡目录、media 资源、core override、ignore-files 等分散配置统一收敛到一个可批量处理的 `jsondb` 中间库，再根据需要导出回 Pegasus，后续也可以继续扩展到 Daijisho、RetroArch playlist、ES-DE、LaunchBox 等前端。

---

## 当前定位

```text
Resource / 脏 metadata.pegasus.txt
        ↓
      jsondb
        ↓
清洗 / 修复 / 规则化：
  - RetroArch Android core alias
  - platform-level launch_block
  - game-level launch_override / core_override
  - ignore-files 异常项
  - assets / media 路径规则
  - multidisc media 规则
        ↓
CanonicalMetadata / metadata.pegasus.txt
        ↓
TF 卡 roms/<平台>/metadata.pegasus.txt
```

项目适合以下场景：

- 已经有大量 Pegasus `metadata.pegasus.txt`。
- ROM、media、说明、排序、改版条目已经人工维护过。
- 想把这些配置结构化成 JSON，便于批量修改。
- 想统一 RetroArch Android 的 core 启动方式。
- 想避免 Daijisho / ES-DE / LaunchBox 等前端重新 scrape media。
- 想把“脏配置包”治理成自己的标准库。

---

## 主要功能

### 1. Pegasus metadata → jsondb

从 `Resource/<platform>/metadata.pegasus.txt` 批量导出结构化 JSON：

```powershell
python .\main.py
# 或
python .\main.py all
```

单个平台：

```powershell
python .\main.py fbneo_act_hack
```

导入时会自动完成 RetroArch Android core alias 清洗，不再需要额外执行
`pegasus_alias_rewrite.py`。

---

### 2. jsondb → Canonical Pegasus metadata

从 JSON 反向生成规范化 Pegasus metadata：

```powershell
python .\main.py all --export-pegasus --out-root jsondb
```

如果你保留了 alias 后的独立目录，也可以：

```powershell
python .\main.py all --export-pegasus --out-root jsondb_alias
```

输出目录：

```text
CanonicalMetadata/<platform>/metadata.pegasus.txt
```

---

### 3. RetroArch Android core alias 清洗

Android 版 RetroArch 在外部 intent 启动时，直接传 `.so` 绝对路径容易出现黑屏、ANR 或 core 初始化异常。实测更稳定的方式是传 core alias：

```text
fbneo_libretro_android.so              → fbneo
mamearcade_libretro_android.so         → mamearcade
mame_libretro_android.so               → mamearcade
mednafen_saturn_libretro_android.so    → mednafen_saturn
swanstation_libretro_android.so        → swanstation
snes9x_libretro_android.so             → snes9x
fbneo_libretro_old_android             → fbneo
```

`main.py` 的新导入结果已经自动完成这一步。独立脚本保留用于修复已有
JSONDB，或检查历史数据：

```powershell
# dry-run，只看报告
python .\pegasus_alias_rewrite.py --dry-run

# 实际写出 / 覆盖配置
python .\pegasus_alias_rewrite.py
```

清洗范围包括：

```text
顶层：
  launch_block
  default_launch_info.raw
  default_launch_info.tokens
  default_launch_info.core
  default_core

单游戏：
  games[*].launch_override
  games[*].launch_info.raw
  games[*].launch_info.tokens
  games[*].launch_info.core
  games[*].core_override
```

目标效果：

```text
-e LIBRETRO /data/data/com.retroarch.aarch64/cores/fbneo_libretro_android.so
```

变成：

```text
-e LIBRETRO fbneo
```

并自动把：

```text
-e ROM {file.path}
```

修正为：

```text
-e ROM "{file.path}"
```

---

### 4. ignore-files 异常扫描与清理

街机平台常见 `ignore-files` 里保留 BIOS / parent / device ROM，例如：

```text
neogeo.zip
pgm.zip
stvbios.zip
sys573.zip
```

这些应该保留。

但部分脏配置会把真实游戏 ROM 也塞进 `ignore-files`，例如：

```text
吞食天地2 多功能加强版/wof.zip
恐龙新世纪 无限保险版/dino.zip
```

如果这些路径同时出现在 `games[*].roms / games[*].file / games[*].files` 中，就应从 `ignore-files` 删除。

扫描：

```powershell
python .\scan_ignore_files.py
```

实际清理：

```powershell
python .\scan_ignore_files.py --apply
```

指定目录：

```powershell
python .\scan_ignore_files.py --json-root jsondb --apply
```

---

### 5. assets / media 输出规则

项目当前采用的 media 规则：

#### 单层 ROM

```text
file: mslugqy.zip
默认 media:
  media/mslugqy/boxfront.png
  media/mslugqy/logo.png
  media/mslugqy/video.mp4
```

这类默认资源不需要写 `assets.*`。

#### 嵌套 ROM

```text
file: mslugd/mslug.zip
assets:
  media/mslugd/boxfront.jpg
  media/mslugd/logo.png
  media/mslugd/video.mp4
```

嵌套 ROM 的资源推断不稳定，只要 JSON 中存在显式 assets，就写回 metadata。

同理：

```text
file: 恐龙新世纪 无限保险版/dino.zip
assets:
  media/恐龙新世纪 无限保险版/boxfront.jpg
```

必须保留。

#### ROM stem 资源 override

```text
file: hxs1/powerins.zip
assets:
  media/powerins/boxfront.jpg
```

虽然 `powerins` 是 ROM stem，但因为 ROM 位于子目录 `hxs1/`，仍然保留显式 assets。

#### 旧噪音资源

如果单层 ROM 被错误补成：

```text
file: mslugqy.zip
assets:
  media/合金弹头1 起源版/boxfront.png
```

这类 `media/<中文游戏名>/...` 对当前实际资源结构是噪音，导出时不写。

---

### 6. multidisc / multifile media 逻辑

多碟 / 多文件游戏继续保留老逻辑。

例如：

```text
files:
  009/Lunar 2 Eternal Blue (Japan).m3u
  009/Lunar 2 Eternal Blue (Japan) (Disc 1).chd
  009/Lunar 2 Eternal Blue (Japan) (Disc 2).chd
```

media 默认指向：

```text
media/009/boxFront.png
media/009/logo.png
media/009/video.mp4
```

multidisc 条目会显式写回 assets，避免前端推断错误。

---

### 7. TF 卡 metadata 写回

将 `CanonicalMetadata/<platform>/metadata.pegasus.txt` 写回 TF 卡：

```text
F:\roms\<平台>\metadata.pegasus.txt
```

只会写入 TF 卡上已经存在、并且至少检测到一个实际 ROM 文件的平台目录。
不存在的平台目录不会创建；空目录或只有 `media/metadata.pegasus.txt` 的目录会以
`NO_ROMS_IN_TF_FOLDER` 跳过。

由于项目 key 与 TF 卡目录名可能不同：

```text
jsondb key:
  fbneo_act_hack

TF 卡目录:
  FBNEO ACT hack
```

写回脚本会做 normalize 匹配，只覆盖存在的 TF 平台目录。

dry-run：

```powershell
python .\write_metadata_to_tf.py
```

实际覆盖：

```powershell
python .\write_metadata_to_tf.py --apply
```

覆盖前会备份旧 metadata 到：

```text
TF_Metadata_Backup/<TF平台目录>/metadata.pegasus.YYYYMMDD_HHMMSS.bak.txt
```

---

## 推荐工作流

### 标准流程

```powershell
# 1. Resource -> jsondb
python .\main.py

# 2. 清理误伤游戏的 ignore-files
python .\scan_ignore_files.py --json-root jsondb --apply

# 3. jsondb -> CanonicalMetadata
python .\main.py all --export-pegasus --out-root jsondb

# 4. dry-run 写回 TF
python .\write_metadata_to_tf.py

# 5. 实际写回 TF
python .\write_metadata_to_tf.py --apply
```

### 修复已有 JSONDB

无需重新导入 Resource 时，可以单独检查并修复历史 JSON：

```powershell
python .\pegasus_alias_rewrite.py --dry-run
python .\pegasus_alias_rewrite.py
```

---

## 常用检查命令

### 检查是否还有旧 RetroArch core path

```powershell
Select-String -Path .\CanonicalMetadata\**\metadata.pegasus.txt -Pattern "_libretro_android|/data/data/com.retroarch"
```

### 检查旧脏 alias 是否残留

```powershell
Select-String -Path .\CanonicalMetadata\**\metadata.pegasus.txt -Pattern "fbneo_libretro_old_android"
```

### 检查某个平台 assets

```powershell
Select-String -Path ".\CanonicalMetadata\fbneo_act_hack\metadata.pegasus.txt" -Pattern "assets.box_front|assets.logo|assets.video"
```

### 检查某个游戏

```powershell
Select-String -Path ".\CanonicalMetadata\fbneo_ftg_hack\metadata.pegasus.txt" -Pattern "豪血寺一族1 降龙简化版" -Context 0,8
```

### 检查 ignore-files 报告

```powershell
python .\scan_ignore_files.py
type .\ignore_scan_report.json
```

---

## 目录结构

```text
PEGASUS2JSONXML/
├── Resource/                     # 原始 Pegasus metadata 与 media
│   └── <platform>/
│       ├── metadata.pegasus.txt
│       └── media/
│
├── jsondb/                       # 结构化 JSON 主库
│   └── <platform>.json
│
├── jsondb_alias/                 # 可选：alias 清洗后的 JSON 输出目录
│
├── CanonicalMetadata/            # 从 jsondb 反向生成的 metadata
│   └── <platform>/
│       └── metadata.pegasus.txt
│
├── TF_Metadata_Backup/           # 写回 TF 前的旧 metadata 备份
│
├── Tools/
│   ├── export_to_json.py         # Pegasus metadata -> jsondb
│   ├── json_to_metadata.py       # jsondb -> CanonicalMetadata
│   ├── metadata_writer.py        # metadata 写回规则
│   └── ...
│
├── Converters/                   # 其他前端导出器，实验/扩展用
│   ├── daijisho_exporter.py
│   ├── esde_exporter.py
│   └── retroarch_exporter.py
│
├── Utils/
│   └── helpers.py
│
├── main.py                       # 主 CLI
├── pegasus_alias_rewrite.py      # RetroArch Android core alias 清洗
├── scan_ignore_files.py          # ignore-files 异常扫描/清理
├── write_metadata_to_tf.py       # CanonicalMetadata 写回 TF 卡
└── README.md
```

---

## JSON Schema 示例

```json
{
  "schema_version": 1,
  "platform": "fbneo_act_hack",
  "collection": "动作街机",
  "default_sort_by": "001",
  "launch_block": "am start --user 0\n  -n com.retroarch.aarch64/com.retroarch.browser.retroactivity.RetroActivityFuture\n  -e ROM \"{file.path}\"\n  -e LIBRETRO fbneo\n  -e CONFIGFILE /storage/emulated/0/Android/data/com.retroarch.aarch64/files/retroarch.cfg\n  --activity-clear-top",
  "default_core": "fbneo",
  "assets_base": "media",
  "ignore_files": [
    "pgm.zip",
    "neogeo.zip",
    "stvbios.zip"
  ],
  "games": [
    {
      "id": "FBNEO ACT hack_a4748c16acb236ec",
      "canonical_name": "恐龙新世纪 无限保险版",
      "game": "恐龙新世纪 无限保险版",
      "file": "恐龙新世纪 无限保险版/dino.zip",
      "roms": [
        "恐龙新世纪 无限保险版/dino.zip"
      ],
      "sort_by": "0103",
      "developer": "恐龙新世纪 无限保险版",
      "description": "可以无限放保险",
      "assets": {
        "box_front": "media/恐龙新世纪 无限保险版/boxfront.jpg",
        "logo": "media/恐龙新世纪 无限保险版/logo.png",
        "video": "media/恐龙新世纪 无限保险版/video.mp4"
      },
      "core_override": "fbneo",
      "launch_override": "am start --user 0\n  -n com.retroarch.aarch64/com.retroarch.browser.retroactivity.RetroActivityFuture\n  -e ROM \"{file.path}\"\n  -e LIBRETRO fbneo\n  -e CONFIGFILE /storage/emulated/0/Android/data/com.retroarch.aarch64/files/retroarch.cfg\n  --activity-clear-top"
    }
  ]
}
```

---

## RetroArch Android core alias 规则

建议在 Pegasus / Android intent 中使用 alias，不直接传 `.so` 绝对路径。

```text
xxx_libretro_android.so       -> xxx
xxx_libretro_android          -> xxx
xxx_libretro_old_android      -> xxx
mame_libretro_android.so      -> mamearcade
mamearcade_libretro_android   -> mamearcade
fbneo_libretro_old_android    -> fbneo
```

常用 alias：

```text
fbneo
mamearcade
mame2003_plus
mame2010
snes9x
bsnes
mgba
genesis_plus_gx
swanstation
mednafen_psx
mednafen_psx_hw
mednafen_saturn
flycast
melonds
mupen64plus_next_gles3
```

---

## 其他前端适配状态

### Pegasus

当前主力输出目标。  
最适合本项目的 ROM + media + metadata 绑定模式。

### Daijisho

适合 Android 日用前端。  
优势是启动快、界面简洁、切 core/player 方便。后续计划：

```text
jsondb -> Daijisho import JSON
jsondb -> Daijisho DB direct inject（root 后研究）
```

### RetroArch playlist

可作为备用启动列表。  
RA 自身 media 体系是 playlist label 对 thumbnail filename，不适合作为主展示前端，但 exporter 可继续完善。

### ES-DE / LaunchBox

二者 media 体系更偏向前端自己的集中式资源库，不天然支持 Pegasus 这种 `media/<资源目录>/三件套` 随 ROM 平台目录分发的模式。  
后续如需支持，应做 media flatten/copy adapter，而不是直接复用 Pegasus media layout。

---

## 后续 TODO

### 高优先级

- `set_core_override.py`
  - 平台级 core 修改
  - 单游戏 core override
  - 按 `platform + file / game / id` 精确修改
- `scan_missing_media.py`
  - 检查缺失 boxfront/logo/video
  - 报告默认 media 目录、嵌套 media 目录、显式 assets 是否存在
- Daijisho exporter
  - jsondb -> Daijisho import JSON
  - 后续研究 root 下 DB direct inject

### 中优先级

- PS2 资源命名治理
  - 魔法数字 `.chd` -> Redump 英文名
  - 中文展示名写回 JSON
  - 批量重命名 CHD 与 media 目录
- RetroArch playlist / thumbnail exporter
- 全项目残留扫描：
  - 旧 core path
  - 旧 alias
  - assets 噪音
  - ignore-files 误伤

### 低优先级

- ES-DE media adapter
- LaunchBox media adapter
- AI 批量润色 description 的 JSONL 管线增强

---

## AI 重写 JSONL Prompt 模板

下面是一批 JSON Lines，每行是一个游戏记录。  
请按照这些规则批量修改其中的 `description` 字段，并输出结构完全相同的 JSON Lines：

1. 除 `description` 外，不要修改、删除或新增任何字段。
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

## 设计原则

```text
jsondb 是主库。
Pegasus / Daijisho / ES-DE / LaunchBox / RetroArch 都只是输出目标。
```

项目目标是把复古游戏库从“前端私有配置”升级为可检查、可清洗、可回滚、可批量分发的数据工程。
