###################
# Contact Processing
###################

import os
from dotenv import load_dotenv
from fuzzywuzzy import fuzz
from math import prod
from process_address import (
    normalize_address,
    AddressValidationMode,
    string_to_address_dict,  # Add this import
)
from process_name import get_contact_name, merge_names
from process_phone import (
    # any_phones_match,
    are_phones_matching,
    normalize_phone_list,
)
import logging
from difflib import SequenceMatcher
from typing import Dict, Any


# Load environment variables from .env file
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")


def create_contact_index(contacts):
    """Create name-based index for faster matching"""
    index = {}
    for contact in contacts:
        name = get_contact_name(contact).lower()
        first_chars = name[:3] if name else ""  # First 3 chars as block key
        if first_chars:
            if first_chars not in index:
                index[first_chars] = []
            index[first_chars].append(contact)
    return index


def extract_name_variants(contact):
    """Extract all name-related fields from a contact"""
    variants = set()

    # Get all name fields
    for field in ["Full Name", "Structured Name", "Name", "Nickname"]:
        if field in contact and contact[field]:
            value = str(contact[field]).strip()
            if value:
                variants.add(value)
                # Add each part as a variant
                variants.update(part.strip() for part in value.split())

    # Add organization as potential match
    if "Organization" in contact and contact["Organization"]:
        org = str(contact["Organization"]).strip()
        if org:
            variants.add(org)
            # Add each part of organization name
            variants.update(part.strip() for part in org.split())

    return variants


def merge_contact_group(duplicates, validation_mode=AddressValidationMode.FULL):
    """Modified contact merging to preserve all name components"""
    merged_contact = {}
    confidence_scores = []

    # Collect all name variants first
    all_names = {
        "Full Name": set(),
        "FirstName": set(),
        "LastName": set(),
        "Name": set(),
        "Structured Name": set(),
    }

    # Initialize empty address list in merged contact
    merged_contact["Address"] = []

    # First pass: collect all name components
    for duplicate in duplicates:
        for key in all_names.keys():
            if key in duplicate and duplicate[key]:
                value = str(duplicate[key]).strip()
                if value:
                    all_names[key].add(value)

    # Regular merge process with modified name handling
    for duplicate in duplicates:
        for key, value in duplicate.items():
            if not value or str(value).strip() == "":
                continue

            value = str(value).strip()
            if key in merged_contact:
                if key in [
                    "Full Name",
                    "FirstName",
                    "LastName",
                    "Name",
                    "Structured Name",
                ]:
                    # Skip if value is already included
                    if value not in all_names[key]:
                        all_names[key].add(value)
                        merged_contact[key] = ", ".join(filter(None, all_names[key]))
                elif key == "Telephone":
                    # Enhanced phone number handling
                    existing_phones = normalize_phone_list(merged_contact[key])
                    new_phones = normalize_phone_list(value)

                    # Only add non-matching phones
                    for new_phone in new_phones:
                        if not any(
                            are_phones_matching(new_phone, existing)
                            for existing in existing_phones
                        ):
                            existing_phones.append(new_phone)  # Added missing code

                    merged_contact[key] = ", ".join(existing_phones)
                elif key == "Address":
                    # Handle multiple addresses
                    if isinstance(value, list):
                        addresses = value
                    else:
                        addresses = [value]

                    for addr in addresses:
                        if isinstance(addr, str):
                            normalized_addr = normalize_address(addr, api_key, validation_mode)
                            new_addr = normalized_addr
                        else:
                            new_addr = addr

                        # Check if this address is already in the list
                        addr_label = new_addr.get("vcard", {}).get("label", "")
                        if not any(existing.get("vcard", {}).get("label") == addr_label
                                   for existing in merged_contact["Address"]):
                            merged_contact["Address"].append(new_addr)  # Added missing code
                else:
                    # ...existing handling for other fields...
                    if len(value) > len(merged_contact[key]):
                        merged_contact[key] = value
                    elif (
                        "," in value
                        or merged_contact[key] in value
                        or value in merged_contact[key]
                    ):
                        existing = merged_contact[key].split(", ")
                        new = value.split(", ")
                        merged_contact[key] = ", ".join(
                            existing + [v for v in new if v not in existing]
                        )
                    else:
                        if key in ["Full Name", "Structured Name", "Name"]:
                            merged_contact[key] = merge_names(
                                merged_contact[key], value
                            )
            else:
                if key in [
                    "Full Name",
                    "FirstName",
                    "LastName",
                    "Name",
                    "Structured Name",
                ]:
                    all_names[key].add(value)
                    merged_contact[key] = value
                elif key == "Address":
                    merged_contact[key] = normalize_address(
                        value, api_key, validation_mode
                    )
                else:
                    merged_contact[key] = value

        # Collect confidence scores for the merged contact
        match_details = is_duplicate_with_confidence(duplicates[0], duplicate)
        confidence_scores.append(match_details["confidence"])

    # Ensure name components are properly joined
    for key in all_names.keys():
        if all_names[key]:
            merged_contact[key] = ", ".join(filter(None, all_names[key]))

    # Calculate overall confidence for the merged contact using geometric mean
    merged_contact["Match Confidence"] = (
        prod(confidence_scores) ** (1 / len(confidence_scores))
        if confidence_scores
        else 0
    )
    return merged_contact


def merge_duplicates(
    contacts: list, validation_mode=AddressValidationMode.FULL
) -> list:
    """Optimized duplicate detection and merging"""
    if not contacts:
        return []

    # Create contact index and mapping of merged contacts
    contact_index = create_contact_index(contacts)
    merged_groups_map = {}  # Track which contacts belong to which merged group

    # Cache for comparison results
    comparison_cache = {}
    processed = set()
    merged_groups = []

    for contact in contacts:
        if id(contact) in processed:
            continue

        name = get_contact_name(contact).lower()
        first_chars = name[:3] if name else ""

        # Initialize new group with current contact
        current_group = [contact]
        merged_groups_map[id(contact)] = len(merged_groups)  # Map contact to its group

        # Find and process all matches for this contact
        if first_chars:
            # Get potential matches from index
            potential_matches = contact_index.get(first_chars, []).copy()
            # Add matches from similar blocks for typo handling
            for i in range(len(first_chars)):
                variant = first_chars[:i] + first_chars[i + 1 :]
                potential_matches.extend(contact_index.get(variant, []))

            # Check all potential matches
            for other in potential_matches:
                if id(other) != id(contact) and id(other) not in processed:
                    if is_duplicate(contact, other, comparison_cache):
                        current_group.append(other)  # Added missing code
                        merged_groups_map[id(other)] = len(merged_groups)
                        processed.add(id(other))

        if len(current_group) > 1:
            merged_groups.append(current_group)
        processed.add(id(contact))

    # Store the merged groups mapping for later use in validation
    # We'll store it as a global or class variable
    global _merged_groups_mapping
    _merged_groups_mapping = {"groups": merged_groups, "map": merged_groups_map}

    # Merge groups and remaining contacts
    result = []
    processed_in_groups = {id(c) for g in merged_groups for c in g}

    # Add merged groups
    for group in merged_groups:
        result.append(merge_contact_group(group, validation_mode))

    # Add non-duplicate contacts
    for contact in contacts:
        if id(contact) not in processed_in_groups:
            result.append(contact)

    return result


def is_name_gender_variant(name1, name2):
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


def is_likely_nickname(name1, name2):
    """Check if names might be nickname variants (e.g., Jonathan/Jona, Christopher/Chris)"""
    # Common nickname patterns
    if not name1 or not name2:
        return False

    # Get shorter and longer name
    short, long = sorted(
        [name1.lower(), name2.lower()], key=len
    )  # Fix: key.len -> key=len

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


def split_name_variants(name):
    """Split name into variants, handling comma-separated lists"""
    variants = []
    # First split by commas
    for part in name.split(","):
        part = part.strip()
        if part:
            # Then split each part by spaces
            variants.extend(p.strip() for p in part.split())
    return variants


def has_conflicting_names(name1_parts, name2_parts):
    """Check if any name parts are gender variants or too different"""
    for n1 in name1_parts:
        for n2 in name2_parts:
            if n1 != n2:  # Don't compare same names
                # If any pair of names are gender variants, names conflict
                if is_name_gender_variant(n1, n2):
                    return True
                # If any pair of names are too different, names conflict
                similarity = fuzz.ratio(n1, n2) / 100
                if similarity < 0.3:
                    return True
    return False


def is_duplicate(
    contact1,
    contact2,
    comparison_cache=None,
    name_ratio=85,
    nickname_ratio=90,
    org_ratio=95,
):
    """Strict prioritization requiring exact matches for similar names"""
    if not contact1 or not contact2:
        return False

    # Cache check
    cache_key = None
    if comparison_cache is not None:
        cache_key = tuple(sorted([id(contact1), id(contact2)]))
        if cache_key in comparison_cache:
            return comparison_cache[cache_key]

    # Calculate name similarity first
    name_similarity = (
        fuzz.ratio(
            get_contact_name(contact1).lower(), get_contact_name(contact2).lower()
        )
        / 100
    )

    # 2. Exact name match case - always merge regardless of phone numbers
    if name_similarity == 1.0:
        result = True

    # 3. Similar but not identical names - require exact phone match
    elif name_similarity >= 0.7:  # Names are similar
        phones1 = set(normalize_phone_list(contact1.get("Telephone", "")))
        phones2 = set(normalize_phone_list(contact2.get("Telephone", "")))
        result = bool(phones1 and phones2 and phones1.intersection(phones2))

    # 4. Different names - don't match unless very strong evidence
    else:
        result = False

    if comparison_cache is not None and cache_key is not None:
        comparison_cache[cache_key] = result
    return result


def is_duplicate_with_confidence(contact1, contact2, ratios=None):
    """Check if two contacts are duplicates and return match details with confidence score"""
    if ratios is None:
        ratios = {
            "name": 85,  # default threshold for name matching
            "nickname": 90,  # higher threshold for nicknames
            "org": 95,  # highest threshold for organization names
        }

    match = is_duplicate(
        contact1,
        contact2,
        name_ratio=ratios["name"],
        nickname_ratio=ratios["nickname"],
        org_ratio=ratios["org"],
    )

    return {
        "is_match": match,
        "confidence": calculate_match_confidence(contact1, contact2),
    }


def string_similarity(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def calculate_match_confidence(contact1: Dict[str, Any], contact2: Dict[str, Any]) -> float:
    """
    Calculate match confidence between two contacts using weighted scoring.
    Returns a float between 0.0 and 1.0
    """
    score = 0.0
    weights = {
        'email': 1.0,
        'full_name': 1.0,
        'first_last': 0.9,
        'last_name': 0.6,
        'first_name': 0.4,
        'organization': 0.3,
        'street': 0.3,
        'city': 0.2,
        'postal_code': 0.3,
        'country': 0.1
    }

    # Email comparison (exact match)
    if contact1.get('Email') and contact2.get('Email'):
        if contact1['Email'].lower() == contact2['Email'].lower():
            score += weights['email']

    # Name comparisons with fuzzy matching
    full_name1 = contact1.get('Full Name', '')
    full_name2 = contact2.get('Full Name', '')
    if full_name1 and full_name2:
        similarity = string_similarity(full_name1, full_name2)
        if similarity > 0.9:
            score += weights['full_name'] * similarity

    # First + Last name comparison
    first1 = contact1.get('FirstName', '')
    first2 = contact2.get('FirstName', '')
    last1 = contact1.get('LastName', '')
    last2 = contact2.get('LastName', '')
    
    if first1 and first2 and last1 and last2:
        first_sim = string_similarity(first1, first2)
        last_sim = string_similarity(last1, last2)
        if first_sim > 0.8 and last_sim > 0.8:
            score += weights['first_last'] * ((first_sim + last_sim) / 2)

    # Organization comparison
    org1 = contact1.get('Organization', '')
    org2 = contact2.get('Organization', '')
    if org1 and org2:
        org_sim = string_similarity(org1, org2)
        if org_sim > 0.8:
            score += weights['organization'] * org_sim

    # Address components comparison
    addr_components = [
        ('ADR_Street', 'street'),
        ('ADR_Locality', 'city'),
        ('ADR_PostalCode', 'postal_code'),
        ('ADR_Country', 'country')
    ]

    for addr_field, weight_key in addr_components:
        val1 = contact1.get(addr_field, '')
        val2 = contact2.get(addr_field, '')
        if val1 and val2:
            similarity = string_similarity(val1, val2)
            if similarity > 0.8:
                score += weights[weight_key] * similarity

    # Normalize score to be between 0 and 1
    return min(1.0, score)


def split_full_name(full_name):
    """Split a full name into first and last name components"""
    if not full_name:
        return "", ""

    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    elif len(parts) >= 2:
        return " ".join(parts[:-1]), parts[-1]
    return "", ""


def process_contact(contact, validation_mode=AddressValidationMode.FULL):
    # Get all name components
    full_name = contact.get("Full Name", contact.get("Name", ""))
    first_name = contact.get("FirstName", "")
    last_name = contact.get("LastName", "")
    structured_name = contact.get("Structured Name", "")

    # If no first/last name but have full name, split it
    if not (first_name or last_name) and full_name:
        first_name, last_name = split_full_name(full_name)

    # Extract base contact information, preserving all name variants
    processed = {
        "Name": contact.get("Name", ""),
        "Full Name": full_name,
        "FirstName": first_name,
        "LastName": last_name,
        "Structured Name": structured_name,
        "Organization": (
            ", ".join(contact.get("Organization", []))
            if isinstance(contact.get("Organization", []), list)
            else contact.get("Organization", "").strip("[]'\"")
        ),
        "Email": ", ".join(contact.get("Email", [])) if isinstance(contact.get("Email", []), list) else contact.get("Email", ""),
        "Phone": contact.get("Phone", []),
        "Birthday": contact.get("Birthday", ""),
    }

    # Before processing the address
    if "Address" in contact and contact["Address"]:
        # Log only address-related fields
        logging.debug(f"Processing address for contact: {contact.get('Name', 'Unknown')}")
        logging.debug(f"Original address: {contact['Address']}")

        address = contact["Address"]
        if isinstance(address, str):
            address = string_to_address_dict(address)

        # Normalize the address
        normalized_address = normalize_address(address, api_key, validation_mode)
        # ...existing code...

        # Optionally log the normalized address
        logging.debug(f"Normalized address: {normalized_address}")

        vcard = normalized_address.get("vcard", {})
        metadata = normalized_address.get("metadata", {})
        processed.update(
            {
                "ADR_POBox": vcard.get("po_box", ""),
                "ADR_Extended": vcard.get("extended", ""),
                "ADR_Street": vcard.get("street", ""),
                "ADR_Locality": vcard.get("locality", ""),
                "ADR_Region": vcard.get("region", ""),
                "ADR_PostalCode": vcard.get("postal_code", ""),
                "ADR_Country": vcard.get("country", ""),
                "ADR_Label": vcard.get("label", ""),
                "ADR_IsBusiness": metadata.get("isBusiness", False),
                "ADR_Complete": metadata.get("addressComplete", False),
                "ADR_Original": normalized_address.get("OriginalAddress", ""),
                "ADR_ValidationVerdict": normalized_address.get("_AddressValidation", {}).get(
                    "verdict", ""
                ),
            }
        )

    else:
        logging.debug("No address found in contact.")

    logging.debug(f"Processed contact: {processed}")
    return processed

# Reconstruct missing utility functions

def get_contact_name(contact):
    """Retrieve the contact's name."""
    return contact.get("Full Name") or contact.get("Name") or "Unknown"

def merge_names(name1, name2):
    """Merge two names into one, avoiding duplicates."""
    names = set(name.strip() for name in [name1, name2] if name)
    return ", ".join(names)

# ...existing code...
