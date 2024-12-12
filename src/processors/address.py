from typing import List, Dict, Optional
import re
import logging
import os
import requests
import pycountry
from enum import Enum
from ..core.contact import Contact

class AddressValidationMode(Enum):
    NONE = 0  # No cleaning or validation
    CLEAN_ONLY = 1  # Only string cleaning
    FULL = 2  # Both cleaning and API validation

def string_to_address_dict(address_str: str) -> Dict:
    """Convert a string address into the standard address dictionary format"""
    return {
        "vcard": {
            "street": address_str,
            "locality": "",
            "postal_code": "",
            "country": "",
            "label": address_str,
        },
        "OriginalAddress": address_str,
        "_AddressValidation": {"verdict": "UNPROCESSED"},
        "isBusiness": False,
        "addressComplete": False,
    }

class AddressProcessor:
    def __init__(self, api_key: str = None, validation_mode: AddressValidationMode = AddressValidationMode.FULL):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.validation_mode = validation_mode
        self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("address_validation.log", mode="w"),
            ],
        )

    def merge_addresses(self, addresses: List[Dict]) -> List[Dict]:
        """Merge multiple addresses, removing duplicates and validating."""
        if not addresses:
            return []

        # Clean and normalize addresses
        normalized_addresses = [
            self.normalize_address(addr, validation_mode=AddressValidationMode.FULL)
            for addr in addresses
        ]

        # Remove duplicates based on normalized form
        unique_addresses = []
        seen_labels = set()
        
        for addr in normalized_addresses:
            label = addr["vcard"]["label"]
            if label not in seen_labels:
                seen_labels.add(label)
                unique_addresses.append(addr)

        return unique_addresses

    def normalize_address(self, address: Dict, validation_mode: AddressValidationMode = None) -> Dict:
        """Normalize an address dictionary using the validation mode."""
        # Use instance validation_mode if none provided
        validation_mode = validation_mode or self.validation_mode
        
        if not address:
            return self._format_vcard_address({})

        # Extract address string for validation
        address_str = address.get("vcard", {}).get("label", "")
        if not address_str:
            address_str = ", ".join(filter(None, [
                address.get("vcard", {}).get("street", ""),
                address.get("vcard", {}).get("locality", ""),
                address.get("vcard", {}).get("postal_code", ""),
                address.get("vcard", {}).get("country", "")
            ]))

        # Clean the address string
        if validation_mode in [AddressValidationMode.CLEAN_ONLY, AddressValidationMode.FULL]:
            address_str = self._clean_address_string(address_str)

        if validation_mode == AddressValidationMode.FULL and self.api_key:
            # Validate with API
            validation_result = self._validate_address(address_str)
            if validation_result:
                return self._format_validated_address(validation_result, address_str)

        # Return cleaned but unvalidated address
        return self._format_vcard_address({
            "street": address.get("vcard", {}).get("street", ""),
            "city": address.get("vcard", {}).get("locality", ""),
            "postal_code": address.get("vcard", {}).get("postal_code", ""),
            "country": address.get("vcard", {}).get("country", ""),
            "OriginalAddress": address_str,
            "verdict": "UNPROCESSED"
        })

    def _clean_address_string(self, address: str) -> str:
        """Clean up an address string"""
        if not address:
            return ""
        address = re.sub(r"\s+", " ", address).strip()
        address = re.sub(r"\n", ", ", address)
        address = re.sub(r",\s*,", ",", address)
        address = re.sub(r",\s*$", "", address)
        return address

    def _validate_address(self, address: str) -> Optional[Dict]:
        """Validate address using Google's Address Validation API"""
        if not address or not self.api_key:
            return None

        # Determine region code based on country pattern
        country_match = re.search(r',\s*([^,]+)$', address)
        country = country_match.group(1) if country_match else None
        
        try:
            if country:
                region = pycountry.countries.lookup(country).alpha_2
            else:
                region = None
        except LookupError:
            region = None

        try:
            url = "https://addressvalidation.googleapis.com/v1:validateAddress"
            headers = {"Content-Type": "application/json"}
            request_body = {
                "address": {
                    "addressLines": [address],
                }
            }
            if region:
                request_body["address"]["regionCode"] = region

            response = requests.post(
                f"{url}?key={self.api_key}", 
                headers=headers, 
                json=request_body
            )

            if not response.ok:
                logging.error(f"API request failed: {response.status_code} - {response.text}")
                return None

            validation_response = response.json()
            result = validation_response.get("result", {})

            if not result or not result.get("address"):
                return None

            return {
                "addressComplete": result.get("verdict", {}).get("addressComplete", False),
                "addressComponents": result.get("address", {}).get("addressComponents", []),
                "isBusiness": result.get("metadata", {}).get("business", False),
                "verdict": result.get("verdict", {}).get("validationGranularity", "UNKNOWN"),
            }

        except Exception as e:
            logging.error(f"Address validation error: {str(e)}")
            return None

    def _format_vcard_address(self, components: Dict) -> Dict:
        """Format address components according to vCard 3.0 standard"""
        # Create formatted label from components
        label_parts = [
            components.get("street", ""),
            components.get("city", ""),
            components.get("region", ""),
            components.get("postal_code", ""),
            components.get("country", "")
        ]
        formatted_label = ", ".join(filter(None, label_parts))

        return {
            "vcard": {
                "po_box": components.get("po_box", ""),
                "extended": components.get("extended", ""),
                "street": components.get("street", ""),
                "locality": components.get("city", ""),
                "region": components.get("region", ""),
                "postal_code": components.get("postal_code", ""),
                "country": components.get("country", ""),
                "label": formatted_label,
            },
            "metadata": {
                "isBusiness": components.get("isBusiness", False),
                "addressComplete": components.get("addressComplete", False),
            },
            "_AddressValidation": {"verdict": components.get("verdict", "UNPROCESSED")},
            "OriginalAddress": components.get("OriginalAddress", formatted_label),
        }

    def _format_validated_address(self, validation_result: Dict, original_address: str) -> Dict:
        """Format validated address result"""
        components = {
            "street": "",
            "city": "",
            "postal_code": "",
            "country": "",
            "isBusiness": validation_result.get("isBusiness", False),
            "addressComplete": validation_result.get("addressComplete", False),
            "verdict": validation_result.get("verdict", "UNKNOWN"),
            "OriginalAddress": original_address,
        }

        for component in validation_result.get("addressComponents", []):
            comp_type = component.get("componentType", "")
            comp_name = component.get("componentName", {}).get("text", "").strip()
            
            if comp_type == "route":
                components["street"] = comp_name
            elif comp_type == "street_number":
                components["street"] = f"{comp_name} {components['street']}"
            elif comp_type == "locality":
                components["city"] = comp_name
            elif comp_type == "postal_code":
                components["postal_code"] = comp_name
            elif comp_type == "country":
                components["country"] = comp_name

        return self._format_vcard_address(components)
