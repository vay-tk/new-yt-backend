import os
import asyncio
import subprocess
from typing import Dict, Any
from utils import validate_file_with_ffprobe

class VideoConverter:
    def __init__(self):
        self.converted_dir = "converted"
        
    async def convert(self, input_path: str) -> Dict[str, Any]:
        """Convert video to HEVC, fallback to H.264, then remux"""
        try:
            # Validate input file first
            if not await validate_file_with_ffprobe(input_path):
                return {"success": False, "error": "Input file is not a valid video"}
            
            filename = os.path.basename(input_path)
            name, ext = os.path.splitext(filename)
            output_path = os.path.join(self.converted_dir, f"{name}_converted.mp4")
            
            # Try HEVC first
            hevc_success = await self._convert_hevc(input_path, output_path)
            if hevc_success:
                return {"success": True, "file_path": output_path}
            
            # Fallback to H.264
            h264_success = await self._convert_h264(input_path, output_path)
            if h264_success:
                return {"success": True, "file_path": output_path}
            
            # Final fallback: remux without re-encoding
            remux_success = await self._remux(input_path, output_path)
            if remux_success:
                return {"success": True, "file_path": output_path}
            
            return {"success": False, "error": "All conversion methods failed"}
            
        except Exception as e:
            return {"success": False, "error": f"Conversion error: {str(e)}"}
    
    async def _convert_hevc(self, input_path: str, output_path: str) -> bool:
        """Convert to HEVC (H.265)"""
        try:
            cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx265',
                '-preset', 'medium',
                '-crf', '28',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y', output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_path):
                return await validate_file_with_ffprobe(output_path)
            
            return False
            
        except Exception as e:
            print(f"HEVC conversion failed: {e}")
            return False
    
    async def _convert_h264(self, input_path: str, output_path: str) -> bool:
        """Convert to H.264"""
        try:
            cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y', output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_path):
                return await validate_file_with_ffprobe(output_path)
            
            return False
            
        except Exception as e:
            print(f"H.264 conversion failed: {e}")
            return False
    
    async def _remux(self, input_path: str, output_path: str) -> bool:
        """Remux without re-encoding"""
        try:
            cmd = [
                'ffmpeg', '-i', input_path,
                '-c', 'copy',
                '-movflags', '+faststart',
                '-y', output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_path):
                return await validate_file_with_ffprobe(output_path)
            
            return False
            
        except Exception as e:
            print(f"Remux failed: {e}")
            return False