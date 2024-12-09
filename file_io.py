###################
# File I/O Functions
###################

import csv
from config import VCARD_FIELD_MAPPING
import vobject
from process_address import string_to_address_dict  # Add this import
import os  # Add this import
from process_name import get_contact_name  # Add this import
import logging


def parse_vcard(vcf_file):
    logging.debug(f"Parsing VCF file: {vcf_file}")
    contacts = []
    with open(vcf_file, "r", encoding="utf-8") as file:
        vcard_data = file.read()
        for vcard in vobject.readComponents(vcard_data):
            contact = {}
            for key, label in VCARD_FIELD_MAPPING.items():
                if hasattr(vcard, key.lower()):
                    field = getattr(vcard, key.lower())
                    logging.debug(f"Processing field: {key}")
                    if key == "N":  # Special handling for Name objects
                        logging.debug(f"Processing Name field: {field}")
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
                    elif key == "ADR":  # Special handling for Address objects
                        logging.debug(f"Processing Address field: {field}")
                        if isinstance(field, list):
                            addresses = []
                            for addr in field:
                                if hasattr(addr, "value"):
                                    logging.debug(f"Processing Address value: {addr.value}")
                                    # Split multiline addresses properly
                                    street_parts = str(addr.value[2] or "").split('\n')
                                    street_address = ' '.join(filter(None, street_parts))
                                    
                                    addr_dict = {
                                        "vcard": {
                                            "po_box": str(addr.value[0] or "").strip(),
                                            "extended": str(addr.value[1] or "").strip(),
                                            "street": street_address.strip(),
                                            "locality": str(addr.value[3] or "").strip(),
                                            "region": str(addr.value[4] or "").strip(),
                                            "postal_code": str(addr.value[5] or "").strip(),
                                            "country": str(addr.value[6] or "").strip(),
                                        },
                                        "OriginalAddress": ", ".join(filter(None, map(str, addr.value))),
                                        "_AddressValidation": {"verdict": "UNPROCESSED"},
                                        "metadata": {"isBusiness": False, "addressComplete": False}
                                    }
                                    logging.debug(f"Address dict: {addr_dict}")
                                    # Create formatted label
                                    label_parts = [
                                        p for p in [
                                            addr_dict["vcard"]["street"],
                                            addr_dict["vcard"]["locality"],
                                            addr_dict["vcard"]["region"],
                                            addr_dict["vcard"]["postal_code"],
                                            addr_dict["vcard"]["country"]
                                        ] if p
                                    ]
                                    addr_dict["vcard"]["label"] = ", ".join(label_parts)
                                    addresses.append(addr_dict)
                            contact[label] = addresses if addresses else None
                            logging.debug(f"Processed Address field: {contact[label]}")
                        else:
                            # Handle single address
                            if hasattr(field, "value"):
                                contact[label] = str(field.value)
                            else:
                                contact[label] = str(field)
                    else:
                        contact[label] = (
                            str(field.value) if hasattr(field, "value") else str(field)
                        )
            # After processing all fields
            if 'Address' in contact and contact['Address']:
                logging.debug(f"Contact has address: {contact['Address']}")
            name_fields = ["Full Name", "Name", "FirstName", "LastName", "Structured Name"]
            if not any(contact.get(field) for field in name_fields):
                logging.debug("No name fields populated, constructing a pseudo-name.")
                # Construct pseudo-name from available fields
                pseudo_name = None
                if contact.get("Email"):
                    email = contact["Email"]
                    if isinstance(email, list):
                        email = email[0]
                    pseudo_name = email.split("@")[0].replace(".", " ").title()
                elif contact.get("Telephone"):
                    phone = contact["Telephone"]
                    if isinstance(phone, list):
                        phone = phone[0]
                    pseudo_name = phone
                elif contact.get("Organization"):
                    pseudo_name = contact["Organization"]
                else:
                    pseudo_name = "Unknown"
                # Set the pseudo-name in name fields
                contact["Full Name"] = pseudo_name
                contact["Name"] = pseudo_name
                logging.debug(f"Constructed pseudo-name: {pseudo_name}")
            contacts.append(contact)
    logging.info(f"Total contacts parsed from {vcf_file}: {len(contacts)}")
    return contacts


def save_to_csv(contacts, output_file):
    logging.debug(f"Saving contacts to CSV: {output_file}")
    """Save contacts to CSV file with proper vCard 4.0 address handling"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    fieldnames = [
        "Full Name",
        "Name",
        "FirstName",
        "LastName",
        "Organization",
        "Email",
        "Telephone",
        "Birthday",
        # vCard 4.0 address components
        "ADR_POBox",  # Post Office Box
        "ADR_Extended",  # Extended Address (apt, suite, etc.)
        "ADR_Street",  # Street Address
        "ADR_Locality",  # City
        "ADR_Region",  # State/Province
        "ADR_PostalCode",  # ZIP/Postal Code
        "ADR_Country",  # Country
        "ADR_Label",  # Formatted address string
        "Match Confidence",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for contact in contacts:
            # Create row directly from contact fields, including ADR_ prefixed fields
            row = {
                "Full Name": contact.get("Full Name", ""),
                "Name": contact.get("Name", ""),
                "FirstName": contact.get("FirstName", ""),
                "LastName": contact.get("LastName", ""),
                "Organization": contact.get("Organization", ""),
                "Email": contact.get("Email", ""),
                "Telephone": contact.get("Telephone", ""),
                "Birthday": contact.get("Birthday", ""),
                "Match Confidence": contact.get("Match Confidence", ""),
                # Add address fields directly from contact
                "ADR_POBox": contact.get("ADR_POBox", ""),
                "ADR_Extended": contact.get("ADR_Extended", ""),
                "ADR_Street": contact.get("ADR_Street", ""),
                "ADR_Locality": contact.get("ADR_Locality", ""),
                "ADR_Region": contact.get("ADR_Region", ""),
                "ADR_PostalCode": contact.get("ADR_PostalCode", ""),
                "ADR_Country": contact.get("ADR_Country", ""),
                "ADR_Label": contact.get("ADR_Label", ""),
            }

            # Handle address fields
            addresses = contact.get("Address", [])
            if addresses:
                addr = addresses[0] if isinstance(addresses, list) else addresses
                if isinstance(addr, dict):  # Ensure we have a dictionary
                    vcard_addr = addr.get('vcard', {})
                    
                    # Map address components to CSV fields
                    row.update({
                        'ADR_POBox': vcard_addr.get('po_box', '').strip(),
                        'ADR_Extended': vcard_addr.get('extended', '').strip(),
                        'ADR_Street': vcard_addr.get('street', '').strip(),
                        'ADR_Locality': vcard_addr.get('locality', '').strip(),
                        'ADR_Region': vcard_addr.get('region', '').strip(),
                        'ADR_PostalCode': vcard_addr.get('postal_code', '').strip(),
                        'ADR_Country': vcard_addr.get('country', '').strip(),
                        'ADR_Label': vcard_addr.get('label', '').strip()
                    })

            logging.debug(f"Writing contact to CSV: {row}")
            writer.writerow(row)
    logging.info(f"Contacts saved to {output_file}")


def save_address_validation_report(contacts, output_file):
    """Save address validation results to CSV"""
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(
            [
                "Contact Name",
                "Original Address",
                "Validated Address",
                "Verdict",
                "Is Business",
                "Is Complete",
            ]
        )

        for contact in contacts:
            name = get_contact_name(contact)
            addresses = contact.get("Address", [])

            # Handle both list and single address formats
            if not isinstance(addresses, list):
                addresses = [addresses]

            # Write a row for each address
            for address in addresses:
                if not address:
                    continue

                processed = address.get("vcard", {})
                validation = address.get("_AddressValidation", {})
                metadata = address.get("metadata", {})

                writer.writerow(
                    [
                        name,
                        address.get("OriginalAddress", ""),
                        processed.get("label", ""),
                        validation.get("verdict", "UNKNOWN"),
                        metadata.get("isBusiness", False),
                        metadata.get("addressComplete", False),
                    ]
                )
