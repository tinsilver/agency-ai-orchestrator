"""
Mock Google Drive Service for testing without real Google Drive API.
Maps fake file IDs to local test files.
"""
import os
from typing import Dict, Any, Optional
from docx import Document
import pypdf
import io


class MockGoogleDriveService:
    """Mock implementation of GoogleDriveService for testing."""
    
    # Map fake file IDs to local test files
    FILE_MAP = {
        "mock_file_id_docx": "test_files/test.docx",
        "mock_file_id_pdf": "test_files/test.pdf",
        "mock_file_id_jpg": "test_files/test.jpg",
        "mock_file_id_wireframe": "test_files/mockwireframe.png",
        # User requested aliases
        "mock_file_id_1": "test_files/mockwireframe.png",
        "mock_file_id_2": "test_files/test.docx",
        # Shorter aliases
        "test_docx": "test_files/test.docx",
        "test_pdf": "test_files/test.pdf",
        "test_jpg": "test_files/test.jpg",
        "test_png": "test_files/mockwireframe.png"
    }
    
    def __init__(self):
        self.service = "mock"  # Indicate this is a mock
    
    async def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get mock file metadata."""
        if file_id not in self.FILE_MAP:
            return None
        
        filepath = self.FILE_MAP[file_id]
        if not os.path.exists(filepath):
            return None
        
        # Determine mime type from extension
        ext = os.path.splitext(filepath)[1].lower()
        mime_map = {
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png'
        }
        
        return {
            "id": file_id,
            "name": os.path.basename(filepath),
            "mimeType": mime_map.get(ext, 'application/octet-stream'),
            "webViewLink": f"file://{os.path.abspath(filepath)}",
            "webContentLink": f"file://{os.path.abspath(filepath)}"
        }
    
    async def download_file(self, file_id: str) -> Optional[bytes]:
        """Read local file as bytes."""
        if file_id not in self.FILE_MAP:
            return None
        
        filepath = self.FILE_MAP[file_id]
        if not os.path.exists(filepath):
            return None
        
        try:
            with open(filepath, 'rb') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading mock file {filepath}: {e}")
            return None
    
    def extract_text_from_docx(self, file_bytes: bytes) -> str:
        """Extract text from a Word document."""
        try:
            doc = Document(io.BytesIO(file_bytes))
            text = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text.append(paragraph.text)
            
            return "\\n".join(text)
        except Exception as e:
            print(f"Error extracting text from DOCX: {e}")
            return ""
    
    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extract text from a PDF document."""
        try:
            pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            text = []
            
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
            
            return "\\n".join(text)
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""
    
    async def get_file_content(self, file_id: str) -> Dict[str, Any]:
        """
        Download file and extract content based on type.
        Returns dict with file metadata and extracted content.
        """
        metadata = await self.get_file_metadata(file_id)
        
        if not metadata:
            return {
                "file_id": file_id,
                "error": "Mock file not found"
            }
        
        mime_type = metadata.get('mimeType', '')
        filename = metadata.get('name', 'unknown')
        file_url = metadata.get('webViewLink', '')
        
        result = {
            "file_id": file_id,
            "filename": filename,
            "mime_type": mime_type,
            "drive_url": file_url,
            "extracted_content": None
        }
        
        # Extract text for document types
        if 'word' in mime_type or filename.endswith('.docx'):
            file_bytes = await self.download_file(file_id)
            if file_bytes:
                result["extracted_content"] = self.extract_text_from_docx(file_bytes)
                result["type"] = "document"
        
        elif 'pdf' in mime_type or filename.endswith('.pdf'):
            file_bytes = await self.download_file(file_id)
            if file_bytes:
                result["extracted_content"] = self.extract_text_from_pdf(file_bytes)
                result["type"] = "document"
        
        elif 'image' in mime_type:
            # For images, we don't extract text here
            # Could add Claude Vision API processing later
            result["type"] = "image"
            result["extracted_content"] = f"[Image: {filename}]"
        
        else:
            result["type"] = "other"
        
        return result


# For backwards compatibility and testing
async def test_mock_service():
    """Test the mock service with sample file IDs."""
    service = MockGoogleDriveService()
    
    print("Testing Mock Google Drive Service...")
    test_ids = ["test_docx", "test_pdf", "test_jpg"]
    
    for file_id in test_ids:
        print(f"\\nProcessing: {file_id}")
        content = await service.get_file_content(file_id)
        print(f"  Filename: {content.get('filename')}")
        print(f"  Type: {content.get('type')}")
        print(f"  Content preview: {content.get('extracted_content', '')[:100]}...")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_mock_service())
