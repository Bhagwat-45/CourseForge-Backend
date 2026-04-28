"""
File processing service - handles PDF, images, audio, video, links
"""
import os
import pdfplumber
import pytesseract
from PIL import Image
import requests
from bs4 import BeautifulSoup
from typing import Optional
import asyncio

# Optional imports
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# Configure Tesseract path (Windows)
if os.name == 'nt':
    tesseract_path = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path


class FileProcessor:
    """Processes various file types and extracts text content"""
    
    def get_source_type(self, content_type: Optional[str]) -> str:
        """Determine source type from content type"""
        if not content_type:
            return "unknown"
        
        if "pdf" in content_type.lower():
            return "pdf"
        elif "image" in content_type.lower():
            return "image"
        elif "audio" in content_type.lower():
            return "audio"
        elif "video" in content_type.lower():
            return "video"
        else:
            return "text"
    
    async def process_file(self, file_path: str, content_type: Optional[str]) -> str:
        """Process a file and extract text content"""
        source_type = self.get_source_type(content_type)
        
        if source_type == "pdf":
            return await self._process_pdf(file_path)
        elif source_type == "image":
            return await self._process_image(file_path)
        elif source_type == "audio":
            return await self._process_audio(file_path)
        elif source_type == "video":
            return await self._process_video(file_path)
        else:
            # Try to read as text
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
    
    async def _process_pdf(self, file_path: str) -> str:
        """Extract text from PDF"""
        text_content = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
        except Exception as e:
            print(f"Error processing PDF: {e}")
            return ""
        return "\n\n".join(text_content)
    
    async def _process_image(self, file_path: str) -> str:
        """Extract text from image using OCR"""
        try:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            return text
        except Exception as e:
            print(f"Error processing image: {e}")
            return ""
    
    async def _process_audio(self, file_path: str) -> str:
        """Extract text from audio using Whisper"""
        if not WHISPER_AVAILABLE:
            return "Audio processing requires whisper package. Install with: pip install openai-whisper"
        try:
            model = whisper.load_model("base")
            result = model.transcribe(file_path)
            return result["text"]
        except Exception as e:
            print(f"Error processing audio: {e}")
            return ""
    
    async def _process_video(self, file_path: str) -> str:
        """Extract audio from video and transcribe"""
        if not WHISPER_AVAILABLE:
            return "Video processing requires whisper package. Install with: pip install openai-whisper"
        try:
            # For now, use Whisper directly on video (it can handle video files)
            model = whisper.load_model("base")
            result = model.transcribe(file_path)
            return result["text"]
        except Exception as e:
            print(f"Error processing video: {e}")
            return ""
    
    async def process_link(self, url: str) -> str:
        """Extract content from a URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
        except Exception as e:
            print(f"Error processing link: {e}")
            return f"Error fetching content from {url}: {str(e)}"

