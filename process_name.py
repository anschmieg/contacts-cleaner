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

def split_name_parts(name):
    """Split name into individual parts, handling special cases"""
    if not name:
        return []
    # First split by commas for truly different name variants
    variants = []
    for variant in name.replace("\\,", ",").split(","):
        # Then split each variant by spaces
        parts = [p.strip() for p in variant.split() if p.strip()]
        if parts:
            variants.append(parts)
    return variants

def merge_name_parts(parts_list):
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
    if len(parts_list) > 1 and not any(set(parts_list[0]) & set(variant) for variant in parts_list[1:]):
        return ", ".join(" ".join(variant) for variant in parts_list)
        
    # Otherwise join as single name
    return " ".join(unique_parts)

def merge_names(name1, name2):
    """Merge two names preserving order and handling duplicates"""
    # Split both names into their parts
    parts1 = split_name_parts(name1)
    parts2 = split_name_parts(name2)
    
    # Merge the parts
    return merge_name_parts(parts1 + parts2)

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
