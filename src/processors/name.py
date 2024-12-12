# src/processors/name_processor.py
from typing import List, Tuple, Set
import re
from fuzzywuzzy import fuzz
from ..core.contact import Contact


class NameProcessor:
    def __init__(self):
        from difflib import SequenceMatcher
        self.string_matcher = SequenceMatcher(None)
        
        self.titles = {"prof", "dr", "mr", "mrs", "ms", "phd"}
        self.suffix_patterns = {
            "generational": r"\b(Sr\.?|Jr\.?|[IVX]+)\b",
            "professional": r"\b(PhD|MD|JD|ESQ)\.?\b",
        }
        self.name_cache = {}

        # Added from settings.py
        self.suffixes = {"II", "III", "IV", "MD", "PhD", "Jr", "Sr"}
        self.prefixes = {"Dr", "Prof", "Mr", "Mrs", "Ms"}
        self.particles = {"von", "van", "de", "la", "das", "dos", "der", "den"}

        # Add these exact constants from process_name.py
        self.NAME_PARTICLES = {"von", "van", "de", "la", "das", "dos", "der", "den"}
        self.NAME_PREFIXES = {"Dr", "Prof", "Mr", "Mrs", "Ms"}
        self.NAME_SUFFIXES = {"II", "III", "IV", "MD", "PhD", "Jr", "Sr"}
        self.ratio_nickname_match = 90

    def process_name(self, name: str) -> str:
        """Main entry point for name processing"""
        if not name:
            return name

        cache_key = name.lower()
        if cache_key in self.name_cache:
            return self.name_cache[cache_key]

        processed = self._clean_name(name)
        processed = self._normalize_case(processed)

        self.name_cache[cache_key] = processed
        return processed

    def _clean_name(self, name: str) -> str:
        """Remove titles and normalize spacing"""
        name = re.sub(r"\s+", " ", name)
        for title in self.titles:
            pattern = rf"\b{title}\b\.?\s*"
            name = re.sub(pattern, "", name, flags=re.IGNORECASE)
        return name.strip()

    def _normalize_case(self, name: str) -> str:
        """Apply proper casing rules to name parts"""
        parts = name.split()
        normalized = []
        for part in parts:
            if "-" in part:
                normalized.append("-".join(p.capitalize() for p in part.split("-")))
            else:
                normalized.append(part.capitalize())
        return " ".join(normalized)

    def split_full_name(self, full_name: str) -> Tuple[str, str]:
        """Extract first and last name from full name"""
        parts = full_name.split()
        if len(parts) == 0:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return " ".join(parts[:-1]), parts[-1]

    def merge_names(self, names: List[str]) -> str:
        """Merge a list of names into a single name"""
        if not names:
            return ""

        parts = []
        for name in names:
            parts.extend(self.split_name_variants(name))

        return self.merge_name_parts(parts)

    def normalize_name(self, name: str) -> str:
        """Single entry point for name normalization"""
        # Combine existing name processing logic here

    def extract_name_variants(self, contact: "Contact") -> Set[str]:
        """Extract all possible name variants from a contact"""
        variants = set()

        # Add full name
        if contact.full_name:
            variants.add(contact.full_name.lower())

        # Add first and last name combinations
        if contact.first_name and contact.last_name:
            variants.add(f"{contact.first_name} {contact.last_name}".lower())
            variants.add(f"{contact.last_name}, {contact.first_name}".lower())

        # Add individual names
        if contact.first_name:
            variants.add(contact.first_name.lower())
        if contact.last_name:
            variants.add(contact.last_name.lower())

        # Add nicknames and variations
        if contact.first_name:
            nicknames = self.get_name_variants(contact.first_name)
            variants.update(n.lower() for n in nicknames)

        return variants

    def get_name_variants(self, name: str) -> Set[str]:
        """Get common variants and nicknames for a given name"""
        # Add logic for nickname lookup if needed
        return {name}

    def is_name_gender_variant(self, name1: str, name2: str) -> bool:
        """Check if names might be gender variants (e.g., Antonio/Antonia)"""
        # Common gender-variant endings
        feminine_endings = {"a", "ina", "elle", "ella", "ette"}
        masculine_endings = {"o", "us", "er", "or"}

        # Get the longer and shorter name for comparison
        n1, n2 = sorted([name1.lower(), name2.lower()], key=len, reverse=True)

        # If names are identical except for the ending
        if n1[:-1] == n2 or n1[:-2] == n2:
            # Check if one ends with feminine ending and the other doesn't
            n1_has_fem = any(n1.endswith(end) for end in feminine_endings)
            n2_has_fem = any(n2.endswith(end) for end in feminine_endings)
            n1_has_masc = any(n1.endswith(end) for end in masculine_endings)
            n2_has_masc = any(n2.endswith(end) for end in masculine_endings)

            # If one name has feminine ending and other has masculine, they're likely variants
            if (n1_has_fem and n2_has_masc) or (n1_has_masc and n2_has_fem):
                return True

        return False

    def is_likely_nickname(self, name1: str, name2: str) -> bool:
        """Check if names might be nickname variants"""
        if not name1 or not name2:
            return False

        # Get shorter and longer name
        short, long = sorted([name1.lower(), name2.lower()], key=len)

        # If one name is contained within the other but they're not the same
        if short != long and (short in long or long.startswith(short)):
            # Require at least 3 chars to match to avoid false positives
            if len(short) >= 3:
                # Calculate what portion of the shorter name matches
                match_ratio = len(short) / len(long)
                # If less than 80% match, likely a nickname variation
                if match_ratio < 0.8:
                    return True

        return False

    def split_name_variants(self, name):
        """Split name into variants, handling comma-separated lists"""
        if not name:
            return []
        variants = []
        for variant in name.replace("\\,", ",").split(","):
            parts = [p.strip() for p in variant.split() if p.strip()]
            if parts:
                variants.append(parts)
        return variants

    def merge_name_parts(self, parts_list: List[List[str]]) -> str:
        """Merge name parts maintaining order and removing duplicates"""
        if not parts_list:
            return ""

        # Track positions of first occurrence of each part
        seen_positions = {}
        for variant in parts_list:
            for pos, part in enumerate(variant):
                if part not in seen_positions:
                    seen_positions[part] = pos

        # Get unique parts and sort by their first occurrence
        unique_parts = sorted(seen_positions.keys(), key=lambda x: seen_positions[x])

        # If we have multiple completely different names, join with comma
        if len(parts_list) > 1 and not any(
            set(parts_list[0]) & set(variant) for variant in parts_list[1:]
        ):
            return ", ".join(" ".join(variant) for variant in parts_list)

        # Otherwise join as single name
        return " ".join(unique_parts)

    def get_index_key(self, name: str) -> str:
        """Generate index key for name matching"""
        if not name:
            return ""
        cleaned = self._clean_name(name.lower())
        return cleaned[:3] if cleaned else ""

    def generate_pseudo_name(self, contact: dict) -> str:
        """Generate a name when no proper name is available"""
        if not contact:
            return "Unknown"

        # Try email first
        if email := contact.get("Email"):
            if isinstance(email, list):
                email = email[0]
            local_part = email.split("@")[0]
            name = self._clean_email_name(local_part)
            return self._normalize_case(name)

        # Try organization
        if org := contact.get("Organization"):
            org_name = self._clean_name(org)
            return self._normalize_case(f"{org_name} (Organization)")

        # Try phone
        if phone := contact.get("Telephone"):
            if isinstance(phone, list):
                phone = phone[0]
            return f"Contact ({phone})"

        return "Unknown Contact"

    def _clean_email_name(self, local_part: str) -> str:
        """Clean up email local part to make it more name-like"""
        # Remove numbers
        name = re.sub(r"\d+", "", local_part)
        # Replace separators with spaces
        name = re.sub(r"[._-]+", " ", name)
        # Capitalize each word
        return " ".join(word.capitalize() for word in name.split())

    def remove_suffixes(self, name: str) -> str:
        """Remove common name suffixes"""
        cleaned_name = name
        for pattern in self.suffix_patterns.values():
            cleaned_name = re.sub(pattern, "", cleaned_name, flags=re.IGNORECASE)
        return " ".join(cleaned_name.split())

    def extract_suffixes(self, name: str) -> Tuple[str, Set[str]]:
        """Extract suffixes from name"""
        suffixes = set()
        cleaned_name = name

        for suffix_type, pattern in self.suffix_patterns.items():
            matches = re.findall(pattern, cleaned_name, flags=re.IGNORECASE)
            if matches:
                suffixes.update(matches)
                cleaned_name = re.sub(pattern, "", cleaned_name, flags=re.IGNORECASE)

        return cleaned_name.strip(), suffixes

    def compare_names(self, name1: str, name2: str) -> float:
        """Compare two names and return similarity score"""
        if not name1 or not name2:
            return 0.0

        # Clean and normalize names
        n1 = self._clean_name(name1.lower())
        n2 = self._clean_name(name2.lower())

        # Check for exact match
        if n1 == n2:
            return 1.0

        # Check for nickname or gender variant
        if self.is_likely_nickname(n1, n2) or self.is_name_gender_variant(n1, n2):
            return 0.9

        # Fallback to fuzzy matching
        return fuzz.ratio(n1, n2) / 100

    def get_name_parts(self, name: str) -> List[str]:
        """Split name into individual parts, handling special cases"""
        if not name:
            return []

        # Clean the name first
        cleaned = self._clean_name(name)

        # Handle hyphenated names
        parts = []
        for word in cleaned.split():
            if "-" in word:
                parts.extend(word.split("-"))
            else:
                parts.append(word)

        return [p for p in parts if p]

    def has_conflicting_names(self, name1_parts, name2_parts):
        """Check if any name parts are gender variants or too different"""
        for n1 in name1_parts:
            for n2 in name2_parts:
                if n1 != n2:  # Don't compare same names
                    # If any pair of names are gender variants, names conflict
                    if self.is_name_gender_variant(n1, n2):
                        return True
                    # If any pair of names are too different, names conflict
                    similarity = fuzz.ratio(n1, n2) / 100
                    if similarity < 0.3:
                        return True
        return False

    def process_contact_name(self, contact_data: dict) -> str:
        """Comprehensive name processing for contact data"""
        # Try standard name fields
        for field in ["Full Name", "Name", "Structured Name"]:
            if name := contact_data.get(field):
                processed = self.process_name(str(name))
                if processed:
                    return processed

        # Try nickname if available
        if nickname := contact_data.get("Nickname"):
            processed = self.process_name(str(nickname))
            if processed:
                return processed

        # Generate pseudo-name if no proper name found
        return self.generate_pseudo_name(contact_data)

    def get_contact_name(self, contact) -> str:
        """Get the best available name from a contact"""
        if contact.full_name:
            return contact.full_name
        
        if contact.first_name or contact.last_name:
            return ' '.join(filter(None, [contact.first_name, contact.last_name]))
            
        if contact.organization:
            return contact.organization
            
        if contact.emails:
            return contact.emails[0].split('@')[0].replace('.', ' ').title()
            
        if contact.phones:
            return contact.phones[0]
            
        return "Unknown"

    def string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity ratio between two strings"""
        if not s1 or not s2:
            return 0.0
        # Set sequences and get ratio
        self.string_matcher.set_seqs(s1.lower(), s2.lower())
        return self.string_matcher.ratio()
