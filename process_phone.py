from config import COUNTRY_PREFIXES

###################
# Phone Number Processing
###################


def normalize_phone(phone):
    """Normalize phone number format without adding default country code"""
    if not phone:
        return ""

    # Keep track of original format before cleaning
    had_plus = phone.startswith("+")
    had_zeros = phone.startswith("0")

    # Remove all non-digit and plus characters
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

    if not cleaned:
        return ""

    # Handle various international formats
    if cleaned.startswith("00"):
        return "+" + cleaned[2:]  # Convert 00XXX to +XXX
    elif had_plus:
        return cleaned  # Keep existing + prefix
    elif had_zeros:
        return cleaned  # Keep local format if it started with zeros
    else:
        return cleaned  # Keep as-is without adding country code


def normalize_phone_list(phone_str):
    """Helper to normalize and split phone numbers"""
    if not phone_str:
        return []

    # Split by any common separator
    phones = []
    for sep in [",", ";", "\n", "/", "|"]:
        if sep in phone_str:
            phones.extend(phone_str.split(sep))
            break
    else:
        phones = [phone_str]

    # Normalize each phone number
    normalized = [normalize_phone(p.strip()) for p in phones]

    # Remove duplicates while preserving order
    seen = set()
    return [x for x in normalized if x and not (x in seen or seen.add(x))]


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
