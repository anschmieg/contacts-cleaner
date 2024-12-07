import logging
import os
from dotenv import load_dotenv
from collections import defaultdict
from pathlib import Path
from process_contact import (
    merge_names,
    are_phones_matching,
    is_duplicate_with_confidence,
)
from process_address import normalize_address, AddressValidationMode

# Load environment variables
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# --- Logging Configuration ---
output_dir = Path("output")
output_dir.mkdir(exist_ok=True)
log_file = output_dir / "test_results.log"

# Set up file handler for all logging
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - [%(levelname)s] - %(filename)s:%(lineno)d - %(funcName)s()\n    %(message)s"
    )
)

# Set up console handler for errors and results only
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)  # Only ERROR and above (including RESULTS) go to console
console_handler.setFormatter(
    logging.Formatter("[%(levelname)s] %(message)s")
)

# Define custom RESULTS level between ERROR and CRITICAL
RESULTS_LEVEL = 45  # Changed to be between ERROR(40) and CRITICAL(50)
logging.addLevelName(RESULTS_LEVEL, "RESULTS")

def log_results(self, message, *args, **kwargs):
    if self.isEnabledFor(RESULTS_LEVEL):
        self._log(RESULTS_LEVEL, message, args, **kwargs)

logging.Logger.results = log_results

# Configure root logger to ERROR to block debug messages
logging.getLogger().setLevel(logging.ERROR)

# Configure our module logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)  # Changed from INFO to ERROR
logger.handlers = []
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = False

# --- Test Cases ---
def generate_test_cases():
    """Generate comprehensive test cases for contact matching"""
    test_pairs = [
        # Name variations
        {
            "pair": (
                {"Name": "John smith", "Email": "john@email.com"},
                {"Name": "JOHN SMITH", "Email": "john@email.com"},
            ),
            "should_match": True,
            "reason": "Case insensitive name matching",
        },
        # Organization vs Full Name
        {
            "pair": (
                {"Name": "Michael Tech Corp", "Organization": ""},
                {"Name": "Michael Johnson", "Organization": "Tech Corp"},
            ),
            "should_match": True,
            "reason": "Name contains organization",
        },
        # Address matching
        {
            "pair": (
                {"Name": "Alice Brown", "Address": "123 Main St, Apt 4B, New York, NY"},
                {"Name": "Alice", "Address": "123 Main Street, #4B, New York, NY"},
            ),
            "should_match": True,
            "reason": "Fuzzy address matching",
        },
        # Phone variations
        {
            "pair": (
                {"Name": "David Lee", "Telephone": "+1 (415) 555-0123"},
                {"Name": "Dave Lee", "Telephone": "4155550123"},
            ),
            "should_match": True,
            "reason": "Phone number normalization",
        },
        # Multiple fields
        {
            "pair": (
                {
                    "Name": "Sarah Johnson",
                    "Organization": "Global Tech",
                    "Email": "sarah@globaltech.com",
                },
                {
                    "Name": "Sarah J",
                    "Organization": "Global Technologies",
                    "Email": "sarah@globaltech.com",
                },
            ),
            "should_match": True,
            "reason": "Multiple field matching",
        },
        # Name order variations
        {
            "pair": (
                {"Name": "Wong, Li Wei", "Organization": "Asia Corp"},
                {"Name": "Li Wei Wong", "Organization": "Asia Corp"},
            ),
            "should_match": True,
            "reason": "Name order normalization",
        },
        # Should not match
        {
            "pair": (
                {"Name": "Thomas Anderson", "Organization": "Matrix Corp"},
                {"Name": "Thomas Anderson", "Organization": "Zion Ltd"},
            ),
            "should_match": False,
            "reason": "Different organizations",
        },
        # Edge cases
        {
            "pair": (
                {"Name": "Dr. James Wilson-Smith Jr.", "Organization": "Hospital"},
                {"Name": "Jim Wilson-Smith", "Organization": "City Hospital"},
            ),
            "should_match": True,
            "reason": "Complex name with titles and hyphens",
        },
        # International characters
        {
            "pair": (
                {"Name": "José García", "Email": "jose@email.com"},
                {"Name": "Jose Garcia", "Email": "jose@email.com"},
            ),
            "should_match": True,
            "reason": "Unicode normalization",
        },
        # Organization variations
        {
            "pair": (
                {"Name": "Linda", "Organization": "IBM Corporation"},
                {"Name": "Linda Smith", "Organization": "IBM Corp"},
            ),
            "should_match": True,
            "reason": "Organization abbreviations",
        },
    ]
    return test_pairs


# --- Test Classes ---
class TestFailureException(Exception):
    """Custom exception for test failures"""

    pass


# --- Test Functions ---
def test_merge_names():
    try:
        logger.info("TEST SUITE: NAME MERGE")  # Changed from debug to info
        tests_run = tests_passed = 0

        # Test 1: Name variants
        logger.info("\tTEST 1/7: Name variants")  # Changed from debug to info
        logger.info("\tInput: 'John Smith' + 'Johnny Smith'")  # Changed from debug to info
        result = merge_names("John Smith", "Johnny Smith")
        logger.info(f"\tOutput: '{result}'")  # Changed from debug to info
        if result != "Johnny Smith":
            raise TestFailureException(f"Name variant test failed. Got: {result}")
        tests_run += 1
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 2: Hyphenated names
        logger.info("\tTEST 2/7: Hyphenated names")  # Changed from debug to info
        logger.info("\tInput: 'George Depression NoCorp' + 'George Winter-Depression'")  # Changed from debug to info
        result = merge_names("George Depression NoCorp", "George Winter-Depression")
        logger.info(f"\tOutput: '{result}'")  # Changed from debug to info
        if result != "George Winter-Depression NoCorp":
            raise TestFailureException(f"Hyphenated name test failed. Got: {result}")
        tests_run += 1
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 3: Formal names with titles
        logger.info("\tTEST 3/7: Formal names with titles")  # Changed from debug to info
        logger.info("\tInput: 'Dr. James Wilson' + 'Jim Wilson MD'")  # Changed from debug to info
        result = merge_names("Dr. James Wilson", "Jim Wilson MD")
        logger.info(f"\tOutput: '{result}'")  # Changed from debug to info
        if result != "Dr. Jim James Wilson MD":
            raise TestFailureException(f"Formal name test failed. Got: {result}")
        tests_run += 1
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 4: Mixed case and spacing
        logger.info("\tTEST 4/7: Mixed case and spacing")  # Changed from debug to info
        logger.info("\tInput: 'mary-jane smith' + 'Mary Jane Smith-Jones'")  # Changed from debug to info
        result = merge_names("mary-jane smith", "Mary Jane Smith-Jones")
        logger.info(f"\tOutput: '{result}'")  # Changed from debug to info
        if result != "Mary-Jane Smith-Jones":
            raise TestFailureException(f"Mixed case test failed. Got: {result}")
        tests_run += 1
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 5: Complex multi-part names
        logger.info("\tTEST 5/7: Complex multi-part names")  # Changed from debug to info
        logger.info("\tInput: 'William Henry Gates III' + 'Bill Gates'")  # Changed from debug to info
        result = merge_names("William Henry Gates III", "Bill Gates")
        logger.info(f"\tOutput: '{result}'")  # Changed from debug to info
        if result != "William Bill Henry Gates III":
            raise TestFailureException(f"Complex name test failed. Got: {result}")
        tests_run += 1
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 6: Names with middle initials
        logger.info("\tTEST 6/7: Names with middle initials")  # Changed from debug to info
        logger.info("\tInput: 'Robert J. Smith' + 'Bob Smith Jr.'")  # Changed from debug to info
        result = merge_names("Robert J. Smith", "Bob Smith Jr.")
        logger.info(f"\tOutput: '{result}'")  # Changed from debug to info
        if result != "Robert Bob J. Smith Jr.":
            raise TestFailureException(f"Middle initial test failed. Got: {result}")
        tests_run += 1
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 7: Different ordering but same components
        logger.info("\tTEST 7/7: Different ordering")  # Changed from debug to info
        logger.info("\tInput: 'Smith, John A.' + 'John Adam Smith'")  # Changed from debug to info
        result = merge_names("Smith, John A.", "John Adam Smith")
        logger.info(f"\tOutput: '{result}'")  # Changed from debug to info
        if result != "John A. Adam Smith":
            raise TestFailureException(f"Ordering test failed. Got: {result}")
        tests_run += 1
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        success_rate = (tests_passed / tests_run) * 100
        logger.results(
            f"Test results: {tests_passed}/{tests_run} passed ({success_rate:.0f}%)"
        )
        return True
    except Exception:
        logger.error("Name merge tests failed", exc_info=True)
        raise


def test_phone_matching():
    try:
        logger.info("TEST SUITE: PHONE MATCHING")  # Changed from debug to info
        tests_run = tests_passed = 0

        # Test 1: Exact match
        logger.info("\tTEST 1/9: Exact phone match")  # Changed from debug to info
        logger.info("\tInput: '+1-800-555-5555' vs '+1-800-555-5555'")  # Changed from debug to info
        result = are_phones_matching("+1-800-555-5555", "+1-800-555-5555")
        logger.info(f"\tResult: {result}")  # Changed from debug to info
        tests_run += 1
        if not result:
            raise TestFailureException("Exact phone match test failed")
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 2: Different formats
        logger.info("\tTEST 2/9: Different formats")  # Changed from debug to info
        logger.info("\tInput: '800-555-5555' vs '+1 800 555 5555'")  # Changed from debug to info
        result = are_phones_matching("800-555-5555", "+1 800 555 5555")
        logger.info(f"\tResult: {result}")  # Changed from debug to info
        tests_run += 1
        if not result:
            raise TestFailureException("Phone format test failed")
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 3: International format vs local format
        logger.info("\tTEST 3/9: International format vs local format")  # Changed from debug to info
        logger.info("\tInput: '+44 20 7946 0958' vs '020 7946 0958'")  # Changed from debug to info
        result = are_phones_matching("+44 20 7946 0958", "020 7946 0958")
        logger.info(f"\tResult: {result}")  # Changed from debug to info
        tests_run += 1
        if not result:
            raise TestFailureException("International format test failed")
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 4: Different country codes
        logger.info("\tTEST 4/9: Different country codes")  # Changed from debug to info
        logger.info("\tInput: '+1-800-555-5555' vs '+44 800 555 5555'")  # Changed from debug to info
        result = are_phones_matching("+1-800-555-5555", "+44 800 555 5555")
        logger.info(f"\tResult: {result}")  # Changed from debug to info
        tests_run += 1
        if result:
            raise TestFailureException("Country code test failed")
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 5: Number with symbols
        logger.info("\tTEST 5/9: Number with symbols")  # Changed from debug to info
        logger.info("\tInput: '(800) 555-5555' vs '+1 800.555.5555'")  # Changed from debug to info
        result = are_phones_matching("(800) 555-5555", "+1 800.555.5555")
        logger.info(f"\tResult: {result}")  # Changed from debug to info
        tests_run += 1
        if not result:
            raise TestFailureException("Symbol test failed")
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 6: Number with extension
        logger.info("\tTEST 6/9: Number with extension")  # Changed from debug to info
        logger.info("\tInput: '+1-800-555-5555 ext. 123' vs '+1 800 555 5555 x123'")  # Changed from debug to info
        result = are_phones_matching("+1-800-555-5555 ext. 123", "+1 800 555 5555 x123")
        logger.info(f"\tResult: {result}")  # Changed from debug to info
        tests_run += 1
        if not result:
            raise TestFailureException("Extension test failed")
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 7: Different numbers
        logger.info("\tTEST 7/9: Different numbers")  # Changed from debug to info
        logger.info("\tInput: '+1-800-555-5555' vs '+1-800-555-5556'")  # Changed from debug to info
        result = are_phones_matching("+1-800-555-5555", "+1-800-555-5556")
        logger.info(f"\tResult: {result}")  # Changed from debug to info
        tests_run += 1
        if result:
            raise TestFailureException("Different number test failed")
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 8: Empty numbers
        logger.info("\tTEST 8/9: Empty numbers")  # Changed from debug to info
        logger.info("\tInput: '' vs '+1-800-555-5555'")  # Changed from debug to info
        result = are_phones_matching("", "+1-800-555-5555")
        logger.info(f"\tResult: {result}")  # Changed from debug to info
        tests_run += 1
        if are_phones_matching("", "+1-800-555-5555"):  # This test is correct
            raise TestFailureException("Empty number test failed")
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        # Test 9: Both numbers empty
        logger.info("\tTEST 9/9: Both numbers empty")  # Changed from debug to info
        logger.info("\tInput: '' vs ''")  # Changed from debug to info
        result = are_phones_matching("", "")
        logger.info(f"\tResult: {result}")  # Changed from debug to info
        tests_run += 1
        if result:  # Changed: empty strings should not match
            raise TestFailureException("Both empty test failed")
        tests_passed += 1
        logger.info("\tStatus: PASSED")  # Changed from debug to info

        success_rate = (tests_passed / tests_run) * 100
        logger.results(
            f"Test results: {tests_passed}/{tests_run} passed ({success_rate:.0f}%)"
        )
        return True
    except Exception:
        logger.error("Phone matching tests failed", exc_info=True)
        raise


def format_address_for_display(addr_dict):
    """Format address dictionary for human readable output"""
    vcard = addr_dict["vcard"]
    parts = []
    if vcard.get("street"):
        parts.append(f"street: {vcard['street']}")
    if vcard.get("locality"):
        parts.append(f"city: {vcard['locality']}")
    if vcard.get("postal_code"):
        parts.append(f"postal: {vcard['postal_code']}")
    if vcard.get("country"):
        parts.append(f"country: {vcard['country']}")
    status = []
    if addr_dict.get("isBusiness"):
        status.append("business")
    if addr_dict.get("addressComplete"):
        status.append("complete")
    return f"{' | '.join(parts)} [{', '.join(status)}]"


def test_address_processing():
    test_cases = [
        {
            "input": "Bergstraße 51\nBerlin,  12169\nDeutschland, 51 Bergstraße\nBerlin",
            "expected": {
                "vcard": {
                    "street": "Bergstraße 51",
                    "locality": "Berlin",
                    "postal_code": "12169",
                    "country": "Deutschland",
                },
                "isBusiness": True,
                "addressComplete": True,
            },
        },
        {
            "input": "Eichhörnchensteig 3\nBerlin,  14195\nDeutschland, 3 Eichhörnchensteig\nBerlin",
            "expected": {
                "vcard": {
                    "street": "Eichhörnchensteig 3",
                    "locality": "Berlin",
                    "postal_code": "14193",
                    "country": "Deutschland",
                },
                "isBusiness": False,
                "addressComplete": True,
            },
        },
        {
            "input": ":::7 Willdenowstr.:::\nBerlin, ::: 13353\n:::",
            "expected": {
                "vcard": {
                    "street": "Willdenowstraße 7",
                    "locality": "Berlin",
                    "postal_code": "13353",
                    "country": "Deutschland",
                },
                "isBusiness": False,
                "addressComplete": True,
            },
        },
        {
            "input": "5-1 Raiffeisenstraße 83129 Höslwang",
            "expected": {
                "vcard": {
                    "street": "Raiffeisenstraße 51",
                    "locality": "Höslwang",
                    "postal_code": "83129",
                    "country": "Deutschland",
                },
                "isBusiness": False,
                "addressComplete": True,
            },
        },
        {
            "input": "Schützallee 35 Berlin,  14169 Germany",
            "expected": {
                "vcard": {
                    "street": "Schützallee 35",
                    "locality": "Berlin",
                    "postal_code": "14169",
                    "country": "Deutschland",
                },
                "isBusiness": False,
                "addressComplete": True,
            },
        },
    ]

    for case in test_cases:
        input_address = case["input"]
        expected_output = case["expected"]
        actual_output = normalize_address(
            input_address, api_key, AddressValidationMode.FULL
        )

        if actual_output != expected_output:
            logger.error("\nAddress Verification Failed:")
            logger.error(f"Input:    {input_address}")
            logger.error(f"Expected: {format_address_for_display(expected_output)}")
            logger.error(f"Actual:   {format_address_for_display(actual_output)}")
            logger.error(f"API Verdict: {actual_output.get('verdict', 'unknown')}")
            logger.error("-" * 80)
            raise AssertionError("Address verification failed")
        else:
            logger.info(f"✓ Verified: {format_address_for_display(actual_output)}")  # Changed from debug to info


def run_tests():
    """Run all test suites and return overall test status"""
    try:
        logger.info("STARTING TEST SUITES")  # Changed from debug to info
        test_merge_names()
        test_phone_matching()
        test_address_processing()
        logger.results("ALL TEST SUITES COMPLETED")
        return True
    except TestFailureException:
        logger.error("Test suite failed", exc_info=True)
        return False
    except Exception:
        logger.error("Unexpected test failure", exc_info=True)
        return False
    finally:
        logger.results("-" * 60)


# --- Evaluation Functions ---
def evaluate_ratios(name_ratio, nickname_ratio, org_ratio, test_cases):
    ratios = {"name": name_ratio, "nickname": nickname_ratio, "org": org_ratio}

    results = {
        "metrics": {
            "true_positives": 0,
            "true_negatives": 0,
            "false_positives": 0,
            "false_negatives": 0,
        },
        "failures": [],
        "categories": defaultdict(lambda: {"correct": 0, "total": 0}),
        "confidence_distribution": defaultdict(list),
    }

    for test in test_cases:
        contact1, contact2 = test["pair"]
        expected = test["should_match"]
        category = test.get("reason", "unknown")

        match_details = is_duplicate_with_confidence(contact1, contact2, ratios)
        result = match_details["is_match"]
        confidence = match_details["confidence"]

        results["confidence_distribution"][category].append(confidence)
        results["categories"][category]["total"] += 1
        if result == expected:
            results["categories"][category]["correct"] += 1

        if result and expected:
            results["metrics"]["true_positives"] += 1
        elif not result and not expected:
            results["metrics"]["true_negatives"] += 1
        elif result and not expected:
            results["metrics"]["false_positives"] += 1
            results["failures"].append(
                {
                    "type": "false_positive",
                    "contact1": contact1,
                    "contact2": contact2,
                    "category": category,
                    "confidence": confidence,
                }
            )
        else:
            results["metrics"]["false_negatives"] += 1
            results["failures"].append(
                {
                    "type": "false_negative",
                    "contact1": contact1,
                    "contact2": contact2,
                    "category": category,
                    "confidence": confidence,
                }
            )

    m = results["metrics"]
    total_positive = m["true_positives"] + m["false_positives"]
    total_actual = m["true_positives"] + m["false_negatives"]

    results["summary"] = {
        "precision": m["true_positives"] / total_positive if total_positive > 0 else 0,
        "recall": m["true_positives"] / total_actual if total_actual > 0 else 0,
        "accuracy": (m["true_positives"] + m["true_negatives"]) / len(test_cases),
        "category_accuracy": {
            cat: stats["correct"] / stats["total"]
            for cat, stats in results["categories"].items()
        },
    }

    p, r = results["summary"]["precision"], results["summary"]["recall"]
    results["summary"]["f1"] = 2 * (p * r) / (p + r) if (p + r) > 0 else 0

    results["recommendations"] = generate_threshold_recommendations(results)

    return results["summary"]


def generate_threshold_recommendations(results):
    """Generate recommendations for threshold adjustments"""
    recommendations = []

    # Analyze false positives
    fp_confidence = [
        f["confidence"] for f in results["failures"] if f["type"] == "false_positive"
    ]
    if fp_confidence:
        avg_fp_confidence = sum(fp_confidence) / len(fp_confidence)
        if avg_fp_confidence < 0.9:
            recommendations.append(
                {
                    "type": "threshold_increase",
                    "reason": f"False positives averaging {avg_fp_confidence:.2f} confidence",
                }
            )

    # Analyze category performance
    for category, accuracy in results["summary"]["category_accuracy"].items():
        if accuracy < 0.8:
            recommendations.append(
                {"type": "category_review", "category": category, "accuracy": accuracy}
            )

    return recommendations


def grid_search():
    test_cases = generate_test_cases()
    best_score = 0
    best_ratios = None

    for name_ratio in range(60, 95, 5):
        for nickname_ratio in range(name_ratio, 95, 5):
            for org_ratio in range(nickname_ratio, 95, 5):
                scores = evaluate_ratios(
                    name_ratio, nickname_ratio, org_ratio, test_cases
                )
                if scores["f1"] > best_score:
                    best_score = scores["f1"]
                    best_ratios = {
                        "name": name_ratio,
                        "nickname": nickname_ratio,
                        "org": org_ratio,
                    }

    return best_ratios, best_score


def test_ratio_optimization():
    best_ratios, score = grid_search()
    logger.info(f"Optimal ratios found (F1={score:.2f}):")
    logger.info(f"ratio_name_match = {best_ratios['name']}")
    logger.info(f"ratio_nickname_match = {best_ratios['nickname']}")
    logger.info(f"ratio_name_org_match = {best_ratios['org']}")
    return best_ratios, score


def main_test_ratio_optimization():
    """Run ratio optimization as a standalone function"""
    logger.info("Starting ratio optimization...")
    best_ratios, score = test_ratio_optimization()
    print("\nOptimization Results:")
    print("-" * 20)
    print(f"Best F1 Score: {score:.3f}")
    print(f"Name Match Ratio: {best_ratios['name']}")
    print(f"Nickname Match Ratio: {best_ratios['nickname']}")
    print(f"Organization Match Ratio: {best_ratios['org']}")
    return best_ratios
