"""
Configuration settings for the contacts cleaner application.
All threshold values are on a scale of 0-100.
"""

###################
# Matching Thresholds
###################

# Base threshold for comparing contact names
# Higher values require more exact matches
NAME_MATCH_THRESHOLD: int = 75

# Threshold for matching potential nicknames or name variants
# Slightly lower than base to allow for common variations
NICKNAME_MATCH_THRESHOLD: int = 70

# Threshold when comparing both name and organization
# Lower to account for potential variations in either field
NAME_ORG_MATCH_THRESHOLD: int = 60

# Threshold for matching non-name fields (addresses, notes, etc.)
# Higher to prevent false positives in longer text fields
FIELD_MATCH_THRESHOLD: int = 85

###################
# Processing Options
###################

# Maximum number of contacts to process in a batch
BATCH_SIZE: int = 100

# Default encoding for reading contact files
DEFAULT_ENCODING: str = 'utf-8'
