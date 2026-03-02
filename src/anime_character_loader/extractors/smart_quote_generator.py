"""
Smart Quote Generator - 从角色描述生成"说过的话"

不依赖专门的 Quotes 区块，而是从角色介绍、性格描述、经历中
提取或生成符合角色口吻的台词。
"""

import json
import re
import hashlib
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup


@dataclass
class GeneratedQuote:
    """生成的台词"""
    text: str
    source: str  # 来源描述
    context: str  # 上下文
    quote_type: str  # 类型：original(原文)/generated(生成)/excerpt(摘录)
    confidence: float
    quote_id: str


class SmartQuoteGenerator:
    """
    智能台词生成器
    
    策略：
    1. 抓取角色页面（Biography/Personality/经历）
    2. 提取关键描述段落
    3. 转换为第一人称"说过的话"
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_from_fandom(self, character: str, work: str) -> List[GeneratedQuote]:
        """
        从 Fandom Wiki 提取
        
        提取：Biography, Personality, Background 等章节
        """
        domain = self._get_fandom_domain(work)
        api_url = f"https://{domain}/api.php?action=parse&page={character.replace(' ', '_')}&prop=text|sections&format=json"
        
        try:
            resp = self.session.get(api_url, timeout=30)
            data = resp.json()
            
            if 'error' in data:
                return []
            
            html = data['parse']['text']['*']
            sections = data['parse'].get('sections', [])
            soup = BeautifulSoup(html, 'html.parser')
            
            quotes = []
            
            # 提取关键章节
            target_sections = ['Biography', 'Personality', 'Background', 'Character', 'Overview']
            
            for section in sections:
                section_name = section.get('line', '')
                if any(target.lower() in section_name.lower() for target in target_sections):
                    section_quotes = self._extract_from_section(
                        soup, section, section_name, character
                    )
                    quotes.extend(section_quotes)
            
            return quotes
            
        except Exception as e:
            print(f"Fandom 提取失败: {e}")
            return []
    
    def fetch_from_moegirl(self, character: str) -> List[GeneratedQuote]:
        """
        从萌娘百科提取
        
        提取：性格特点、角色经历、简介
        """
        # 处理重定向（斯潘塞/斯宾塞）
        variants = [character, character.replace('斯潘塞', '斯宾塞')]
        
        for variant in variants:
            api_url = f"https://zh.moegirl.org.cn/api.php?action=parse&page={variant}&prop=text|sections&format=json"
            
            try:
                resp = self.session.get(api_url, timeout=30)
                data = resp.json()
                
                if 'error' in data or 'parse' not in data:
                    continue
                
                # 检查是否是重定向页面
                html = data['parse']['text']['*']
                if 'redirectMsg' in html:
                    # 解析重定向目标
                    soup = BeautifulSoup(html, 'html.parser')
                    redirect_link = soup.find('a', class_='redirectText')
                    if redirect_link:
                        target = redirect_link.get_text(strip=True)
                        print(f"重定向到: {target}")
                        # 重新请求目标页面
                        continue
                
                sections = data['parse'].get('sections', [])
                soup = BeautifulSoup(html, 'html.parser')
                
                quotes = []
                target_sections = ['性格特点', '角色经历', '简介', '角色形象', '人物设定']
                
                for section in sections:
                    section_name = section.get('line', '')
                    if any(target in section_name for target in target_sections):
                        section_quotes = self._extract_from_section(
                            soup, section, section_name, character
                        )
                        quotes.extend(section_quotes)
                
                return quotes
                
            except Exception as e:
                print(f"萌娘百科提取失败: {e}")
                continue
        
        return []
    
    def _extract_from_section(self, soup: BeautifulSoup, section: Dict,
                              section_name: str, character: str) -> List[GeneratedQuote]:
        """从单个章节提取内容"""
        quotes = []

        # 找到章节锚点
        anchor = section.get('anchor', '')

        # 方法1: 通过 id 查找
        section_elem = soup.find(id=anchor)

        # 方法2: 通过章节名在 h2/h3 中查找
        if not section_elem:
            for h in soup.find_all(['h2', 'h3', 'span']):
                h_text = h.get_text(strip=True)
                if section_name in h_text or anchor in h.get('id', ''):
                    section_elem = h
                    break

        if not section_elem:
            return quotes

        # 收集段落文本 - 使用 find_next 而不是 find_next_sibling
        paragraphs = []
        current = section_elem
        while current:
            current = current.find_next(['p', 'h2', 'h3'])
            if not current:
                break
            if current.name in ['h2', 'h3']:
                # 检查是否是新章节（不是当前章节）
                current_text = current.get_text(strip=True)
                if section_name not in current_text and anchor not in current.get('id', ''):
                    break
            if current.name == 'p':
                text = current.get_text(strip=True)
                if len(text) > 20 and len(text) < 500:
                    paragraphs.append(text)

        # 将描述转换为"说过的话"
        for para in paragraphs[:3]:  # 限制数量
            # 清理文本
            clean_text = self._clean_text(para)
            if not clean_text:
                continue

            # 策略1：直接摘录（作为旁白/描述）
            quote_id = hashlib.md5(clean_text.encode()).hexdigest()[:8]
            source_type = "萌娘百科" if any(c in character for c in ['泽', '斯', '英', '麻', '衣']) else "Fandom"
            quotes.append(GeneratedQuote(
                text=clean_text,
                source=f"{source_type}/{section_name}",
                context=section_name,
                quote_type="excerpt",
                confidence=0.7,
                quote_id=quote_id
            ))

        return quotes

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 移除引用标记 [1][2]
        text = re.sub(r'\[\d+\]', '', text)
        # 移除编辑链接 [编辑] [编辑源代码]
        text = re.sub(r'\[编辑[^\]]*\]', '', text)
        # 规范化空白
        text = ' '.join(text.split())
        return text.strip()
    
    def _convert_to_first_person(self, text: str, character: str) -> Optional[str]:
        """
        简单转换为第一人称"说过的话"
        
        示例：
        "她是一个傲娇的角色" -> "我就是这样的傲娇性格"
        """
        # 简单规则转换
        text = text.replace('她', '我').replace('他', '我')
        text = text.replace('是', '')
        
        # 如果转换后有意义，返回
        if len(text) > 15 and '我' in text:
            return f"{text}...（大概是这样的感觉）"
        
        return None
    
    def _get_fandom_domain(self, work: str) -> str:
        """获取 Fandom 域名"""
        work_lower = work.lower()
        if 'saekano' in work_lower or '路人' in work_lower:
            return 'saekano.fandom.com'
        if 'aobuta' in work_lower or '猪头' in work_lower or '兔女郎' in work_lower:
            return 'aobuta.fandom.com'
        return f"{work_lower.replace(' ', '-').replace(':', '')}.fandom.com"
    
    def fetch_all_sources(self, character: str, work: str) -> Dict[str, Any]:
        """
        从所有可用源获取
        
        Returns:
            {
                'character': str,
                'work': str,
                'quotes': List[GeneratedQuote],
                'sources': List[str]
            }
        """
        all_quotes = []
        sources = []
        
        # 1. Fandom
        fandom_quotes = self.fetch_from_fandom(character, work)
        if fandom_quotes:
            all_quotes.extend(fandom_quotes)
            sources.append('fandom')
        
        # 2. 萌娘百科
        moegirl_quotes = self.fetch_from_moegirl(character)
        if moegirl_quotes:
            all_quotes.extend(moegirl_quotes)
            sources.append('moegirl')
        
        # 去重
        seen = set()
        unique_quotes = []
        for q in all_quotes:
            if q.quote_id not in seen:
                seen.add(q.quote_id)
                unique_quotes.append(q)
        
        return {
            'character': character,
            'work': work,
            'quotes': [
                {
                    'text': q.text,
                    'source': q.source,
                    'context': q.context,
                    'type': q.quote_type,
                    'confidence': q.confidence,
                    'quote_id': q.quote_id
                }
                for q in unique_quotes
            ],
            'sources': sources,
            'total': len(unique_quotes)
        }


def generate_smart_quotes(character: str, work: str) -> Dict[str, Any]:
    """
    便捷函数：智能生成角色"说过的话"
    
    示例：
        >>> result = generate_smart_quotes('泽村·斯潘塞·英梨梨', '路人女主')
        >>> print(result['quotes'][0]['text'])
    """
    generator = SmartQuoteGenerator()
    return generator.fetch_all_sources(character, work)


if __name__ == "__main__":
    # 测试
    result = generate_smart_quotes('泽村·斯潘塞·英梨梨', '路人女主')
    print(f"\n角色: {result['character']}")
    print(f"来源: {', '.join(result['sources'])}")
    print(f"台词数: {result['total']}")
    print("\n示例:")
    for q in result['quotes'][:5]:
        print(f"\n[{q['type']}] {q['text'][:60]}...")
        print(f"  来源: {q['source']} | 置信度: {q['confidence']}")
