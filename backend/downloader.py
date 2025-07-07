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
                    # Try to decode base64 cookies, fallback to treating as plain text
                    try:
                        decoded_cookies = base64.b64decode(cookies).decode('utf-8')
                        print("Successfully decoded base64 cookies")
                    except Exception:
                        # If base64 decode fails, treat as plain text
                        decoded_cookies = cookies
                        print("Using cookies as plain text")
                    
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                        f.write(decoded_cookies)
                        opts['cookiefile'] = f.name
                        print(f"Using decoded cookies from parameter")
                        
                    # Use web client with cookies to avoid android/cookie conflict
                    opts['extractor_args'] = {
                        'youtube': {
                            'player_client': ['web'],
                        }
                    }
            except Exception as e:
                print(f"Failed to process cookies: {e}")
                # Keep default android client if cookies fail
        elif os.path.exists(self.cookies_file):
            opts['cookiefile'] = self.cookies_file
            opts['extractor_args'] = {
                'youtube': {
                    'player_client': ['web'],
                }
            }
            print(f"Using cookies file: {self.cookies_file}")
        
        return opts
    
    async def download_with_subprocess(self, url: str, cookies: Optional[str] = None) -> Dict[str, Any]:
        """Download using yt-dlp subprocess to avoid Python integration issues"""
        try:
            # Build base command with better format selection
            cmd = [
                'yt-dlp',
                '--format', 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
                '--output', f'{self.temp_dir}/%(title)s.%(ext)s',
                '--no-playlist',
                '--retries', '3',
                '--fragment-retries', '3',
                '--socket-timeout', '60',
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--prefer-free-formats',
                '--no-youtube-include-dash-manifest',
                '--merge-output-format', 'mp4',
                url
            ]
            
            # Handle cookies and client selection
            cookie_file_path = None
            if cookies:
                try:
                    if isinstance(cookies, str) and cookies.strip():
                        # Try to decode base64 cookies, fallback to treating as plain text
                        try:
                            decoded_cookies = base64.b64decode(cookies).decode('utf-8')
                            print("Successfully decoded base64 cookies")
                        except Exception:
                            # If base64 decode fails, treat as plain text
                            decoded_cookies = cookies
                            print("Using cookies as plain text")
                        
                        # Write cookies to temporary file
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                            f.write(decoded_cookies)
                            cookie_file_path = f.name
                            cmd.extend(['--cookies', cookie_file_path])
                            print(f"Using cookies from parameter")
                            
                        # Don't use android client with cookies as it causes conflicts
                        cmd.extend(['--extractor-args', 'youtube:player_client=web'])
                except Exception as e:
                    print(f"Failed to process cookies: {e}")
                    # Fallback to android client without cookies
                    cmd.extend(['--extractor-args', 'youtube:player_client=android'])
            elif os.path.exists(self.cookies_file):
                cmd.extend(['--cookies', self.cookies_file])
                cmd.extend(['--extractor-args', 'youtube:player_client=web'])
                print(f"Using cookies file: {self.cookies_file}")
            else:
                # No cookies, use android client
                cmd.extend(['--extractor-args', 'youtube:player_client=android'])
            
            print(f"Running command: {' '.join(cmd[:10])}...")  # Don't log full command for security
            
            # Run subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd()
            )
            
            stdout, stderr = await process.communicate()
            
            # Cleanup temporary cookie file
            if cookie_file_path and os.path.exists(cookie_file_path):
                try:
                    os.unlink(cookie_file_path)
                except Exception as e:
                    print(f"Failed to cleanup cookie file: {e}")
            
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
                
                # Get better error message
                error_message = self.get_better_error_message(stderr_str)
                return {"success": False, "error": error_message}
                    
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
    
    def get_better_error_message(self, stderr_str: str) -> str:
        """Get a more user-friendly error message based on the stderr output"""
        stderr_lower = stderr_str.lower()
        
        if 'sign in to confirm' in stderr_lower or 'not a bot' in stderr_lower:
            return "YouTube is asking for bot verification. Please upload valid cookies from a logged-in browser session."
        elif 'precondition check failed' in stderr_lower:
            return "YouTube is blocking automated requests. Try uploading cookies from a logged-in browser session."
        elif 'private video' in stderr_lower:
            return "This video is private and cannot be downloaded."
        elif 'video unavailable' in stderr_lower:
            return "Video is unavailable or has been removed."
        elif 'http error 403' in stderr_lower:
            return "Access denied. The video may be geo-restricted or require special permissions."
        elif 'http error 429' in stderr_lower:
            return "Rate limited by YouTube. Please try again later."
        elif 'skipping client' in stderr_lower and 'cookies' in stderr_lower:
            return "Cookie format issue. Please re-upload cookies using a different export method."
        elif 'requested format is not available' in stderr_lower:
            return "The requested video format is not available. The video may be a live stream or have limited formats."
        elif 'only images are available' in stderr_lower:
            return "This URL contains only images, not videos. Please check the URL."
        elif 'no video formats found' in stderr_lower:
            return "No downloadable video formats found. The video may be live-only or geo-restricted."
        elif 'connection' in stderr_lower or 'network' in stderr_lower:
            return "Network connection error. Please check your internet connection and try again."
        elif 'timeout' in stderr_lower:
            return "Connection timeout. Please try again later."
        else:
            # Return a cleaned version of the original error
            return f"Download failed: {stderr_str[:200]}..."
