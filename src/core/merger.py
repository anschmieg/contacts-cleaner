from typing import List, Dict
from math import prod
from .contact import Contact
from ..processors.name import NameProcessor
from ..processors.address import AddressProcessor, AddressValidationMode
from .matcher import ContactMatcher


class ContactMerger:
    def __init__(self, name_processor: NameProcessor, address_processor: AddressProcessor):
        self.name_processor = name_processor
        self.address_processor = address_processor
        self.matcher = ContactMatcher(name_processor)

    def merge_contacts(self, contacts: List[Contact]) -> List[Contact]:
        """Main entry point for merging contacts"""
        if not contacts:
            return []
            
        duplicates = self.matcher.find_duplicates(contacts)
        if not duplicates:
            return contacts  # Return original contacts if no duplicates found
            
        return self.merge_duplicate_groups(duplicates)

    def merge_contact_group(self, duplicates: List[Contact], validation_mode=AddressValidationMode.FULL) -> Contact:
        """Match exact implementation from v1/process_contact.py"""
        if not duplicates:
            return None

        merged = Contact()
        confidence_scores = []

        # Process first and last names
        first_names = set()
        last_names = set()

        # Extract names from duplicates with exact same logic as v1
        for duplicate in duplicates:
            if duplicate.first_name:
                first_names.update(n.strip() for n in duplicate.first_name.split(','))
            if duplicate.last_name:
                last_names.update(n.strip() for n in duplicate.last_name.split(','))

            # Extend lists instead of updating sets for these fields
            merged.emails.extend(duplicate.emails)
            merged.phones.extend(duplicate.phones)
            merged.addresses.extend(duplicate.addresses)

            confidence = self.matcher.calculate_match_confidence(duplicates[0], duplicate)
            confidence_scores.append(confidence)

        # Merge names using name processor with exact same logic as v1
        if first_names:
            first = next(iter(first_names))
            for name in first_names:
                if name != first:
                    first = self.name_processor.merge_names([first, name])
            merged.first_name = first

        if last_names:
            last = next(iter(last_names))
            for name in last_names:
                if name != last:
                    last = self.name_processor.merge_names([last, name])
            merged.last_name = last

        # Update merged contact same as v1
        merged.full_name = ' '.join(filter(None, [merged.first_name, merged.last_name]))
        merged.emails = list(set(merged.emails))
        merged.phones = list(set(merged.phones))
        
        # Normalize addresses exactly like v1
        if merged.addresses:
            merged.addresses = self.address_processor.normalize_addresses(
                merged.addresses, 
                validation_mode
            )

        # Calculate confidence score using geometric mean like v1
        merged.match_confidence = (
            prod(confidence_scores) ** (1.0 / len(confidence_scores))
            if confidence_scores else 0.0
        )

        return merged

    def merge_duplicate_groups(self, groups: List[List[Contact]]) -> List[Contact]:
        """Merge each group of duplicates into single contacts"""
        if not groups:
            return []
            
        merged = []
        for group in groups:
            if not group:
                continue
                
            # Add all single-contact groups directly
            if len(group) == 1:
                merged.append(group[0])
            else:
                merged_contact = self.merge_contact_group(group)
                if merged_contact:
                    merged.append(merged_contact)
        
        return merged

    def _merge_addresses(self, addresses: List[Dict]) -> List[Dict]:
        """Merge multiple addresses, removing duplicates."""
        return self.address_processor.merge_addresses(addresses)

    def _calculate_group_confidence(self, scores: List[float]) -> float:
        """Calculate overall confidence score for merged group."""
        return sum(scores) / len(scores) if scores else 0.0
