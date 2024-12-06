###################
# File I/O Functions
###################

import csv
from config import VCARD_FIELD_MAPPING
import vobject


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


def save_to_csv(contacts, output_csv):
    """
    Save the list of contacts to a CSV file.
    """
    if not contacts:
        print("No contacts to save.")
        return

    # Get all unique field names
    fieldnames = set()
    for contact in contacts:
        fieldnames.update(contact.keys())

    # Write to CSV
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=sorted(fieldnames))
        writer.writeheader()
        writer.writerows(contacts)
    print(f"Saved {len(contacts)} contacts to {output_csv}")
