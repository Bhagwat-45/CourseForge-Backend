import fitz  # PyMuPDF
from youtube_transcript_api import YouTubeTranscriptApi
from bs4 import BeautifulSoup
import requests
import re
import io

class IngestionService:
    @staticmethod
    def extract_text_from_pdf(file_content: bytes) -> str:
        """Extracts text from a PDF byte stream."""
        pdf_file = fitz.open(stream=file_content, filetype="pdf")
        text = ""
        for page in pdf_file:
            text += page.get_text()
        return text

    @staticmethod
    def extract_youtube_transcript(url: str) -> str:
        """Extracts transcript from a YouTube video URL."""
        video_id = None
        # Extract video ID using regex
        regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
        match = re.search(regex, url)
        if match:
            video_id = match.group(1)
        
        if not video_id:
            raise ValueError("Invalid YouTube URL")

        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            return " ".join([t['text'] for t in transcript_list])
        except Exception as e:
            raise Exception(f"Failed to fetch YouTube transcript: {str(e)}")

    @staticmethod
    def scrape_web_page(url: str) -> str:
        """Scrapes text content from a web page."""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Break into lines and remove leading/trailing whitespace
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Drop blank lines
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text
        except Exception as e:
            raise Exception(f"Failed to scrape web page: {str(e)}")

ingestion_service = IngestionService()
