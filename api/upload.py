"""
File upload and processing endpoints
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import os
import aiofiles
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from services.file_processor import FileProcessor
from services.course_generator import CourseGenerator
from app.core.database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends
import uuid

router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_file(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    link: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload a file, text, or link to generate a course.
    Accepts: PDF, images, audio, video, text, or URL
    """
    try:
        processor = FileProcessor()
        generator = CourseGenerator()
        
        # Determine input type and extract content
        if file:
            # Save uploaded file
            file_id = str(uuid.uuid4())
            file_ext = os.path.splitext(file.filename)[1]
            file_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_ext}")
            
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            # Process file based on type
            content_text = await processor.process_file(file_path, file.content_type)
            source_type = processor.get_source_type(file.content_type)
            
        elif text:
            content_text = text
            file_path = None
            source_type = "text"
            
        elif link:
            content_text = await processor.process_link(link)
            file_path = None
            source_type = "link"
            
        else:
            raise HTTPException(status_code=400, detail="No input provided")
        
        # Generate course from extracted content
        course_data = await generator.generate_course(content_text, source_type, file_path)
        
        # Save course to database
        course = generator.save_course_to_db(db, course_data)
        
        return JSONResponse({
            "success": True,
            "course_id": course.id,
            "title": course.title,
            "message": "Course generated successfully"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")


@router.get("/upload/status/{course_id}")
async def get_upload_status(course_id: int, db: Session = Depends(get_db)):
    """Get the status of course generation"""
    from app.models import Course
    
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    return {
        "course_id": course.id,
        "title": course.title,
        "status": "completed" if course.modules else "processing"
    }

