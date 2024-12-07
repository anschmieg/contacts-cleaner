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
    level=logging.ERROR,  # Changed from DEBUG to ERROR
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def format_vcard_address(components):
    """Format address components according to vCard 3.0 standard"""
    # Create formatted label from components
    label_parts = []
    if components.get("street"):
        label_parts.append(components["street"])
    if components.get("city"):
        label_parts.append(components["city"])
    if components.get("region"):
        label_parts.append(components["region"])
    if components.get("postal_code"):
        label_parts.append(components["postal_code"])
    if components.get("country"):
        label_parts.append(components["country"])

    formatted_label = ", ".join(filter(None, label_parts))

    return {
        "vcard": {
            "po_box": components.get("po_box", ""),  # Post Office Box
            "extended": components.get("extended", ""),  # Extended Address
            "street": components.get("street", ""),  # Street
            "locality": components.get("city", ""),  # Locality
            "region": components.get("region", ""),  # Region
            "postal_code": components.get("postal_code", ""),  # Postal Code
            "country": components.get("country", ""),  # Country
            "label": formatted_label,  # Add formatted label
        },
        "isBusiness": components.get("isBusiness", False),
        "addressComplete": components.get("addressComplete", False),
    }


def string_to_address_dict(address_str):
    """Convert a string address into the standard address dictionary format"""
    return {
        "vcard": {
            "street": address_str,
            "locality": "",
            "postal_code": "",
            "country": "",
            "label": address_str,  # Add label field
        },
        "OriginalAddress": address_str,
        "_AddressValidation": {"verdict": "UNPROCESSED"},
        "isBusiness": False,
        "addressComplete": False,
    }


def normalize_address(address, api_key, validation_mode=AddressValidationMode.FULL):
    if not address:
        return format_vcard_address({})

    # Convert string addresses to dictionary format
    if isinstance(address, str):
        original_address = address
        # Clean the string address if needed
        if validation_mode in [
            AddressValidationMode.CLEAN_ONLY,
            AddressValidationMode.FULL,
        ]:
            address = clean_address_string(address)
        address = string_to_address_dict(address)
    else:
        original_address = address.get(
            "OriginalAddress", address.get("vcard", {}).get("street", "")
        )

    if validation_mode == AddressValidationMode.NONE:
        return address

    if validation_mode == AddressValidationMode.CLEAN_ONLY:
        # For CLEAN_ONLY, just ensure the address is in dictionary format
        return address

    # Proceed with API validation for FULL mode
    raw_address = ", ".join(
        filter(
            None,
            [
                address["vcard"].get("street", ""),
                address["vcard"].get("locality", ""),
                address["vcard"].get("postal_code", ""),
                address["vcard"].get("country", ""),
            ],
        )
    )

    validation_result = validate_address(raw_address, api_key)
    if not validation_result:
        components = {}
        verdict = "failed"
    else:
        components = {
            "street": "",
            "house_number": "",
            "city": "",
            "postal_code": "",
            "country": "",
            "isBusiness": validation_result.get("isBusiness", False),
            "addressComplete": validation_result.get("addressComplete", False),
            "verdict": validation_result.get(
                "verdict", "unknown"
            ),  # Add verdict information
        }
        verdict = validation_result.get("verdict", "unknown")

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
    result = format_vcard_address(components)
    result["_AddressValidation"] = {"verdict": verdict}
    result["OriginalAddress"] = original_address  # Add original address
    return result


def clean_address_string(address):
    """Clean up an address string"""
    address = re.sub(r"\s+", " ", address).strip()
    address = re.sub(r"\n", ", ", address)
    address = re.sub(r",\s*,", ",", address)
    address = re.sub(r",\s*$", "", address)
    address = re.sub(r"[^\w\s,]", "", address)
    return address


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

            # Extract confirmation levels for each component
            confirmation_levels = {}
            for component in result.get("address", {}).get("addressComponents", []):
                comp_type = component.get("componentType")
                conf_level = component.get("confirmationLevel", "UNKNOWN")
                confirmation_levels[comp_type] = conf_level

            return {
                "addressComplete": result.get("verdict", {}).get(
                    "addressComplete", False
                ),
                "addressComponents": result.get("address", {}).get(
                    "addressComponents", []
                ),
                "isBusiness": result.get("metadata", {}).get("business", False),
                "verdict": result.get("verdict", {}).get(
                    "validationGranularity", "unknown"
                ),
                "confirmationLevels": confirmation_levels,
                "unconfirmedComponents": result.get("address", {}).get(
                    "unconfirmedComponentTypes", []
                ),
                "missingComponents": result.get("address", {}).get(
                    "missingComponentTypes", []
                ),
            }
    except Exception as e:
        logging.error(f"Address validation error: {e}")
    return None
