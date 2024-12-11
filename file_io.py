###################
# File I/O Functions
###################

import csv
from config import VCARD_FIELD_MAPPING
import vobject

# from process_address import string_to_address_dict  # Add this import
import os  # Add this import
from process_name import get_contact_name  # Add this import
import logging
import re  # Add this import
from process_phone import normalize_phone_list  # Add this import
from process_name import merge_names, capitalize_name  # Add this import


def format_phone_number(phone):
    """Format phone numbers to have spaces between groups and remove non-standard separators."""
    if not phone:
        return phone
    # Replace non-digit characters with space, then collapse multiple spaces
    formatted = re.sub(r"[^\d+]", " ", phone)
    formatted = re.sub(r"\s+", " ", formatted).strip()
    return formatted


def deduplicate_keeping_order(items):
    """Remove duplicates while preserving order of first occurrence."""
    seen = set()
    return [x for x in items if not (x in seen or seen.add(x))]


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
                            # First unescape any escaped commas
                            family = str(field.value.family).replace("\\,", ",").strip()
                            given = str(field.value.given).replace("\\,", ",").strip()
                            additional = (
                                str(field.value.additional).replace("\\,", ",").strip()
                            )
                            prefix = str(field.value.prefix).replace("\\,", ",").strip()
                            suffix = str(field.value.suffix).replace("\\,", ",").strip()

                            # Split and normalize each part that contains commas
                            if "," in given:
                                given = merge_names(
                                    *[p.strip() for p in given.split(",")]
                                )
                            if "," in family:
                                family = merge_names(
                                    *[p.strip() for p in family.split(",")]
                                )

                            # Construct the full name in proper order
                            name_parts = []
                            if prefix:
                                name_parts.append(prefix)
                            if given:
                                name_parts.append(given)
                            if additional:
                                name_parts.append(additional)
                            if family:
                                name_parts.append(family)
                            if suffix:
                                name_parts.append(suffix)

                            contact[label] = " ".join(filter(None, name_parts))

                            # Also set FirstName and LastName
                            contact["FirstName"] = given
                            contact["LastName"] = family
                    elif key == "ADR":  # Special handling for Address objects
                        logging.debug(f"Processing Address field: {field}")
                        if isinstance(field, list):
                            addresses = []
                            for addr in field:
                                if hasattr(addr, "value"):
                                    logging.debug(
                                        f"Processing Address value: {addr.value}"
                                    )
                                    # Split multiline addresses properly
                                    street_parts = str(addr.value[2] or "").split("\n")
                                    street_address = " ".join(
                                        filter(None, street_parts)
                                    )

                                    addr_dict = {
                                        "vcard": {
                                            "po_box": str(addr.value[0] or "").strip(),
                                            "extended": str(
                                                addr.value[1] or ""
                                            ).strip(),
                                            "street": street_address.strip(),
                                            "locality": str(
                                                addr.value[3] or ""
                                            ).strip(),
                                            "region": str(addr.value[4] or "").strip(),
                                            "postal_code": str(
                                                addr.value[5] or ""
                                            ).strip(),
                                            "country": str(addr.value[6] or "").strip(),
                                        },
                                        "OriginalAddress": ", ".join(
                                            filter(None, map(str, addr.value))
                                        ),
                                        "_AddressValidation": {
                                            "verdict": "UNPROCESSED"
                                        },
                                        "metadata": {
                                            "isBusiness": False,
                                            "addressComplete": False,
                                        },
                                    }
                                    logging.debug(f"Address dict: {addr_dict}")
                                    # Create formatted label
                                    label_parts = [
                                        p
                                        for p in [
                                            addr_dict["vcard"]["street"],
                                            addr_dict["vcard"]["locality"],
                                            addr_dict["vcard"]["region"],
                                            addr_dict["vcard"]["postal_code"],
                                            addr_dict["vcard"]["country"],
                                        ]
                                        if p
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
            if "Address" in contact and contact["Address"]:
                logging.debug(f"Contact has address: {contact['Address']}")
            name_fields = [
                "Full Name",
                "Name",
                "FirstName",
                "LastName",
                "Structured Name",
            ]
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
            # After processing fields, deduplicate phone numbers and emails
            if "Telephone" in contact:
                phones = (
                    contact["Telephone"]
                    if isinstance(contact["Telephone"], list)
                    else [contact["Telephone"]]
                )
                phones = [p for p in phones if p]  # Remove empty values
                contact["Telephone"] = deduplicate_keeping_order(phones)

            if "Email" in contact:
                emails = (
                    contact["Email"]
                    if isinstance(contact["Email"], list)
                    else [contact["Email"]]
                )
                emails = [e.lower().strip() for e in emails if e]  # Normalize emails
                contact["Email"] = deduplicate_keeping_order(emails)
            contacts.append(contact)
            # Ensure FN and N fields are populated
            if not contact.get("Full Name"):
                contact["Full Name"] = contact.get("Name", "Unknown")
            if not contact.get("Name"):
                contact["Name"] = contact.get("Full Name", "Unknown")
            # Address handling - remove line breaks
            if "Address" in contact and contact["Address"]:
                addresses = contact["Address"]
                if isinstance(addresses, list):
                    for addr in addresses:
                        original = addr.get("OriginalAddress", "")
                        addr["OriginalAddress"] = original.replace("\n", " ").strip()
            # Normalize Telephone to ensure it's a flat list of strings
            telephone = contact.get("Telephone", [])
            if not isinstance(telephone, list):
                telephone = [telephone] if telephone else []
            contact["Telephone"] = normalize_phone_list(telephone)
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
                "Email": (
                    "; ".join(contact.get("Email", []))
                    if isinstance(contact.get("Email"), list)
                    else contact.get("Email", "")
                ),
                "Telephone": (
                    "; ".join(contact.get("Telephone", []))
                    if isinstance(contact.get("Telephone"), list)
                    else contact.get("Telephone", "")
                ),
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
                    vcard_addr = addr.get("vcard", {})

                    # Map address components to CSV fields
                    row.update(
                        {
                            "ADR_POBox": vcard_addr.get("po_box", "").strip(),
                            "ADR_Extended": vcard_addr.get("extended", "").strip(),
                            "ADR_Street": vcard_addr.get("street", "").strip(),
                            "ADR_Locality": vcard_addr.get("locality", "").strip(),
                            "ADR_Region": vcard_addr.get("region", "").strip(),
                            "ADR_PostalCode": vcard_addr.get("postal_code", "").strip(),
                            "ADR_Country": vcard_addr.get("country", "").strip(),
                            "ADR_Label": vcard_addr.get("label", "").strip(),
                        }
                    )

            logging.debug(f"Writing contact to CSV: {row}")
            writer.writerow(row)
    logging.info(f"Contacts saved to {output_file}")


def save_to_vcf(contacts, output_file):
    """Save contacts to VCF file according to vCard 4.0 spec (RFC 6350)"""
    logging.debug(f"Saving contacts to VCF: {output_file}")

    with open(output_file, "w", encoding="utf-8") as vcf_file:
        for contact in contacts:
            try:
                vcard = vobject.vCard()
                vcard.add("version").value = "4.0"
                vcard.add("prodid").value = "-//github.com/anschmieg/contacts-cleaner//EN"

                # Name handling - normalize before saving
                full_name = contact.get("Full Name", "").replace("\\,", ",")
                if "," in full_name:
                    # Handle cases where name contains commas
                    parts = [p.strip() for p in full_name.split(",")]
                    full_name = merge_names(*parts)

                # Set FN (formatted name)
                vcard.add("fn").value = (
                    capitalize_name(full_name) if full_name else "Unknown"
                )

                # Handle structured name (N property)
                vcard.add("n")

                # Get FirstName and LastName, either from contact or by splitting full name
                given = contact.get("FirstName", "").replace("\\,", ",")
                family = contact.get("LastName", "").replace("\\,", ",")

                # If we don't have FirstName/LastName, split full name
                if not (given and family) and full_name:
                    name_parts = full_name.split()
                    if len(name_parts) >= 2:
                        given = " ".join(name_parts[:-1])
                        family = name_parts[-1]
                    else:
                        given = full_name
                        family = ""

                # Clean up any duplicates in given/family names
                if "," in given:
                    given = merge_names(*[p.strip() for p in given.split(",")])
                if "," in family:
                    family = merge_names(*[p.strip() for p in family.split(",")])

                # Ensure no part of the family name appears in given name
                if family and given:
                    given_parts = given.split()
                    given_parts = [p for p in given_parts if p not in family.split()]
                    given = " ".join(given_parts)

                vcard.n.value = vobject.vcard.Name(
                    family=family, given=given, additional="", prefix="", suffix=""
                )

                # Email handling - preserve multiple emails
                emails = contact.get("Email", [])
                if not isinstance(emails, list):
                    emails = [emails] if emails else []
                emails = deduplicate_keeping_order([e for e in emails if e])
                for email in emails:
                    if email:
                        email_field = vcard.add("email")
                        email_field.value = email
                        email_field.params["TYPE"] = ["INTERNET"]

                # Phone handling - preserve multiple numbers
                phones = contact.get("Telephone", [])
                if not isinstance(phones, list):
                    phones = [phones] if phones else []
                phones = deduplicate_keeping_order([p for p in phones if p])
                formatted_phones = [format_phone_number(phone) for phone in phones]
                for phone in formatted_phones:
                    if phone:
                        tel = vcard.add("tel")
                        tel.value = phone
                        tel.params["TYPE"] = ["VOICE"]

                # Address handling - fixed to use vobject.vcard.Address
                if any(
                    contact.get(f"ADR_{field}")
                    for field in [
                        "POBox",
                        "Extended",
                        "Street",
                        "Locality",
                        "Region",
                        "PostalCode",
                        "Country",
                    ]
                ):
                    vcard_addr = vcard.add("adr")
                    vcard_addr.value = vobject.vcard.Address(
                        box=contact.get("ADR_POBox", ""),
                        extended=contact.get("ADR_Extended", ""),
                        street=contact.get("ADR_Street", ""),
                        city=contact.get("ADR_Locality", ""),
                        region=contact.get("ADR_Region", ""),
                        code=contact.get("ADR_PostalCode", ""),
                        country=contact.get("ADR_Country", ""),
                    )

                    # Add LABEL parameter if present
                    if contact.get("ADR_Label"):
                        label = contact["ADR_Label"].replace("\n", "\\n")
                        vcard_addr.params["LABEL"] = [label]

                    # Add TYPE parameter
                    vcard_addr.params["TYPE"] = (
                        ["WORK"] if contact.get("ADR_IsBusiness") else ["HOME"]
                    )

                    # Add PREF parameter if it's the preferred address
                    if contact.get("ADR_Complete"):
                        vcard_addr.params["PREF"] = ["1"]

                # Write the vCard
                vcf_file.write(vcard.serialize())

            except Exception as e:
                logging.error(
                    f"Error processing contact: {contact.get('Full Name', 'Unknown')}"
                )
                logging.error(f"Error details: {str(e)}")
                continue

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
