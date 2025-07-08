import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import yt_dlp
import ffmpeg
import os
import random
import time
import json

class VideoDownloader:
    def __init__(self):
        self.cookies_file = Path("cookies.txt")
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15'
        ]
        # Track failed attempts for rate limiting
        self.failed_attempts = 0
        self.last_attempt_time = 0
        # Try to detect browser installation for cookie extraction
        self.detected_browsers = self._detect_browsers()
    
    def _detect_browsers(self):
        """Detect available browsers for cookie extraction"""
        browsers = []
        
        # Common browser executables and their names
        browser_checks = [
            ('chrome', ['chrome', 'google-chrome', 'chromium', 'chrome.exe']),
            ('firefox', ['firefox', 'firefox.exe']),
            ('edge', ['msedge', 'msedge.exe']),
            ('safari', ['safari']),
            ('opera', ['opera', 'opera.exe']),
        ]
        
        for browser_name, executables in browser_checks:
            for exe in executables:
                try:
                    # Try to find the executable
                    result = subprocess.run(['where' if os.name == 'nt' else 'which', exe], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        browsers.append(browser_name)
                        break
                except:
                    continue
        
        return browsers
    
    def validate_cookies_file(self) -> dict:
        """Validate the cookies.txt file and return status info"""
        if not self.cookies_file.exists():
            return {
                "valid": False,
                "error": "cookies.txt file not found",
                "size": 0,
                "line_count": 0
            }
        
        try:
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.strip().split('\n')
                
            # Basic validation
            if not content.strip():
                return {
                    "valid": False,
                    "error": "cookies.txt is empty",
                    "size": 0,
                    "line_count": 0
                }
            
            # Check for Netscape format indicators
            valid_lines = 0
            youtube_cookies = 0
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Split by tabs (Netscape format)
                parts = line.split('\t')
                if len(parts) >= 6:
                    valid_lines += 1
                    # Check if it's a YouTube cookie
                    if '.youtube.com' in parts[0] or 'youtube.com' in parts[0]:
                        youtube_cookies += 1
            
            if valid_lines == 0:
                return {
                    "valid": False,
                    "error": "No valid cookie entries found (expected Netscape format)",
                    "size": len(content),
                    "line_count": len(lines)
                }
            
            if youtube_cookies == 0:
                return {
                    "valid": False,
                    "error": "No YouTube cookies found - make sure to export cookies from youtube.com",
                    "size": len(content),
                    "line_count": len(lines),
                    "valid_entries": valid_lines
                }
            
            return {
                "valid": True,
                "size": len(content),
                "line_count": len(lines),
                "valid_entries": valid_lines,
                "youtube_cookies": youtube_cookies
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Failed to read cookies.txt: {str(e)}",
                "size": 0,
                "line_count": 0
            }
    
    def get_ydl_opts(self, download=True, use_browser_cookies=False):
        """Get yt-dlp options with enhanced anti-detection measures"""
        # Much more aggressive delay based on failed attempts
        base_delay = 5 + (self.failed_attempts * 10)  # Start with 5s, increase by 10s each failure
        current_time = time.time()
        if current_time - self.last_attempt_time < base_delay:
            sleep_time = base_delay - (current_time - self.last_attempt_time)
            print(f"Rate limiting: sleeping for {sleep_time:.1f} seconds...")
            time.sleep(sleep_time)
        
        # Select a random user agent
        selected_ua = random.choice(self.user_agents)
        
        # Enhanced headers that mimic real browser behavior more closely
        browser_type = 'chrome' if 'chrome' in selected_ua.lower() else 'firefox' if 'firefox' in selected_ua.lower() else 'edge' if 'edge' in selected_ua.lower() else 'safari' if 'safari' in selected_ua.lower() else 'chrome'
        
        # Browser-specific headers
        if browser_type == 'chrome':
            sec_ch_ua = '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
            sec_ch_ua_platform = '"Windows"'
        elif browser_type == 'firefox':
            sec_ch_ua = None
            sec_ch_ua_platform = None
        elif browser_type == 'edge':
            sec_ch_ua = '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
            sec_ch_ua_platform = '"Windows"'
        else:
            sec_ch_ua = '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
            sec_ch_ua_platform = '"macOS"'

        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': selected_ua,
        }
        
        # Add Chrome-specific headers
        if sec_ch_ua:
            headers.update({
                'sec-ch-ua': sec_ch_ua,
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': sec_ch_ua_platform,
            })

        opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'user_agent': selected_ua,
            'referer': 'https://www.youtube.com/',
            'headers': headers,
            # More conservative retry settings to avoid triggering rate limits
            'sleep_interval': 5,
            'max_sleep_interval': 15,
            'sleep_interval_subtitles': 3,
            'http_chunk_size': 10485760,
            'extractor_retries': 2,  # Reduced from 3
            'retries': 3,  # Reduced from 5
            'fragment_retries': 5,  # Reduced from 10
            'file_access_retries': 3,  # Reduced from 5
            'socket_timeout': 45,  # Increased timeout
            # Additional anti-detection measures
            'youtube_include_dash_manifest': False,
            'extract_flat': False,
            'writethumbnail': False,
            'writeinfojson': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'ignoreerrors': False,
            'noplaylist': True,
            'geo_bypass': True,
            'age_limit': 99,
            # Additional YouTube-specific options
            'prefer_insecure': False,
            'no_check_certificate': False,
            # Force IPv4 to avoid potential IPv6 issues
            'force_ipv4': True,
            # Add random delays to mimic human behavior
            'playlist_random': True,
        }
        
        if not download:
            opts['skip_download'] = True
        
        # Cookie handling priority:
        # 1. Browser cookies (if requested and available)
        # 2. Uploaded cookies.txt file
        # 3. No cookies (fallback)
        
        if use_browser_cookies and self.detected_browsers:
            # Try to use browser cookies - Chrome first, then others
            browser_priority = ['chrome', 'firefox', 'edge', 'safari', 'opera']
            for browser in browser_priority:
                if browser in self.detected_browsers:
                    try:
                        opts['cookiesfrombrowser'] = (browser, None)
                        print(f"Using cookies from {browser} browser")
                        break
                    except:
                        continue
        elif self.cookies_file.exists() and self.cookies_file.stat().st_size > 0:
            opts['cookiefile'] = str(self.cookies_file)
            print(f"Using cookies from file: {self.cookies_file}")
        else:
            print("No cookies available - this may limit access to private/age-restricted videos")
        
        return opts
    
    async def extract_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract video information using yt-dlp with enhanced anti-detection"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Try browser cookies first, then file cookies
                use_browser_cookies = retry_count == 0 and self.detected_browsers
                ydl_opts = self.get_ydl_opts(download=False, use_browser_cookies=use_browser_cookies)
                
                def _extract():
                    try:
                        # Much longer delays to avoid rate limiting - mimic very slow human behavior
                        delay = random.uniform(10, 20) + (retry_count * 10)  # 10-20s base, +10s per retry
                        print(f"Waiting {delay:.1f} seconds before extraction attempt...")
                        time.sleep(delay)
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            return ydl.extract_info(url, download=False)
                    except yt_dlp.utils.DownloadError as e:
                        error_msg = str(e)
                        print(f"yt-dlp extract error (attempt {retry_count + 1}): {error_msg}")
                        
                        # Check for specific YouTube blocking patterns
                        if any(phrase in error_msg.lower() for phrase in [
                            'sign in to confirm', 'not a bot', 'private video', 
                            'video unavailable', 'removed by the user'
                        ]):
                            raise Exception(f"Video access blocked: {error_msg}")
                        elif 'http error 403' in error_msg.lower():
                            raise Exception("Access forbidden - video may be region-locked or require authentication")
                        elif 'http error 404' in error_msg.lower():
                            raise Exception("Video not found - it may have been deleted or made private")
                        elif 'http error 429' in error_msg.lower():
                            # Rate limited - will retry
                            raise yt_dlp.utils.DownloadError("Rate limited")
                        else:
                            raise Exception(f"Failed to extract video info: {error_msg}")
                    except Exception as e:
                        print(f"Unexpected extract error: {e}")
                        raise Exception(f"Could not extract video information: {str(e)}")
                
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, _extract)
                
                # Success - reset failed attempts
                self.failed_attempts = 0
                return info
                
            except Exception as e:
                retry_count += 1
                self.failed_attempts += 1
                self.last_attempt_time = time.time()
                
                error_msg = str(e)
                print(f"Extract info error (attempt {retry_count}): {error_msg}")
                
                # If rate limited or bot detection, wait much longer before retry
                if retry_count < max_retries and ('rate limited' in error_msg.lower() or 'bot' in error_msg.lower()):
                    wait_time = random.uniform(30, 60) + (retry_count * 30)  # 30-60s base, +30s per retry
                    print(f"Anti-bot detection triggered. Waiting {wait_time:.1f} seconds before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                
                # Last attempt or non-retryable error
                raise e
        
        raise Exception("Max retries exceeded")
    
    async def download_video(self, url: str, task_id: str) -> Optional[Path]:
        """Download video using yt-dlp with enhanced error handling"""
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        
        output_template = str(temp_dir / f"{task_id}_temp.%(ext)s")
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Try browser cookies first, then file cookies
                use_browser_cookies = retry_count == 0 and self.detected_browsers
                ydl_opts = self.get_ydl_opts(download=True, use_browser_cookies=use_browser_cookies)
                
                # Progressive format fallback strategy
                if retry_count == 0:
                    # First attempt: Prefer MP4 with quality constraints
                    format_selector = 'best[ext=mp4][height<=720]/best[ext=mp4][height<=1080]/best[ext=mp4]/best[height<=720]/best'
                elif retry_count == 1:
                    # Second attempt: Any format, prefer MP4, no height restrictions
                    format_selector = 'best[ext=mp4]/best[vcodec!=none]/best'
                else:
                    # Final attempt: Accept any available format
                    format_selector = 'best/worst'
                
                print(f"Download attempt {retry_count + 1}: Using format selector: {format_selector}")
                
                ydl_opts.update({
                    'format': format_selector,
                    'outtmpl': output_template,
                    'writesubtitles': False,
                    'writeautomaticsub': False,
                    'ignoreerrors': False,
                    'merge_output_format': 'mp4',  # Force MP4 container when merging
                    'prefer_free_formats': False,  # Don't avoid non-free formats
                    # Enhanced retry settings
                    'retries': 5,
                    'fragment_retries': 10,
                    'file_access_retries': 5,
                    'socket_timeout': 45,
                    'http_chunk_size': 10485760,
                })
                
                def _download():
                    try:
                        # Much longer delay for downloads - critical to avoid detection
                        delay = random.uniform(15, 30) + (retry_count * 15)  # 15-30s base, +15s per retry
                        print(f"Waiting {delay:.1f} seconds before download attempt...")
                        time.sleep(delay)
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([url])
                            return True
                    except yt_dlp.utils.DownloadError as e:
                        error_msg = str(e)
                        print(f"yt-dlp download error (attempt {retry_count + 1}): {error_msg}")
                        
                        # Provide specific error messages
                        if any(phrase in error_msg.lower() for phrase in [
                            'sign in to confirm', 'not a bot'
                        ]):
                            raise Exception("YouTube is blocking automated access. Please try uploading cookies.txt file or try again later.")
                        elif 'requested format is not available' in error_msg.lower():
                            # Format selection issue - will retry with different strategy
                            if retry_count < max_retries - 1:
                                print(f"Format not available, will retry with different strategy...")
                                raise yt_dlp.utils.DownloadError("Format not available")
                            else:
                                raise Exception("Video format not available. The video may have limited quality options or be unavailable for download.")
                        elif 'http error 403' in error_msg.lower():
                            raise Exception("Access forbidden. Video may be region-locked, private, or require authentication. Try uploading cookies.txt.")
                        elif 'http error 404' in error_msg.lower():
                            raise Exception("Video not found. It may have been deleted, made private, or the URL is incorrect.")
                        elif 'http error 429' in error_msg.lower():
                            # Rate limited - will retry
                            raise yt_dlp.utils.DownloadError("Rate limited")
                        elif 'private video' in error_msg.lower():
                            raise Exception("This is a private video. You need to upload cookies.txt from a logged-in session.")
                        elif 'video unavailable' in error_msg.lower():
                            raise Exception("Video is unavailable. It may be region-locked or removed.")
                        else:
                            raise Exception(f"Download failed: {error_msg}")
                    except Exception as e:
                        print(f"Unexpected download error: {e}")
                        raise Exception(f"Download failed: {str(e)}")
                
                # Run in thread pool
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(None, _download)
                
                if not success:
                    raise Exception("Download failed - unknown error")
                
                # Find the downloaded file
                downloaded_files = list(temp_dir.glob(f"{task_id}_temp.*"))
                if not downloaded_files:
                    raise Exception("Download completed but no file was created")
                
                # Get the largest file (in case multiple formats were downloaded)
                downloaded_file = max(downloaded_files, key=lambda f: f.stat().st_size)
                
                if downloaded_file.stat().st_size == 0:
                    raise Exception("Downloaded file is empty")
                
                # Validate the file is a proper video file
                if not await self.validate_video_file(downloaded_file):
                    raise Exception("Downloaded file is not a valid video file")
                
                # Success - reset failed attempts
                self.failed_attempts = 0
                return downloaded_file
                
            except Exception as e:
                retry_count += 1
                self.failed_attempts += 1
                self.last_attempt_time = time.time()
                
                error_msg = str(e)
                print(f"Download error (attempt {retry_count}): {error_msg}")
                
                # Clean up any partial downloads
                for temp_file in temp_dir.glob(f"{task_id}_temp.*"):
                    try:
                        temp_file.unlink()
                    except:
                        pass
                
                # If rate limited or bot detection, wait much longer before retry
                if retry_count < max_retries and ('rate limited' in error_msg.lower() or 'bot' in error_msg.lower()):
                    wait_time = random.uniform(60, 120) + (retry_count * 60)  # 1-2min base, +1min per retry
                    print(f"Download blocked by anti-bot. Waiting {wait_time:.1f} seconds before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                
                # Last attempt or non-retryable error
                raise e
        
        raise Exception("Max retries exceeded")
    
    async def validate_video_file(self, file_path: Path) -> bool:
        """Validate that the file is a proper video file using ffprobe"""
        def _validate():
            try:
                result = subprocess.run([
                    'ffprobe', '-v', 'quiet', '-print_format', 'json',
                    '-show_format', '-show_streams', str(file_path)
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    print(f"ffprobe failed: {result.stderr}")
                    return False
                
                # Parse the JSON output
                probe_data = json.loads(result.stdout)
                
                # Check if we have video streams
                video_streams = [s for s in probe_data.get('streams', []) if s.get('codec_type') == 'video']
                if not video_streams:
                    print("No video streams found in file")
                    return False
                
                # Check if format is recognized
                format_info = probe_data.get('format', {})
                if not format_info.get('format_name'):
                    print("Unknown format")
                    return False
                
                print(f"Video validation successful: {format_info.get('format_name')}")
                return True
                
            except subprocess.TimeoutExpired:
                print("Video validation timed out")
                return False
            except json.JSONDecodeError:
                print("Failed to parse ffprobe output")
                return False
            except Exception as e:
                print(f"Video validation error: {e}")
                return False
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _validate)
    
    async def convert_to_hevc(self, input_file: Path, output_file: Path):
        """Convert video to HEVC using ffmpeg with better error handling"""
        def _convert():
            try:
                # First, validate input file again
                probe_result = subprocess.run([
                    'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                    '-show_format', '-show_streams', str(input_file)
                ], capture_output=True, text=True, timeout=30)
                
                if probe_result.returncode != 0:
                    print(f"Input file validation failed: {probe_result.stderr}")
                    raise Exception("Input file is corrupted or invalid")
                
                # Parse probe data to get video info
                try:
                    probe_data = json.loads(probe_result.stdout)
                    video_streams = [s for s in probe_data.get('streams', []) if s.get('codec_type') == 'video']
                    if not video_streams:
                        raise Exception("No video streams found in input file")
                    
                    print(f"Input video info: {video_streams[0].get('codec_name', 'unknown')} "
                          f"{video_streams[0].get('width', '?')}x{video_streams[0].get('height', '?')}")
                except:
                    print("Could not parse video info, proceeding anyway...")
                
                # Try HEVC conversion first
                hevc_cmd = [
                    'ffmpeg', '-i', str(input_file),
                    '-c:v', 'libx265',
                    '-c:a', 'aac',
                    '-b:a', '96k',
                    '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2',
                    '-preset', 'medium',
                    '-crf', '23',
                    '-movflags', 'faststart',
                    '-avoid_negative_ts', 'make_zero',
                    '-fflags', '+genpts',
                    '-y',  # Overwrite output file
                    str(output_file)
                ]
                
                print("Starting HEVC conversion...")
                result = subprocess.run(hevc_cmd, capture_output=True, text=True, timeout=1800)
                
                if result.returncode == 0 and output_file.exists() and output_file.stat().st_size > 0:
                    print("HEVC conversion successful")
                    return True
                
                # If HEVC fails, try H.264
                print("HEVC conversion failed, trying H.264...")
                h264_cmd = [
                    'ffmpeg', '-i', str(input_file),
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    '-b:a', '96k',
                    '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2',
                    '-preset', 'medium',
                    '-crf', '23',
                    '-movflags', 'faststart',
                    '-avoid_negative_ts', 'make_zero',
                    '-fflags', '+genpts',
                    '-y',
                    str(output_file)
                ]
                
                result = subprocess.run(h264_cmd, capture_output=True, text=True, timeout=1800)
                
                if result.returncode == 0 and output_file.exists() and output_file.stat().st_size > 0:
                    print("H.264 conversion successful")
                    return True
                
                # If both fail, try simple copy with container change
                print("Both encoders failed, trying simple remux...")
                copy_cmd = [
                    'ffmpeg', '-i', str(input_file),
                    '-c', 'copy',
                    '-movflags', 'faststart',
                    '-avoid_negative_ts', 'make_zero',
                    '-y',
                    str(output_file)
                ]
                
                result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=600)
                
                if result.returncode == 0 and output_file.exists() and output_file.stat().st_size > 0:
                    print("Simple remux successful")
                    return True
                
                # If everything fails, provide detailed error
                error_msg = result.stderr if result.stderr else "Unknown conversion error"
                print(f"All conversion attempts failed. Last error: {error_msg}")
                raise Exception(f"Video conversion failed: {error_msg}")
                
            except subprocess.TimeoutExpired:
                raise Exception("Video conversion timed out (file too large or processing issue)")
            except Exception as e:
                print(f"Conversion error: {e}")
                raise Exception(f"Video conversion failed: {str(e)}")
        
        # Run in thread pool
        loop = asyncio.get_event_loop()
        try:
            success = await loop.run_in_executor(None, _convert)
            if not success:
                raise Exception("Video conversion failed")
            
            # Final validation of output file
            if not await self.validate_video_file(output_file):
                raise Exception("Converted file is not valid")
                
        except Exception as e:
            print(f"Conversion error: {e}")
            raise

    async def extract_info_with_fallback(self, url: str) -> Optional[Dict[str, Any]]:
        """Try different extraction strategies if the main one fails"""
        strategies = [
            # Strategy 1: Standard extraction with browser cookies
            {'name': 'browser_cookies', 'opts': {'use_browser_cookies': True}},
            
            # Strategy 2: Standard extraction with file cookies
            {'name': 'file_cookies', 'opts': {'use_browser_cookies': False}},
            
            # Strategy 3: No cookies but with geo bypass
            {'name': 'geo_bypass', 'opts': {'geo_bypass': True, 'geo_bypass_country': 'US'}},
            
            # Strategy 4: Disable age gating
            {'name': 'no_age_gate', 'opts': {'age_limit': 0}},
            
            # Strategy 5: Minimal options
            {'name': 'minimal', 'opts': {'extract_flat': False, 'youtube_include_dash_manifest': False}},
        ]
        
        last_error = None
        
        for strategy in strategies:
            try:
                print(f"Trying extraction strategy: {strategy['name']}")
                
                # Get base options
                use_browser_cookies = strategy['opts'].pop('use_browser_cookies', False)
                ydl_opts = self.get_ydl_opts(download=False, use_browser_cookies=use_browser_cookies)
                
                # Apply strategy-specific options
                ydl_opts.update(strategy['opts'])
                
                def _extract():
                    try:
                        # Much longer delays between fallback strategies
                        delay = random.uniform(15, 25)
                        print(f"Strategy {strategy['name']}: waiting {delay:.1f} seconds...")
                        time.sleep(delay)
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            return ydl.extract_info(url, download=False)
                    except Exception as e:
                        print(f"Strategy {strategy['name']} failed: {e}")
                        raise
                
                # Run in thread pool
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, _extract)
                
                if info:
                    print(f"Success with strategy: {strategy['name']}")
                    return info
                    
            except Exception as e:
                last_error = e
                # Much longer wait between strategies to avoid triggering rate limits
                wait_time = random.uniform(30, 60)
                print(f"Strategy failed, waiting {wait_time:.1f} seconds before next attempt...")
                await asyncio.sleep(wait_time)
                continue
        
        # If all strategies failed, raise the last error
        if last_error:
            raise last_error
        else:
            raise Exception("All extraction strategies failed")
