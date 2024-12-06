import re
import logging
from dotenv import load_dotenv
import os
import requests  # Add this import
from enum import Enum


class AddressValidationMode(Enum):
    NONE = 0  # No cleaning or validation
    CLEAN_ONLY = 1  # Only string cleaning
    FULL = 2  # Both cleaning and API validation


# Load environment variables from .env file
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")


# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

abbreviations = {
    r"\bst\b": "street",
    r"\bave\b": "avenue",
    r"\bblvd\b": "boulevard",
    r"\brd\b": "road",
    r"\bapt\b": "apartment",
    r"\bstr\b": "straße",
    r"\bpl\b": "platz",
    r"\bweg\b": "way",
    r"\bgasse\b": "alley",
    r"\bhof\b": "court",
}


def format_vcard_address(components):
    """Format address components according to vCard 3.0 standard"""
    # vCard 3.0 format: PO Box;Extended Address;Street;Locality;Region;Postal Code;Country
    return {
        'formatted': components.get('street', ''),  # For display/legacy support
        'vcard': [
            '',  # PO Box
            '',  # Extended Address
            components.get('street', ''),  # Street
            components.get('city', ''),    # Locality
            '',  # Region
            components.get('postal_code', ''),  # Postal Code
            components.get('country', '')  # Country
        ],
        'metadata': {
            'isBusiness': components.get('isBusiness', False),
            'addressComplete': components.get('addressComplete', False)
        }
    }


def normalize_address(address, api_key, validation_mode=AddressValidationMode.FULL):
    if not address:
        return format_vcard_address({})

    if validation_mode == AddressValidationMode.NONE:
        return format_vcard_address({"street": address})

    logging.debug(f"Original address: {address}")

    # Process string cleaning if mode is CLEAN_ONLY or FULL
    if validation_mode in [
        AddressValidationMode.CLEAN_ONLY,
        AddressValidationMode.FULL,
    ]:
        # Remove duplicate spaces
        address = re.sub(r"\s+", " ", address).strip()
        logging.debug(f"Address after removing duplicate spaces: {address}")

        # Standardize common abbreviations
        for abbr, full in abbreviations.items():
            address = re.sub(abbr, full, address)
        logging.debug(f"Address after standardizing abbreviations: {address}")

        # Simplify address format
        address = re.sub(r"\n", ", ", address)
        address = re.sub(r",\s*,", ",", address)
        address = re.sub(r",\s*$", "", address)
        address = re.sub(r"[^\w\s,]", "", address)  # Remove special characters
        logging.debug(f"Simplified address: {address}")

        # Remove empty parts
        address_parts = address.split(", ")
        address_parts = [part for part in address_parts if part]
        # Remove duplicate parts while preserving street numbers
        unique_parts = []
        seen_parts = set()
        for part in address_parts:
            if re.search(r"\d", part) or part not in seen_parts:
                unique_parts.append(part)
                seen_parts.add(part)
        address = ", ".join(unique_parts)
        logging.debug(
            f"Address after removing duplicates while preserving street numbers: {address}"
        )

    if validation_mode == AddressValidationMode.CLEAN_ONLY:
        return format_vcard_address({"street": address})

    # Proceed with API validation for FULL mode
    validation_result = validate_address(address, api_key)
    if not validation_result:
        return format_vcard_address({})

    components = {
        "street": "",
        "house_number": "",
        "city": "",
        "postal_code": "",
        "country": "",
        "isBusiness": validation_result.get("isBusiness", False),
        "addressComplete": validation_result.get("addressComplete", False),
    }

    address_components = validation_result.get("addressComponents", [])

    for component in address_components:
        component_type = component.get("componentType", "")
        component_name = component.get("componentName", {}).get("text", "")
        if component_type == "route":
            components["street"] = component_name
        elif component_type == "street_number":
            components["house_number"] = component_name
        elif component_type == "locality":
            components["city"] = component_name
        elif component_type == "postal_code":
            components["postal_code"] = component_name
        elif component_type == "country":
            components["country"] = component_name

    # Combine street and house number
    if components["house_number"]:
        components["street"] = f"{components['street']} {components['house_number']}"

    logging.debug(f"Normalized components: {components}")
    return format_vcard_address(components)


def validate_address(address, api_key):
    logging.debug(f"Requesting address validation for: {address}")
    try:
        url = "https://addressvalidation.googleapis.com/v1:validateAddress"
        headers = {
            "Content-Type": "application/json",
        }
        request_body = {"address": {"addressLines": [address], "regionCode": "DE"}}

        response = requests.post(
            f"{url}?key={api_key}", headers=headers, json=request_body
        )

        validation_response = response.json()
        logging.debug(f"Response: {validation_response}")
        if validation_response and validation_response.get("result", {}).get("address"):
            result = validation_response.get("result", {})
            return {
                "addressComplete": result.get("verdict", {}).get(
                    "addressComplete", False
                ),
                "addressComponents": result.get("address", {}).get(
                    "addressComponents", []
                ),
                "isBusiness": result.get("metadata", {}).get("business", False),
            }
    except Exception as e:
        logging.error(f"Address validation error: {e}")
    return None


# Example addresses
addresses = [
    "Bergstraße 51\nBerlin,  12169\nDeutschland, 51 Bergstraße\nBerlin",
    # "Eichhörnchensteig 3\nBerlin,  14195\nDeutschland, 3 Eichhörnchensteig\nBerlin",
    # ":::7 Willdenowstr.:::\nBerlin, ::: 13353\n:::",
    # "35 Föhrenstr Eggstätt 83125 ,",
    # "Schützallee 35 Berlin,  14169 Germany, 35 Schützallee Berlin",
    # "Albrecht-Dürer-Straße 10 Lampertheim,  68623 Deutschland, 10 Albrecht-Dürer-Straße Lampertheim",
]


# # Examples of different validation modes
# no_validation = [normalize_address(addr, api_key, AddressValidationMode.NONE) for addr in addresses]
# clean_only = [normalize_address(addr, api_key, AddressValidationMode.CLEAN_ONLY) for addr in addresses]
# full_validation = [normalize_address(addr, api_key, AddressValidationMode.FULL) for addr in addresses]

# # Print normalized addresses
# for address in full_validation:
#     print(address)
