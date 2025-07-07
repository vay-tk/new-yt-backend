import os
import asyncio
import random
import base64
import tempfile
import time
from typing import Dict, Any, Optional
import yt_dlp
from utils import get_random_headers, validate_file_with_ffprobe

class YTDownloader:
    def __init__(self):
        self.temp_dir = "temp"
        self.cookies_file = "cookies.txt"
        
    def get_ydl_opts(self, cookies: Optional[str] = None) -> Dict[str, Any]:
        """Get yt-dlp options with enhanced anti-detection measures"""
        headers = get_random_headers()
        
        opts = {
            'format': 'best[height<=720][ext=mp4]/best[ext=mp4]/best',
            'outtmpl': f'{self.temp_dir}/%(title)s.%(ext)s',
            'noplaylist': True,
            'extract_flat': False,
            'writethumbnail': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'ignoreerrors': True,
            'no_warnings': False,
            'retries': 5,
            'fragment_retries': 5,
            'socket_timeout': 120,
            'http_headers': headers,
            
            # Enhanced anti-detection measures
            'extractor_args': {
                'youtube': {
                    'skip': ['hls', 'dash'],
                    'player_client': ['android', 'web'],
                    'player_skip': ['configs'],
                }
            },
            
            # Additional options to avoid detection
            'sleep_interval': 1,
            'max_sleep_interval': 3,
            'sleep_interval_requests': 1,
            'sleep_interval_subtitles': 1,
            
            # Use different user agents for different requests
            'http_chunk_size': 10485760,  # 10MB chunks
            'prefer_free_formats': True,
            'youtube_include_dash_manifest': False,
            
            # Geo bypass attempts
            'geo_bypass': True,
            'geo_bypass_country': ['US', 'GB', 'CA', 'AU'],
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
        """Download video from URL with enhanced error handling"""
        try:
            # Add random delay to avoid rate limiting
            await asyncio.sleep(random.uniform(1, 3))
            
            opts = self.get_ydl_opts(cookies)
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Extract info first with multiple attempts
                info = None
                for attempt in range(3):
                    try:
                        print(f"Attempt {attempt + 1}: Extracting video info...")
                        info = ydl.extract_info(url, download=False)
                        if info:
                            break
                    except Exception as e:
                        error_msg = str(e).lower()
                        
                        # Check for specific YouTube errors
                        if 'sign in to confirm' in error_msg or 'not a bot' in error_msg:
                            return {"success": False, "error": "YouTube is blocking requests. This video may require authentication or be geo-restricted. Try uploading cookies from a logged-in browser session."}
                        
                        if 'precondition check failed' in error_msg:
                            if attempt < 2:
                                print(f"Precondition check failed, retrying with different settings...")
                                await asyncio.sleep(random.uniform(2, 5))
                                # Try with different extractor args
                                opts['extractor_args']['youtube']['player_client'] = ['web', 'android']
                                continue
                            else:
                                return {"success": False, "error": "YouTube is currently blocking automated requests. Please try again later or use cookies from a logged-in session."}
                        
                        if 'private video' in error_msg:
                            return {"success": False, "error": "This video is private and cannot be downloaded"}
                        
                        if 'video unavailable' in error_msg:
                            return {"success": False, "error": "Video is unavailable or has been removed"}
                        
                        if attempt == 2:  # Last attempt
                            return {"success": False, "error": f"Failed to extract video information: {str(e)}"}
                        
                        await asyncio.sleep(random.uniform(3, 6))
                
                if not info:
                    return {"success": False, "error": "Failed to extract video information after multiple attempts"}
                
                # Enhanced video validation
                if info.get('age_limit', 0) > 0:
                    return {"success": False, "error": "Video is age-restricted. Please provide cookies from a logged-in YouTube session."}
                
                if info.get('is_live'):
                    return {"success": False, "error": "Live streams are not supported"}
                
                if info.get('availability') == 'private':
                    return {"success": False, "error": "Video is private and cannot be downloaded"}
                
                if info.get('availability') == 'premium_only':
                    return {"success": False, "error": "Video requires YouTube Premium"}
                
                # Check for login requirements
                title = info.get('title', '').lower()
                if any(keyword in title for keyword in ['login', 'sign in', 'private']):
                    return {"success": False, "error": "Video may require login. Try providing cookies."}
                
                # Download the video with retry logic
                download_success = False
                for attempt in range(3):
                    try:
                        print(f"Download attempt {attempt + 1}...")
                        ydl.download([url])
                        download_success = True
                        break
                    except Exception as e:
                        error_msg = str(e).lower()
                        
                        if 'http error 403' in error_msg:
                            if attempt < 2:
                                print("HTTP 403 error, retrying with different settings...")
                                await asyncio.sleep(random.uniform(5, 10))
                                # Try with more conservative settings
                                opts['format'] = 'worst[ext=mp4]/worst'
                                opts['http_chunk_size'] = 1048576  # 1MB chunks
                                continue
                            else:
                                return {"success": False, "error": "YouTube is blocking download requests. The video may be geo-restricted or require special permissions."}
                        
                        if 'http error 429' in error_msg:
                            return {"success": False, "error": "Rate limited by YouTube. Please try again later."}
                        
                        if attempt == 2:  # Last attempt
                            return {"success": False, "error": f"Download failed: {str(e)}"}
                        
                        await asyncio.sleep(random.uniform(5, 10))
                
                if not download_success:
                    return {"success": False, "error": "Download failed after multiple attempts"}
            
            # Find the downloaded file
            downloaded_file = None
            for file in os.listdir(self.temp_dir):
                if file.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv')):
                    downloaded_file = os.path.join(self.temp_dir, file)
                    break
            
            if not downloaded_file:
                return {"success": False, "error": "No video file found after download"}
            
            # Validate the downloaded file
            if not await validate_file_with_ffprobe(downloaded_file):
                # Check if it's an HTML file (common with restricted videos)
                try:
                    with open(downloaded_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(1000)  # Read first 1KB
                        if '<!DOCTYPE html>' in content or '<html' in content:
                            return {"success": False, "error": "Downloaded file is HTML instead of video. This usually means the video is geo-restricted, age-restricted, or requires login. Try providing cookies from a logged-in browser session."}
                except:
                    pass
                
                return {"success": False, "error": "Downloaded file is not a valid video"}
            
            return {"success": True, "file_path": downloaded_file}
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if 'network' in error_msg or 'connection' in error_msg:
                return {"success": False, "error": "Network error. Please check your internet connection and try again."}
            
            return {"success": False, "error": f"Unexpected error: {str(e)}"}
