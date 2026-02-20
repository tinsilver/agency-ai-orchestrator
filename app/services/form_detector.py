"""
FormDetectorService: Detect and analyze forms on web pages.
"""
from typing import Dict, Any, List, Optional
from langfuse import observe
from bs4 import BeautifulSoup
from app.services.web_scraper import WebScraperService


class FormDetectorService:
    """
    Detects forms on web pages and extracts their structure.
    Extends WebScraperService functionality.
    """

    def __init__(self):
        self.web_scraper = WebScraperService()

    @observe(name="form-detector")
    async def detect_forms(self, url: str) -> Dict[str, Any]:
        """
        Detect all forms on a webpage and analyze their structure.

        Args:
            url: URL to analyze

        Returns:
            Dict with form information or error
        """
        # First, scrape the page
        scrape_result = await self.web_scraper.scrape_url(url)

        if scrape_result.get("error"):
            return {"error": f"Failed to fetch page: {scrape_result['error']}"}

        html_content = scrape_result.get("html", "")
        if not html_content:
            return {"error": "No HTML content available"}

        # Parse forms
        forms = self._parse_forms(html_content, url)

        return {
            "url": url,
            "forms_found": len(forms),
            "forms": forms,
            "has_contact_form": any(self._is_contact_form(form) for form in forms),
            "has_newsletter_form": any(self._is_newsletter_form(form) for form in forms),
            "has_search_form": any(self._is_search_form(form) for form in forms)
        }

    def _parse_forms(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """
        Parse all forms from HTML content.

        Args:
            html: HTML content
            base_url: Base URL for resolving relative actions

        Returns:
            List of form dictionaries
        """
        soup = BeautifulSoup(html, 'html.parser')
        forms = soup.find_all('form')

        parsed_forms = []
        for idx, form in enumerate(forms):
            form_data = {
                'index': idx,
                'id': form.get('id', f'form-{idx}'),
                'name': form.get('name', ''),
                'action': form.get('action', ''),
                'method': form.get('method', 'GET').upper(),
                'fields': self._extract_fields(form),
                'classes': form.get('class', [])
            }

            # Determine form type
            form_data['type'] = self._determine_form_type(form_data)

            parsed_forms.append(form_data)

        return parsed_forms

    def _extract_fields(self, form) -> List[Dict[str, Any]]:
        """
        Extract all input fields from a form.

        Args:
            form: BeautifulSoup form element

        Returns:
            List of field dictionaries
        """
        fields = []
        inputs = form.find_all(['input', 'textarea', 'select'])

        for inp in inputs:
            field_type = inp.get('type', 'text')

            # Skip submit buttons
            if field_type in ['submit', 'button', 'image']:
                continue

            field = {
                'name': inp.get('name', ''),
                'id': inp.get('id', ''),
                'type': field_type,
                'placeholder': inp.get('placeholder', ''),
                'required': inp.has_attr('required'),
                'label': self._find_label(inp)
            }

            # Add options for select fields
            if inp.name == 'select':
                options = [opt.get_text(strip=True) for opt in inp.find_all('option')]
                field['options'] = options

            fields.append(field)

        return fields

    def _find_label(self, input_elem) -> Optional[str]:
        """
        Try to find the label associated with an input element.

        Args:
            input_elem: BeautifulSoup input element

        Returns:
            Label text if found, None otherwise
        """
        # Try by for attribute
        input_id = input_elem.get('id')
        if input_id:
            label = input_elem.find_previous('label', {'for': input_id})
            if label:
                return label.get_text(strip=True)

        # Try parent label
        parent_label = input_elem.find_parent('label')
        if parent_label:
            return parent_label.get_text(strip=True)

        # Try nearest previous label
        prev_label = input_elem.find_previous('label')
        if prev_label:
            return prev_label.get_text(strip=True)

        return None

    def _determine_form_type(self, form_data: Dict[str, Any]) -> str:
        """
        Determine the type of form based on its fields and attributes.

        Args:
            form_data: Parsed form data

        Returns:
            Form type string
        """
        fields = form_data['fields']
        field_names = [f['name'].lower() for f in fields if f['name']]
        field_labels = [f['label'].lower() if f['label'] else '' for f in fields]
        all_text = ' '.join(field_names + field_labels + form_data['classes'])

        # Contact form detection
        if any(keyword in all_text for keyword in ['contact', 'message', 'inquiry', 'email', 'phone']):
            if any(keyword in all_text for keyword in ['message', 'comment', 'inquiry']):
                return 'contact'

        # Newsletter/subscription form
        if any(keyword in all_text for keyword in ['newsletter', 'subscribe', 'subscription']):
            return 'newsletter'

        # Search form
        if any(keyword in all_text for keyword in ['search', 'query']):
            return 'search'

        # Login form
        if 'password' in field_names or 'passwd' in all_text:
            return 'login'

        # Registration form
        if any(keyword in all_text for keyword in ['register', 'signup', 'sign-up']):
            return 'registration'

        # Payment/checkout form
        if any(keyword in all_text for keyword in ['payment', 'checkout', 'billing', 'card']):
            return 'payment'

        return 'other'

    def _is_contact_form(self, form: Dict[str, Any]) -> bool:
        """Check if form is a contact form."""
        return form['type'] == 'contact'

    def _is_newsletter_form(self, form: Dict[str, Any]) -> bool:
        """Check if form is a newsletter subscription form."""
        return form['type'] == 'newsletter'

    def _is_search_form(self, form: Dict[str, Any]) -> bool:
        """Check if form is a search form."""
        return form['type'] == 'search'
