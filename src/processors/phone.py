from typing import List, Union
import re
from phonenumbers import parse, format_number, PhoneNumberFormat, NumberParseException
import phonenumbers


class PhoneProcessor:
    """Handles phone number processing and validation"""

    def __init__(self, default_region: str = "US"):
        self.default_region = default_region
        self._number_cache = {}

    def normalize_phone(self, phone: str) -> str:
        """Normalize a single phone number"""
        if not phone:
            return ""

        cache_key = (phone, self.default_region)
        if cache_key in self._number_cache:
            return self._number_cache[cache_key]

        # Remove all non-digit characters first
        cleaned = re.sub(r"[^\d+]", "", str(phone))

        try:
            # Parse and format the number
            parsed = parse(cleaned, self.default_region)
            normalized = format_number(parsed, PhoneNumberFormat.E164)
            self._number_cache[cache_key] = normalized
            return normalized
        except NumberParseException:
            # If parsing fails, return cleaned version
            return cleaned if cleaned else ""

    def normalize_phone_list(self, phones: Union[str, List[str]]) -> List[str]:
        """Normalize a list of phone numbers"""
        if not phones:
            return []

        # Convert to list if string
        if isinstance(phones, str):
            phones = [p.strip() for p in phones.replace(";", ",").split(",")]
        elif not isinstance(phones, list):
            phones = [str(phones)]

        # Normalize each phone number
        normalized = []
        seen = set()

        for phone in phones:
            norm = self.normalize_phone(phone)
            if norm and norm not in seen:
                seen.add(norm)
                normalized.append(norm)

        return normalized

    def are_phones_matching(self, phone1: str, phone2: str) -> bool:
        """Check if two phone numbers match"""
        norm1 = self.normalize_phone(phone1)
        norm2 = self.normalize_phone(phone2)

        if not norm1 or not norm2:
            return False

        # Compare normalized versions
        return norm1 == norm2

    def any_phones_match(self, phones1: List[str], phones2: List[str]) -> bool:
        """Check if any phone numbers match between two lists"""
        if not phones1 or not phones2:
            return False

        norm1 = set(self.normalize_phone_list(phones1))
        norm2 = set(self.normalize_phone_list(phones2))

        return bool(norm1.intersection(norm2))

    def extract_phone_numbers(self, text: str) -> List[str]:
        """Extract potential phone numbers from text"""
        if not text:
            return []

        # Basic phone number pattern
        pattern = r"\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}"
        matches = re.finditer(pattern, text)

        numbers = []
        for match in matches:
            number = self.normalize_phone(match.group())
            if number:
                numbers.append(number)

        return numbers

    def is_valid_phone(self, phone: str) -> bool:
        """Check if a phone number is valid"""
        try:
            number = parse(phone, self.default_region)
            return phonenumbers.is_valid_number(number)
        except NumberParseException:
            return False

    def get_number_type(self, phone: str) -> str:
        """Get the type of phone number (mobile, fixed line, etc)"""
        try:
            number = parse(phone, self.default_region)
            if not phonenumbers.is_valid_number(number):
                return "UNKNOWN"

            number_type = phonenumbers.number_type(number)
            type_map = {
                phonenumbers.PhoneNumberType.MOBILE: "MOBILE",
                phonenumbers.PhoneNumberType.FIXED_LINE: "FIXED_LINE",
                phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "FIXED_LINE_OR_MOBILE",
                # Add more types as needed
            }
            return type_map.get(number_type, "UNKNOWN")

        except NumberParseException:
            return "UNKNOWN"
