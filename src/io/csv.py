import csv
from typing import List, Dict, Optional, Union
from ..core.contact import Contact


class CSVHandler:
    """Handles reading and writing contacts in CSV format"""

    # Common CSV field mappings
    DEFAULT_FIELD_MAP = {
        "Full Name": ["Full Name", "Name", "DisplayName"],
        "FirstName": ["First Name", "FirstName", "Given Name"],
        "LastName": ["Last Name", "LastName", "Family Name"],
        "Organization": ["Organization", "Company", "Business"],
        "Email": ["Email", "E-mail", "E-mail Address", "E-mail 1", "Primary Email"],
        "Telephone": ["Phone", "Telephone", "Primary Phone", "Mobile", "Cell"],
        "Address": ["Address", "Home Address", "Primary Address"],
        "MatchConfidence": ["Match Confidence", "Confidence"],
    }

    def __init__(self, field_map: Optional[Dict] = None):
        self.field_map = field_map or self.DEFAULT_FIELD_MAP

    def read_csv(self, filepath: str) -> List[Contact]:
        """Read contacts from CSV file"""
        contacts = []
        with open(filepath, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            headers = self._normalize_headers(reader.fieldnames)

            for row in reader:
                normalized_row = self._normalize_row(row, headers)
                contact = Contact.from_dict(normalized_row)
                contacts.append(contact)

        return contacts

    def write_csv(self, contacts: List[Union[Contact, Dict]], filepath: str) -> None:
        """Write contacts to CSV file

        Args:
            contacts: List of Contact objects or dictionaries
            filepath: Output file path
        """
        if not contacts:
            return

        fieldnames = list(self.DEFAULT_FIELD_MAP.keys())

        with open(filepath, "w", encoding="utf-8", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for contact in contacts:
                # Handle both Contact objects and dictionaries
                contact_data = (
                    contact.to_dict() if hasattr(contact, "to_dict") else contact
                )

                # Filter to include only known fields
                filtered_data = {
                    k: v for k, v in contact_data.items() if k in fieldnames
                }
                writer.writerow(filtered_data)

    def _normalize_headers(self, headers: List[str]) -> Dict[str, str]:
        """Map CSV headers to standardized field names"""
        header_map = {}
        for header in headers:
            normalized = None
            for std_field, variations in self.field_map.items():
                if header in variations or header == std_field:
                    normalized = std_field
                    break
            header_map[header] = normalized or header
        return header_map

    def _normalize_row(self, row: Dict, header_map: Dict) -> Dict:
        """Convert CSV row to standardized format"""
        normalized = {}
        for original_header, value in row.items():
            normalized_header = header_map[original_header]
            if value:  # Only include non-empty values
                normalized[normalized_header] = value.strip()
        return normalized

    def _split_merged_fields(self, value: str) -> List[str]:
        """Split merged fields (e.g., multiple emails) into list"""
        if not value:
            return []
        return [v.strip() for v in value.replace(";", ",").split(",") if v.strip()]
