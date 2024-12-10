import re
import phonenumbers
from phonenumbers import NumberParseException
from config import COUNTRY_PREFIXES

###################
# Phone Number Processing
###################


def normalize_phone(phone):
    """Normalize individual phone number to international format."""
    if not phone:
        return phone
    # Replace leading '00' with '+'
    phone = re.sub(r'^00', '+', phone)
    try:
        # Attempt to parse the phone number with a default region (e.g., 'DE' for Germany)
        parsed_number = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed_number):
            return None  # Invalid number
        # Format to E.164 standard
        return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
    except NumberParseException:
        return None  # Unable to parse number


def normalize_phone_list(phones, default_region='DE'):
    """Normalize a list of phone numbers to international format."""
    normalized = []
    for p in phones:
        if isinstance(p, list):
            for sub_p in p:
                if isinstance(sub_p, str):
                    normalized_number = normalize_phone(sub_p.strip())
                    if normalized_number:
                        normalized.append(normalized_number)
        elif isinstance(p, str):
            normalized_number = normalize_phone(p.strip())
            if normalized_number:
                normalized.append(normalized_number)
    return normalized


def are_phones_matching(phone1, phone2):
    """Compare two phone numbers considering various formats"""
    if not phone1 or not phone2:
        return False

    n1 = normalize_phone(phone1)
    n2 = normalize_phone(phone2)

    if not n1 or not n2:
        return False

    # Direct match
    if n1 == n2:
        return True

    # Compare without plus
    n1_bare = n1.lstrip("+")
    n2_bare = n2.lstrip("+")

    if n1_bare == n2_bare:
        return True

    # Split the numbers into parts for comparison if they don't have a country code
    if not n1.startswith("+") and not n2.startswith("+"):
        n1_parts = n1_bare.split()
        n2_parts = n2_bare.split()
        if len(n1_parts) == len(n2_parts) and all(
            part1 == part2 for part1, part2 in zip(n1_parts, n2_parts)
        ):
            return True

    # Handle international prefix vs local format
    # e.g., +44 20 1234 5678 should match 020 1234 5678
    for prefix in COUNTRY_PREFIXES:
        if n1_bare.startswith(prefix):
            local = n1_bare[len(prefix) :]
            if local.startswith("0"):
                local = local[1:]  # Remove leading 0
            if n2_bare.startswith("0"):
                if local == n2_bare[1:]:  # Match without leading 0
                    return True
            elif local == n2_bare:
                return True
        if n2_bare.startswith(prefix):
            local = n2_bare[len(prefix) :]
            if local.startswith("0"):
                local = local[1:]  # Remove leading 0
            if n1_bare.startswith("0"):
                if local == n1_bare[1:]:  # Match without leading 0
                    return True
            elif local == n1_bare:
                return True

    return False


def any_phones_match(contact1, contact2):
    """
    Check if any phone numbers match between two contacts.
    Uses are_phones_matching() for individual number comparison.
    """
    phones1 = normalize_phone_list(contact1.get("Telephone", ""))
    phones2 = normalize_phone_list(contact2.get("Telephone", ""))

    return any(
        are_phones_matching(phone1, phone2) for phone1 in phones1 for phone2 in phones2
    )


def get_bare_numbers(phone_list):
    """Extract bare numbers without country codes or prefixes for comparison"""
    numbers = []
    for phone in phone_list:
        # Remove common prefixes
        clean = phone.lstrip("+")
        # Remove country code if present
        for prefix in sorted(COUNTRY_PREFIXES.keys(), key=len, reverse=True):
            if clean.startswith(prefix):
                clean = clean[len(prefix) :]
                break
        # Remove leading zeros
        clean = clean.lstrip("0")
        if clean:
            numbers.append(clean)
    return numbers
