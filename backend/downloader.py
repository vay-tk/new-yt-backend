import os
import asyncio
import random
import base64
import tempfile
from typing import Dict, Any, Optional
import yt_dlp
from utils import get_random_headers, validate_file_with_ffprobe

class YTDownloader:
    def __init__(self):
        self.temp_dir = "temp"
        self.cookies_file = "cookies.txt"
        
    def get_ydl_opts(self, cookies: Optional[str] = None) -> Dict[str, Any]:
        """Get yt-dlp options with random headers and cookies"""
        headers = get_random_headers()
        
        opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'{self.temp_dir}/%(title)s.%(ext)s',
            'noplaylist': True,
            'extract_flat': False,
            'writethumbnail': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'ignoreerrors': True,
            'no_warnings': False,
            'retries': 3,
            'socket_timeout': 60,
            'http_headers': headers,
        }
        
        # Add cookies if provided
        if cookies:
            try:
                # Decode base64 cookies
                decoded_cookies = base64.b64decode(cookies).decode('utf-8')
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write(decoded_cookies)
                    opts['cookiefile'] = f.name
            except Exception as e:
                print(f"Failed to decode cookies: {e}")
        elif os.path.exists(self.cookies_file):
            opts['cookiefile'] = self.cookies_file
        
        return opts
    
    async def download(self, url: str, cookies: Optional[str] = None) -> Dict[str, Any]:
        """Download video from URL"""
        try:
            opts = self.get_ydl_opts(cookies)
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Extract info first
                try:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        return {"success": False, "error": "Failed to extract video information"}
                    
                    # Check for common restrictions
                    if info.get('age_limit', 0) > 0:
                        return {"success": False, "error": "Video is age-restricted"}
                    
                    if info.get('is_live'):
                        return {"success": False, "error": "Live streams are not supported"}
                    
                    # Check if video requires login
                    if 'login' in info.get('title', '').lower() or 'sign in' in info.get('title', '').lower():
                        return {"success": False, "error": "Video requires login"}
                    
                except Exception as e:
                    return {"success": False, "error": f"Failed to extract video info: {str(e)}"}
                
                # Download the video
                try:
                    ydl.download([url])
                except Exception as e:
                    return {"success": False, "error": f"Download failed: {str(e)}"}
            
            # Find the downloaded file
            downloaded_file = None
            for file in os.listdir(self.temp_dir):
                if file.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                    downloaded_file = os.path.join(self.temp_dir, file)
                    break
            
            if not downloaded_file:
                return {"success": False, "error": "No video file found after download"}
            
            # Validate the downloaded file
            if not await validate_file_with_ffprobe(downloaded_file):
                # Check if it's an HTML file
                try:
                    with open(downloaded_file, 'r', encoding='utf-8') as f:
                        content = f.read(1000)  # Read first 1KB
                        if '<!DOCTYPE html>' in content or '<html' in content:
                            return {"success": False, "error": "Downloaded file is HTML, not a video. Video may be geo-restricted or require login."}
                except:
                    pass
                
                return {"success": False, "error": "Downloaded file is not a valid video"}
            
            return {"success": True, "file_path": downloaded_file}
            
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}