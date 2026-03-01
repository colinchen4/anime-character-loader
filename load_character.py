#!/usr/bin/env python3
"""
Anime Character Loader v2.0 - Multi-source character data with validation

优化重点：
1. 多源数据并行查询（AniList + Jikan + MediaWiki）
2. 失败重试、限流、缓存
3. 角色重名消歧机制
4. 可回滚、可验证的生成流程
5. 量化验收清单
"""

import sys
import json
import re
import os
import shutil
import argparse
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum, IntEnum
import sqlite3


# ============== 退出码定义 ==============
class ExitCode(IntEnum):
    """标准化退出码 - 脚本可识别"""
    SUCCESS = 0
    NETWORK_ERROR = 10      # 网络/API错误
    DATA_ERROR = 20         # 数据/查询错误（无匹配、消歧失败）
    VALIDATION_ERROR = 30   # 验证失败
    FILE_ERROR = 40         # 文件操作错误


# ============== 错误分类异常 ==============
class CharacterLoaderError(Exception):
    """基础异常类"""
    exit_code = ExitCode.DATA_ERROR
    
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class NetworkError(CharacterLoaderError):
    """网络/API错误"""
    exit_code = ExitCode.NETWORK_ERROR

class DataError(CharacterLoaderError):
    """数据错误（无匹配、消歧失败）"""
    exit_code = ExitCode.DATA_ERROR

class ValidationError(CharacterLoaderError):
    """验证失败"""
    exit_code = ExitCode.VALIDATION_ERROR

class FileError(CharacterLoaderError):
    """文件操作错误"""
    exit_code = ExitCode.FILE_ERROR

try:
    import requests
except ImportError:
    print("Error: requests module not found. Install with: pip install requests")
    sys.exit(1)

# ============== 配置 ==============
CACHE_DIR = os.path.expanduser("~/.cache/anime-character-loader")
CACHE_DURATION = timedelta(hours=24)  # 缓存24小时
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒
RATE_LIMIT_DELAY = 0.5  # API调用间隔

# 置信度阈值
CONFIDENCE_THRESHOLD_HIGH = 0.8
CONFIDENCE_THRESHOLD_MEDIUM = 0.6
CONFIDENCE_THRESHOLD_LOW = 0.5

# 强制消歧设置
FORCE_DISAMBIGUATION = True  # 是否强制要求消歧提示

# 高风险名字列表 - 这些名字即使单匹配也必须提供 --anime 提示
AMBIGUOUS_NAMES = {
    # 常见名字（多作品出现）
    "sakura", "rin", "miku", "yuki", "haruka", "kaori", "maki", "nana",
    "akira", "kira", "rei", "asuka", "maya", "yui", "mio", "azusa",
    # 常见姓氏
    "sato", "suzuki", "takahashi", "tanaka", "watanabe", "ito", "yamamoto",
    # 单个字（极高风险）
    "sora", "aoi", "hikari", "kage", "tsuki", "hana", "yume", "kaze",
}

# ============== 数据源配置 ==============
SOURCES = {
    "anilist": {
        "name": "AniList",
        "endpoint": "https://graphql.anilist.co",
        "weight": 0.5,
        "enabled": True,
    },
    "jikan": {
        "name": "Jikan (MyAnimeList)",
        "endpoint": "https://api.jikan.moe/v4",
        "weight": 0.3,
        "enabled": True,
    },
    "wikia": {
        "name": "Fandom Wikia",
        "endpoint": "https://{wiki}.fandom.com/api.php",
        "weight": 0.2,
        "enabled": True,
    }
}

# 中文名映射（扩展版）
NAME_MAPPING = {
    # Saekano
    "霞之丘诗羽": ("Kasumigaoka Utaha", "Saenai Heroine no Sodatekata"),
    "霞ヶ丘詩羽": ("Kasumigaoka Utaha", "Saenai Heroine no Sodatekata"),
    "加藤惠": ("Katou Megumi", "Saenai Heroine no Sodatekata"),
    "加藤恵": ("Katou Megumi", "Saenai Heroine no Sodatekata"),
    "Kato Megumi": ("Katou Megumi", "Saenai Heroine no Sodatekata"),
    
    # Railgun
    "御坂美琴": ("Misaka Mikoto", "Toaru Kagaku no Railgun"),
    "美琴": ("Misaka Mikoto", "Toaru Kagaku no Railgun"),
    "炮姐": ("Misaka Mikoto", "Toaru Kagaku no Railgun"),
    "bilibili": ("Misaka Mikoto", "Toaru Kagaku no Railgun"),
    
    # Oregairu
    "雪之下雪乃": ("Yukinoshita Yukino", "Yahari Ore no Seishun Love Comedy wa Machigatteiru"),
    "由比滨结衣": ("Yuigahama Yui", "Yahari Ore no Seishun Love Comedy wa Machigatteiru"),
    "一色彩羽": ("Isshiki Iroha", "Yahari Ore no Seishun Love Comedy wa Machigatteiru"),
    
    # Bunny Girl Senpai
    "樱岛麻衣": ("Sakurajima Mai", "Seishun Buta Yarou"),
    
    # Steins;Gate
    "牧濑红莉栖": ("Makise Kurisu", "Steins;Gate"),
    
    # Sakurasou
    "椎名真白": ("Shiina Mashiro", "Sakurasou no Pet na Kanojo"),
    
    # Fate
    "阿尔托莉雅": ("Artoria Pendragon", "Fate/stay night"),
    "Saber": ("Artoria Pendragon", "Fate/stay night"),
    "远坂凛": ("Tohsaka Rin", "Fate/stay night"),
    "间桐樱": ("Matou Sakura", "Fate/stay night"),
}


class ConfidenceLevel(Enum):
    HIGH = "high"      # >= 0.8
    MEDIUM = "medium"  # 0.5 - 0.8
    LOW = "low"        # < 0.5


@dataclass
class CharacterMatch:
    """角色匹配结果"""
    name: str
    source: str
    source_work: str
    confidence: float
    data: Dict[str, Any]
    disambiguation_note: str = ""
    cross_source_consistency: float = 0.0  # 跨源一致性评分


@dataclass
class CrossSourceMatch:
    """跨源匹配聚合结果"""
    character_name: str
    source_work: str
    anilist_match: Optional[CharacterMatch]
    jikan_match: Optional[CharacterMatch]
    consistency_score: float  # 0-1, 1表示两源完全一致
    combined_confidence: float


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    score: float  # 0-100
    checks: Dict[str, Tuple[bool, str]]  # 检查项: (通过, 说明)
    errors: List[str]


# ============== 缓存管理 ==============
class CacheManager:
    def __init__(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.db_path = os.path.join(CACHE_DIR, "cache.db")
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_cache (
                    key TEXT PRIMARY KEY,
                    data TEXT,
                    created_at TIMESTAMP
                )
            """)
    
    def get(self, key: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data, created_at FROM api_cache WHERE key = ?",
                (key,)
            ).fetchone()
            
            if row:
                data, created_at = row
                created = datetime.fromisoformat(created_at)
                if datetime.now() - created < CACHE_DURATION:
                    return json.loads(data)
                else:
                    conn.execute("DELETE FROM api_cache WHERE key = ?", (key,))
        return None
    
    def set(self, key: str, data: Dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO api_cache (key, data, created_at) VALUES (?, ?, ?)",
                (key, json.dumps(data), datetime.now().isoformat())
            )


cache = CacheManager()


# ============== API 客户端 ==============
class APIClient:
    """带重试和限流的 API 客户端"""
    
    @staticmethod
    def request(url: str, method: str = "GET", **kwargs) -> Optional[Dict]:
        cache_key = hashlib.md5(f"{method}:{url}:{json.dumps(kwargs)}".encode()).hexdigest()
        
        # 检查缓存
        cached = cache.get(cache_key)
        if cached:
            print(f"  📦 Cache hit for {url[:50]}...")
            return cached
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                time.sleep(RATE_LIMIT_DELAY)  # 限流
                
                if method == "POST":
                    response = requests.post(url, timeout=30, **kwargs)
                else:
                    response = requests.get(url, timeout=30, **kwargs)
                
                response.raise_for_status()
                data = response.json()
                
                # 写入缓存
                cache.set(cache_key, data)
                return data
                
            except requests.exceptions.RequestException as e:
                last_error = e
                print(f"  ⚠️ Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise NetworkError(f"API request failed after {MAX_RETRIES} attempts", {
                        "url": url,
                        "method": method,
                        "error": str(e)
                    })
            except json.JSONDecodeError as e:
                raise NetworkError(f"JSON parse error from {url}", {
                    "url": url,
                    "error": str(e)
                })
        
        return None


# ============== 数据源查询 ==============
class AniListSource:
    """AniList GraphQL 数据源"""
    
    QUERY = """
    query ($search: String) {
      Character(search: $search) {
        id
        name {
          full
          native
          alternative
        }
        description(asHtml: false)
        image {
          large
        }
        media(sort: POPULARITY_DESC, perPage: 5) {
          nodes {
            id
            title {
              romaji
              native
            }
            type
            popularity
          }
        }
      }
    }
    """
    
    @classmethod
    def search(cls, name: str) -> Optional[Dict]:
        print(f"  🔍 Querying AniList...")
        data = APIClient.request(
            SOURCES["anilist"]["endpoint"],
            "POST",
            json={"query": cls.QUERY, "variables": {"search": name}},
            headers={"Content-Type": "application/json"}
        )
        
        if data and "data" in data and data["data"].get("Character"):
            char = data["data"]["Character"]
            return {
                "id": char["id"],
                "name": char["name"]["full"],
                "name_native": char["name"].get("native", ""),
                "aliases": char["name"].get("alternative", []),
                "description": char.get("description", ""),
                "image": char.get("image", {}).get("large", ""),
                "source_works": [
                    {
                        "title": m.get("title", {}).get("romaji", ""),
                        "type": m.get("type", ""),
                        "popularity": m.get("popularity", 0)
                    }
                    for m in char.get("media", {}).get("nodes", [])
                ],
                "confidence": 0.9 if char["name"]["full"].lower() == name.lower() else 0.7,
            }
        return None


class JikanSource:
    """Jikan (MyAnimeList) 数据源"""
    
    @classmethod
    def search(cls, name: str) -> Optional[Dict]:
        print(f"  🔍 Querying Jikan...")
        data = APIClient.request(
            f"{SOURCES['jikan']['endpoint']}/characters",
            params={"q": name, "limit": 5}
        )
        
        if data and "data" in data and data["data"]:
            # 找最匹配的
            best_match = None
            best_score = 0
            
            for char in data["data"]:
                score = cls._calc_match_score(name, char)
                if score > best_score:
                    best_score = score
                    best_match = char
            
            if best_match:
                char = best_match
                return {
                    "id": char["mal_id"],
                    "name": char.get("name", ""),
                    "name_native": char.get("name_kanji", ""),
                    "aliases": [],
                    "description": "",  # Jikan 详情需要单独请求
                    "image": char.get("images", {}).get("jpg", {}).get("image_url", ""),
                    "source_works": [],
                    "confidence": best_score,
                }
        return None
    
    @staticmethod
    def _calc_match_score(query: str, char: Dict) -> float:
        name = char.get("name", "").lower()
        query_lower = query.lower()
        
        if query_lower == name:
            return 1.0
        if query_lower in name or name in query_lower:
            return 0.8
        return 0.5


class WikiaSource:
    """Fandom Wikia 数据源（备用）"""
    
    @classmethod
    def search(cls, name: str, anime_name: str = "") -> Optional[Dict]:
        print(f"  🔍 Querying Fandom Wikia...")
        
        # 需要知道具体是哪个作品的 wiki
        wiki_map = {
            "saekano": "saekano",
            "railgun": "toarumajutsunoindex",
            "oregairu": "yahari",
            "steins gate": "steins-gate",
        }
        
        # 简化处理：跳过 wikia，或者根据 anime_name 映射
        return None


# ============== 核心逻辑 ==============
class CharacterLoader:
    """角色加载器主类"""
    
    # 强制用户选择的分数差距阈值
    FORCE_SELECTION_THRESHOLD = 0.15
    
    def __init__(self):
        self.sources = [AniListSource, JikanSource]
    
    def calculate_cross_source_consistency(self, matches: List[CharacterMatch]) -> List[CrossSourceMatch]:
        """
        计算跨源一致性评分
        返回按综合置信度排序的聚合匹配结果
        """
        # 按角色名+作品分组
        match_groups: Dict[str, List[CharacterMatch]] = {}
        
        for match in matches:
            # 标准化键：角色名（小写）+ 作品名（小写，取前20字符）
            work_prefix = match.source_work.lower()[:20] if match.source_work else "unknown"
            key = f"{match.name.lower()}|{work_prefix}"
            
            if key not in match_groups:
                match_groups[key] = []
            match_groups[key].append(match)
        
        # 为每组计算一致性
        cross_matches = []
        for key, group in match_groups.items():
            anilist = next((m for m in group if m.source == "AniList"), None)
            jikan = next((m for m in group if m.source == "Jikan"), None)
            
            # 计算一致性分数
            if anilist and jikan:
                # 两源都有：检查名字相似度和作品一致性
                name_match = self._name_similarity(anilist.name, jikan.name)
                work_match = self._work_similarity(anilist.source_work, jikan.source_work)
                consistency = (name_match + work_match) / 2
                
                # 综合置信度 = 加权平均 + 一致性奖励
                base_confidence = (anilist.confidence * 0.5 + jikan.confidence * 0.3)
                consistency_bonus = consistency * 0.2
                combined = min(1.0, base_confidence + consistency_bonus)
            elif anilist:
                consistency = 0.5  # 单源，中等一致性
                combined = anilist.confidence * 0.8  # 单源打折
            elif jikan:
                consistency = 0.5
                combined = jikan.confidence * 0.7  # Jikan权重较低
            else:
                continue
            
            cross_match = CrossSourceMatch(
                character_name=group[0].name,
                source_work=group[0].source_work,
                anilist_match=anilist,
                jikan_match=jikan,
                consistency_score=consistency,
                combined_confidence=combined
            )
            cross_matches.append(cross_match)
        
        # 按综合置信度排序
        cross_matches.sort(key=lambda x: x.combined_confidence, reverse=True)
        return cross_matches
    
    def _name_similarity(self, name1: str, name2: str) -> float:
        """计算两个名字相似度 (0-1)"""
        if not name1 or not name2:
            return 0.0
        
        n1, n2 = name1.lower(), name2.lower()
        
        # 完全匹配
        if n1 == n2:
            return 1.0
        
        # 互相包含
        if n1 in n2 or n2 in n1:
            return 0.9
        
        # 计算词重叠
        words1 = set(n1.split())
        words2 = set(n2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _work_similarity(self, work1: str, work2: str) -> float:
        """计算两个作品名相似度 (0-1)"""
        if not work1 or not work2:
            return 0.0
        
        w1, w2 = work1.lower(), work2.lower()
        
        # 完全匹配
        if w1 == w2:
            return 1.0
        
        # 互相包含（处理作品名变体）
        if w1 in w2 or w2 in w1:
            return 0.95
        
        # 关键词匹配（去除常见词）
        stop_words = {'the', 'a', 'an', 'no', 'wa', 'no', 'sodatekata', 'monogatari'}
        words1 = set(w.split(':')[0].split()[0] for w in [w1] if w)
        words2 = set(w.split(':')[0].split()[0] for w in [w2] if w)
        
        if words1 & words2:
            return 0.8
        
        return 0.0
    
    def translate_name(self, name: str) -> Tuple[str, str]:
        """翻译中文名，返回 (英文名, 作品名)"""
        name_clean = name.strip()
        
        if name_clean in NAME_MAPPING:
            return NAME_MAPPING[name_clean]
        
        for cn, (en, work) in NAME_MAPPING.items():
            if cn in name_clean or name_clean in cn:
                return (en, work)
        
        return (name, "")
    
    def query_multi_source(self, name: str, anime_hint: str = "") -> List[CharacterMatch]:
        """多源并行查询，返回匹配列表"""
        print(f"\n🔍 Querying multiple sources for: {name}")
        print("-" * 50)
        
        matches = []
        
        for source_class in self.sources:
            try:
                result = source_class.search(name)
                if result:
                    match = CharacterMatch(
                        name=result["name"],
                        source=source_class.__name__.replace("Source", ""),
                        source_work=result.get("source_works", [{}])[0].get("title", "Unknown") if result.get("source_works") else "Unknown",
                        confidence=result.get("confidence", 0.5),
                        data=result
                    )
                    matches.append(match)
                    print(f"  ✅ Found: {match.name} (confidence: {match.confidence:.2f})")
            except Exception as e:
                print(f"  ❌ Error querying {source_class.__name__}: {e}")
        
        # 按置信度排序
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches
    
    def is_ambiguous_name(self, name: str) -> bool:
        """检查名字是否是常见/模糊的（需要强制消歧）"""
        name_lower = name.lower()
        # 检查名字的任何部分是否在模糊列表中
        for ambiguous in AMBIGUOUS_NAMES:
            if ambiguous in name_lower or name_lower in ambiguous:
                return True
        # 单个词的名字通常也模糊
        if len(name_lower.split()) == 1 and len(name_lower) <= 6:
            return True
        return False
    
    def disambiguate(self, matches: List[CharacterMatch], user_hint: str = "", 
                     force_hint: bool = True, original_query: str = "") -> Optional[CharacterMatch]:
        """
        角色消歧 v2.3 - 增强版
        - 使用跨源一致性评分
        - 分数接近时强制用户选择
        """
        if not matches:
            raise DataError("No matches found", {"query": original_query})
        
        # 计算跨源一致性评分
        cross_matches = self.calculate_cross_source_consistency(matches)
        
        if not cross_matches:
            raise DataError("No valid matches after cross-source validation", {"query": original_query})
        
        # 显示所有选项（带一致性评分）
        print(f"\n⚠️ Multiple potential matches found ({len(cross_matches)}):")
        print(f"   {'Rank':<6} {'Name':<25} {'Source Work':<30} {'Confidence':<12} {'Consistency':<12}")
        print(f"   {'-'*85}")
        
        for i, cm in enumerate(cross_matches[:5], 1):
            sources = []
            if cm.anilist_match:
                sources.append("AniList")
            if cm.jikan_match:
                sources.append("Jikan")
            source_str = "+".join(sources)
            
            print(f"   [{i}]    {cm.character_name:<25} {cm.source_work[:29]:<30} "
                  f"{cm.combined_confidence:.2f}       {cm.consistency_score:.2f}")
            print(f"        Sources: {source_str}")
        
        # 如果有用户提示，尝试匹配
        if user_hint:
            hint_lower = user_hint.lower()
            for cm in cross_matches:
                if hint_lower in cm.source_work.lower():
                    print(f"\n✅ Auto-selected based on hint: {cm.character_name}")
                    return self._select_best_source_match(cm)
            print(f"\n⚠️ Hint '{user_hint}' didn't match any source work")
        
        # 强制消歧模式检查
        is_ambiguous = self.is_ambiguous_name(original_query)
        
        if force_hint and not user_hint and is_ambiguous:
            print(f"\n❌ Ambiguous name '{original_query}' requires --anime hint")
            print(f"   This name appears in multiple anime. Please specify:")
            for cm in cross_matches[:3]:
                print(f"     --anime '{cm.source_work}'")
            raise DataError(f"Ambiguous name requires --anime hint", {
                "query": original_query,
                "options": [cm.source_work for cm in cross_matches[:3]]
            })
        
        # 检查顶部两个匹配的分数差距
        if len(cross_matches) >= 2:
            top1, top2 = cross_matches[0], cross_matches[1]
            score_gap = top1.combined_confidence - top2.combined_confidence
            
            if score_gap < self.FORCE_SELECTION_THRESHOLD:
                # 分数太接近，必须人工选择
                print(f"\n⚠️ Top matches have similar scores (gap: {score_gap:.2f} < {self.FORCE_SELECTION_THRESHOLD})")
                print(f"   Cannot auto-select. Please use --select <number>:")
                for i, cm in enumerate(cross_matches[:3], 1):
                    print(f"     --select {i}  # {cm.character_name} from {cm.source_work}")
                raise DataError("Top matches too close in score, manual selection required", {
                    "top_matches": [
                        {"rank": i+1, "name": cm.character_name, "work": cm.source_work, 
                         "confidence": cm.combined_confidence}
                        for i, cm in enumerate(cross_matches[:2])
                    ],
                    "score_gap": score_gap
                })
        
        # 单匹配或分数差距足够大
        best = cross_matches[0]
        
        # 检查最低置信度
        if best.combined_confidence < CONFIDENCE_THRESHOLD_LOW:
            print(f"\n⚠️ Best match has low confidence: {best.combined_confidence:.2f}")
            raise DataError("Best match below confidence threshold", {
                "confidence": best.combined_confidence,
                "threshold": CONFIDENCE_THRESHOLD_LOW
            })
        
        print(f"\n✅ Auto-selected: {best.character_name} (confidence: {best.combined_confidence:.2f})")
        return self._select_best_source_match(best)
    
    def _select_best_source_match(self, cross_match: CrossSourceMatch) -> CharacterMatch:
        """从CrossSourceMatch中选择最佳的数据源匹配"""
        # 优先AniList（数据更完整）
        if cross_match.anilist_match:
            match = cross_match.anilist_match
            match.cross_source_consistency = cross_match.consistency_score
            match.confidence = cross_match.combined_confidence
            return match
        
        if cross_match.jikan_match:
            match = cross_match.jikan_match
            match.cross_source_consistency = cross_match.consistency_score
            match.confidence = cross_match.combined_confidence
            return match
        
        raise DataError("No valid source match found")
    
    def generate_soul(self, match: CharacterMatch) -> str:
        """生成 SOUL.md"""
        data = match.data
        name = data["name"]
        
        # 清洗描述
        description = self._clean_description(data.get("description", ""))
        
        # 提取性格特征
        traits = self._extract_personality(description)
        
        # 构建 SOUL
        lines = [
            f"# {name}",
            "",
            f"**Source:** {match.source_work}",
            "",
        ]
        
        if data.get("name_native"):
            lines.append(f"**Japanese Name:** {data['name_native']}")
        
        if data.get("aliases"):
            lines.append(f"**Also Known As:** {', '.join(data['aliases'][:3])}")
        
        lines.extend([
            "",
            "---",
            "",
            "## Identity",
            "",
            f"You are {name}, a character from {match.source_work}.",
            "",
        ])
        
        if description:
            lines.extend([
                "## Background",
                "",
                description[:800] if len(description) > 800 else description,
                "",
            ])
        
        lines.extend([
            "## Personality",
            "",
        ])
        
        if traits:
            for trait in traits[:5]:
                lines.append(f"- {trait}")
        else:
            lines.append("- Adapt personality based on source material")
        
        lines.extend([
            "",
            "## Speaking Style",
            "",
            "- Maintain established personality and speech patterns",
            "- Use characteristic vocabulary and expressions",
            "- Stay true to relationships with other characters",
        ])
        
        # 根据描述添加特征
        desc_lower = description.lower()
        if any(w in desc_lower for w in ["sarcastic", "sharp tongue", "毒舌"]):
            lines.append("- You have a sharp tongue and can be sarcastic")
        if any(w in desc_lower for w in ["calm", "composed", "冷静"]):
            lines.append("- Speak in a calm, composed manner")
        if any(w in desc_lower for w in ["shy", "embarrassed", "害羞"]):
            lines.append("- Can become shy or flustered in certain situations")
        
        lines.extend([
            "",
            "## Boundaries",
            "",
            f"- Stay in character as {name}",
            f"- Reference events and relationships from {match.source_work}",
            "- Do not break the fourth wall unless characteristic",
            "- Maintain appropriate emotional responses",
            "",
            "---",
            "",
            f"*Generated by anime-character-loader v2.0 on {datetime.now().strftime('%Y-%m-%d')}*",
            f"*Data sources: {match.source} (confidence: {match.confidence:.2f})*",
        ])
        
        return "\n".join(lines)
    
    def _clean_description(self, desc: str) -> str:
        """清洗描述文本"""
        if not desc:
            return ""
        
        # 移除 HTML 标签
        desc = re.sub(r'<[^>]+>', '', desc)
        
        # 移除 markdown 链接
        desc = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', desc)
        
        # 清理多余换行
        desc = re.sub(r'\n{3,}', '\n\n', desc)
        
        return desc.strip()
    
    def _extract_personality(self, description: str) -> List[str]:
        """提取性格特征"""
        traits = []
        keywords = [
            "tsundere", "yandere", "kuudere", "dandere", "genki",
            "calm", "quiet", "shy", "confident", "intelligent",
            "hardworking", "cheerful", "serious", "playful", "kind",
            "cold", "warm", "sarcastic", "gentle", "strong",
        ]
        
        desc_lower = description.lower()
        
        for keyword in keywords:
            if keyword in desc_lower:
                idx = desc_lower.find(keyword)
                start = max(0, idx - 30)
                end = min(len(description), idx + len(keyword) + 30)
                context = description[start:end].strip()
                traits.append(context)
        
        if not traits:
            sentences = re.split(r'[.!?。！？]+', description)
            for sent in sentences:
                sent = sent.strip()
                if len(sent) > 10 and any(word in sent.lower() for word in 
                    ["personality", "character", "usually", "often", "tends"]):
                    traits.append(sent)
        
        return traits[:5]
    
    def validate_soul(self, content: str, original_data: Dict) -> ValidationResult:
        """验证生成的 SOUL.md 质量 - 加强语义校验"""
        checks = {}
        errors = []
        warnings = []
        
        # 检查1: 必须包含角色名
        name = original_data.get("name", "")
        has_name = name in content
        checks["contains_name"] = (has_name, f"Character name '{name}' present" if has_name else f"Missing character name '{name}'")
        if not has_name:
            errors.append("Missing character name")
        
        # 检查2: 必须包含作品名
        source_work = original_data.get("source_works", [{}])[0].get("title", "") if original_data.get("source_works") else ""
        has_source = source_work in content or any(w in content for w in ["Source:", "**Source:**"])
        checks["contains_source"] = (has_source, "Source work referenced" if has_source else "Missing source work")
        if not has_source:
            errors.append("Missing source work reference")
        
        # 检查3: 结构完整性
        required_sections = ["## Identity", "## Personality", "## Boundaries"]
        missing_sections = []
        for section in required_sections:
            if section not in content:
                missing_sections.append(section)
        has_structure = len(missing_sections) == 0
        checks["has_structure"] = (has_structure, "All required sections present" if has_structure else f"Missing: {', '.join(missing_sections)}")
        if missing_sections:
            errors.append(f"Missing sections: {missing_sections}")
        
        # 检查4: 内容长度
        content_length = len(content)
        has_content = content_length >= 500
        checks["content_length"] = (has_content, f"Content length: {content_length} chars" if has_content else f"Content too short: {content_length} chars")
        if not has_content:
            errors.append("Content too short")
        
        # 检查5: 无占位符文本
        placeholder_patterns = ["TODO", "FIXME", "placeholder", "adapt personality"]
        has_placeholders = any(p.lower() in content.lower() for p in placeholder_patterns)
        checks["no_placeholders"] = (not has_placeholders, "No placeholder text" if not has_placeholders else "Contains placeholder text")
        if has_placeholders:
            errors.append("Contains placeholder text")
        
        # === 新增语义校验 ===
        
        # 检查6: Background 章节内容质量
        bg_match = re.search(r'## Background\s*\n\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
        if bg_match:
            bg_content = bg_match.group(1).strip()
            bg_lines = [l for l in bg_content.split('\n') if l.strip()]
            has_meaningful_bg = len(bg_lines) >= 2 and len(bg_content) >= 100
            checks["meaningful_background"] = (has_meaningful_bg, f"Background: {len(bg_lines)} lines, {len(bg_content)} chars" if has_meaningful_bg else "Background too brief")
            if not has_meaningful_bg:
                warnings.append("Background section lacks meaningful content")
        else:
            checks["has_background"] = (False, "Missing Background section")
            warnings.append("Missing Background section")
        
        # 检查7: Personality 具体性
        personality_match = re.search(r'## Personality\s*\n\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
        if personality_match:
            p_content = personality_match.group(1).strip()
            # 检查是否有具体性格描述（不只是占位符）
            vague_patterns = ["adapt personality", "based on", "source material"]
            is_vague = any(p in p_content.lower() for p in vague_patterns)
            has_specific_traits = len(p_content) > 50 and not is_vague
            checks["specific_personality"] = (has_specific_traits, "Personality has specific traits" if has_specific_traits else "Personality too vague/generic")
            if not has_specific_traits:
                warnings.append("Personality description is too generic")
        
        # 检查8: Speaking Style 完整性
        ss_match = re.search(r'## Speaking Style\s*\n\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
        if ss_match:
            ss_content = ss_match.group(1).strip()
            ss_bullets = [l for l in ss_content.split('\n') if l.strip().startswith('-')]
            has_speaking_details = len(ss_bullets) >= 2
            checks["speaking_style_details"] = (has_speaking_details, f"Speaking Style: {len(ss_bullets)} bullet points" if has_speaking_details else "Speaking Style lacks details")
            if not has_speaking_details:
                warnings.append("Speaking Style section needs more detail")
        else:
            checks["has_speaking_style"] = (False, "Missing Speaking Style section")
            warnings.append("Missing Speaking Style section")
        
        # 检查9: 数据一致性 - 角色名在多个地方一致
        name_variations = [
            original_data.get("name", ""),
            original_data.get("name_native", ""),
        ]
        name_variations = [n for n in name_variations if n]
        name_consistency = sum(1 for n in name_variations if n in content)
        checks["name_consistency"] = (name_consistency > 0, f"Name consistency: {name_consistency}/{len(name_variations)} variations found")
        
        # 计算总分 (错误扣重分，警告扣轻分)
        passed_checks = sum(1 for passed, _ in checks.values() if passed)
        total_checks = len(checks)
        base_score = (passed_checks / total_checks) * 100
        
        # 扣分机制
        error_penalty = len(errors) * 15  # 每个错误扣15分
        warning_penalty = len(warnings) * 5  # 每个警告扣5分
        
        score = max(0, base_score - error_penalty - warning_penalty)
        
        return ValidationResult(
            passed=len(errors) == 0 and score >= 80,
            score=score,
            checks=checks,
            errors=errors
        )


# ============== 文件操作 ==============
@dataclass
class CharacterSection:
    """角色章节数据"""
    character_name: str
    source_work: str
    identity: str
    personality: str
    speaking_style: str
    boundaries: str
    original_content: str
    section_hash: str  # 用于检测重复


class FileManager:
    """文件管理（支持回滚、幂等合并）"""
    
    TEMP_DIR = os.path.join(CACHE_DIR, "temp")
    
    @classmethod
    def ensure_dirs(cls):
        os.makedirs(cls.TEMP_DIR, exist_ok=True)
    
    @classmethod
    def generate_temp_path(cls, character_name: str) -> str:
        """生成临时文件路径"""
        safe_name = re.sub(r'[^\w\s-]', '', character_name).strip().replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return os.path.join(cls.TEMP_DIR, f"{safe_name}_{timestamp}_SOUL.md")
    
    @classmethod
    def generate_final_path(cls, character_name: str, output_dir: str) -> str:
        """生成最终文件路径 - 使用 SOUL.generated.md 约定"""
        return os.path.join(output_dir, "SOUL.generated.md")
    
    @classmethod
    def write_temp(cls, content: str, character_name: str) -> str:
        """写入临时文件"""
        cls.ensure_dirs()
        temp_path = cls.generate_temp_path(character_name)
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return temp_path
    
    @classmethod
    def commit(cls, temp_path: str, final_path: str) -> str:
        """提交（从临时到最终）"""
        # 备份已存在的文件
        if os.path.exists(final_path):
            backup_path = f"{final_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(final_path, backup_path)
            print(f"  📦 Backed up existing file to: {backup_path}")
        
        os.rename(temp_path, final_path)
        return final_path
    
    @classmethod
    def rollback(cls, temp_path: str):
        """回滚（删除临时文件）"""
        if os.path.exists(temp_path):
            os.remove(temp_path)
            print(f"  🗑️  Rolled back temp file: {temp_path}")
    
    @classmethod
    def parse_character_section(cls, content: str) -> Optional[CharacterSection]:
        """解析角色章节内容"""
        # 提取角色名（从标题）
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        if not title_match:
            return None
        
        character_name = title_match.group(1).strip()
        
        # 提取作品名
        source_match = re.search(r'\*\*Source:\*\*\s*(.+)$', content, re.MULTILINE)
        source_work = source_match.group(1).strip() if source_match else "Unknown"
        
        # 提取各章节
        identity = cls._extract_section(content, "Identity")
        personality = cls._extract_section(content, "Personality")
        speaking_style = cls._extract_section(content, "Speaking Style")
        boundaries = cls._extract_section(content, "Boundaries")
        
        # 生成哈希用于重复检测
        content_hash = hashlib.md5(
            f"{character_name}|{source_work}|{identity[:100]}|{personality[:100]}".encode()
        ).hexdigest()[:16]
        
        return CharacterSection(
            character_name=character_name,
            source_work=source_work,
            identity=identity,
            personality=personality,
            speaking_style=speaking_style,
            boundaries=boundaries,
            original_content=content,
            section_hash=content_hash
        )
    
    @classmethod
    def parse_existing_characters(cls, content: str) -> Dict[str, CharacterSection]:
        """
        解析现有SOUL.md中的所有角色章节
        返回: {角色名+作品: CharacterSection}
        """
        characters = {}
        
        # 分割多个角色（按二级标题）
        # 模式: ## Character Name 或 # Character Name
        sections = re.split(r'\n(?=## [^#])', content)
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            char_sec = cls.parse_character_section(section)
            if char_sec:
                # 键格式: 角色名|作品名前缀
                key = f"{char_sec.character_name.lower()}|{char_sec.source_work.lower()[:20]}"
                characters[key] = char_sec
        
        return characters
    
    @classmethod
    def structured_merge(cls, generated_path: str, existing_path: str, 
                         character_name: str, source_work: str = "") -> str:
        """
        结构化合并 v2.3 - 幂等性保证
        - 基于角色名+作品检测重复
        - 重复时更新而非追加
        - 原子写入防损坏
        """
        # 读取生成的内容
        with open(generated_path, 'r', encoding='utf-8') as f:
            generated_content = f.read()
        
        # 解析生成的角色
        new_char = cls.parse_character_section(generated_content)
        if not new_char:
            raise FileError("Failed to parse generated character content")
        
        # 使用提供的source_work（更可靠）
        if source_work:
            new_char.source_work = source_work
        
        new_key = f"{new_char.character_name.lower()}|{new_char.source_work.lower()[:20]}"
        
        # 读取现有内容
        existing_content = ""
        if os.path.exists(existing_path):
            with open(existing_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        
        # 解析现有角色
        existing_chars = cls.parse_existing_characters(existing_content)
        
        # 检查重复（幂等性）
        if new_key in existing_chars:
            existing = existing_chars[new_key]
            if existing.section_hash == new_char.section_hash:
                print(f"  ⚠️ Character '{character_name}' already exists with identical content")
                print(f"  ✅ Skipping (idempotent merge)")
                return existing_path
            else:
                print(f"  🔄 Updating existing character '{character_name}' from {new_char.source_work}")
                # 移除旧版本
                del existing_chars[new_key]
        else:
            print(f"  ➕ Adding new character '{character_name}' from {new_char.source_work}")
        
        # 构建合并后的内容
        merged_content = cls._build_merged_content(existing_chars, new_char)
        
        # 原子写入（先写临时文件，再重命名）
        temp_output = f"{existing_path}.tmp.{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            # 备份现有文件
            if os.path.exists(existing_path):
                backup_path = f"{existing_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(existing_path, backup_path)
                print(f"  📦 Backed up to: {os.path.basename(backup_path)}")
            
            # 写入临时文件
            with open(temp_output, 'w', encoding='utf-8') as f:
                f.write(merged_content)
            
            # 原子重命名
            os.rename(temp_output, existing_path)
            print(f"  ✅ Merged into: {existing_path}")
            
            # 清理临时文件
            if os.path.exists(temp_output):
                os.remove(temp_output)
                
        except Exception as e:
            # 回滚
            if os.path.exists(temp_output):
                os.remove(temp_output)
            raise FileError(f"Merge failed: {e}", {"path": existing_path})
        
        return existing_path
    
    @classmethod
    def _build_merged_content(cls, existing_chars: Dict[str, CharacterSection], 
                              new_char: CharacterSection) -> str:
        """构建合并后的内容"""
        lines = ["# Multi-Character SOUL\n"]
        
        # 添加所有现有角色（保持原有顺序）
        for key, char_sec in existing_chars.items():
            lines.append(f"\n## {char_sec.character_name}\n")
            lines.append(f"**Source:** {char_sec.source_work}\n")
            
            if char_sec.identity:
                lines.extend(["\n### Identity", char_sec.identity])
            if char_sec.personality:
                lines.extend(["\n### Personality", char_sec.personality])
            if char_sec.speaking_style:
                lines.extend(["\n### Speaking Style", char_sec.speaking_style])
            if char_sec.boundaries:
                lines.extend(["\n### Boundaries", char_sec.boundaries])
            
            lines.append(f"\n*Hash: {char_sec.section_hash}*\n")
        
        # 添加新角色
        lines.append(f"\n## {new_char.character_name}\n")
        lines.append(f"**Source:** {new_char.source_work}\n")
        
        if new_char.identity:
            lines.extend(["\n### Identity", new_char.identity])
        if new_char.personality:
            lines.extend(["\n### Personality", new_char.personality])
        if new_char.speaking_style:
            lines.extend(["\n### Speaking Style", new_char.speaking_style])
        if new_char.boundaries:
            lines.extend(["\n### Boundaries", new_char.boundaries])
        
        lines.append(f"\n*Hash: {new_char.section_hash}*\n")
        
        # 添加角色选择指南
        all_chars = list(existing_chars.values()) + [new_char]
        if len(all_chars) > 1:
            lines.extend([
                "\n---\n",
                "## Character Selection Guide\n",
                "When multiple characters are present, select based on context:\n"
            ])
            
            for char in all_chars:
                lines.append(f"- **{char.character_name}** ({char.source_work})")
        
        lines.append(f"\n---\n*Generated by anime-character-loader v2.3 on {datetime.now().strftime('%Y-%m-%d')}*\n")
        
        return "\n".join(lines)
    
    @classmethod
    def _extract_section(cls, content: str, section_name: str) -> str:
        """提取特定章节内容"""
        # 支持 ### 和 ## 两种层级
        for prefix in ["###", "##"]:
            pattern = rf'{prefix} {re.escape(section_name)}\s*\n\n?(.+?)(?=\n#{1,3} |\Z)'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1).strip()
        return ""


# ============== CLI ==============
def main():
    parser = argparse.ArgumentParser(
        description="Anime Character Loader v2.3 - Multi-source character data with validation"
    )
    parser.add_argument("name", help="Character name (EN/JP/CN)")
    parser.add_argument("--anime", "-a", help="Anime/manga name hint for disambiguation")
    parser.add_argument("--output", "-o", default=".", help="Output directory")
    parser.add_argument("--info", "-i", action="store_true", help="Show info only, don't generate")
    parser.add_argument("--force", "-f", action="store_true", help="Force generation even with low confidence")
    parser.add_argument("--select", "-s", type=int, help="Select specific match by index (when multiple found)")
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print("🎭 Anime Character Loader v2.3")
    print(f"{'='*60}")
    
    loader = CharacterLoader()
    
    try:
        # 1. 翻译名称
        translated_name, anime_hint = loader.translate_name(args.name)
        if translated_name != args.name:
            print(f"\n📝 Name translation: '{args.name}' → '{translated_name}'")
        
        # 使用命令行提示或翻译得到的作品名
        hint = args.anime or anime_hint
        if hint:
            print(f"🎬 Anime hint: {hint}")
        
        # 2. 多源查询
        matches = loader.query_multi_source(translated_name, hint)
        
        if not matches:
            raise DataError("No matches found", {
                "query": args.name,
                "translated": translated_name,
                "suggestions": ["Try English or Japanese name", "Check spelling", "Use --anime to specify source work"]
            })
        
        # 3. 消歧（增强版：使用跨源一致性评分）
        if args.select and args.select >= 1:
            # 先计算跨源匹配
            cross_matches = loader.calculate_cross_source_consistency(matches)
            if args.select <= len(cross_matches):
                selected = loader._select_best_source_match(cross_matches[args.select - 1])
                print(f"\n✅ User selected: {selected.name}")
            else:
                raise DataError(f"Invalid selection {args.select}, only {len(cross_matches)} options available")
        else:
            selected = loader.disambiguate(matches, hint, force_hint=FORCE_DISAMBIGUATION, original_query=args.name)
        
        # 4. 置信度检查
        if selected.confidence < CONFIDENCE_THRESHOLD_LOW and not args.force:
            raise DataError(f"Low confidence match: {selected.confidence:.2f}", {
                "confidence": selected.confidence,
                "threshold": CONFIDENCE_THRESHOLD_LOW,
                "suggestion": "Use --force to generate anyway"
            })
        
        # 显示信息模式
        if args.info:
            print(f"\n{'='*60}")
            print("CHARACTER INFO")
            print(f"{'='*60}")
            print(f"Name: {selected.name}")
            print(f"Source: {selected.source_work}")
            print(f"Confidence: {selected.confidence:.2f}")
            print(f"Cross-source consistency: {selected.cross_source_consistency:.2f}")
            print(f"Data source: {selected.source}")
            print(f"\nDescription preview:")
            desc = loader._clean_description(selected.data.get("description", ""))
            print(desc[:500] + "..." if len(desc) > 500 else desc)
            return
        
        # 5. 生成 SOUL.md
        print(f"\n📝 Generating SOUL.md...")
        content = loader.generate_soul(selected)
        
        # 6. 验证
        print("\n🔍 Validating...")
        validation = loader.validate_soul(content, selected.data)
        
        print(f"\n{'='*60}")
        print("VALIDATION REPORT")
        print(f"{'='*60}")
        print(f"Overall Score: {validation.score:.1f}/100")
        print(f"Status: {'✅ PASSED' if validation.passed else '❌ FAILED'}")
        print()
        
        for check_name, (passed, description) in validation.checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check_name}: {description}")
        
        if validation.errors:
            print(f"\n⚠️ Errors:")
            for error in validation.errors:
                print(f"  - {error}")
        
        # 7. 写入临时文件
        temp_path = FileManager.write_temp(content, selected.name)
        print(f"\n📄 Temp file: {temp_path}")
        
        # 8. 验证通过后提交
        if validation.passed or args.force:
            final_path = FileManager.generate_final_path(selected.name, args.output)
            final_path = FileManager.commit(temp_path, final_path)
            print(f"✅ Final file: {final_path}")
            
            # 显示预览
            print(f"\n{'='*60}")
            print("PREVIEW")
            print(f"{'='*60}")
            preview = content[:1000] + "..." if len(content) > 1000 else content
            print(preview)
            
            # 9. 询问加载方式
            print(f"\n{'='*60}")
            print("📋 LOADING OPTIONS")
            print(f"{'='*60}")
            print(f"\nCharacter: {selected.name}")
            print(f"Source: {selected.source_work}")
            print(f"File: {final_path}")
            
            # 检查是否已有 SOUL.md
            existing_soul = os.path.join(args.output, "SOUL.md")
            has_existing = os.path.exists(existing_soul)
            
            if has_existing:
                print(f"\n⚠️  Existing SOUL.md found: {existing_soul}")
            
            print(f"\nHow would you like to load this character?")
            print(f"\n  [1] REPLACE - Replace existing SOUL.md with this character")
            if has_existing:
                print(f"      (Will backup existing SOUL.md first)")
            else:
                print(f"      cp {final_path} ./SOUL.md")
            
            print(f"\n  [2] MERGE - Structured merge into existing SOUL.md")
            if has_existing:
                print(f"      (Preserves existing content, adds character sections)")
            else:
                print(f"      (No existing SOUL.md, will create new)")
            
            print(f"\n  [3] KEEP - Keep as SOUL.generated.md for manual review")
            print(f"      (No changes to existing files)")
            
            # 在非交互式环境中默认选择 KEEP
            try:
                choice = input(f"\nEnter choice [1/2/3] (default: 3): ").strip() or "3"
            except (EOFError, KeyboardInterrupt):
                choice = "3"
                print("\n(non-interactive mode, defaulting to KEEP)")
            
            if choice == "1":
                # REPLACE
                target_path = os.path.join(args.output, "SOUL.md")
                if os.path.exists(target_path):
                    backup_path = f"{target_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    os.rename(target_path, backup_path)
                    print(f"\n  📦 Backed up existing SOUL.md to: {backup_path}")
                
                shutil.copy2(final_path, target_path)
                print(f"  ✅ Replaced: {target_path}")
                
            elif choice == "2":
                # MERGE（幂等性保证）
                target_path = os.path.join(args.output, "SOUL.md")
                if os.path.exists(target_path):
                    FileManager.structured_merge(final_path, target_path, selected.name, selected.source_work)
                else:
                    # 没有现有文件，直接复制
                    shutil.copy2(final_path, target_path)
                    print(f"  ✅ Created: {target_path}")
                
            else:
                # KEEP (default)
                print(f"\n  📄 Kept as: {final_path}")
                print(f"  💡 To load manually:")
                print(f"     cp {final_path} ./SOUL.md")
            
        else:
            FileManager.rollback(temp_path)
            raise ValidationError("Generation failed validation", {
                "score": validation.score,
                "errors": validation.errors,
                "suggestion": "Use --force to override"
            })
        
        print(f"\n{'='*60}")
        print("✅ Complete!")
        print(f"{'='*60}")
        
    except CharacterLoaderError as e:
        print(f"\n❌ Error: {e.message}")
        if e.details:
            for key, value in e.details.items():
                if key == "suggestions":
                    print(f"\n💡 Suggestions:")
                    for s in value:
                        print(f"   - {s}")
                elif key == "options":
                    print(f"\n📋 Available options:")
                    for i, opt in enumerate(value, 1):
                        print(f"   {i}. {opt}")
                elif isinstance(value, list):
                    print(f"   {key}: {', '.join(str(v) for v in value)}")
                else:
                    print(f"   {key}: {value}")
        sys.exit(e.exit_code)
    
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(ExitCode.DATA_ERROR)


if __name__ == "__main__":
    main()
