"""
PDFExtractorService: Extract text and metadata from PDF files.
"""
from typing import Dict, Any, List
from langfuse import observe
from pathlib import Path
import re


class PDFExtractorService:
    """
    Extracts text content and metadata from PDF files.
    Useful for brand guidelines, specifications, mockups with text.
    """

    @observe(name="pdf-extractor")
    async def extract(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text and metadata from a PDF file.

        Args:
            file_path: Path to PDF file

        Returns:
            Dict with extracted content or error
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return {"error": f"File not found: {file_path}"}

            if not path.suffix.lower() == '.pdf':
                return {"error": f"Not a PDF file: {file_path}"}

            # Extract text using pypdf
            text_content = self._extract_text_pypdf(file_path)

            # Extract structured information
            structured_data = self._extract_structured_info(text_content)

            return {
                "file_path": file_path,
                "file_name": path.name,
                "text_content": text_content,
                "text_length": len(text_content),
                "page_count": structured_data.get("page_count", 0),
                "colors": structured_data.get("colors", []),
                "fonts": structured_data.get("fonts", []),
                "urls": structured_data.get("urls", []),
                "emails": structured_data.get("emails", []),
                "is_brand_guidelines": structured_data.get("is_brand_guidelines", False)
            }

        except Exception as e:
            return {"error": f"PDF extraction failed: {str(e)}"}

    def _extract_text_pypdf(self, file_path: str) -> str:
        """Extract text using pypdf library."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(file_path)
            text_parts = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            full_text = "\n\n".join(text_parts)
            return full_text

        except ImportError:
            return "pypdf library not installed"
        except Exception as e:
            return f"Error extracting text: {str(e)}"

    def _extract_structured_info(self, text: str) -> Dict[str, Any]:
        """
        Extract structured information from PDF text.

        Args:
            text: Extracted text content

        Returns:
            Dict with structured data
        """
        structured = {}

        # Extract hex color codes
        color_pattern = r'#(?:[0-9a-fA-F]{3}){1,2}\b'
        colors = list(set(re.findall(color_pattern, text)))
        structured["colors"] = colors

        # Extract font names (common fonts)
        common_fonts = [
            'Arial', 'Helvetica', 'Times New Roman', 'Georgia',
            'Verdana', 'Courier', 'Comic Sans', 'Impact',
            'Montserrat', 'Open Sans', 'Roboto', 'Lato', 'Raleway',
            'Poppins', 'Inter', 'Nunito', 'Proxima Nova'
        ]
        fonts = []
        text_lower = text.lower()
        for font in common_fonts:
            if font.lower() in text_lower:
                fonts.append(font)
        structured["fonts"] = list(set(fonts))

        # Extract URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+|www\.[^\s<>"{}|\\^`\[\]]+'
        urls = list(set(re.findall(url_pattern, text)))
        structured["urls"] = urls

        # Extract email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = list(set(re.findall(email_pattern, text)))
        structured["emails"] = emails

        # Estimate page count (rough estimate based on text length)
        estimated_pages = max(1, len(text) // 3000)  # ~3000 chars per page
        structured["page_count"] = estimated_pages

        # Detect if it's brand guidelines
        brand_keywords = ['brand', 'guidelines', 'style guide', 'color palette', 'logo usage', 'typography']
        is_brand_guidelines = sum(1 for keyword in brand_keywords if keyword.lower() in text_lower) >= 3
        structured["is_brand_guidelines"] = is_brand_guidelines

        return structured

    def format_for_display(self, extracted_data: Dict[str, Any]) -> str:
        """
        Format extracted PDF data for human-readable display.

        Args:
            extracted_data: Extracted PDF data

        Returns:
            Formatted string
        """
        if "error" in extracted_data:
            return f"Error: {extracted_data['error']}"

        output = [
            f"📄 {extracted_data['file_name']}",
            f"Pages: ~{extracted_data['page_count']}",
            f"Text length: {extracted_data['text_length']} characters"
        ]

        if extracted_data.get('colors'):
            output.append(f"Colors found: {', '.join(extracted_data['colors'])}")

        if extracted_data.get('fonts'):
            output.append(f"Fonts mentioned: {', '.join(extracted_data['fonts'])}")

        if extracted_data.get('is_brand_guidelines'):
            output.append("✅ Appears to be brand guidelines document")

        return "\n".join(output)
