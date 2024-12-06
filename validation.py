###################
# Validation Functions
###################


import pandas as pd
from process_name import get_contact_name
from process_phone import normalize_phone_list


def generate_merge_validation(
    original_contacts, merged_contacts, output_file="output/merge_report.csv"
):
    """Enhanced validation report generation"""
    print("\nGenerating validation report:")
    print(f"Original contacts: {len(original_contacts)}")
    print(f"Merged contacts: {len(merged_contacts)}")

    validation_data = []

    # Use the stored merged groups information
    global _merged_groups_mapping
    if hasattr(globals(), "_merged_groups_mapping") and _merged_groups_mapping:
        merged_groups = _merged_groups_mapping["groups"]

        # Process each merged group
        for group in merged_groups:
            if len(group) > 1:  # Only process groups with actual merges
                # Get the merged contact (first in group)
                merged = group[0]
                merged_name = get_contact_name(merged)

                # Collect all original names and phones
                original_names = []
                original_phones = set()
                for orig in group:
                    orig_name = get_contact_name(orig)
                    if orig_name:
                        original_names.append(orig_name)
                    phones = normalize_phone_list(orig.get("Telephone", ""))
                    original_phones.update(phones)

                # Get merged phone numbers
                merged_phones = set(normalize_phone_list(merged.get("Telephone", "")))

                print(f"\nMerged group for {merged_name}:")
                for name in original_names:
                    print(f"  - {name}")

                validation_data.append(
                    {
                        "Original Names": ", ".join(sorted(set(original_names))),
                        "Merged Name": merged_name,
                        "Original Phone Numbers": ", ".join(sorted(original_phones)),
                        "Merged Phone Numbers": ", ".join(sorted(merged_phones)),
                        "Match Confidence": merged.get("Match Confidence", 0),
                    }
                )

    # Also process individual contacts (not merged)
    for contact in merged_contacts:
        merged_name = get_contact_name(contact)
        if not any(merged_name == data["Merged Name"] for data in validation_data):
            phones = normalize_phone_list(contact.get("Telephone", ""))
            validation_data.append(
                {
                    "Original Names": merged_name,
                    "Merged Name": merged_name,
                    "Original Phone Numbers": ", ".join(phones),
                    "Merged Phone Numbers": ", ".join(phones),
                    "Match Confidence": contact.get("Match Confidence", 0),
                }
            )

    df = pd.DataFrame(validation_data)
    if output_file:
        df.to_csv(output_file, index=False)
        print(f"\nMerge validation report saved to {output_file}")
        print(
            f"Found {len(validation_data)} entries ({len([d for d in validation_data if ',' in d['Original Names']])} merged groups)"
        )

    return df
