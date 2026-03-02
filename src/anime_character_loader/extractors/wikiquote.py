"""
Wikiquote Fetcher 模块

从 Fandom Wiki 抓取角色台词数据
支持缓存（24小时）和错误处理
"""

import json
import hashlib
import os
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import quote, unquote
import logging

import requests
from bs4 import BeautifulSoup

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class Quote:
    """台词数据类"""
    text: str
    context: str = ""  # 场景/上下文
    emotion: str = ""  # 情绪标签
    
    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class QuoteCollection:
    """角色台词集合"""
    character: str
    work: str = ""  # 作品名
    quotes: List[Quote] = None
    source_url: str = ""
    fetched_at: float = 0
    
    def __post_init__(self):
        if self.quotes is None:
            self.quotes = []
        if self.fetched_at == 0:
            self.fetched_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "character": self.character,
            "work": self.work,
            "quotes": [q.to_dict() for q in self.quotes],
            "source_url": self.source_url,
            "fetched_at": self.fetched_at
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class WikiquoteError(Exception):
    """Wikiquote 抓取错误基类"""
    pass


class CharacterNotFoundError(WikiquoteError):
    """角色未找到错误"""
    pass


class NetworkError(WikiquoteError):
    """网络错误"""
    pass


class ParseError(WikiquoteError):
    """解析错误"""
    pass


class CacheManager:
    """缓存管理器 - 24小时缓存"""
    
    CACHE_DURATION = 24 * 60 * 60  # 24小时（秒）
    
    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), "..", "cache")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, character: str, work: str) -> str:
        """生成缓存键"""
        key = f"{character}_{work}".lower().replace(" ", "_")
        return hashlib.md5(key.encode()).hexdigest()
    
    def _get_cache_path(self, character: str, work: str) -> Path:
        """获取缓存文件路径"""
        cache_key = self._get_cache_key(character, work)
        return self.cache_dir / f"{cache_key}.json"
    
    def get(self, character: str, work: str) -> Optional[QuoteCollection]:
        """获取缓存数据"""
        cache_path = self._get_cache_path(character, work)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查缓存是否过期
            fetched_at = data.get('fetched_at', 0)
            if time.time() - fetched_at > self.CACHE_DURATION:
                logger.info(f"缓存已过期: {character}@{work}")
                cache_path.unlink()
                return None
            
            # 重建 QuoteCollection
            quotes = [Quote(**q) for q in data.get('quotes', [])]
            return QuoteCollection(
                character=data['character'],
                work=data.get('work', ''),
                quotes=quotes,
                source_url=data.get('source_url', ''),
                fetched_at=fetched_at
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"缓存解析失败: {e}")
            cache_path.unlink(missing_ok=True)
            return None
    
    def set(self, collection: QuoteCollection) -> None:
        """设置缓存数据"""
        cache_path = self._get_cache_path(collection.character, collection.work)
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(collection.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"缓存已保存: {cache_path}")
        except IOError as e:
            logger.warning(f"缓存保存失败: {e}")
    
    def clear(self, character: Optional[str] = None, work: Optional[str] = None) -> int:
        """清除缓存"""
        if character and work:
            cache_path = self._get_cache_path(character, work)
            if cache_path.exists():
                cache_path.unlink()
                return 1
            return 0
        else:
            # 清除所有缓存
            count = 0
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
            return count


class WikiquoteFetcher:
    """
    萌娘百科 台词抓取器
    
    支持从萌娘百科（moegirl.org.cn）网站抓取动漫/游戏角色台词
    """
    
    # 萌娘百科 域名映射
    MOEGIRL_DOMAINS = {
        "冴えない彼女の育てかた": "zh.moegirl.org.cn",
        "路人女主": "zh.moegirl.org.cn",
        "saekano": "zh.moegirl.org.cn",
        "fate": "zh.moegirl.org.cn",
        "re:zero": "zh.moegirl.org.cn",
        "進撃の巨人": "zh.moegirl.org.cn",
        "attack on titan": "zh.moegirl.org.cn",
    }
    
    DEFAULT_DOMAIN = "zh.moegirl.org.cn"
    REQUEST_TIMEOUT = 30  # 请求超时（秒）
    MAX_RETRIES = 3  # 最大重试次数
    
    def __init__(self, cache_dir: Optional[str] = None):
        self.cache = CacheManager(cache_dir)
        self.session = requests.Session()
        # 模拟真实浏览器请求头，绕过萌娘百科反爬
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
    
    def _get_domain(self, work: str) -> str:
        """根据作品名获取萌娘百科域名"""
        work_lower = work.lower()
        for key, domain in self.MOEGIRL_DOMAINS.items():
            if key in work_lower or work_lower in key:
                return domain
        return self.DEFAULT_DOMAIN

    def _build_search_url(self, character: str, work: str) -> str:
        """构建搜索 URL"""
        domain = self._get_domain(work)
        character_encoded = quote(character.replace(' ', '_'))
        return f"https://{domain}/{character_encoded}"
    
    def _build_quotes_url(self, character: str, work: str) -> str:
        """构建台词页面 URL"""
        return self._build_search_url(character, work)
    
    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """获取页面内容"""
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"请求页面: {url} (尝试 {attempt + 1}/{self.MAX_RETRIES})")
                response = self.session.get(url, timeout=self.REQUEST_TIMEOUT)
                
                if response.status_code == 404:
                    logger.warning(f"页面未找到 (404): {url}")
                    return None
                
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
                
            except requests.exceptions.Timeout:
                logger.warning(f"请求超时: {url}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"网络请求失败: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise NetworkError(f"无法获取页面: {url}, 错误: {e}")
        
        return None
    
    def _extract_quotes_from_soup(self, soup: BeautifulSoup, character: str) -> List[Quote]:
        """从页面解析台词数据"""
        quotes = []
        
        if not soup:
            return quotes
        
        # 查找主要内容区域
        content = soup.find('div', {'class': 'mw-parser-output'})
        if not content:
            content = soup.find('main') or soup.find('article') or soup
        
        # 策略1: 查找引用块 (blockquote, dl > dd)
        quote_blocks = content.find_all(['blockquote', 'dd'])
        
        for block in quote_blocks:
            text = block.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            
            # 清理文本
            text = self._clean_quote_text(text)
            
            # 尝试提取上下文（通常在同级的 dt 或前一个元素）
            context = self._extract_context(block)
            
            # 分析情绪
            emotion = self._analyze_emotion(text, context)
            
            quotes.append(Quote(text=text, context=context, emotion=emotion))
        
        # 策略2: 查找列表项中的台词
        if not quotes:
            list_items = content.find_all('li')
            for item in list_items:
                text = item.get_text(strip=True)
                if self._is_likely_quote(text, character):
                    text = self._clean_quote_text(text)
                    context = ""
                    emotion = self._analyze_emotion(text, context)
                    quotes.append(Quote(text=text, context=context, emotion=emotion))
        
        # 策略3: 查找段落中可能的台词
        if not quotes:
            paragraphs = content.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                # 寻找引号包裹的文本
                quote_matches = re.findall(r'["""「『](.+?)["""」』]', text)
                for match in quote_matches:
                    if len(match) > 5:
                        emotion = self._analyze_emotion(match, "")
                        quotes.append(Quote(text=match, context="", emotion=emotion))
        
        return quotes
    
    def _clean_quote_text(self, text: str) -> str:
        """清理台词文本"""
        # 移除引用标记
        text = re.sub(r'^["""「『]', '', text)
        text = re.sub(r'["""」』]$', '', text)
        # 移除方括号中的编辑标记
        text = re.sub(r'\[.+?\]', '', text)
        # 规范化空白
        text = ' '.join(text.split())
        return text.strip()
    
    def _extract_context(self, element) -> str:
        """提取台词的上下文/场景"""
        context = ""
        
        # 尝试获取前一个 dt 元素（定义列表的标题）
        prev = element.find_previous('dt')
        if prev:
            context = prev.get_text(strip=True)
        else:
            # 尝试获取父级标题
            for parent in element.parents:
                heading = parent.find_previous(['h2', 'h3', 'h4'])
                if heading:
                    context = heading.get_text(strip=True)
                    break
        
        return self._clean_context(context)
    
    def _clean_context(self, context: str) -> str:
        """清理上下文文本"""
        # 移除编辑链接
        context = re.sub(r'\[edit\]|编辑', '', context)
        return context.strip()
    
    def _is_likely_quote(self, text: str, character: str) -> bool:
        """判断文本是否可能是角色的台词"""
        # 包含引号的文本
        if any(c in text for c in ['"', '"', '"', '「', '『']):
            return True
        # 包含角色名
        if character.lower() in text.lower():
            return True
        # 句子长度适中
        if 10 < len(text) < 200:
            return True
        return False
    
    def _analyze_emotion(self, text: str, context: str) -> str:
        """
        分析台词的情绪标签
        基于关键词和语气分析
        """
        text_lower = text.lower()
        combined = f"{text} {context}".lower()
        
        # 情绪关键词映射
        emotion_patterns = {
            "傲娇": [r'バカ|笨蛋|baka', r'哼|っ', r'才不是|違う|じゃない'],
            "生气": [r'可恶|くそ|可恶', r'怒|愤怒', r'だめ|不行', r'違う|不对'],
            "温柔": [r'谢谢|ありがとう', r'好き|喜欢', r'大丈夫|没事', r'優しい|温柔'],
            "悲伤": [r'悲伤|悲しい', r'难过|辛い', r'泪|涙', r'さようなら|再见'],
            "开心": [r'开心|嬉しい', r'耶|やった', r'太好了|良かった', r'笑|わら'],
            "惊讶": [r'诶|えっ', r'什么|何', r'真的|本当', r'不会吧|うそ'],
            "坚定": [r'一定|必ず', r'绝不|絶対', r'会做到的|やる', r'相信|信じる'],
            "害羞": [r'那个|あの', r'不要看|見ないで', r'笨蛋|バカ.*', r'脸红了|赤い'],
            "自信": [r'当然|当然', r'交给我|任せて', r'没问题|問題ない', r'必ず|一定'],
            "吐槽": [r'吐槽|ツッコミ', r'所以说|だから', r'真是的|もう', r'唉|はぁ'],
        }
        
        scores = {}
        for emotion, patterns in emotion_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, combined):
                    score += 1
            if score > 0:
                scores[emotion] = score
        
        if scores:
            # 返回得分最高的情绪
            return max(scores, key=scores.get)
        
        # 根据文本特征判断
        if '?' in text or '？' in text:
            return "疑问"
        if '!' in text or '！' in text:
            return "激动"
        
        return "平静"
    
    def _load_from_local_db(self, character: str) -> Optional[QuoteCollection]:
        """从本地 JSON 数据库加载台词"""
        try:
            # 查找本地数据库文件
            db_paths = [
                Path(__file__).parent.parent.parent.parent / "data" / "quotes_database.json",
                Path(__file__).parent / ".." / ".." / ".." / "data" / "quotes_database.json",
                Path.cwd() / "data" / "quotes_database.json",
            ]
            
            for db_path in db_paths:
                if db_path.exists():
                    with open(db_path, 'r', encoding='utf-8') as f:
                        db = json.load(f)
                    
                    # 尝试匹配角色名（支持模糊匹配）
                    for key, data in db.items():
                        if character in key or key in character:
                            # Schema 校验
                            if not self._validate_quote_data(data):
                                logger.error(f"本地数据格式错误: {key}")
                                continue
                            
                            quotes = [Quote(**q) for q in data.get('quotes', [])]
                            return QuoteCollection(
                                character=data['character'],
                                work=data.get('work', ''),
                                quotes=quotes,
                                source_url=f"local://{db_path}#{key}",
                                fetched_at=data.get('fetched_at', time.time())
                            )
                    break
        except Exception as e:
            logger.warning(f"本地数据库加载失败: {e}")
        
        return None
    
    def _validate_quote_data(self, data: dict) -> bool:
        """校验本地数据格式"""
        required_fields = ['character', 'quotes']
        for field in required_fields:
            if field not in data:
                logger.error(f"缺少必需字段: {field}")
                return False
        
        if not isinstance(data['quotes'], list):
            logger.error("quotes 必须是列表")
            return False
        
        for i, q in enumerate(data['quotes']):
            if 'text' not in q:
                logger.error(f"第{i+1}条台词缺少 text 字段")
                return False
        
        return True
    
    def fetch(self, character: str, work: str, use_cache: bool = True, use_local_db: bool = True) -> QuoteCollection:
        """
        抓取角色台词
        
        Args:
            character: 角色名
            work: 作品名
            use_cache: 是否使用缓存
            use_local_db: 是否优先使用本地数据库
        
        Returns:
            QuoteCollection: 台词集合
        
        Raises:
            CharacterNotFoundError: 角色未找到
            NetworkError: 网络错误
        """
        # 检查缓存
        if use_cache:
            cached = self.cache.get(character, work)
            if cached:
                logger.info(f"使用缓存数据: {character}@{work}")
                return cached
        
        # 优先尝试本地数据库
        if use_local_db:
            local_data = self._load_from_local_db(character)
            if local_data:
                logger.info(f"使用本地数据库: {character}")
                if use_cache:
                    self.cache.set(local_data)
                return local_data
        
        # 构建 URL 并获取页面
        quotes_url = self._build_quotes_url(character, work)
        soup = self._fetch_page(quotes_url)
        
        # 如果 Quotes 子页面不存在，尝试主页面
        if soup is None:
            main_url = self._build_search_url(character, work)
            soup = self._fetch_page(main_url)
            
            if soup is None:
                raise CharacterNotFoundError(f"未找到角色页面: {character}@{work}")
        
        # 解析台词
        quotes = self._extract_quotes_from_soup(soup, character)
        
        if not quotes:
            logger.warning(f"未找到台词数据: {character}@{work}")
        
        # 构建结果
        collection = QuoteCollection(
            character=character,
            work=work,
            quotes=quotes,
            source_url=quotes_url if soup else main_url
        )
        
        # 保存缓存
        self.cache.set(collection)
        
        return collection
    
    def search_and_fetch(self, character: str, work: str, use_cache: bool = True) -> QuoteCollection:
        """
        搜索并抓取角色台词（带备用策略）
        
        Args:
            character: 角色名
            work: 作品名
            use_cache: 是否使用缓存
        
        Returns:
            QuoteCollection: 台词集合
        """
        try:
            return self.fetch(character, work, use_cache)
        except CharacterNotFoundError:
            # 尝试使用英文角色名
            logger.info(f"尝试英文搜索: {character}")
            # 这里可以集成翻译 API
            raise


def fetch_quotes(character: str, work: str = "", use_cache: bool = True, 
                 cache_dir: Optional[str] = None, use_local_db: bool = True) -> Dict[str, Any]:
    """
    便捷函数：抓取角色台词（优先本地数据库）
    
    Args:
        character: 角色名
        work: 作品名（可选，本地数据库优先时可省略）
        use_cache: 是否使用缓存
        cache_dir: 缓存目录
        use_local_db: 是否优先使用本地数据库
    
    Returns:
        dict: 结构化台词数据
    
    Example:
        >>> result = fetch_quotes("泽村·斯潘塞·英梨梨")
        >>> print(result['quotes'][0]['text'])
    """
    fetcher = WikiquoteFetcher(cache_dir=cache_dir)
    collection = fetcher.fetch(character, work, use_cache, use_local_db)
    return collection.to_dict()


if __name__ == "__main__":
    # 示例用法
    logging.basicConfig(level=logging.DEBUG)
    
    try:
        result = fetch_quotes("Eriri Spencer Sawamura", "Saekano")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.error(f"抓取失败: {e}")
