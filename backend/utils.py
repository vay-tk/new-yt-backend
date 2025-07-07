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
    """Get random browser headers"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
    ]
    
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

async def validate_file_with_ffprobe(file_path: str) -> bool:
    """Validate file using ffprobe"""
    try:
        if not os.path.exists(file_path):
            return False
        
        # Check if file is HTML (common issue with restricted videos)
        try:
            with open(file_path, 'rb') as f:
                first_bytes = f.read(1000)
                if b'<!DOCTYPE html>' in first_bytes or b'<html' in first_bytes:
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
                has_video = any(stream.get('codec_type') == 'video' for stream in streams)
                return has_video
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
        except Exception as e:
            print(f"Failed to cleanup {file_path}: {e}")