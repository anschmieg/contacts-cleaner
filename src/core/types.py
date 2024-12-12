
from typing import List, Dict, Optional
from enum import Enum

class ValidationLevel(Enum):
    NONE = 0
    BASIC = 1
    STRICT = 2

ContactDict = Dict[str, List[str]]
ValidationResults = Dict[str, List[str]]