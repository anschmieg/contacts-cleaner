from typing import List, Optional
from difflib import SequenceMatcher
import re


def string_similarity(s1: str, s2: str) -> float:
    """Calculate string similarity ratio between two strings"""
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def clean_string(text: str, keep_chars: str = "") -> str:
    """Remove all non-alphanumeric characters except those specified"""
    if not text:
        return ""
    pattern = fr'[^a-zA-Z0-9\s{re.escape(keep_chars)}]'
    return re.sub(pattern, '', text).strip()


def normalize_whitespace(text: str) -> str:
    """Normalize all whitespace to single spaces"""
    if not text:
        return ""
    return " ".join(text.split())


def extract_numbers(text: str) -> List[str]:
    """Extract all numbers from text"""
    if not text:
        return []
    return re.findall(r'\d+', text)


def remove_special_chars(text: str) -> str:
    """Remove special characters while preserving spaces"""
    if not text:
        return ""
    return re.sub(r'[^\w\s]', '', text)


def find_longest_common_substring(s1: str, s2: str) -> str:
    """Find the longest common substring between two strings"""
    if not s1 or not s2:
        return ""
    
    matcher = SequenceMatcher(None, s1.lower(), s2.lower())
    match = matcher.find_longest_match(0, len(s1), 0, len(s2))
    return s1[match.a:match.a + match.size]


def extract_initials(name: str) -> str:
    """Extract initials from a name"""
    if not name:
        return ""
    return ''.join(word[0].upper() for word in name.split() if word)


def is_substring_fuzzy(substring: str, full_string: str, threshold: float = 0.8) -> bool:
    """Check if string is substring with fuzzy matching"""
    if not substring or not full_string:
        return False
    
    sub_len = len(substring)
    for i in range(len(full_string) - sub_len + 1):
        if string_similarity(substring, full_string[i:i+sub_len]) >= threshold:
            return True
    return False


def strip_punctuation(text: str) -> str:
    """Remove all punctuation from text"""
    if not text:
        return ""
    return re.sub(r'[^\w\s]', '', text)


def split_by_separators(text: str, separators: Optional[str] = None) -> List[str]:
    """Split text by multiple separators"""
    if not text:
        return []
    if separators is None:
        separators = r'[,;\s]+'
    return [part.strip() for part in re.split(separators, text) if part.strip()]


def remove_accents(text: str) -> str:
    """Remove diacritical marks from text"""
    import unicodedata
    if not text:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFKD', text)
                  if not unicodedata.combining(c))