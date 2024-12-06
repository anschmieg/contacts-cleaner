###################
# Configuration options
###################

# Matching thresholds for fuzzy string comparison (0-100 scale)
ratio_name_match = 75  # Base threshold for matching contact names
ratio_nickname_match = 80  # Threshold for matching name variants/nicknames
ratio_name_org_match = 85  # Threshold when both name AND organization present
ratio_field_match = 70  # Threshold for matching non-name fields,e.g.
# addresses, notes, descriptions

# Name normalization constants
NAME_SUFFIXES = {"II", "III", "IV", "MD", "PhD", "Jr", "Sr"}
NAME_PREFIXES = {"Dr", "Prof", "Mr", "Mrs", "Ms"}
NAME_PARTICLES = {"von", "van", "de", "la", "das", "dos", "der", "den"}

# Country codes
COUNTRY_PREFIXES = {
    # North America
    "1": "US/CA",  # USA/Canada
    # Europe
    "30": "GR",  # Greece
    "31": "NL",  # Netherlands
    "32": "BE",  # Belgium
    "33": "FR",  # France
    "34": "ES",  # Spain
    "36": "HU",  # Hungary
    "39": "IT",  # Italy
    "40": "RO",  # Romania
    "41": "CH",  # Switzerland
    "43": "AT",  # Austria
    "44": "UK",  # United Kingdom
    "45": "DK",  # Denmark
    "46": "SE",  # Sweden
    "47": "NO",  # Norway
    "48": "PL",  # Poland
    "49": "DE",  # Germany
    # Asia
    "81": "JP",  # Japan
    "82": "KR",  # South Korea
    "84": "VN",  # Vietnam
    "86": "CN",  # China
    "852": "HK",  # Hong Kong
    "855": "KH",  # Cambodia
    "861": "CN",  # China (alternative)
    "886": "TW",  # Taiwan
    "91": "IN",  # India
    "92": "PK",  # Pakistan
    "95": "MM",  # Myanmar
    "966": "SA",  # Saudi Arabia
    # Oceania
    "61": "AU",  # Australia
    "64": "NZ",  # New Zealand
    # South America
    "51": "PE",  # Peru
    "52": "MX",  # Mexico
    "54": "AR",  # Argentina
    "55": "BR",  # Brazil
    "56": "CL",  # Chile
    "57": "CO",  # Colombia
    "58": "VE",  # Venezuela
    # Africa
    "20": "EG",  # Egypt
    "212": "MA",  # Morocco
    "234": "NG",  # Nigeria
    "27": "ZA",  # South Africa
    # Middle East
    "971": "AE",  # UAE
    "972": "IL",  # Israel
    "974": "QA",  # Qatar
}

# vCard field mapping
VCARD_FIELD_MAPPING = {
    "ADR": "Address",
    "AGENT": "Agent",
    "ANNIVERSARY": "Anniversary",
    "BDAY": "Birthday",
    "BEGIN": "Begin",
    "CALADRURI": "Calendar Address URI",
    "CALURI": "Calendar URI",
    "CATEGORIES": "Categories",
    "CLASS": "Class",
    "CLIENTPIDMAP": "Client PID Map",
    "EMAIL": "Email",
    "END": "End",
    "FBURL": "Free/Busy URL",
    "FN": "Full Name",
    "GENDER": "Gender",
    "GEO": "Geolocation",
    "IMPP": "Instant Messaging",
    "KEY": "Public Key",
    "KIND": "Kind",
    "LABEL": "Label",
    "LANG": "Language",
    "LOGO": "Logo",
    "MAILER": "Mailer",
    "MEMBER": "Member",
    "N": "Structured Name",
    "NAME": "Name",
    "NICKNAME": "Nickname",
    "NOTE": "Note",
    "ORG": "Organization",
    "PHOTO": "Photo",
    "PRODID": "Product ID",
    "PROFILE": "Profile",
    "RELATED": "Related",
    "REV": "Revision",
    "ROLE": "Role",
    "SORT-STRING": "Sort String",
    "SOUND": "Sound",
    "SOURCE": "Source",
    "TEL": "Telephone",
    "TITLE": "Title",
    "TZ": "Time Zone",
    "UID": "Unique Identifier",
    "URL": "URL",
    "VERSION": "Version",
    "XML": "XML",
}
