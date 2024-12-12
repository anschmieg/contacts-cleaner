from typing import List, Dict
from .types import ValidationResults

class Contact:
    def __init__(self, first_name="", last_name="", emails=None, phones=None, addresses=None, organization="", data=None, validation_level=None):
        self.first_name = first_name
        self.last_name = last_name
        self.emails = emails if emails is not None else []
        self.phones = phones if phones is not None else []
        self.addresses = addresses if addresses is not None else []
        self.full_name = f"{first_name} {last_name}".strip()
        self.match_confidence = 0.0
        self.organization = organization  # Ensure organization is initialized
        
        # Initialize validation
        self.raw_data: Dict = data or {}
        self.validation_results: ValidationResults = {"errors": [], "warnings": []}

        if data:
            from ..utils.validation import validate_contact_data, log_validation_results
            # Validate data first
            self.validation_results = validate_contact_data(data, validation_level)
            log_validation_results(self.validation_results)
            
            # Process data if validation passed or only has warnings
            if not self.validation_results["errors"]:
                self._process_data(data)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Contact':
        """Create a Contact instance from a dictionary"""
        contact = cls()  # Create empty contact
        contact.full_name = data.get("Full Name", "")
        contact.first_name = data.get("FirstName", "")
        contact.last_name = data.get("LastName", "")
        contact.organization = data.get("Organization", "")
        contact.emails = data.get("Email", [])
        contact.phones = data.get("Telephone", [])
        contact.addresses = data.get("Address", [])
        contact.match_confidence = data.get("MatchConfidence", 0.0)
        return contact

    def _process_data(self, data: Dict) -> None:
        """Process contact data and populate fields"""
        from ..processors.name import NameProcessor
        name_processor = NameProcessor()
        
        # Process name using NameProcessor and ensure it's not empty
        self.full_name = name_processor.process_contact_name(data) or "Unknown Contact"
        
        # Split full name into first and last if not provided
        if not (self.first_name or self.last_name) and self.full_name != "Unknown Contact":
            self.first_name, self.last_name = name_processor.split_full_name(self.full_name)
        
        # Process other fields
        self.emails = data.get('Email', []) if isinstance(data.get('Email'), list) else [data.get('Email')] if data.get('Email') else []
        self.phones = data.get('Phone', []) if isinstance(data.get('Phone'), list) else [data.get('Phone')] if data.get('Phone') else []
        self.addresses = data.get('Address', []) if isinstance(data.get('Address'), list) else [data.get('Address')] if data.get('Address') else []
        self.organization = data.get('Organization')

    def to_dict(self) -> Dict:
        """Convert contact to dictionary with standardized field names"""
        # Ensure full name is populated
        if not self.full_name:
            if self.first_name or self.last_name:
                self.full_name = " ".join(filter(None, [self.first_name, self.last_name]))
            else:
                self.full_name = "Unknown Contact"
                
        return {
            'Full Name': self.full_name,
            'FirstName': self.first_name,
            'LastName': self.last_name,
            'Email': self.emails,
            'Telephone': self.phones,  # Changed from 'Phone' to 'Telephone'
            'Address': self.addresses,
            'Organization': self.organization,
            'MatchConfidence': self.match_confidence
        }

    @property
    def is_valid(self) -> bool:
        """Check if contact has any validation errors"""
        return len(self.validation_results["errors"]) == 0

    def get_validation_status(self) -> Dict[str, List[str]]:
        """Get validation results"""
        return self.validation_results
