###################
# File I/O Functions
###################

import csv
from config import VCARD_FIELD_MAPPING
import vobject
from process_address import string_to_address_dict  # Add this import
import os  # Add this import


def parse_vcard(vcf_file):
    contacts = []
    with open(vcf_file, "r", encoding="utf-8") as file:
        vcard_data = file.read()
        for vcard in vobject.readComponents(vcard_data):
            contact = {}
            for key, label in VCARD_FIELD_MAPPING.items():
                if hasattr(vcard, key.lower()):
                    field = getattr(vcard, key.lower())
                    if key == "N":  # Special handling for Name objects
                        if hasattr(field, "value"):
                            name_parts = []
                            # Extract available name components
                            if field.value.family:
                                name_parts.append(str(field.value.family))
                            if field.value.given:
                                name_parts.append(str(field.value.given))
                            if field.value.additional:
                                name_parts.append(str(field.value.additional))
                            if field.value.prefix:
                                name_parts.append(str(field.value.prefix))
                            if field.value.suffix:
                                name_parts.append(str(field.value.suffix))
                            contact[label] = " ".join(filter(None, name_parts))
                    elif isinstance(field, list):
                        contact[label] = ", ".join(
                            [
                                str(f.value) if hasattr(f, "value") else str(f)
                                for f in field
                            ]
                        )
                    else:
                        contact[label] = (
                            str(field.value) if hasattr(field, "value") else str(field)
                        )
            contacts.append(contact)
    print(f"--> {len(contacts)} contacts from {vcf_file}")
    return contacts


def save_to_csv(contacts, output_file):
    """Save contacts to CSV file with proper vCard 4.0 address handling"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    fieldnames = [
        'Full Name', 'Name', 'FirstName', 'LastName',
        'Organization', 'Email', 'Telephone', 'Birthday',
        # vCard 4.0 address components
        'ADR_POBox',          # Post Office Box
        'ADR_Extended',       # Extended Address (apt, suite, etc.)
        'ADR_Street',         # Street Address
        'ADR_Locality',       # City
        'ADR_Region',         # State/Province
        'ADR_PostalCode',     # ZIP/Postal Code
        'ADR_Country',        # Country
        'ADR_Label',          # Formatted address string
        'Match Confidence'
    ]

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for contact in contacts:
            # Extract address components if present
            address_components = {}
            if 'Address' in contact:
                addr = contact['Address']
                if isinstance(addr, dict):
                    vcard = addr.get('vcard', {})
                    address_components = {
                        'ADR_POBox': vcard.get('po_box', ''),
                        'ADR_Extended': vcard.get('extended', ''),
                        'ADR_Street': vcard.get('street', ''),
                        'ADR_Locality': vcard.get('locality', ''),
                        'ADR_Region': vcard.get('region', ''),
                        'ADR_PostalCode': vcard.get('postal_code', ''),
                        'ADR_Country': vcard.get('country', ''),
                        'ADR_Label': vcard.get('label', '')
                    }

            # Combine with other contact fields
            row = {
                'Full Name': contact.get('Full Name', ''),
                'Name': contact.get('Name', ''),
                'FirstName': contact.get('FirstName', ''),
                'LastName': contact.get('LastName', ''),
                'Organization': contact.get('Organization', ''),
                'Email': contact.get('Email', ''),
                'Telephone': contact.get('Telephone', ''),
                'Birthday': contact.get('Birthday', ''),
                'Match Confidence': contact.get('Match Confidence', ''),
                **address_components  # Merge in address components
            }
            
            writer.writerow(row)


def save_address_validation_report(contacts, output_file):
    """Save address validation results to a CSV file."""
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Contact Name",
                "Original Address",
                "Processed Address",
                "Validation Status",
                "Unconfirmed Components",
                "Missing Components",
                "Component Confirmation Levels",
            ]
        )

        for contact in contacts:
            if "Address" not in contact:
                continue

            name = contact.get("FullName", "Unknown")
            address = contact["Address"]
            if isinstance(address, str):
                address = string_to_address_dict(address)

            processed = address.get("vcard", {})
            processed_addr = ", ".join(
                filter(
                    None,
                    [
                        processed.get("street", ""),
                        processed.get("locality", ""),
                        processed.get("postal_code", ""),
                        processed.get("country", ""),
                    ],
                )
            )

            validation = address.get("_AddressValidation", {})
            verdict = validation.get("verdict", "UNPROCESSED")

            status = "Invalid"
            if verdict == "CONFIRMED":
                status = "Valid"
            elif verdict not in ["failed", "UNCONFIRMED", "UNPROCESSED"]:
                status = "Ambiguous"

            # Extract confirmation levels and components
            confirmation_levels = validation.get("confirmationLevels", {})
            unconfirmed = ", ".join(validation.get("unconfirmedComponents", []))
            missing = ", ".join(validation.get("missingComponents", []))

            # Consolidate confirmation levels
            confirmation_counts = {}
            for level in confirmation_levels.values():
                # Clean up level names
                level = level.replace("UNCONFIRMED_BUT_", "")
                level = level.replace("UNCONFIRMED_AND_", "")
                if level != "UNKNOWN":
                    confirmation_counts[level] = confirmation_counts.get(level, 0) + 1

            # Format the confirmation summary
            confirmation_summary = (
                ", ".join(
                    f"{count} {level}"
                    for level, count in sorted(confirmation_counts.items())
                )
                or "UNKNOWN"
            )

            writer.writerow(
                [
                    name,
                    address.get("OriginalAddress", processed_addr),
                    processed_addr,
                    status,
                    unconfirmed,
                    missing,
                    confirmation_summary,
                ]
            )
