###################
# Name Processing
###################

from fuzzywuzzy import fuzz
from config import NAME_PARTICLES, NAME_PREFIXES, NAME_SUFFIXES, ratio_nickname_match

def capitalize_name(name):
    """Properly capitalize name parts, preserving internal casing"""
    if not name:
        return name

    def cap_part(part):
        # Handle hyphenated names
        if "-" in part:
            return "-".join(cap_part(p) for p in part.split("-"))
        # Handle suffixes
        if part.upper() in NAME_SUFFIXES:
            return part.upper()
        # Handle prefixes
        if part.upper().rstrip(".") in NAME_PREFIXES:
            return part.upper()
        # Handle particles
        if part.lower() in NAME_PARTICLES:
            return part.lower()
        # Smart capitalization: only force first letter to upper, preserve rest
        if len(part) > 1:
            return part[0].upper() + part[1:]
        return part.capitalize()

    return " ".join(cap_part(part) for part in name.split())

def merge_names(name1, name2):
    """
    Merge two names preserving relative ordering and structure
    """

    def normalize_name_order(name):
        """Convert 'LastName, FirstName' to 'FirstName LastName'"""
        if "," in name:
            parts = [p.strip() for p in name.split(",")]
            if len(parts) == 2:
                name = f"{parts[1]} {parts[0]}"
        return name

    # Normalize name order first
    name1 = normalize_name_order(name1)
    name2 = normalize_name_order(name2)

    # Rest of the name processing
    def get_position_map(name):
        """Create map of word positions, treating hyphenated names as single units"""
        parts = []
        for part in name.split():
            if part.endswith("-"):
                continue
            if part.startswith("-"):
                if parts:
                    parts[-1] = f"{parts[-1]}{part}"
                continue
            parts.append(part)
        return {part.lower(): i for i, part in enumerate(parts)}

    def is_name_variant(short, long):
        """Check if one name is a variant/nickname of another"""
        short = short.lower()
        long = long.lower()
        if any(x in ["dr.", "dr", "md", "phd"] for x in [short, long]):
            return False
        return (
            short in long
            or long.startswith(short)
            or fuzz.ratio(short, long) > ratio_nickname_match
        )

    # Pre-process names to handle hyphenated parts
    def normalize_name(name):
        parts = []
        current = []
        for part in name.split():
            if part.endswith("-"):
                current.append(part[:-1])
            elif part.startswith("-"):
                current.append(part[1:])
                parts.append("-".join(current))
                current = []
            else:
                if current:
                    current.append(part)
                else:
                    parts.append(part)
        if current:
            parts.append("-".join(current))
        return parts

    parts1 = normalize_name(name1)
    parts2 = normalize_name(name2)

    # Get position maps
    pos1 = get_position_map(" ".join(parts1))
    pos2 = get_position_map(" ".join(parts2))

    all_parts = []
    seen = set()

    def is_initial(text):
        """Check if text is an initial (single letter possibly followed by period)"""
        text = text.rstrip(".")
        return len(text) == 1 and text.isalpha()

    def keep_initial(initial, all_parts):
        """Check if an initial should be kept based on existing full names"""
        initial = initial.rstrip(".").lower()
        for part in all_parts:
            if part.lower().startswith(initial) and len(part) > 1:
                return False
        return True

    def add_part(part):
        part_lower = part.lower()
        if part_lower in seen:
            return

        # Special handling for initials
        if is_initial(part):
            if not keep_initial(part, all_parts):
                return  # Skip initial if we have the full name

        # Check for variants
        for existing_idx, existing in enumerate(all_parts):
            if is_name_variant(existing, part):
                if len(part) > len(existing):
                    if not (is_initial(existing) and not is_initial(part)):
                        all_parts[existing_idx] = part
                return
            elif is_name_variant(part, existing):
                return

        all_parts.append(part)
        seen.add(part_lower)

    # Process both names
    all_parts = []
    prefix_parts = []
    suffix_parts = []

    for parts in [parts1, parts2]:
        for part in parts:
            part_upper = part.upper().rstrip(".")
            if part_upper in NAME_PREFIXES:
                if part not in prefix_parts:
                    prefix_parts.append(part)
            elif part_upper in NAME_SUFFIXES:
                if part not in suffix_parts:
                    suffix_parts.append(part)
            else:
                add_part(part)

    # Sort main parts based on original positions
    all_parts.sort(
        key=lambda x: min(
            pos1.get(x.lower(), float("inf")), pos2.get(x.lower(), float("inf"))
        )
    )

    # Combine all parts
    result = " ".join(prefix_parts + all_parts + suffix_parts)

    # Before returning, capitalize the result
    return capitalize_name(result)


def generate_pseudo_name(contact):
    """Generate a pseudo-name using available contact information."""
    if contact.get("Email"):
        email = contact["Email"][0] if isinstance(contact["Email"], list) else contact["Email"]
        return email.split("@")[0].replace(".", " ").title()
    elif contact.get("Telephone"):
        phone = contact["Telephone"][0] if isinstance(contact["Telephone"], list) else contact["Telephone"]
        return phone
    elif contact.get("Organization"):
        return contact["Organization"]
    else:
        return "Unknown"

def get_contact_name(contact):
    """Retrieve the contact's name."""
    return contact.get("Full Name", contact.get("Name", "Unknown"))
