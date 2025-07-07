# YouTube Video Downloader Backend

A production-grade FastAPI backend for downloading YouTube videos, converting them to optimal formats, and uploading to Cloudinary.

## Features

- **Safe Downloads**: Uses `yt-dlp` with random headers, cookies support, and retry logic
- **Video Validation**: Uses `ffprobe` to validate downloaded files
- **Smart Conversion**: Converts to HEVC (H.265) with H.264 fallback
- **Cloud Storage**: Uploads to Cloudinary with automatic optimization
- **Error Handling**: Detects restricted videos, login requirements, and geo-blocks
- **Progress Tracking**: Real-time status updates via task IDs
- **Logging**: Comprehensive logging for debugging

## API Endpoints

- `POST /api/download` - Start video download
- `GET /api/status/{task_id}` - Check download status
- `POST /api/upload-cookies` - Upload cookies.txt file
- `GET /health` - Health check

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
cp .env.example .env
# Edit .env with your Cloudinary credentials
```

3. Run locally:
```bash
python main.py
```

## Deployment to Render

1. Connect your GitHub repository to Render
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `./start.sh`
4. Add environment variable: `CLOUDINARY_URL`

## Docker Deployment

```bash
docker build -t youtube-downloader .
docker run -p 10000:10000 -e CLOUDINARY_URL=your_url youtube-downloader
```

## Usage

### Download Video
```bash
curl -X POST "http://localhost:10000/api/download" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=VIDEO_ID"}'
```

### Check Status
```bash
curl "http://localhost:10000/api/status/TASK_ID"
```

### Upload Cookies
```bash
curl -X POST "http://localhost:10000/api/upload-cookies" \
  -F "file=@cookies.txt"
```

## Error Handling

The API handles various error scenarios:
- Age-restricted videos
- Geo-blocked content
- Login-required videos
- Invalid video URLs
- Network timeouts
- Conversion failures

## File Structure

```
backend/
├── main.py                 # FastAPI application
├── downloader.py          # yt-dlp wrapper
├── convert.py             # FFmpeg video conversion
├── cloudinary_uploader.py # Cloudinary upload
├── utils.py               # Utility functions
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── start.sh              # Render start script
├── .env.example          # Environment variables template
└── README.md             # Documentation
```

## Requirements

- Python 3.11+
- FFmpeg
- yt-dlp
- Cloudinary account