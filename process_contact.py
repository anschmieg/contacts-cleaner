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
    string_to_address_dict  # Add this import
)
from process_name import get_contact_name, merge_names
from process_phone import (
    any_phones_match,
    are_phones_matching,
    normalize_phone_list,
)


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
    """Modified contact merging to combine names when phones match but names don't"""
    # print(f"\nMerging contact group with {len(duplicates)} contacts:")
    # for d in duplicates:
    #     name = d.get("Full Name", d.get("Structured Name", d.get("Name", "UNKNOWN")))
    #     phones = d.get("Telephone", "NO PHONE")
    #     print(f"  - {name} (Tel: {phones})")

    merged_contact = {}
    confidence_scores = []

    for duplicate in duplicates:
        for key, value in duplicate.items():
            if not value or str(value).strip() == "":
                continue

            value = str(value).strip()
            if key in merged_contact:
                if key == "Telephone":
                    # Enhanced phone number handling
                    existing_phones = normalize_phone_list(merged_contact[key])
                    new_phones = normalize_phone_list(value)

                    # Only add non-matching phones
                    for new_phone in new_phones:
                        if not any(
                            are_phones_matching(new_phone, existing)
                            for existing in existing_phones
                        ):
                            existing_phones.append(new_phone)

                    merged_contact[key] = ", ".join(existing_phones)
                elif key == "Address":
                    # Handle vCard address format
                    if key in merged_contact:
                        existing_addr = merged_contact[key]
                        new_addr = normalize_address(value, api_key, validation_mode)
                        if existing_addr.get("formatted") != new_addr.get("formatted"):
                            # Merge addresses if different
                            merged_addr = {
                                "formatted": f"{existing_addr.get('formatted')}, {new_addr.get('formatted')}".strip(
                                    ", "
                                ),
                                "vcard": [
                                    # Combine non-empty values or keep existing
                                    a or b
                                    for a, b in zip(
                                        existing_addr["vcard"], new_addr["vcard"]
                                    )
                                ],
                                "metadata": {
                                    "isBusiness": existing_addr["metadata"][
                                        "isBusiness"
                                    ]
                                    or new_addr["metadata"]["isBusiness"],
                                    "addressComplete": existing_addr["metadata"][
                                        "addressComplete"
                                    ]
                                    and new_addr["metadata"]["addressComplete"],
                                },
                            }
                            merged_contact[key] = merged_addr
                    else:
                        merged_contact[key] = normalize_address(
                            value, api_key, validation_mode
                        )
                elif key in ["Full Name", "Structured Name", "Name"]:
                    # Always merge names for phone-matched contacts
                    if key in merged_contact:
                        merged_contact[key] = merge_names(merged_contact[key], value)
                    else:
                        merged_contact[key] = value
                elif len(value) > len(merged_contact[key]):
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
                        merged_contact[key] = merge_names(merged_contact[key], value)
            else:
                if key == "Address":
                    merged_contact[key] = normalize_address(
                        value, api_key, validation_mode
                    )
                else:
                    merged_contact[key] = value

        # Collect confidence scores for the merged contact
        match_details = is_duplicate_with_confidence(duplicates[0], duplicate)
        confidence_scores.append(match_details["confidence"])

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
                        current_group.append(other)
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


def is_duplicate(
    contact1,
    contact2,
    comparison_cache=None,
    name_ratio=85,
    nickname_ratio=90,
    org_ratio=95,
):
    """Enhanced duplicate detection with configurable ratio thresholds"""
    if not contact1 or not contact2:
        return False

    # Cache check
    if comparison_cache is not None:
        cache_key = tuple(sorted([id(contact1), id(contact2)]))
        if cache_key in comparison_cache:
            return comparison_cache[cache_key]

    # 1. Phone number check
    if any_phones_match(contact1, contact2):
        if comparison_cache is not None:
            comparison_cache[cache_key] = True
        return True

    # 2. Organization-Name Crossover Check
    name1 = get_contact_name(contact1).lower()
    name2 = get_contact_name(contact2).lower()
    org1 = contact1.get("Organization", "").strip().lower()
    org2 = contact2.get("Organization", "").strip().lower()

    # Check if org from one contact appears in name of other
    if (org1 and org1 in name2) or (org2 and org2 in name1):
        name_match = fuzz.ratio(name1, name2)
        result = name_match >= name_ratio
        if comparison_cache is not None:
            comparison_cache[cache_key] = result
        return result

    # 3. Regular name matching with organization verification
    name_match = fuzz.ratio(name1, name2)
    if name_match >= name_ratio:
        # If both have orgs, they must match
        if org1 and org2:
            org_match = fuzz.ratio(org1, org2)
            result = org_match >= org_ratio
            if comparison_cache is not None:
                comparison_cache[cache_key] = result
            return result
        # If only one has org, no match
        if org1 or org2:
            if comparison_cache is not None:
                comparison_cache[cache_key] = False
            return False
        # Neither has org, rely on name match
        if comparison_cache is not None:
            comparison_cache[cache_key] = True
        return True

    if comparison_cache is not None:
        comparison_cache[cache_key] = False
    return False


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


def calculate_match_confidence(contact1, contact2):
    """Calculate confidence score for contact matching based on multiple criteria"""
    confidence_scores = []

    # 1. Name similarity (0-1)
    name1 = get_contact_name(contact1).lower()
    name2 = get_contact_name(contact2).lower()
    if name1 and name2:
        name_similarity = fuzz.ratio(name1, name2) / 100
        confidence_scores.append(name_similarity)

    # 2. Organization matching (0-1)
    org1 = contact1.get("Organization", "").strip().lower()
    org2 = contact2.get("Organization", "").strip().lower()
    if org1 and org2:
        org_similarity = fuzz.ratio(org1, org2) / 100
        confidence_scores.append(org_similarity)

    # 3. Phone number exact match (1.0)
    if any_phones_match(contact1, contact2):
        confidence_scores.append(1.0)

    # 4. Email exact match (1.0)
    email1 = contact1.get("Email", [])
    email2 = contact2.get("Email", [])
    # Convert to lists if strings
    if isinstance(email1, str):
        email1 = [email1]
    if isinstance(email2, str):
        email2 = [email2]
    # Compare emails
    if email1 and email2:
        # Check if any emails match between the two contacts
        if any(e1.strip().lower() == e2.strip().lower() 
              for e1 in email1 for e2 in email2):
            confidence_scores.append(1.0)

    # Calculate weighted average if we have any scores
    if confidence_scores:
        return prod(confidence_scores) ** (1 / len(confidence_scores)) if confidence_scores else 0.0

    return 0.0


def process_contact(contact, validation_mode=AddressValidationMode.FULL):
    """Process a single contact and standardize its format"""
    # Extract base contact information
    processed = {
        "Name": contact.get("Name", ""),
        "FirstName": contact.get("FirstName", ""),
        "LastName": contact.get("LastName", ""),
        "Organization": contact.get("Organization", ""),
        "Email": contact.get("Email", []),
        "Phone": contact.get("Phone", []),
        "Birthday": contact.get("Birthday", ""),
    }
    
    # Process address if present
    if "Address" in contact:
        address = contact["Address"]
        if isinstance(address, str):
            address = string_to_address_dict(address)
            
        vcard = address.get("vcard", {})
        processed.update({
            "ADR_POBox": vcard.get("po_box", ""),
            "ADR_Extended": vcard.get("extended", ""),
            "ADR_Street": vcard.get("street", ""),
            "ADR_Locality": vcard.get("locality", ""),
            "ADR_Region": vcard.get("region", ""),
            "ADR_PostalCode": vcard.get("postal_code", ""),
            "ADR_Country": vcard.get("country", ""),
            "ADR_Label": vcard.get("label", ""),
            "ADR_IsBusiness": address.get("isBusiness", False),
            "ADR_Complete": address.get("addressComplete", False),
            "ADR_Original": address.get("OriginalAddress", ""),
            "ADR_ValidationVerdict": address.get("_AddressValidation", {}).get("verdict", "")
        })
    
    return processed
