import os
import uuid
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
from datetime import datetime

from downloader import YTDownloader
from convert import VideoConverter
from cloudinary_uploader import CloudinaryUploader
from utils import setup_directories, cleanup_temp_files

# Initialize FastAPI app
app = FastAPI(title="YouTube Video Downloader API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup directories
setup_directories()

# Initialize services
downloader = YTDownloader()
converter = VideoConverter()
uploader = CloudinaryUploader()

# In-memory task storage (use Redis in production)
tasks: Dict[str, Dict[str, Any]] = {}

class DownloadRequest(BaseModel):
    url: str
    cookies: Optional[str] = None

class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: Optional[str] = None
    error: Optional[str] = None
    cloudinary_url: Optional[str] = None

def save_task_log(task_id: str, log_data: Dict[str, Any]):
    """Save task log to file"""
    log_file = f"logs/{task_id}.json"
    try:
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2, default=str)
    except Exception as e:
        print(f"Failed to save log for task {task_id}: {e}")

async def process_download(task_id: str, url: str, cookies: Optional[str] = None):
    """Background task to process video download"""
    log_data = {
        "task_id": task_id,
        "url": url,
        "started_at": datetime.now(),
        "user_agent": "YouTube Downloader API v1.0",
        "steps": []
    }
    
    try:
        # Update status: downloading
        tasks[task_id]["status"] = "downloading"
        tasks[task_id]["progress"] = "Connecting to YouTube..."
        log_data["steps"].append({"step": "download_start", "timestamp": datetime.now()})
        
        # Download video
        download_result = await downloader.download(url, cookies)
        if not download_result["success"]:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = download_result["error"]
            log_data["steps"].append({
                "step": "download_failed", 
                "timestamp": datetime.now(),
                "error": download_result["error"]
            })
            save_task_log(task_id, log_data)
            return
        
        video_path = download_result["file_path"]
        log_data["steps"].append({
            "step": "download_success", 
            "timestamp": datetime.now(),
            "file_path": video_path
        })
        
        # Update status: converting
        tasks[task_id]["status"] = "converting"
        tasks[task_id]["progress"] = "Converting video..."
        log_data["steps"].append({"step": "convert_start", "timestamp": datetime.now()})
        
        # Convert video
        convert_result = await converter.convert(video_path)
        if not convert_result["success"]:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = convert_result["error"]
            log_data["steps"].append({
                "step": "convert_failed", 
                "timestamp": datetime.now(),
                "error": convert_result["error"]
            })
            save_task_log(task_id, log_data)
            return
        
        converted_path = convert_result["file_path"]
        log_data["steps"].append({
            "step": "convert_success", 
            "timestamp": datetime.now(),
            "file_path": converted_path
        })
        
        # Update status: uploading
        tasks[task_id]["status"] = "uploading"
        tasks[task_id]["progress"] = "Uploading to Cloudinary..."
        log_data["steps"].append({"step": "upload_start", "timestamp": datetime.now()})
        
        # Upload to Cloudinary
        upload_result = await uploader.upload(converted_path)
        if not upload_result["success"]:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = upload_result["error"]
            log_data["steps"].append({
                "step": "upload_failed", 
                "timestamp": datetime.now(),
                "error": upload_result["error"]
            })
            save_task_log(task_id, log_data)
            return
        
        # Update status: completed
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["cloudinary_url"] = upload_result["url"]
        tasks[task_id]["progress"] = "Completed successfully!"
        log_data["steps"].append({
            "step": "upload_success", 
            "timestamp": datetime.now(),
            "cloudinary_url": upload_result["url"]
        })
        log_data["completed_at"] = datetime.now()
        
        # Cleanup temp files
        cleanup_temp_files([video_path, converted_path])
        
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = f"Unexpected error: {str(e)}"
        log_data["steps"].append({
            "step": "unexpected_error", 
            "timestamp": datetime.now(),
            "error": str(e)
        })
        print(f"Unexpected error in task {task_id}: {e}")
    
    finally:
        save_task_log(task_id, log_data)

@app.post("/api/download")
async def download_video(request: DownloadRequest, background_tasks: BackgroundTasks):
    """Start video download process"""
    # Validate and sanitize inputs
    if not isinstance(request.url, str):
        raise HTTPException(status_code=400, detail="URL must be a string")
    
    if request.cookies is not None and not isinstance(request.cookies, str):
        raise HTTPException(status_code=400, detail="Cookies must be a string")
    
    task_id = str(uuid.uuid4())
    
    # Initialize task
    tasks[task_id] = {
        "status": "pending",
        "progress": "Initializing...",
        "error": None,
        "cloudinary_url": None
    }
    
    # Start background task
    background_tasks.add_task(process_download, task_id, request.url, request.cookies)
    
    return {"task_id": task_id, "status": "pending"}

@app.get("/api/status/{task_id}")
async def get_task_status(task_id: str):
    """Get task status"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskStatus(
        task_id=task_id,
        status=tasks[task_id]["status"],
        progress=tasks[task_id]["progress"],
        error=tasks[task_id]["error"],
        cloudinary_url=tasks[task_id]["cloudinary_url"]
    )

@app.post("/api/upload-cookies")
async def upload_cookies(file: UploadFile = File(...)):
    """Upload cookies.txt file"""
    if not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="File must be a .txt file")
    
    try:
        content = await file.read()
        cookies_path = "cookies.txt"
        
        # Try to decode as text first
        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            # If UTF-8 fails, try other encodings
            try:
                text_content = content.decode('latin-1')
            except UnicodeDecodeError:
                raise HTTPException(status_code=400, detail="Unable to decode cookie file. Please ensure it's a valid text file.")
        
        # Validate cookies content
        if not validate_cookies_content(text_content):
            raise HTTPException(status_code=400, detail="Invalid cookie format. Please ensure you're uploading a valid cookies.txt file from your browser.")
        
        # Write cookies file
        with open(cookies_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        # Basic stats for user feedback
        lines = text_content.strip().split('\n')
        cookie_count = len([line for line in lines if line.strip() and not line.startswith('#')])
        
        return {
            "message": "Cookies uploaded successfully", 
            "path": cookies_path,
            "cookie_count": cookie_count
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload cookies: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint for Render"""
    return {"status": "OK", "message": "YouTube Video Downloader API is running"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "YouTube Video Downloader API", "version": "1.0.0"}

@app.get("/api/test-cookies")
async def test_cookies():
    """Test if cookies file exists and is valid"""
    try:
        cookies_path = "cookies.txt"
        if not os.path.exists(cookies_path):
            return {"valid": False, "message": "No cookies file found"}
        
        with open(cookies_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not validate_cookies_content(content):
            return {"valid": False, "message": "Invalid cookie format"}
        
        lines = content.strip().split('\n')
        cookie_count = len([line for line in lines if line.strip() and not line.startswith('#')])
        
        return {
            "valid": True, 
            "message": "Cookies file is valid",
            "cookie_count": cookie_count
        }
    
    except Exception as e:
        return {"valid": False, "message": f"Error reading cookies: {str(e)}"}

def validate_cookies_content(content: str) -> bool:
    """Validate if cookies content looks valid"""
    try:
        # Check for common cookie patterns
        if 'youtube.com' in content.lower() or 'google.com' in content.lower():
            return True
        # Check for Netscape cookie format
        if content.strip().startswith('# Netscape HTTP Cookie File'):
            return True
        # Check for cookie entries (basic validation)
        lines = content.strip().split('\n')
        for line in lines:
            if line.strip() and not line.startswith('#'):
                parts = line.split('\t')
                if len(parts) >= 6:  # Basic cookie format check
                    return True
        return False
    except:
        return False

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
