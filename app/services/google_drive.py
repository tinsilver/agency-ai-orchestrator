import os
import io
from typing import Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from docx import Document
import PyPDF2
from dotenv import load_dotenv

load_dotenv()

class GoogleDriveService:
    """Service for downloading and extracting content from Google Drive files."""
    
    def __init__(self):
        # Load service account credentials from environment
        credentials_json = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
        
        if credentials_json:
            import json
            creds_dict = json.loads(credentials_json)
            self.credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
            self.service = build('drive', 'v3', credentials=self.credentials)
        else:
            print("Warning: GOOGLE_DRIVE_CREDENTIALS not found. File processing disabled.")
            self.service = None
    
    async def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata from Google Drive."""
        if not self.service:
            return None
            
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, webViewLink, webContentLink'
            ).execute()
            return file
        except Exception as e:
            print(f"Error getting file metadata for {file_id}: {e}")
            return None
    
    async def download_file(self, file_id: str) -> Optional[bytes]:
        """Download file content as bytes."""
        if not self.service:
            return None
            
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_buffer.seek(0)
            return file_buffer.getvalue()
        except Exception as e:
            print(f"Error downloading file {file_id}: {e}")
            return None
    
    def extract_text_from_docx(self, file_bytes: bytes) -> str:
        """Extract text from a Word document."""
        try:
            doc = Document(io.BytesIO(file_bytes))
            text = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text.append(paragraph.text)
            
            return "\n".join(text)
        except Exception as e:
            print(f"Error extracting text from DOCX: {e}")
            return ""
    
    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extract text from a PDF document."""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text = []
            
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
            
            return "\n".join(text)
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
                "error": "Could not fetch file metadata"
            }
        
        mime_type = metadata.get('mimeType', '')
        filename = metadata.get('name', 'unknown')
        drive_url = metadata.get('webViewLink', '')
        
        result = {
            "file_id": file_id,
            "filename": filename,
            "mime_type": mime_type,
            "drive_url": drive_url,
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
        
        else:
            result["type"] = "other"
        
        return result
