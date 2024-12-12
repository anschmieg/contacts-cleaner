import re
from typing import List, Dict
from .contact import Contact
from ..processors.name import NameProcessor
from ..processors.address import AddressProcessor, AddressValidationMode


class ContactMerger:
    def __init__(
        self, name_processor: NameProcessor, address_processor: AddressProcessor
    ):
        self.name_processor = name_processor
        self.address_processor = address_processor
        self.matcher = ContactMatcher(name_processor)

    def merge_contact_group(
        self, duplicates: List[Contact], validation_mode=AddressValidationMode.FULL
    ) -> Contact:
        """Merge a group of duplicate contacts into one"""
        if not duplicates:
            return None

        merged = Contact(full_name="")
        confidence_scores = []

        # Process first and last names
        first_names = set()
        last_names = set()

        # Extract names from duplicates
        for duplicate in duplicates:
            # Name handling
            if duplicate.first_name:
                first_names.update(n.strip() for n in duplicate.first_name.split(","))
            if duplicate.last_name:
                last_names.update(n.strip() for n in duplicate.last_name.split(","))

            # Process other fields
            merged.emails.extend(duplicate.emails)
            merged.phones.extend(duplicate.phones)
            merged.addresses.extend(duplicate.addresses)

            # Calculate confidence
            confidence = self.matcher.calculate_match_confidence(
                duplicates[0], duplicate
            )
            confidence_scores.append(confidence)

        # Merge names using name processor
        if first_names:
            merged.first_name = self.name_processor.merge_names(list(first_names))
        if last_names:
            merged.last_name = self.name_processor.merge_names(list(last_names))

        # Update merged contact
        merged.full_name = " ".join(filter(None, [merged.first_name, merged.last_name]))
        merged.emails = list(set(merged.emails))
        merged.phones = list(set(merged.phones))
        merged.addresses = self._merge_addresses(merged.addresses)
        merged.match_confidence = self._calculate_group_confidence(confidence_scores)

        return merged

    def merge_duplicates(
        self, contacts: list, validation_mode=AddressValidationMode.FULL
    ) -> list:
        """Optimized duplicate detection and merging"""
        if not contacts:
            return []

        # Create contact index and mapping of merged contacts
        contact_index = self._create_contact_index(contacts)
        merged_groups_map = {}  # Track which contacts belong to which merged group

        # Cache for comparison results
        comparison_cache = {}
        processed = set()
        merged_groups = []

        for contact in contacts:
            if id(contact) in processed:
                continue

            name = self.name_processor.get_index_key(contact.full_name).lower()
            first_chars = name[:3] if name else ""

            # Initialize new group with current contact
            current_group = [contact]
            merged_groups_map[id(contact)] = len(merged_groups)  # Map contact to its group

            # Find and process all matches for this contact
            if first_chars:
                # Get potential matches from index
                potential_matches = contact_index.get(first_chars, []).copy()
                # Add matches from similar blocks for typo handling
                for i in range(len(first_chars)):
                    variant = first_chars[:i] + first_chars[i + 1 :]
                    potential_matches.extend(contact_index.get(variant, []))

                # Check all potential matches
                for other in potential_matches:
                    if id(other) != id(contact) and id(other) not in processed:
                        if self.is_duplicate(contact, other):
                            current_group.append(other)
                            merged_groups_map[id(other)] = len(merged_groups)
                            processed.add(id(other))

            if len(current_group) > 1:
                merged_groups.append(current_group)
            processed.add(id(contact))

        # Store the merged groups mapping for later use in validation
        global _merged_groups_mapping
        _merged_groups_mapping = {"groups": merged_groups, "map": merged_groups_map}

        # Merge groups and remaining contacts
        result = []
        processed_in_groups = {id(c) for g in merged_groups for c in g}

        # Add merged groups
        for group in merged_groups:
            result.append(self.merge_contact_group(group, validation_mode))

        # Add non-duplicate contacts
        for contact in contacts:
            if id(contact) not in processed_in_groups:
                result.append(contact)

        return result


class ContactMatcher:
    def __init__(self, name_processor: NameProcessor):
        self.name_processor = name_processor
        self.comparison_cache = {}

    def is_duplicate(self, contact1: Contact, contact2: Contact, name_ratio=85, nickname_ratio=90, org_ratio=95) -> bool:
        """Match exact implementation from v1/process_contact.py"""
        if not contact1 or not contact2:
            return False

        # Cache check
        cache_key = tuple(sorted([id(contact1), id(contact2)]))
        if cache_key in self.comparison_cache:
            return self.comparison_cache[cache_key]

        # Get names and normalize them
        name1 = self.name_processor.get_contact_name(contact1).lower()
        name2 = self.name_processor.get_contact_name(contact2).lower()

        # Remove common titles and honorifics
        titles = {'prof', 'dr', 'professor', 'mr', 'mrs', 'ms', 'phd', 'md', 'i', 'ii', 'iii', 'iv', 'v'}
        for title in titles:
            name1 = re.sub(rf'\b{title}\b\.?\s*', '', name1)
            name2 = re.sub(rf'\b{title}\b\.?\s*', '', name2)

        # Split names into parts and remove empty/short parts
        parts1 = [p for p in name1.split() if len(p) > 2]
        parts2 = [p for p in name2.split() if len(p) > 2]

        # Count matching parts
        matching_parts = sum(1 for p1 in parts1 
                           for p2 in parts2 
                           if p1 == p2 or self.name_processor.string_similarity(p1, p2) > 0.8)

        # Calculate match ratio based on the number of matching parts
        total_parts = max(len(parts1), len(parts2))
        name_match_ratio = matching_parts / total_parts if total_parts > 0 else 0

        # Check phone numbers
        phones1 = set(contact1.phones)
        phones2 = set(contact2.phones)
        have_matching_phones = bool(phones1 and phones2 and phones1.intersection(phones2))

        # Consider it a match if:
        # 1. Phone numbers match exactly AND at least 1/3 of name parts match
        # 2. OR more than 2/3 of name parts match exactly
        result = (have_matching_phones and name_match_ratio >= 0.33) or name_match_ratio >= 0.67

        self.comparison_cache[cache_key] = result
        return result

    def calculate_match_confidence(self, contact1: Contact, contact2: Contact) -> float:
        """Match exact implementation from v1/process_contact.py"""
        score = 0.0
        weights = {
            'email': 1.0,
            'full_name': 1.0,
            'first_last': 0.9,
            'last_name': 0.6,
            'first_name': 0.4,
            'organization': 0.3,
            'street': 0.3,
            'city': 0.2,
            'postal_code': 0.3,
            'country': 0.1,
        }

        # Email comparison (exact match)
        if contact1.emails and contact2.emails:
            if any(e1.lower() == e2.lower() 
                  for e1 in contact1.emails 
                  for e2 in contact2.emails):
                score += weights['email']

        # Name comparisons
        if contact1.full_name and contact2.full_name:
            similarity = self.name_processor.string_similarity(
                contact1.full_name, contact2.full_name)
            if similarity > 0.9:
                score += weights['full_name'] * similarity

        # First + Last name comparison
        if (contact1.first_name and contact2.first_name and 
            contact1.last_name and contact2.last_name):
            first_sim = self.name_processor.string_similarity(
                contact1.first_name, contact2.first_name)
            last_sim = self.name_processor.string_similarity(
                contact1.last_name, contact2.last_name)
            if first_sim > 0.8 and last_sim > 0.8:
                score += weights['first_last'] * ((first_sim + last_sim) / 2)

        # Organization comparison
        if contact1.organization and contact2.organization:
            org_sim = self.name_processor.string_similarity(
                contact1.organization, contact2.organization)
            if org_sim > 0.8:
                score += weights['organization'] * org_sim

        # Address components comparison
        if contact1.addresses and contact2.addresses:
            for addr1 in contact1.addresses:
                for addr2 in contact2.addresses:
                    for field, weight_key in [
                        ('street', 'street'),
                        ('locality', 'city'),
                        ('postal_code', 'postal_code'),
                        ('country', 'country')
                    ]:
                        val1 = addr1.get(field, '')
                        val2 = addr2.get(field, '')
                        if val1 and val2:
                            similarity = self.name_processor.string_similarity(val1, val2)
                            if similarity > 0.8:
                                score += weights[weight_key] * similarity

        return min(1.0, score)

    def find_duplicates(self, contacts: List[Contact]) -> List[List[Contact]]:
        """Find groups of duplicate contacts using optimized indexing"""
        if not contacts:
            return []

        contact_index = self._create_contact_index(contacts) 
        processed = set()
        groups = []

        # First pass: find duplicate groups
        for contact in contacts:
            if id(contact) in processed:
                continue

            group = [contact]
            key = self.name_processor.get_index_key(contact.full_name)

            if key in contact_index:
                for other in contact_index[key]:
                    if id(other) != id(contact) and id(other) not in processed:
                        if self.is_duplicate(contact, other):
                            group.append(other)
                            processed.add(id(other))

            if len(group) > 1:  # Changed: only add to groups if duplicates found
                groups.append(group)
            processed.add(id(contact))

        # Second pass: add all unique contacts as single-item groups
        for contact in contacts:
            if id(contact) not in processed:
                groups.append([contact])  # Add single contact as its own group
                processed.add(id(contact))

        # Sort groups by size in descending order to process duplicates first
        groups.sort(key=len, reverse=True)
        return groups

    def _calculate_detail_score(self, contact1: Contact, contact2: Contact) -> float:
        """Calculate match confidence based on contact details"""
        scores = []
        
        # Email match
        if self._compare_emails(contact1, contact2):
            scores.append(1.0)
        
        # Phone match
        if self._compare_phones(contact1, contact2):
            scores.append(1.0)
            
        # Address match (simplified for now)
        if self._compare_addresses(contact1, contact2):
            scores.append(0.8)  # Lower weight for simple address comparison
            
        return max(scores) if scores else 0.0

    def _create_contact_index(
        self, contacts: List[Contact]
    ) -> Dict[str, List[Contact]]:
        """Create optimized index for contact matching"""
        index = {}
        for contact in contacts:
            key = self.name_processor.get_index_key(contact.full_name)
            if key:
                if key not in index:
                    index[key] = []
                index[key].append(contact)
        return index

    def _group_duplicates(
        self, contacts: List[Contact], index: Dict[str, List[Contact]]
    ) -> List[List[Contact]]:
        """Group duplicate contacts using the index"""
        processed = set()
        groups = []

        for contact in contacts:
            if id(contact) in processed:
                continue

            group = [contact]
            key = self.name_processor.get_index_key(contact.full_name)

            if key in index:
                for other in index[key]:
                    if id(other) != id(contact) and id(other) not in processed:
                        if self.is_duplicate(contact, other):
                            group.append(other)
                            processed.add(id(other))

            if len(group) > 1:
                groups.append(group)
            processed.add(id(contact))

        return groups

    def _compare_names(self, contact1: Contact, contact2: Contact) -> float:
        """Compare names using NameProcessor"""
        # Extract all name variants from both contacts
        variants1 = self.name_processor.extract_name_variants(contact1)
        variants2 = self.name_processor.extract_name_variants(contact2)
        
        max_similarity = 0.0
        # Compare each combination of names
        for name1 in variants1:
            for name2 in variants2:
                similarity = self.name_processor.compare_names(name1, name2)
                max_similarity = max(max_similarity, similarity)
        
        return max_similarity

    def _calculate_name_score(self, contact1: Contact, contact2: Contact) -> float:
        """Calculate name match confidence using NameProcessor"""
        variants1 = self.name_processor.extract_name_variants(contact1)
        variants2 = self.name_processor.extract_name_variants(contact2)
        
        max_score = 0.0
        for name1 in variants1:
            for name2 in variants2:
                score = self.name_processor.compare_names(name1, name2)
                max_score = max(max_score, score)
        
        return max_score

    def _compare_emails(self, contact1: Contact, contact2: Contact) -> bool:
        return bool(set(contact1.emails) & set(contact2.emails))

    def _compare_phones(self, contact1: Contact, contact2: Contact) -> bool:
        return bool(set(contact1.phones) & set(contact2.phones))

    def _compare_addresses(self, contact1: Contact, contact2: Contact) -> bool:
        # Simple address comparison
        return True  # Implement actual comparison

# Remove these duplicate functions as they're now in NameProcessor
# - split_name_variants
# - has_conflicting_names
# - is_likely_nickname
# - string_similarity
