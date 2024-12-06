###################
# Main Execution
###################


import os
import sys
from file_io import parse_vcard, save_to_csv
from process_contact import merge_duplicates
from validation import generate_merge_validation


def main(input_paths):
    all_contacts = []
    total_contacts = 0
    for input_path in input_paths:
        if os.path.isdir(input_path):
            for file_name in os.listdir(input_path):
                if file_name.endswith(".vcf"):
                    vcf_path = os.path.join(input_path, file_name)
                    contacts = parse_vcard(vcf_path)
                    all_contacts.extend(contacts)
                    total_contacts += len(contacts)
        elif os.path.isfile(input_path) and input_path.endswith(".vcf"):
            contacts = parse_vcard(input_path)
            all_contacts.extend(contacts)
            total_contacts += len(contacts)
        else:
            print(f"Invalid input path: {input_path}")
            return

    print(f"Read  {total_contacts} in total.")

    # Keep copy of original contacts for validation
    original_contacts = all_contacts.copy()

    # Merge contacts
    all_contacts = merge_duplicates(all_contacts)

    # Save merged contacts
    output_csv = "output/merged_contacts.csv"
    save_to_csv(all_contacts, output_csv)

    # Generate and display merge validation
    print("\nGenerating merge validation report...")
    generate_merge_validation(original_contacts, all_contacts)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python main.py <input_directory_or_file> [<input_directory_or_file> ...] [-t|--test]"
        )
    elif sys.argv[1] in ["-t", "--test"]:
        # Import test functions and run them
        from tests import test_merge_names, test_phone_matching

        test_merge_names = test_merge_names()
        test_phone_matching = test_phone_matching()
        (
            print("--     Test Names failed!    --")
            if not test_merge_names
            else print("       Test Names passed!      ")
        )
        (
            print("--     Test Phones failed!   --")
            if not test_phone_matching
            else print("       Test Phones passed!     ")
        )
        if test_merge_names and test_phone_matching:
            print("-----> All tests passed! <-----")
        elif test_merge_names and not test_phone_matching:
            print("--     Test Names passed!    --")
        elif not test_merge_names and test_phone_matching:
            print("--     Test Phones passed!   --")
        else:
            print("-----> All tests failed! <-----")
    else:
        main(sys.argv[1:])
