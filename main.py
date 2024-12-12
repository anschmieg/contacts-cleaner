#!/usr/bin/env python3

import argparse
import logging
from typing import List
from pathlib import Path

from src.core.contact import Contact
from src.core.merger import ContactMerger
from src.processors.name import NameProcessor
from src.processors.address import AddressProcessor, AddressValidationMode
from src.io.csv import CSVHandler
from src.io.vcard import VCardHandler


def load_contacts(input_paths: List[Path]) -> List[Contact]:
    """Load contacts from input files"""
    contacts = []
    csv_handler = CSVHandler()
    vcard_handler = VCardHandler()

    logging.info(f"Loading contacts from {len(input_paths)} files")
    for path in input_paths:
        try:
            logging.debug(f"Processing file: {path}")
            if path.suffix.lower() == ".csv":
                new_contacts = csv_handler.read_csv(str(path))
                logging.debug(f"Loaded {len(new_contacts)} contacts from CSV: {path}")
                contacts.extend(new_contacts)
            elif path.suffix.lower() in [".vcf", ".vcard"]:
                new_contacts = vcard_handler.read_vcard(str(path))
                logging.debug(f"Loaded {len(new_contacts)} contacts from VCard: {path}")
                contacts.extend(new_contacts)
            else:
                logging.warning(f"Unsupported file format: {path}")
        except Exception as e:
            logging.error(f"Error loading file {path}: {e}")
            raise

    logging.info(f"Successfully loaded {len(contacts)} contacts in total")
    return contacts


def save_results(contacts: List[Contact], output_dir: Path) -> None:
    """Save processed contacts"""
    logging.info(f"Saving {len(contacts)} processed contacts to {output_dir}")
    csv_handler = CSVHandler()
    vcard_handler = VCardHandler()

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save as CSV
    csv_path = output_dir / "contacts.csv"
    csv_handler.write_csv(contacts, str(csv_path))
    logging.debug(f"Saved contacts to CSV: {csv_path}")

    # Save as VCF
    vcf_path = output_dir / "contacts.vcf"
    vcard_handler.write_vcard(contacts, str(vcf_path))
    logging.debug(f"Saved contacts to VCard: {vcf_path}")
    
    logging.info("Successfully saved all output files")


def generate_validation_report(contacts: List[Contact], output_dir: Path) -> None:
    """Generate validation report for processed contacts"""
    logging.info("Generating validation report")
    report_path = output_dir / "validation_report.csv"
    csv_handler = CSVHandler()

    # Create a simplified version of contacts with validation info
    validation_data = []
    for contact in contacts:
        for address in contact.addresses:
            validation_data.append(
                {
                    "Full Name": contact.full_name,
                    "Address": address.get("original", ""),
                    "Validated": address.get("formatted", ""),
                    "Status": address.get("validation_status", "UNKNOWN"),
                }
            )

    # Save validation report
    csv_handler.write_csv(validation_data, str(report_path))
    logging.debug(f"Saved validation report to: {report_path}")


def main(
    input_paths: List[Path],
    output_dir: Path,
    api_key: str,
    validation_mode: AddressValidationMode = AddressValidationMode.FULL,
) -> None:
    # Initialize processors
    logging.info("Initializing contact processors")
    name_processor = NameProcessor()
    address_processor = AddressProcessor(api_key, validation_mode)
    merger = ContactMerger(name_processor, address_processor)

    try:
        # Load contacts
        contacts = load_contacts(input_paths)
        
        # Process and merge
        logging.info("Processing and merging contacts")
        merged_contacts = merger.merge_contacts(contacts)
        logging.info(f"Successfully merged into {len(merged_contacts)} unique contacts")

        # Save results
        save_results(merged_contacts, output_dir)

        # Generate validation report
        if validation_mode != AddressValidationMode.NONE:
            generate_validation_report(merged_contacts, output_dir)

        logging.info("Contact processing completed successfully")

    except Exception as e:
        logging.error(f"Error processing contacts: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process contact files and clean addresses."
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Input file paths (.vcf or .csv). Can also be a directory containing the files.",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="output",
        help="Output directory for processed files",
    )
    parser.add_argument(
        "--address-cleaning",
        "-a",
        choices=["none", "clean", "full"],
        default="full",
        help="Address validation mode (none: no cleaning, clean: string cleaning only, full: cleaning and API validation)",
    )
    parser.add_argument(
        "--api-key", "-k", help="API key for address validation service"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if not args.inputs:
        parser.print_help()
    else:
        # Configure logging based on verbose flag
        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        
        # Convert inputs to Path objects
        input_paths = [Path(p) for p in args.inputs]
        output_dir = Path(args.output_dir)

        # Set validation mode
        validation_modes = {
            "none": AddressValidationMode.NONE,
            "clean": AddressValidationMode.CLEAN_ONLY,
            "full": AddressValidationMode.FULL,
        }
        validation_mode = validation_modes[args.address_cleaning]

        # Run main process
        main(input_paths, output_dir, args.api_key, validation_mode)
