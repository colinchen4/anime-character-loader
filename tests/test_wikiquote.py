"""
Wikiquote Fetcher 测试用例

测试覆盖:
1. 数据类 (Quote, QuoteCollection)
2. 缓存管理 (CacheManager)
3. 抓取器 (WikiquoteFetcher)
4. 错误处理
5. 网络超时/重试
"""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from anime_character_loader.extractors.wikiquote import (
    Quote, QuoteCollection, CacheManager, WikiquoteFetcher,
    WikiquoteError, CharacterNotFoundError, NetworkError, ParseError,
    fetch_quotes
)


class TestQuote:
    """测试 Quote 数据类"""
    
    def test_quote_creation(self):
        """测试创建 Quote"""
        quote = Quote(text="バカ！", context="生气时", emotion="傲娇")
        assert quote.text == "バカ！"
        assert quote.context == "生气时"
        assert quote.emotion == "傲娇"
    
    def test_quote_to_dict(self):
        """测试 Quote 转字典"""
        quote = Quote(text="ありがとう", emotion="温柔")
        d = quote.to_dict()
        assert d["text"] == "ありがとう"
        assert d["emotion"] == "温柔"
        assert d["context"] == ""


class TestQuoteCollection:
    """测试 QuoteCollection 数据类"""
    
    def test_collection_creation(self):
        """测试创建集合"""
        quotes = [
            Quote("台词1", "场景1", "情绪1"),
            Quote("台词2", "场景2", "情绪2"),
        ]
        collection = QuoteCollection(
            character="英梨々",
            work="冴えない彼女",
            quotes=quotes
        )
        assert collection.character == "英梨々"
        assert len(collection.quotes) == 2
        assert collection.fetched_at > 0
    
    def test_collection_to_dict(self):
        """测试集合转字典"""
        collection = QuoteCollection(
            character="Test",
            quotes=[Quote("Hello")]
        )
        d = collection.to_dict()
        assert d["character"] == "Test"
        assert len(d["quotes"]) == 1
        assert "fetched_at" in d
    
    def test_collection_to_json(self):
        """测试集合转 JSON"""
        collection = QuoteCollection(character="Test")
        json_str = collection.to_json()
        assert "Test" in json_str
        assert '"quotes":' in json_str


class TestCacheManager:
    """测试缓存管理器"""
    
    def test_cache_save_and_load(self, tmp_path):
        """测试缓存保存和加载"""
        cache = CacheManager(str(tmp_path))
        
        collection = QuoteCollection(
            character="英梨々",
            work="Saekano",
            quotes=[Quote("バカ！")]
        )
        
        # 保存
        cache.set(collection)
        
        # 加载
        loaded = cache.get("英梨々", "Saekano")
        assert loaded is not None
        assert loaded.character == "英梨々"
        assert len(loaded.quotes) == 1
    
    def test_cache_expiration(self, tmp_path):
        """测试缓存过期"""
        cache = CacheManager(str(tmp_path))
        cache.CACHE_DURATION = 0  # 立即过期
        
        collection = QuoteCollection(character="Test")
        cache.set(collection)
        
        # 应该返回 None（已过期）
        loaded = cache.get("Test", "")
        assert loaded is None
    
    def test_cache_clear(self, tmp_path):
        """测试清除缓存"""
        cache = CacheManager(str(tmp_path))
        
        collection = QuoteCollection(character="Test")
        cache.set(collection)
        
        # 清除特定缓存
        count = cache.clear("Test", "")
        assert count == 1
        
        # 确认已清除
        assert cache.get("Test", "") is None
    
    def test_cache_clear_all(self, tmp_path):
        """测试清除所有缓存"""
        cache = CacheManager(str(tmp_path))
        
        cache.set(QuoteCollection(character="Test1"))
        cache.set(QuoteCollection(character="Test2"))
        
        # 清除所有
        count = cache.clear()
        assert count == 2


class TestWikiquoteFetcher:
    """测试 WikiquoteFetcher"""
    
    def test_fetcher_init(self):
        """测试初始化"""
        fetcher = WikiquoteFetcher()
        assert fetcher.cache is not None
        assert fetcher.session is not None
    
    def test_get_domain(self):
        """测试域名解析"""
        fetcher = WikiquoteFetcher()
        
        # 已知作品
        domain = fetcher._get_domain("Saekano")
        assert domain == "zh.moegirl.org.cn"
        
        # 未知作品（现在默认返回 zh.moegirl.org.cn）
        domain = fetcher._get_domain("Unknown Work")
        assert domain == "zh.moegirl.org.cn"
    
    def test_analyze_emotion(self):
        """测试情绪分析"""
        fetcher = WikiquoteFetcher()
        
        # 傲娇
        emotion = fetcher._analyze_emotion("バカ！違う！", "")
        assert emotion == "傲娇"
        
        # 温柔
        emotion = fetcher._analyze_emotion("ありがとう", "")
        assert emotion == "温柔"
        
        # 惊讶（"本当"匹配惊讶关键词）
        emotion = fetcher._analyze_emotion("本当？", "")
        assert emotion == "惊讶"
    
    def test_clean_quote_text(self):
        """测试文本清理"""
        fetcher = WikiquoteFetcher()
        
        text = fetcher._clean_quote_text('"Hello World"')
        assert text == "Hello World"
        
        text = fetcher._clean_quote_text("  Multiple   Spaces  ")
        assert text == "Multiple Spaces"
    
    @pytest.mark.skip(reason="需要网络")
    def test_fetch_real_character(self):
        """测试真实角色抓取（需要网络）"""
        fetcher = WikiquoteFetcher()
        
        try:
            result = fetcher.fetch("Eriri Spencer Sawamura", "Saekano")
            assert result.character == "Eriri Spencer Sawamura"
            assert isinstance(result.quotes, list)
        except (CharacterNotFoundError, NetworkError):
            pytest.skip("网络或角色不可用")
    
    def test_fetch_with_invalid_character(self):
        """测试无效角色抓取"""
        fetcher = WikiquoteFetcher()
        
        # 使用错误的 URL 格式，应该返回空或抛出异常
        # 这里主要测试错误处理不崩溃
        try:
            result = fetcher.fetch("InvalidCharacter12345", "InvalidWork", use_cache=False)
            # 如果没有抛出异常，应该返回空结果或少量结果
            assert isinstance(result.quotes, list)
        except (CharacterNotFoundError, NetworkError):
            pass  # 预期的异常


class TestErrors:
    """测试错误处理"""
    
    def test_error_hierarchy(self):
        """测试错误继承关系"""
        assert issubclass(CharacterNotFoundError, WikiquoteError)
        assert issubclass(NetworkError, WikiquoteError)
        assert issubclass(ParseError, WikiquoteError)
    
    def test_raise_character_not_found(self):
        """测试角色未找到错误"""
        with pytest.raises(CharacterNotFoundError) as exc_info:
            raise CharacterNotFoundError("角色不存在")
        assert "角色不存在" in str(exc_info.value)
    
    def test_raise_network_error(self):
        """测试网络错误"""
        with pytest.raises(NetworkError) as exc_info:
            raise NetworkError("连接超时")
        assert "连接超时" in str(exc_info.value)


class TestIntegration:
    """集成测试"""
    
    def test_full_workflow(self, tmp_path):
        """测试完整工作流程"""
        cache_dir = str(tmp_path)
        
        # 1. 创建 fetcher
        fetcher = WikiquoteFetcher(cache_dir=cache_dir)
        
        # 2. 尝试抓取（可能失败，但不应崩溃）
        try:
            result = fetcher.fetch("英梨々", "冴えない彼女の育てかた")
            
            # 3. 验证结果结构
            assert "character" in result.to_dict()
            assert "quotes" in result.to_dict()
            assert isinstance(result.quotes, list)
            
            # 4. 验证缓存
            cached = fetcher.cache.get("英梨々", "冴えない彼女の育てかた")
            assert cached is not None
            
        except (CharacterNotFoundError, NetworkError):
            pytest.skip("网络不可用")
    
    def test_convenience_function(self, tmp_path):
        """测试便捷函数"""
        cache_dir = str(tmp_path)
        
        try:
            result = fetch_quotes("Test", "Test", use_cache=True, cache_dir=cache_dir)
            assert isinstance(result, dict)
            assert "character" in result
        except (CharacterNotFoundError, NetworkError):
            pytest.skip("网络不可用")


class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_quote_list(self):
        """测试空台词列表"""
        collection = QuoteCollection(character="Test", quotes=[])
        assert len(collection.quotes) == 0
        assert collection.to_dict()["quotes"] == []
    
    def test_very_long_quote(self):
        """测试超长台词"""
        long_text = "A" * 1000
        quote = Quote(text=long_text)
        assert len(quote.text) == 1000
    
    def test_special_characters(self):
        """测试特殊字符"""
        quote = Quote(text="特殊字符：日本語「」『』😊")
        d = quote.to_dict()
        assert "日本語" in d["text"]
    
    def test_cache_corruption(self, tmp_path):
        """测试缓存损坏处理"""
        cache = CacheManager(str(tmp_path))
        
        # 创建损坏的缓存文件
        cache_key = cache._get_cache_key("Test", "")
        cache_path = cache.cache_dir / f"{cache_key}.json"
        cache_path.write_text("invalid json")
        
        # 应该返回 None 而不是崩溃
        result = cache.get("Test", "")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
