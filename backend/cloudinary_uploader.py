import os
import asyncio
from typing import Dict, Any
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

class CloudinaryUploader:
    def __init__(self):
        # Initialize Cloudinary with environment variable
        cloudinary_url_env = os.getenv('CLOUDINARY_URL')
        if not cloudinary_url_env:
            raise ValueError("CLOUDINARY_URL environment variable is required")
        
        cloudinary.config(cloudinary_url=cloudinary_url_env)
    
    async def upload(self, file_path: str) -> Dict[str, Any]:
        """Upload video to Cloudinary"""
        try:
            # Check file size (Cloudinary has limits)
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:  # 100MB limit
                return {"success": False, "error": "File too large (max 100MB)"}
            
            # Upload to Cloudinary
            result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                file_path,
                resource_type="video",
                public_id=f"youtube_downloads/{os.path.basename(file_path)}",
                overwrite=True,
                quality="auto",
                format="mp4"
            )
            
            if result.get('secure_url'):
                return {"success": True, "url": result['secure_url']}
            else:
                return {"success": False, "error": "Failed to get upload URL"}
                
        except Exception as e:
            return {"success": False, "error": f"Upload failed: {str(e)}"}