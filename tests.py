from collections import defaultdict
from contact_processing import merge_names, are_phones_matching
from name_processing import get_contact_name
from phone_processing import any_phones_match, is_duplicate
from fuzzywuzzy import fuzz


###################
# Testing Functions
###################


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


def evaluate_ratios(name_ratio, nickname_ratio, org_ratio, test_cases):
    """Enhanced evaluation with detailed metrics and failure analysis"""
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

        # Get match result and confidence
        match_details = is_duplicate_with_confidence(
            contact1,
            contact2,
            ratio_name_match=name_ratio,
            ratio_nickname_match=nickname_ratio,
            ratio_name_org_match=org_ratio,
        )
        result = match_details["is_match"]
        confidence = match_details["confidence"]

        # Track confidence scores
        results["confidence_distribution"][category].append(confidence)

        # Update category stats
        results["categories"][category]["total"] += 1
        if result == expected:
            results["categories"][category]["correct"] += 1

        # Update confusion matrix
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

    # Calculate core metrics
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

    # Calculate F1 score
    p, r = results["summary"]["precision"], results["summary"]["recall"]
    results["summary"]["f1"] = 2 * (p * r) / (p + r) if (p + r) > 0 else 0

    # Generate recommendations
    results["recommendations"] = generate_threshold_recommendations(results)

    return results


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
    """Find optimal ratio values"""
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
    print(f"Optimal ratios found (F1={score:.2f}):")
    print(f"ratio_name_match = {best_ratios['name']}")
    print(f"ratio_nickname_match = {best_ratios['nickname']}")
    print(f"ratio_name_org_match = {best_ratios['org']}")


def test_merge_names():
    # Test 1: Name variants (preferring longer forms)
    result = merge_names("John Smith", "Johnny Smith")
    print(f"Test 1: {result}")
    assert result == "Johnny Smith"

    # Test 2: Hyphenated names and ordering
    result = merge_names("George Depression NoCorp", "George Winter-Depression")
    print(f"Test 2: {result}")
    assert result == "George Winter-Depression NoCorp"

    # Test 3: Formal names with titles
    result = merge_names("Dr. James Wilson", "Jim Wilson MD")
    print(f"Test 3: {result}")
    assert result == "Dr. Jim James Wilson MD"

    # Test 4: Mixed case and spacing
    result = merge_names("mary-jane smith", "Mary Jane Smith-Jones")
    print(f"Test 4: {result}")
    assert result == "Mary-Jane Smith-Jones"

    # Test 5: Complex multi-part names
    result = merge_names("William Henry Gates III", "Bill Gates")
    print(f"Test 5: {result}")
    assert result == "William Bill Henry Gates III"

    # Test 6: Names with middle initials
    result = merge_names("Robert J. Smith", "Bob Smith Jr.")
    print(f"Test 6: {result}")
    assert result == "Robert Bob J. Smith Jr."

    # Test 7: Different ordering but same components
    result = merge_names("Smith, John A.", "John Adam Smith")
    print(f"Test 7: {result}")
    assert result == "John A. Adam Smith"

    print("All tests passed!")


def test_phone_matching():
    # Test 1: Exact match
    assert are_phones_matching("+1-800-555-5555", "+1-800-555-5555")
    print("Test 1 passed")

    # Test 2: Different formats, same number
    assert are_phones_matching("800-555-5555", "+1 800 555 5555")
    print("Test 2 passed")

    # Test 3: International format vs local format
    assert are_phones_matching("+44 20 7946 0958", "020 7946 0958")
    print("Test 3 passed")

    # Test 4: Different country codes
    assert not are_phones_matching("+1-800-555-5555", "+44 800 555 5555")
    print("Test 4 passed")

    # Test 5: Number with symbols
    assert are_phones_matching("(800) 555-5555", "+1 800.555.5555")
    print("Test 5 passed")

    # Test 6: Number with extension
    assert are_phones_matching("+1-800-555-5555 ext. 123", "+1 800 555 5555 x123")
    print("Test 6 passed")

    # Test 7: Different numbers
    assert not are_phones_matching("+1-800-555-5555", "+1-800-555-5556")
    print("Test 7 passed")

    # Test 8: Empty numbers
    assert not are_phones_matching("", "+1-800-555-5555")
    print("Test 8 passed")

    # Test 9: Both numbers empty
    assert not are_phones_matching("", "")
    print("Test 9 passed")

    print("All phone matching tests passed!")
