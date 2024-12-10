import re
import logging
from dotenv import load_dotenv
import os
import requests
from enum import Enum
import pycountry  # Add this import at the top

# Configure logging first, before any other operations
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to see all messages
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),  # Console handler
        logging.FileHandler(
            "address_validation.log", mode="w"
        ),  # File handler, 'w' mode overwrites the file each run
    ],
)

# Test logging is working
logging.info("=== Address Validation Script Started ===")
logging.debug("Debug logging is enabled")


class AddressValidationMode(Enum):
    NONE = 0  # No cleaning or validation
    CLEAN_ONLY = 1  # Only string cleaning
    FULL = 2  # Both cleaning and API validation


# Load environment variables from .env file
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")


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

    result = {
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
        "metadata": {
            "isBusiness": components.get("isBusiness", False),
            "addressComplete": components.get("addressComplete", False),
        },
        "_AddressValidation": {"verdict": components.get("verdict", "UNPROCESSED")},
    }

    # Preserve original address if provided
    if "OriginalAddress" in components:
        result["OriginalAddress"] = components["OriginalAddress"]

    return result


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
    logging.debug(
        f"normalize_address called with address: {address}, validation_mode: {validation_mode}"
    )

    if not address:
        logging.debug("No address provided, returning empty formatted address.")
        return format_vcard_address({})

    # Handle list of addresses
    if isinstance(address, list):
        return [normalize_address(addr, api_key, validation_mode) for addr in address]

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
        logging.debug("Validation mode is NONE, returning address as is.")
        return address

    if validation_mode == AddressValidationMode.CLEAN_ONLY:
        logging.debug("Validation mode is CLEAN_ONLY, cleaning address string.")
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
    logging.debug(f"Raw address for validation: {raw_address}")

    # Extract country for region code
    country = address["vcard"].get("country", "")

    validation_result = validate_address(
        raw_address, api_key, country=country if country else None
    )
    logging.debug(f"Validation result: {validation_result}")

    if not validation_result or not validation_result.get("addressComponents"):
        logging.debug("No validation matches found, using original address.")
        # Use the original address
        return address

    logging.debug("Validation successful, processing validation result.")
    components = {
        "street": "",
        "house_number": "",
        "city": "",
        "postal_code": "",
        "country": "",
        "isBusiness": validation_result.get("isBusiness", False),
        "addressComplete": validation_result.get("addressComplete", False),
        "verdict": validation_result.get("verdict", "UNKNOWN"),
    }

    # Process address components
    address_components = validation_result.get("addressComponents", [])
    for component in address_components:
        component_type = component.get("componentType", "")
        component_name = component.get("componentName", {}).get("text", "").strip()
        if not component_name:
            continue

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

    # Only combine street and house number if both exist
    if components["street"] and components["house_number"]:
        components["street"] = f"{components['street']} {components['house_number']}"

    verdict = validation_result.get("verdict", "UNKNOWN")

    logging.debug(f"Final components used for formatted address: {components}")
    result = format_vcard_address(components)
    result["_AddressValidation"] = {"verdict": verdict}
    result["OriginalAddress"] = original_address  # Add original address
    logging.debug(f"Normalized address result: {result}")
    return result


def clean_address_string(address):
    """Clean up an address string"""
    address = re.sub(r"\s+", " ", address).strip()
    address = re.sub(r"\n", ", ", address)
    address = re.sub(r",\s*,", ",", address)
    address = re.sub(r",\s*$", "", address)
    address = re.sub(r"[^\w\s,]", "", address)
    return address


def validate_address(address, api_key, country=None):
    if not address or not api_key:
        logging.error("Missing address or API key")
        return None

    # Determine region code based on country
    if country:
        try:
            region = pycountry.countries.lookup(country).alpha_2
        except LookupError:
            logging.warning(
                f"Unrecognized country '{country}', proceeding without region code"
            )
            region = None
    else:
        region = None  # Do not assume a default region

    if region:
        logging.debug(f"Using region code: {region}")
    else:
        logging.debug("No region code provided")

    logging.debug(f"Requesting address validation for: {address}")
    try:
        url = "https://addressvalidation.googleapis.com/v1:validateAddress"
        headers = {"Content-Type": "application/json"}
        request_body = {
            "address": {
                "addressLines": [address],
            }
        }
        if region:
            request_body["address"][
                "regionCode"
            ] = region  # Include only if region is specified

        print(f"DEBUG: API Request URL: {url}")
        print(f"DEBUG: Request body: {request_body}")

        response = requests.post(
            f"{url}?key={api_key}", headers=headers, json=request_body
        )

        print(f"DEBUG: API Response status: {response.status_code}")
        print(
            f"DEBUG: API Response content: {response.text[:500]}..."
        )  # First 500 chars

        if not response.ok:
            logging.error(
                f"API request failed: {response.status_code} - {response.text}"
            )
            return None

        validation_response = response.json()
        result = validation_response.get("result", {})

        print(f"DEBUG: Parsed response result: {result}")

        if not result or not result.get("address"):
            logging.error("Invalid API response structure")
            return None

        # Extract confirmation levels for each component
        confirmation_levels = {}
        for component in result.get("address", {}).get("addressComponents", []):
            comp_type = component.get("componentType")
            conf_level = component.get("confirmationLevel", "UNKNOWN")
            if comp_type:
                confirmation_levels[comp_type] = conf_level

        return {
            "addressComplete": result.get("verdict", {}).get("addressComplete", False),
            "addressComponents": result.get("address", {}).get("addressComponents", []),
            "isBusiness": result.get("metadata", {}).get("business", False),
            "verdict": result.get("verdict", {}).get(
                "validationGranularity", "UNKNOWN"
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
        logging.error(f"Address validation error: {str(e)}")
        return None


def parse_address_string(address_str):
    """Attempt to parse an address string into components."""
    components = {
        "street": "",
        "city": "",
        "postal_code": "",
        "country": "",
        "isBusiness": False,
        "addressComplete": False,
        "verdict": "PARSED",
    }

    # Clean the address string
    address_str = clean_address_string(address_str)

    # Split the address string by commas
    parts = [part.strip() for part in address_str.split(",") if part.strip()]

    # Assign parts to components based on their positions
    if parts:
        # Assume the last part is the country if it's a recognized country name
        components["country"] = parts.pop() if parts else ""
        # Try to find postal code and city
        if parts:
            last_part = parts.pop()
            if re.search(r"\d{5}", last_part):
                components["postal_code"] = last_part
                if parts:
                    components["city"] = parts.pop()
            else:
                components["city"] = last_part
        # Remaining parts are considered as street
        components["street"] = ", ".join(parts) if parts else ""

    return components


def clean_address(address):
    """Remove line breaks and extra spaces from address."""
    if not address:
        return address
    return ' '.join(address.split()).replace('\\n', ' ').strip()

# ...existing code...

# Example usage within parsing functions
# address = clean_address(raw_address)
