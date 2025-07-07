import os
import asyncio
import random
import base64
import tempfile
import time
import subprocess
import json
from typing import Dict, Any, Optional
from utils import get_random_headers, validate_file_with_ffprobe

class YTDownloader:
    def __init__(self):
        self.temp_dir = "temp"
        self.cookies_file = "cookies.txt"
        
    def get_ydl_opts(self, cookies: Optional[str] = None) -> Dict[str, Any]:
        """Get yt-dlp options with minimal configuration to avoid errors"""
        
        # Use minimal, safe configuration
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
            'retries': 3,
            'fragment_retries': 3,
            'socket_timeout': 60,
            
            # Minimal headers to avoid list/string issues
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            
            # Minimal extractor args
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                }
            },
            
            # Basic options
            'sleep_interval': 1,
            'max_sleep_interval': 2,
            'prefer_free_formats': True,
            'youtube_include_dash_manifest': False,
        }
        
        # Add cookies if provided
        if cookies:
            try:
                if isinstance(cookies, str) and cookies.strip():
                    # Decode base64 cookies
                    decoded_cookies = base64.b64decode(cookies).decode('utf-8')
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                        f.write(decoded_cookies)
                        opts['cookiefile'] = f.name
                        print(f"Using decoded cookies from parameter")
            except Exception as e:
                print(f"Failed to decode cookies: {e}")
        elif os.path.exists(self.cookies_file):
            opts['cookiefile'] = self.cookies_file
            print(f"Using cookies file: {self.cookies_file}")
        
        return opts
    
    async def download_with_subprocess(self, url: str, cookies: Optional[str] = None) -> Dict[str, Any]:
        """Download using yt-dlp subprocess to avoid Python integration issues"""
        try:
            # Build command
            cmd = [
                'yt-dlp',
                '--format', 'best[height<=720][ext=mp4]/best[ext=mp4]/best',
                '--output', f'{self.temp_dir}/%(title)s.%(ext)s',
                '--no-playlist',
                '--retries', '3',
                '--fragment-retries', '3',
                '--socket-timeout', '60',
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--extractor-args', 'youtube:player_client=android',
                '--prefer-free-formats',
                '--no-youtube-include-dash-manifest',
                url
            ]
            
            # Add cookies if available
            if cookies:
                try:
                    if isinstance(cookies, str) and cookies.strip():
                        decoded_cookies = base64.b64decode(cookies).decode('utf-8')
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                            f.write(decoded_cookies)
                            cmd.extend(['--cookies', f.name])
                            print(f"Using decoded cookies from parameter")
                except Exception as e:
                    print(f"Failed to decode cookies: {e}")
            elif os.path.exists(self.cookies_file):
                cmd.extend(['--cookies', self.cookies_file])
                print(f"Using cookies file: {self.cookies_file}")
            
            print(f"Running command: {' '.join(cmd[:10])}...")  # Don't log full command for security
            
            # Run subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd()
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Find downloaded file
                downloaded_file = None
                for file in os.listdir(self.temp_dir):
                    if file.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv')):
                        downloaded_file = os.path.join(self.temp_dir, file)
                        break
                
                if downloaded_file and await validate_file_with_ffprobe(downloaded_file):
                    return {"success": True, "file_path": downloaded_file}
                else:
                    return {"success": False, "error": "No valid video file found after download"}
            else:
                stderr_str = stderr.decode('utf-8', errors='ignore')
                print(f"yt-dlp subprocess failed: {stderr_str}")
                
                # Parse common errors
                if 'sign in to confirm' in stderr_str.lower() or 'not a bot' in stderr_str.lower():
                    return {"success": False, "error": "YouTube is blocking requests. This video may require authentication or be geo-restricted. Try uploading cookies from a logged-in browser session."}
                elif 'precondition check failed' in stderr_str.lower():
                    return {"success": False, "error": "YouTube is currently blocking automated requests. Please try again later or use cookies from a logged-in session."}
                elif 'private video' in stderr_str.lower():
                    return {"success": False, "error": "This video is private and cannot be downloaded"}
                elif 'video unavailable' in stderr_str.lower():
                    return {"success": False, "error": "Video is unavailable or has been removed"}
                elif 'http error 403' in stderr_str.lower():
                    return {"success": False, "error": "YouTube is blocking download requests. The video may be geo-restricted or require special permissions."}
                elif 'http error 429' in stderr_str.lower():
                    return {"success": False, "error": "Rate limited by YouTube. Please try again later."}
                else:
                    return {"success": False, "error": f"Download failed: {stderr_str[:200]}"}
                    
        except Exception as e:
            print(f"Subprocess download error: {e}")
            return {"success": False, "error": f"Download process failed: {str(e)}"}
    
    async def download(self, url: str, cookies: Optional[str] = None) -> Dict[str, Any]:
        """Download video from URL using subprocess method to avoid Python integration issues"""
        try:
            # Validate inputs
            if not isinstance(url, str):
                return {"success": False, "error": "URL must be a string"}
            
            if cookies is not None and not isinstance(cookies, str):
                print(f"Warning: cookies parameter type is {type(cookies)}, converting to string")
                cookies = str(cookies) if cookies else None
            
            # Add random delay to avoid rate limiting
            await asyncio.sleep(random.uniform(1, 3))
            
            # Use subprocess method to avoid Python integration issues
            result = await self.download_with_subprocess(url, cookies)
            return result
            
        except Exception as e:
            error_msg = str(e).lower()
            print(f"Unexpected download error: {e}")
            
            if 'network' in error_msg or 'connection' in error_msg:
                return {"success": False, "error": "Network error. Please check your internet connection and try again."}
            
            return {"success": False, "error": f"Unexpected error: {str(e)}"}
