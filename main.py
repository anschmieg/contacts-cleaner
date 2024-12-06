###################
# Main Execution
###################


import os
import argparse
from file_io import parse_vcard, save_to_csv
from process_contact import merge_duplicates
from validation import generate_merge_validation
from process_address import AddressValidationMode


def main(input_paths, validation_mode=AddressValidationMode.FULL):
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
    all_contacts = merge_duplicates(all_contacts, validation_mode=validation_mode)

    # Save merged contacts
    output_csv = "output/merged_contacts.csv"
    save_to_csv(all_contacts, output_csv)

    # Generate and display merge validation
    print("\nGenerating merge validation report...")
    generate_merge_validation(original_contacts, all_contacts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process vCard files and clean addresses.')
    parser.add_argument('inputs', nargs='*', help='Input directory or file paths')
    parser.add_argument('-t', '--test', action='store_true', help='Run tests')
    parser.add_argument('--address-cleaning', '-a', 
                      choices=['none', 'clean', 'full'],
                      default='full',
                      help='Address validation mode (none: no cleaning, clean: string cleaning only, full: cleaning and API validation)')
    
    args = parser.parse_args()
    
    if args.test:
        from tests import run_tests
        run_tests()
    elif not args.inputs:
        parser.print_help()
    else:
        validation_modes = {
            'none': AddressValidationMode.NONE,
            'clean': AddressValidationMode.CLEAN_ONLY,
            'full': AddressValidationMode.FULL
        }
        validation_mode = validation_modes[args.address_validation]
        main(args.inputs, validation_mode)
