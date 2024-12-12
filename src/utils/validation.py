from typing import Dict, List, Any, Optional
import re
from enum import Enum
import logging


class ValidationLevel(Enum):
    NONE = 0
    BASIC = 1
    STRICT = 2


def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return False

    # Basic email regex pattern
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Validate phone number format"""
    if not phone:
        return False

    # Remove all non-digit characters except + for international prefix
    cleaned = re.sub(r"[^\d+]", "", phone)

    # Check for minimum length and valid characters
    return len(cleaned) >= 7 and bool(re.match(r"^\+?\d+$", cleaned))


def validate_required_fields(
    data: Dict[str, Any],
    required_fields: List[str],
    level: ValidationLevel = ValidationLevel.BASIC,
) -> List[str]:
    """Validate presence and format of required fields"""
    errors = []

    if level == ValidationLevel.NONE:
        return errors

    for field in required_fields:
        if field not in data or not data[field]:
            errors.append(f"Missing required field: {field}")
            continue

        if level == ValidationLevel.STRICT:
            # Additional format validation for specific fields
            value = data[field]
            if field == "Email" and not validate_email(value):
                errors.append(f"Invalid email format: {value}")
            elif field == "Telephone" and not validate_phone(value):
                errors.append(f"Invalid phone format: {value}")

    return errors


def validate_contact_data(data: Dict[str, Any], level: ValidationLevel = ValidationLevel.BASIC) -> Dict[str, List[str]]:
    """Validate contact data structure and content"""
    validation_results = {"errors": [], "warnings": []}

    if not data:
        validation_results["errors"].append("Empty contact data")
        return validation_results

    # Required fields based on validation level
    required = {
        ValidationLevel.NONE: [],
        ValidationLevel.BASIC: ["Full Name"],
        ValidationLevel.STRICT: ["Full Name", "Email", "Telephone"],
    }[level]

    # Check required fields
    validation_results["errors"].extend(
        validate_required_fields(data, required, level)
    )

    # Only proceed with additional validations if basic requirements are met
    if not validation_results["errors"]:
        # Validate emails
        if emails := data.get("Email"):
            emails_list = [emails] if isinstance(emails, str) else emails
            for email in emails_list:
                if not validate_email(email):
                    validation_results["errors"].append(f"Invalid email format: {email}")

        # Validate phones
        if phones := data.get("Telephone", data.get("Phone")):
            phones_list = [phones] if isinstance(phones, str) else phones
            for phone in phones_list:
                if not validate_phone(phone):
                    validation_results["warnings"].append(f"Suspicious phone format: {phone}")

        # Validate data types
        type_validations = {
            "emails": (data.get("Email", []), list, str),
            "phones": (data.get("Telephone", []), list, str),
            "addresses": (data.get("Address", []), list, dict),
        }

        for field, (value, expected_type, element_type) in type_validations.items():
            if value and not isinstance(value, expected_type):
                if isinstance(value, element_type):
                    validation_results["warnings"].append(
                        f"Expected list for {field}, got single {element_type.__name__}"
                    )
                else:
                    validation_results["errors"].append(
                        f"Invalid type for {field}: expected {expected_type.__name__}"
                    )

    return validation_results


def log_validation_results(
    results: Dict[str, List[str]], logger: Optional[logging.Logger] = None
) -> None:
    """Log validation results with appropriate severity"""
    if logger is None:
        logger = logging.getLogger(__name__)

    if results["errors"]:
        for error in results["errors"]:
            logger.error(f"Validation error: {error}")

    if results["warnings"]:
        for warning in results["warnings"]:
            logger.warning(f"Validation warning: {warning}")


def sanitize_field(value: Any, field_type: type = str) -> Any:
    """Sanitize field value to expected type"""
    if value is None:
        return None if field_type is not str else ""

    try:
        if field_type is str:
            return str(value).strip()
        elif field_type is list:
            if isinstance(value, str):
                return [v.strip() for v in value.split(",")]
            elif isinstance(value, list):
                return value
            else:
                return [value]
        elif field_type is dict:
            return dict(value) if value else {}
    except (ValueError, TypeError) as e:
        logging.warning(f"Error sanitizing field: {e}")
        return None if field_type is not str else ""
