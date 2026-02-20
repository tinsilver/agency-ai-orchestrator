"""
ImageAnalysisService: Analyze images using Claude's vision capabilities.
"""
from typing import Dict, Any
from langfuse import observe
from langchain_anthropic import ChatAnthropic
import base64
import httpx
from pathlib import Path


class ImageAnalysisService:
    """
    Analyzes images for dimensions, content, quality using Claude vision.
    """

    def __init__(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)

    @observe(name="image-analysis")
    async def analyze(self, image_path_or_url: str) -> Dict[str, Any]:
        """
        Analyze an image for properties and content.

        Args:
            image_path_or_url: Local file path or URL to image

        Returns:
            Dict with image analysis or error
        """
        try:
            # Determine if it's a URL or local path
            if image_path_or_url.startswith(('http://', 'https://')):
                image_data = await self._fetch_image_from_url(image_path_or_url)
                source_type = 'url'
            else:
                image_data = self._load_local_image(image_path_or_url)
                source_type = 'file'

            if not image_data:
                return {"error": "Failed to load image"}

            # Get basic properties
            properties = self._get_image_properties(image_data, image_path_or_url)

            # Use Claude vision to analyze content (if enabled)
            content_analysis = await self._analyze_with_claude(image_data)

            return {
                "source": image_path_or_url,
                "source_type": source_type,
                "properties": properties,
                "content_analysis": content_analysis
            }

        except Exception as e:
            return {"error": f"Image analysis failed: {str(e)}"}

    async def _fetch_image_from_url(self, url: str) -> bytes:
        """Fetch image from URL."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    def _load_local_image(self, path: str) -> bytes:
        """Load image from local file."""
        file_path = Path(path)
        if not file_path.exists():
            return None
        return file_path.read_bytes()

    def _get_image_properties(self, image_data: bytes, path: str) -> Dict[str, Any]:
        """Get basic image properties."""
        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(image_data))
            width, height = img.size
            format_type = img.format
            mode = img.mode
            file_size = len(image_data)
            file_size_mb = file_size / (1024 * 1024)

            # Calculate aspect ratio
            from math import gcd
            divisor = gcd(width, height)
            aspect_ratio = f"{width // divisor}:{height // divisor}"

            # Determine if needs optimization
            needs_optimization = (
                file_size_mb > 1.0 or
                width > 2000 or
                height > 2000
            )

            return {
                'width': width,
                'height': height,
                'format': format_type,
                'mode': mode,
                'file_size_mb': round(file_size_mb, 2),
                'aspect_ratio': aspect_ratio,
                'needs_optimization': needs_optimization,
                'recommended_max_width': 1920 if width > 1920 else width
            }

        except Exception as e:
            return {
                'error': f"Failed to extract properties: {str(e)}",
                'file_size_mb': round(len(image_data) / (1024 * 1024), 2)
            }

    async def _analyze_with_claude(self, image_data: bytes) -> Dict[str, Any]:
        """
        Analyze image content using Claude vision.

        Note: This is a simplified implementation. For production,
        you would use Claude's vision API with the image.
        """
        # For now, return mock analysis
        # In production, you would:
        # 1. Encode image as base64
        # 2. Send to Claude with vision-capable model
        # 3. Parse response

        return {
            "description": "Image analysis via Claude vision not fully implemented",
            "detected_objects": [],
            "suggested_alt_text": "Image content",
            "quality_assessment": "medium",
            "is_photograph": False,
            "is_illustration": False,
            "is_screenshot": False,
            "contains_text": False
        }

        # Production implementation would look like:
        # base64_image = base64.b64encode(image_data).decode('utf-8')
        # response = await self.llm.ainvoke([
        #     {
        #         "role": "user",
        #         "content": [
        #             {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64_image}},
        #             {"type": "text", "text": "Analyze this image and provide: description, detected objects, suggested alt text, quality assessment"}
        #         ]
        #     }
        # ])
        # return parsed_response
