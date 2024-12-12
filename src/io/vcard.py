from typing import List, Dict, Optional
import vobject
from ..core.contact import Contact
from ..processors.address import AddressValidationMode, AddressProcessor, string_to_address_dict


class VCardHandler:
    """Handles reading and writing contacts in vCard format"""

    def read_vcard(self, filepath: str) -> List[Contact]:
        """Read contacts from vCard file"""
        contacts = []
        with open(filepath, "r", encoding="utf-8") as f:
            vcards = vobject.readComponents(f.read())
            for vcard in vcards:
                contact_data = self._parse_vcard(vcard)
                contact = Contact.from_dict(contact_data)
                contacts.append(contact)
        return contacts

    def write_vcard(self, contacts: List[Contact], filepath: str) -> None:
        """Write contacts to vCard file"""
        with open(filepath, "w", encoding="utf-8") as f:
            for contact in contacts:
                vcard = self._create_vcard(contact)
                f.write(vcard.serialize())

    def _parse_vcard(self, vcard: vobject.vCard) -> Dict:
        """Convert vCard to contact dictionary"""
        data = {
            "Full Name": self._get_vcard_value(vcard, "fn"),
            "FirstName": "",
            "LastName": "",
            "Organization": self._get_vcard_value(vcard, "org"),
            "Email": self._get_vcard_values(vcard, "email"),
            "Telephone": self._get_vcard_values(vcard, "tel"),
        }

        # Handle structured name
        if hasattr(vcard, "n") and vcard.n.value:
            data["LastName"] = vcard.n.value.family
            data["FirstName"] = vcard.n.value.given

        # Handle addresses
        if hasattr(vcard, "adr"):
            addresses = []
            for adr in vcard.adr_list:
                address = self._parse_vcard_address(adr)
                if address:
                    addresses.append(address)
            data["Address"] = addresses

        return data

    def _create_vcard(self, contact: Contact) -> vobject.vCard:
        """Convert contact to vCard object"""
        vcard = vobject.vCard()

        # Add basic fields
        self._add_vcard_field(vcard, "fn", contact.full_name or "Unknown Contact")
        if contact.first_name or contact.last_name:
            vcard.add("n")
            vcard.n.value = vobject.vcard.Name(
                family=contact.last_name or "", given=contact.first_name or ""
            )

        # Add organization
        if contact.organization:
            self._add_vcard_field(vcard, "org", contact.organization)

        # Add emails
        for email in contact.emails:
            self._add_vcard_field(vcard, "email", email)

        # Add phones
        for phone in contact.phones:
            self._add_vcard_field(vcard, "tel", phone)

        # Add addresses
        for address in contact.addresses:
            self._add_vcard_address(vcard, address)

        return vcard

    @staticmethod
    def _get_vcard_value(vcard: vobject.vCard, field: str) -> str:
        """Safely get single value from vCard field"""
        if hasattr(vcard, field):
            return getattr(vcard, field).value
        return ""

    @staticmethod
    def _get_vcard_values(vcard: vobject.vCard, field: str) -> List[str]:
        """Safely get multiple values from vCard field"""
        values = []
        if hasattr(vcard, field):
            field_list = getattr(vcard, f"{field}_list")
            for f in field_list:
                values.append(f.value)
        return values

    @staticmethod
    def _parse_vcard_address(adr) -> Optional[Dict]:
        """Parse vCard address into dictionary"""
        if not adr.value:
            return None

        return {
            "po_box": adr.value.box,
            "extended": adr.value.extended,
            "street": adr.value.street,
            "locality": adr.value.city,
            "region": adr.value.region,
            "postal_code": adr.value.code,
            "country": adr.value.country,
            "type": getattr(adr, "type_param", []),
        }

    @staticmethod
    def _add_vcard_field(vcard: vobject.vCard, field: str, value: str) -> None:
        """Add field to vCard"""
        if value:
            vcard.add(field)
            getattr(vcard, field).value = value

    @staticmethod
    def _add_vcard_address(vcard: vobject.vCard, address: Dict) -> None:
        """Add address to vCard"""
        if not address:
            return

        vcard.add("adr")
        vcard.adr.value = vobject.vcard.Address(
            box=address.get("po_box", ""),
            extended=address.get("extended", ""),
            street=address.get("street", ""),
            city=address.get("locality", ""),
            region=address.get("region", ""),
            code=address.get("postal_code", ""),
            country=address.get("country", ""),
        )

        if "type" in address:
            vcard.adr.type_param = address["type"]
