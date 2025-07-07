import os
import random
import asyncio
import subprocess
from typing import Dict, List

def setup_directories():
    """Setup required directories"""
    dirs = ["temp", "converted", "logs"]
    for dir_name in dirs:
        os.makedirs(dir_name, exist_ok=True)

def get_random_headers() -> Dict[str, str]:
    """Get random browser headers with more realistic patterns"""
    # FIXED: Ensure all values are strings, not lists
    user_agents = [
        # Chrome on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        
        # Chrome on macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        
        # Firefox on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0',
        
        # Firefox on macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0',
        
        # Safari on macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        
        # Edge on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    ]
    
    accept_languages = [
        'en-US,en;q=0.9',
        'en-US,en;q=0.8',
        'en-GB,en;q=0.9',
        'en-CA,en;q=0.9',
        'en-AU,en;q=0.9',
    ]
    
    # FIXED: Ensure all header values are strings
    headers = {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': random.choice(accept_languages),
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    # Double-check all values are strings
    for key, value in headers.items():
        if not isinstance(value, str):
            print(f"Warning: Header {key} has non-string value: {type(value)}")
            headers[key] = str(value)
    
    return headers

async def validate_file_with_ffprobe(file_path: str) -> bool:
    """Validate file using ffprobe with enhanced checks"""
    try:
        if not os.path.exists(file_path):
            return False
        
        # Check file size (must be > 1KB)
        file_size = os.path.getsize(file_path)
        if file_size < 1024:
            return False
        
        # Check if file is HTML (common issue with restricted videos)
        try:
            with open(file_path, 'rb') as f:
                first_bytes = f.read(2048)  # Read first 2KB
                if b'<!DOCTYPE html>' in first_bytes or b'<html' in first_bytes:
                    return False
                
                # Check for common error page indicators
                if b'error' in first_bytes.lower() or b'blocked' in first_bytes.lower():
                    return False
        except:
            pass
        
        # Use ffprobe to validate
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', file_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            # Additional check: ensure it has video streams
            import json
            try:
                data = json.loads(stdout.decode())
                streams = data.get('streams', [])
                
                # Check for video streams
                has_video = any(stream.get('codec_type') == 'video' for stream in streams)
                if not has_video:
                    return False
                
                # Check duration (must be > 0)
                format_info = data.get('format', {})
                duration = float(format_info.get('duration', 0))
                if duration <= 0:
                    return False
                
                return True
            except:
                return False
        
        return False
        
    except Exception as e:
        print(f"ffprobe validation failed: {e}")
        return False

def cleanup_temp_files(file_paths: List[str]):
    """Clean up temporary files"""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Cleaned up: {file_path}")
        except Exception as e:
            print(f"Failed to cleanup {file_path}: {e}")
