---
name: anime-character-loader
description: |
  Load anime character info from multiple sources and generate validated SOUL.generated.md files.
  Features: multi-source query, forced disambiguation, semantic validation, loading options.
version: 2.1.0
author: OpenClaw

commands:
  - name: load
    description: Load character with multi-source validation
    usage: load_character.py <character_name> [options]
    examples:
      - "load_character.py 'Kasumigaoka Utaha'"
      - "load_character.py '霞之丘诗羽' --anime 'Saekano'"
      - "load_character.py 'Sakurajima Mai' -o ./characters"

options:
  --anime, -a: Anime/manga name hint for disambiguation (REQUIRED for ambiguous names)
  --output, -o: Output directory (default: current)
  --info, -i: Show character info only
  --force, -f: Force generation even with low confidence
  --select, -s: Select specific match by index

output:
  filename: SOUL.generated.md
  loading_options:
    - "[1] REPLACE - cp SOUL.generated.md SOUL.md"
    - "[2] MERGE - Append to existing SOUL.md"
    - "[3] KEEP - Manual review"

validation:
  score_threshold: 80
  required_sections:
    - Identity
    - Personality
    - Boundaries
  semantic_checks:
    - contains_name: Character name present
    - contains_source: Source work referenced
    - has_structure: All required sections present
    - content_length: Minimum 500 characters
    - no_placeholders: No TODO/FIXME/placeholder text
    - meaningful_background: Background has substance
    - specific_personality: Personality not generic
    - speaking_style_details: Speaking Style has bullets
    - name_consistency: Name variations consistent

data_sources:
  - name: AniList
    endpoint: https://graphql.anilist.co
    weight: 0.5
    auth: none
  - name: Jikan (MyAnimeList)
    endpoint: https://api.jikan.moe/v4
    weight: 0.3
    auth: none
  - name: Fandom Wikia
    endpoint: https://{wiki}.fandom.com/api.php
    weight: 0.2
    auth: none

features:
  - Multi-source parallel query
  - Automatic failover and retry
  - 24-hour response cache
  - FORCED disambiguation (requires --anime for ambiguous names)
  - Semantic validation with 9 checks
  - Atomic write with rollback
  - Loading options prompt

confidence_levels:
  high: ">= 0.8 (auto-select with hint)"
  medium: "0.5-0.8 (requires --anime or --select)"
  low: "< 0.5 (reject or --force)"

forced_disambiguation: |
  When multiple matches found OR single match with low confidence,
  --anime hint is REQUIRED. Prevents selecting wrong character.
---

# Anime Character Loader v2.1

## Overview

多源动漫角色数据加载器，生成经过验证的 SOUL.generated.md 人格文件。

**⚠️ 重要: v2.1 强制消歧模式** - 同名角色必须提供 `--anime` 提示

## Key Improvements (v2.1)

### 1. 输出文件约定
- **固定文件名**: `SOUL.generated.md`
- **加载选项**: 生成后提示 REPLACE / MERGE / KEEP

### 2. 强制消歧 (Force Disambiguation)
```bash
# ❌ 会失败 - Sakura 有多个角色
python load_character.py "Sakura"

# ✅ 必须提供作品提示
python load_character.py "Sakura" --anime "Fate"
python load_character.py "Sakura" --anime "Naruto"

# ✅ 或用 --select 手动选择
python load_character.py "Sakura" --select 2
```

### 3. 语义校验 (9项检查)
| 检查项 | 类型 | 说明 |
|--------|------|------|
| contains_name | 基础 | 角色名存在 |
| contains_source | 基础 | 作品名存在 |
| has_structure | 基础 | 必需章节完整 |
| content_length | 基础 | 内容长度≥500 |
| no_placeholders | 基础 | 无占位符文本 |
| meaningful_background | 语义 | Background 有实质内容 |
| specific_personality | 语义 | Personality 非通用描述 |
| speaking_style_details | 语义 | Speaking Style 有细节 |
| name_consistency | 语义 | 角色名变体一致 |

**通过标准**: 无错误 + 总分 ≥ 80/100

### 4. 加载选项
生成完成后自动提示：
```
How would you like to load this character?

  [1] REPLACE - Replace existing SOUL.md
      cp ./SOUL.generated.md ./SOUL.md

  [2] MERGE - Add to existing SOUL.md
      Append character content

  [3] KEEP - Manual review
```

## Usage Examples

### Basic Usage (Unique Names)
```bash
# 唯一名字可以直接生成
python load_character.py "Kasumigaoka Utaha"
python load_character.py "霞之丘诗羽"
```

### Disambiguation Required
```bash
# 同名角色必须指定作品
python load_character.py "Sakura" --anime "Fate"
python load_character.py "Rin" --anime "Fate"
python load_character.py "Miku" --anime "Quintessential"
```

### Manual Selection
```bash
# 列出所有匹配手动选择
python load_character.py "Sakura" --select 2
```

### Preview Mode
```bash
# 只查看信息不生成
python load_character.py "加藤惠" --info
```

## Workflow

```
1. 名称翻译 (中文→英文/日文)
        ↓
2. 多源并行查询 (AniList + Jikan)
        ↓
3. 强制消歧检查
   - 多匹配? → 需要 --anime
   - 低置信? → 需要 --anime
        ↓
4. 生成 SOUL.generated.md
        ↓
5. 语义验证 (9项检查)
        ↓
6. 提示加载选项 (REPLACE/MERGE/KEEP)
```

## Configuration

### 强制消歧开关
```python
# 在 load_character.py 顶部
FORCE_DISAMBIGUATION = True  # 设为 False 恢复宽松模式
```

### 置信度阈值
```python
CONFIDENCE_THRESHOLD_HIGH = 0.8    # 高置信度
CONFIDENCE_THRESHOLD_MEDIUM = 0.6  # 中等置信度
CONFIDENCE_THRESHOLD_LOW = 0.5     # 最低接受线
```

## Error Handling

| 场景 | 处理 |
|------|------|
| 同名无提示 | ❌ 强制失败，提示用 `--anime` |
| API 失败 | 重试3次，使用缓存 |
| 验证失败 | 回滚，可 `--force` 覆盖 |
| 文件存在 | 自动备份到 `.backup.{timestamp}` |

## Cache & Performance

- SQLite 缓存 (`~/.cache/anime-character-loader/`)
- 24小时过期
- 自动限流 (0.5s 间隔)
- 失败重试 (指数退避)
