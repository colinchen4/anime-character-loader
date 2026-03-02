"""Wikiquote fetcher for extracting character dialogue from Fandom Wiki.

This module fetches character quotes from Fandom Wiki pages and structures
them for SOUL.md generation.
"""

import re
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


@dataclass
class Quote:
    """A single quote with metadata."""
    text: str
    context: str = ""
    emotion: str = ""
    source: str = ""


class WikiquoteFetcher:
    """Fetch character quotes from Fandom Wiki."""
    
    def __init__(self, cache_duration: int = 86400):
        self.cache_duration = cache_duration
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def _build_url(self, character_name: str, series_name: Optional[str] = None) -> str:
        """Build Fandom Wiki URL for character quotes."""
        # Format: https://[series].fandom.com/wiki/[Character]/Quotes
        series_slug = self._slugify(series_name or "")
        char_slug = self._slugify(character_name)
        
        # Try series-specific fandom first
        if series_slug:
            return f"https://{series_slug}.fandom.com/wiki/{char_slug}/Quotes"
        
        # Fallback to general search
        return f"https://{char_slug.replace('_', '')}.fandom.com/wiki/{char_slug}/Quotes"
    
    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text
    
    def fetch_quotes(self, character_name: str, series_name: Optional[str] = None) -> List[Quote]:
        """Fetch quotes for a character.
        
        Args:
            character_name: Character name (e.g., "Eriri Sawamura")
            series_name: Series name for wiki lookup (e.g., "saekano")
            
        Returns:
            List of Quote objects with text, context, and emotion
        """
        url = self._build_url(character_name, series_name)
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"⚠️ Failed to fetch {url}: {e}")
            return []
        
        return self._parse_quotes(response.text, character_name)
    
    def _parse_quotes(self, html: str, character_name: str) -> List[Quote]:
        """Parse quotes from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        quotes = []
        
        # Find quotes sections
        # Fandom wikis typically use h2/h3 for sections and various formats for quotes
        content = soup.find('div', {'class': 'mw-parser-output'})
        if not content:
            return quotes
        
        current_context = ""
        current_emotion = ""
        
        for element in content.find_all(['h2', 'h3', 'dl', 'p', 'li']):
            # Section headers give context
            if element.name in ['h2', 'h3']:
                text = element.get_text().strip()
                if 'quotes' not in text.lower():
                    current_context = text.replace('[edit]', '').strip()
                    current_emotion = self._infer_emotion(text)
                continue
            
            # Parse quote text
            quote_text = self._extract_quote_text(element)
            if not quote_text:
                continue
            
            # Skip if it's just metadata/template text
            if len(quote_text) < 10:
                continue
            
            quotes.append(Quote(
                text=quote_text,
                context=current_context,
                emotion=current_emotion,
                source="Fandom Wiki"
            ))
        
        return quotes
    
    def _extract_quote_text(self, element) -> str:
        """Extract clean quote text from element."""
        # Remove references, edit links, etc.
        for tag in element.find_all(['sup', 'span']):
            if 'reference' in tag.get('class', []) or tag.get('class') == ['mw-editsection']:
                tag.decompose()
        
        text = element.get_text().strip()
        
        # Clean up common wiki artifacts
        text = re.sub(r'\[\d+\]', '', text)  # Remove citation numbers
        text = re.sub(r'\s+', ' ', text)      # Normalize whitespace
        
        return text
    
    def _infer_emotion(self, context: str) -> str:
        """Infer emotion from context text."""
        context_lower = context.lower()
        
        emotions = {
            'angry': ['angry', 'mad', 'furious', 'annoyed'],
            'sad': ['sad', 'cry', 'tear', 'upset'],
            'happy': ['happy', 'joy', 'excited', 'glad'],
            'tsundere': ['tsundere', 'embarrassed', 'flustered'],
            'confident': ['confident', 'proud', 'cocky'],
        }
        
        for emotion, keywords in emotions.items():
            if any(kw in context_lower for kw in keywords):
                return emotion
        
        return "neutral"
    
    def to_soul_prompt(self, quotes: List[Quote]) -> str:
        """Convert quotes to SOUL.md generation prompt."""
        if not quotes:
            return "No quotes found."
        
        # Group by emotion
        emotion_groups: Dict[str, List[str]] = {}
        for q in quotes:
            emotion_groups.setdefault(q.emotion, []).append(q.text)
        
        prompt_lines = [
            "Based on the following character dialogue samples from Fandom Wiki:",
            "",
            "## Dialogue Samples by Emotion:",
        ]
        
        for emotion, texts in emotion_groups.items():
            prompt_lines.append(f"\n### {emotion.upper()}")
            for text in texts[:5]:  # Limit to 5 per emotion
                prompt_lines.append(f'- "{text[:200]}..."' if len(text) > 200 else f'- "{text}"')
        
        prompt_lines.extend([
            "",
            "## Analysis Tasks:",
            "1. Extract 5-10 signature phrases/word patterns",
            "2. Identify speech mannerisms (stuttering, honorifics, etc.)",
            "3. Note emotional transition patterns",
            "4. Summarize unique speaking style",
            "5. Generate SOUL.md Identity and Speaking Style sections",
        ])
        
        return "\n".join(prompt_lines)


def fetch_character_quotes(character_name: str, series_name: Optional[str] = None) -> Dict:
    """Convenience function to fetch and format quotes.
    
    Returns:
        Dict with 'quotes' list and 'prompt' string
    """
    fetcher = WikiquoteFetcher()
    quotes = fetcher.fetch_quotes(character_name, series_name)
    
    return {
        'character': character_name,
        'series': series_name,
        'quote_count': len(quotes),
        'quotes': [
            {'text': q.text, 'context': q.context, 'emotion': q.emotion}
            for q in quotes
        ],
        'soul_prompt': fetcher.to_soul_prompt(quotes)
    }


if __name__ == "__main__":
    # Test with Eriri
    result = fetch_character_quotes("Eriri Sawamura", "saekano")
    print(f"Found {result['quote_count']} quotes")
    print("\nSOUL Prompt preview:")
    print(result['soul_prompt'][:1000])
