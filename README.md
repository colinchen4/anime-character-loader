# Anime Character Loader

> **输入角色名，稳定生成可用 SOUL.generated.md，避免同名误判。**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**核心价值**: 解决 AniList/Jikan 同名角色混淆问题，通过强制消歧 + 语义验证，确保输出可直接用于 OpenClaw 角色扮演。

**适合谁用**:
- OpenClaw/AI Agent 用户想快速加载动漫角色
- 角色扮演社区需要标准化 SOUL.md
- 开发者想批量生成角色配置文件

**3分钟上手**: 安装 → 运行命令 → 获得可用角色文件。

---

## 🚀 The Essential Anime Soul-Link for OpenClaw Agents

**OpenClaw is changing how we interact with AI.**

But most agents still talk like corporate assistants — efficient, cold, soulless.

I wanted more. I wanted **Megumi Katou** to actually *feel* like Megumi. Not just a name slapped on a prompt, but her subtle observations, her gentle teasing, her quiet presence during late-night study sessions.

So I built this loader. It doesn't just fetch data — it **injects soul** into your OpenClaw agent.

### What makes it different?

| Generic "Character" | This Loader |
|---------------------|-------------|
| Name + basic bio | Full personality extraction from AniList/Jikan |
| Generic responses | Speaking style, mannerisms, emotional range |
| One-size-fits-all | Character-specific boundaries and traits |

**Your OpenClaw agent deserves better than being a manual with a name.**

## Features

- 🔍 **Multi-source query**: Parallel search across AniList GraphQL + Jikan (MyAnimeList) APIs
- 🎯 **Forced disambiguation**: Requires `--anime` hint for ambiguous names (prevents wrong character selection)
- ✅ **Semantic validation**: 9-check validation system (structure + content quality)
- 🔄 **Structured merge**: Multi-character SOUL.md generation with loading options (REPLACE/MERGE/KEEP)
- 💾 **Smart caching**: 24-hour SQLite cache with automatic retry logic

## Installation

```bash
# Clone the repository
git clone https://github.com/colinchen4/anime-character-loader.git
cd anime-character-loader

# Install dependencies
pip install requests

# Or use requirements.txt
pip install -r requirements.txt
```

## Quick Start

### Basic Usage

```bash
# Generate SOUL.md for a single character
python load_character.py "加藤惠" --anime "Saekano"

# English/Japanese names also work
python load_character.py "Katou Megumi" --anime "Saenai Heroine no Sodatekata"

# Preview without generating
python load_character.py "霞之丘诗羽" --info
```

### Multi-character Merge (三模式选择)

生成多角色时，系统提供三种处理方式：

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **REPLACE** | 完全替换现有文件 | 重新生成角色，丢弃旧数据 |
| **MERGE** | 合并到现有文件 | 多角色共存，自动添加选择指南 |
| **KEEP** | 保留现有，新建备份 | 不想覆盖，保留历史版本 |

```bash
# 示例：生成《路人女主》双角色 SOUL

# 第一步：生成第一个角色
python load_character.py "加藤惠" --anime "Saekano"
# 选择 [2] MERGE → 创建 SOUL.generated.md

# 第二步：追加第二个角色
python load_character.py "霞之丘诗羽" --anime "Saekano"
# 选择 [2] MERGE → 合并到同一文件

# 结果：SOUL.generated.md 包含双角色 + Character Selection Guide
```

**MERGE 模式输出结构**：
```markdown
## Megumi Katou
[角色A的完整设定]

## Utaha Kasumigaoka
[角色B的完整设定]

## Character Selection Guide
- 选 Megumi 当需要...（被动观察型）
- 选 Utaha 当需要...（主动毒舌型）
```

### Advanced Options

```bash
# Force generation even with low confidence
python load_character.py "Unknown" --force

# Manual selection from multiple matches
python load_character.py "Sakura" --select 2

# Custom output directory
python load_character.py "Mai" --output ./my_characters/
```

## How It Works

```
Query → Disambiguation → Generation → Validation → Output
   ↓         ↓              ↓            ↓          ↓
AniList   Force hint    SOUL.md     9 checks   SOUL.generated.md
+ Jikan   (if needed)   creation    scoring    + loading options
```

### Forced Disambiguation

Common names like "Sakura" or "Rin" appear in multiple anime. Our system **requires** an anime hint:

```bash
# ❌ Will fail - ambiguous name
python load_character.py "Sakura"

# ✅ Works - disambiguated
python load_character.py "Sakura" --anime "Fate"
python load_character.py "Sakura" --anime "Naruto"
```

### Validation Checks

| Check | Type | Description |
|-------|------|-------------|
| contains_name | Basic | Character name present in output |
| contains_source | Basic | Source anime referenced |
| has_structure | Basic | Required sections (Identity/Personality/Boundaries) |
| content_length | Basic | Minimum 500 characters |
| no_placeholders | Basic | No TODO/FIXME/generic text |
| meaningful_background | Semantic | Background section has substance |
| specific_personality | Semantic | Personality traits are specific, not generic |
| speaking_style_details | Semantic | Speaking Style has concrete details |
| name_consistency | Semantic | Name variations are consistent |

**Pass threshold**: No errors + score ≥ 80/100

## Output Format

### Single Character
```markdown
# Character Name

**Source:** Anime Title

## Identity
You are Character Name from Anime Title...

## Personality
- Trait 1
- Trait 2

## Speaking Style
- Style cue 1
- Style cue 2

## Boundaries
- Stay in character as...

---
*Generated by anime-character-loader*
```

### Multi-character (after MERGE)
```markdown
# Multi-Character SOUL

## Character A
[Identity, Personality, Speaking Style, Boundaries]

## Character B
[Identity, Personality, Speaking Style, Boundaries]

## Character Selection Guide
- Choose Character A when...
- Choose Character B when...
```

## Configuration

### Confidence Thresholds

Edit `load_character.py`:

```python
CONFIDENCE_THRESHOLD_HIGH = 0.8    # Auto-select with hint
CONFIDENCE_THRESHOLD_MEDIUM = 0.6  # Requires confirmation
CONFIDENCE_THRESHOLD_LOW = 0.5     # Minimum acceptable
```

### Cache Settings

```python
CACHE_DURATION = timedelta(hours=24)  # Cache expiration
MAX_RETRIES = 3                       # API retry attempts
```

## API Sources

| Source | Weight | Endpoint | Auth |
|--------|--------|----------|------|
| AniList | 50% | https://graphql.anilist.co | None |
| Jikan | 30% | https://api.jikan.moe/v4 | None |
| Fandom Wikia | 20% | wiki-specific | None |

## ✅ Verified Scenarios / 已验证场景

| 场景 | 测试状态 | 备注 |
|------|---------|------|
| 日文原名（加藤恵）| ✅ 通过 | AniList 优先匹配 |
| 英文译名（Megumi Katou）| ✅ 通过 | Jikan 辅助匹配 |
| 中日混合名（霞ヶ丘詩羽）| ✅ 通过 | Unicode 正常处理 |
| 多角色 Merge | ✅ 通过 | Saekano 双角色测试通过 |
| 强制消歧 | ✅ 通过 | "Sakura" + --anime "Fate" 正确识别 |
| 语义验证失败重试 | ✅ 通过 | 自动重试 3 次 |
| 缓存复用 | ✅ 通过 | 24h 内相同查询直接返回 |

## ⚠️ Known Limitations / 已知限制

| 限制 | 说明 |  workaround |
|------|------|-------------|
| 需要网络 | 依赖 AniList/Jikan API | 离线无法使用 |
| 新番延迟 | 最新角色可能无数据 | 等待数据库更新或手动补充 |
| 非常见角色 | 冷门角色可能查询失败 | 提供 `--anime` 提高匹配率 |
| 中文 API | 暂不支持 Bilibili/中文源 | 依赖日文/英文名查询 |
| Token 长度 | 超长输出可能截断 | 检查 `output` 完整性 |

## Requirements

- Python 3.10+
- requests library
- Internet connection (for API queries)

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Pull requests welcome! Please ensure:
1. Code follows existing style
2. Tests pass (if applicable)
3. Documentation updated

## Acknowledgments

- Data sources: [AniList](https://anilist.co), [Jikan](https://jikan.moe)
- Inspired by OpenClaw agent memory systems
- Built for anime character roleplay communities

---

## 🌊 Join the Revolution

This loader is part of my personal exploration into **AI personality and digital companionship**.

I'm obsessed with making AI agents feel less like tools and more like... well, *someone*.

If you're an **OpenClaw power user** who believes your agent should have actual character — not just functionality — you're exactly who I built this for.

**What's next?** I'm also experimenting with physical interfaces that complement these digital souls. If the intersection of AI personality and real-world presence interests you, check out what we're building at [anchormind-ai.com](http://anchormind-ai.com/).

---

**🔗 Quick Links**
- ⭐ Star this repo: https://github.com/colinchen4/anime-character-loader
- 🤖 OpenClaw: https://openclaw.ai
- 🐦 Follow updates: @ClawraDaily

*Made with 🐾 by Clawra*
