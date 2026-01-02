# API Reference

This document details the external APIs used by Clip Cutter and their integration.

## Table of Contents

- [Gemini API](#gemini-api)
- [AssemblyAI API](#assemblyai-api)
- [yt-dlp](#yt-dlp)
- [FFmpeg](#ffmpeg)

---

## Gemini API

### Overview

Google's Gemini API is used for two purposes:
1. **Clip Extraction** - Analyzing transcripts to identify viral moments
2. **SEO Generation** - Researching trending hashtags with web search grounding

### Configuration

```python
from google import genai
from google.genai import types

# Client setup with timeout
http_options = types.HttpOptions(client_args={"timeout": 120.0})
client = genai.Client(api_key=api_key, http_options=http_options)
```

### Clip Extraction Call

**Location:** `clipper.py:find_clips()`

**Model:** `gemini-3-pro-preview`

**Request:**
```python
response = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents=prompt + "\n\nTRANSCRIPT:\n" + transcript,
)
```

**Input:**
- `prompt`: Contents of `prompts/clip_extraction.txt`
- `transcript`: Timestamped transcript from YouTube captions

**Output:** JSON array of clip objects
```json
[
  {
    "platform": "tiktok",
    "start": "1:45",
    "end": "2:12",
    "transcript": "exact words from segment",
    "hook": "attention-grabbing opener",
    "caption": null
  }
]
```

### SEO Generation Call

**Location:** `clip_cutter/seo.py:generate_seo_caption()`

**Model:** `gemini-3-flash-preview`

**Request:**
```python
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=full_prompt,
    config=types.GenerateContentConfig(
        tools=[
            types.Tool(google_search=types.GoogleSearch())
        ]
    ),
)
```

**Input:**
- `full_prompt`: Contents of `prompts/seo_captions.txt` + clip context

**Output:** JSON object with SEO data
```json
{
  "platform": "tiktok",
  "topic_keywords": ["keyword1", "keyword2"],
  "caption": "Full caption with hashtags...",
  "hashtags": ["hashtag1", "hashtag2"],
  "seo_notes": "Research findings..."
}
```

### Google Search Grounding

The SEO generation uses Gemini's Google Search tool for real-time research:

```python
config=types.GenerateContentConfig(
    tools=[
        types.Tool(google_search=types.GoogleSearch())
    ]
)
```

This enables the model to:
- Search for trending hashtags
- Research current viral formats
- Find platform-specific best practices

### Error Handling

```python
start_time = time.time()
try:
    response = client.models.generate_content(...)
except Exception as e:
    elapsed = time.time() - start_time
    print(f"❌ GEMINI API ERROR")
    print(f"   Elapsed time: {elapsed:.1f}s")
    print(f"   Error type: {type(e).__name__}")
    print(f"   Error message: {e}")
    if elapsed >= 115:  # Near timeout
        print(f"   ⚠️ Likely a timeout")
    raise
```

### Rate Limits

| Tier | Requests/min | Tokens/min |
|------|--------------|------------|
| Free | 60 | 1M |
| Paid | Higher | Higher |

---

## AssemblyAI API

### Overview

AssemblyAI provides speech-to-text transcription with word-level timestamps, used for generating karaoke-style subtitles.

### Configuration

```python
import assemblyai as aai

aai.settings.api_key = api_key

config = aai.TranscriptionConfig(
    language_code="en",
)
```

### Transcription Call

**Location:** `clip_cutter/captions.py:transcribe_with_assemblyai()`

**Request:**
```python
transcriber = aai.Transcriber()
transcript = transcriber.transcribe(str(audio_path), config=config)
```

**Input:**
- `audio_path`: Path to WAV file (16kHz mono PCM)

**Output:** Transcript object with word-level timestamps
```python
transcript.words  # List of Word objects
transcript.text   # Full transcript text

# Each word:
word.text        # "Hello"
word.start       # 1500 (milliseconds)
word.end         # 1800 (milliseconds)
word.confidence  # 0.95
```

### Audio Preparation

Before sending to AssemblyAI, audio is extracted and converted:

```python
cmd = [
    "ffmpeg", "-y",
    "-ss", str(start),           # Start time
    "-t", str(duration),         # Duration
    "-i", str(video_path),       # Input video
    "-vn",                       # No video
    "-acodec", "pcm_s16le",      # PCM 16-bit
    "-ar", "16000",              # 16kHz sample rate
    "-ac", "1",                  # Mono
    str(output_path),            # Output WAV
]
```

### Error Handling

```python
start_time = time.time()
try:
    transcript = transcriber.transcribe(str(audio_path), config=config)
except Exception as e:
    elapsed = time.time() - start_time
    print(f"❌ ASSEMBLYAI API ERROR")
    print(f"   Elapsed time: {elapsed:.1f}s")
    print(f"   Error: {e}")
    raise

if transcript.status == aai.TranscriptStatus.error:
    print(f"❌ TRANSCRIPTION ERROR: {transcript.error}")
    raise RuntimeError(f"Transcription failed: {transcript.error}")
```

### Pricing

| Item | Cost |
|------|------|
| Transcription | $0.00025/second |
| 30-second clip | ~$0.0075 |
| 60-second clip | ~$0.015 |

Free tier includes 100 hours.

---

## yt-dlp

### Overview

yt-dlp is a command-line tool for downloading videos and metadata from YouTube.

### Video Download

**Location:** `clipper.py:download_video()`

```python
video_cmd = [
    "yt-dlp",
    "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best",
    "--merge-output-format", "mp4",
    "-o", str(video_path),
    youtube_url,
]
subprocess.run(video_cmd, check=True, capture_output=True)
```

**Options:**
- `-f`: Format selection (1080p max, prefer MP4)
- `--merge-output-format`: Output container format
- `-o`: Output path template

### Caption Download

```python
captions_cmd = [
    "yt-dlp",
    "--write-auto-sub",          # Download auto-generated subs
    "--sub-lang", "en",          # English only
    "--convert-subs", "vtt",     # Convert to VTT format
    "--skip-download",           # Don't re-download video
    "-o", str(TMP_DIR / video_id),
    youtube_url,
]
subprocess.run(captions_cmd, capture_output=True)
```

**Options:**
- `--write-auto-sub`: Download auto-generated captions
- `--sub-lang`: Language filter
- `--convert-subs`: Output subtitle format
- `--skip-download`: Only get subtitles

### VTT Parsing

The downloaded VTT file is parsed to extract timestamped text:

```python
def parse_vtt_to_transcript(vtt_path: Path) -> str:
    # Input VTT format:
    # 00:00:15.000 --> 00:00:18.000
    # First sentence here

    # Output format:
    # [0:15] First sentence here
    # [0:18] Second sentence here
```

---

## FFmpeg

### Overview

FFmpeg handles all video processing: trimming, scaling, composition, and subtitle burning.

### Render Pipeline

**Location:** `clip_cutter/render.py:render_clip()`

### Filter Graph Construction

```python
filter_complex = (
    # Trim to clip duration
    f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[trimmed];"

    # Create blurred background (scale up, crop, blur)
    f"[trimmed]scale=1080:1920:force_original_aspect_ratio=increase,"
    f"crop=1080:1920,boxblur=20:5[bg];"

    # Scale foreground to fit width
    f"[trimmed]scale=1080:-2[fg];"

    # Overlay centered
    f"[bg][fg]overlay=(W-w)/2:(H-h)/2[comp]"
)

# Add subtitles if provided
if captions_path:
    filter_complex += f";[comp]subtitles='{captions_path}'[out]"
    output_label = "[out]"
else:
    output_label = "[comp]"
```

### Complete Command

```python
cmd = [
    "ffmpeg", "-y",
    "-i", str(video_path),
    "-filter_complex", filter_complex,
    "-map", output_label,
    "-map", "0:a",
    "-c:v", "libx264",
    "-preset", "medium",
    "-crf", "23",
    "-c:a", "aac",
    "-b:a", "128k",
    "-ss", str(start),
    "-t", str(duration),
    str(output_path),
]
```

### Output Specifications

| Property | Value |
|----------|-------|
| Resolution | 1080x1920 |
| Aspect Ratio | 9:16 (portrait) |
| Video Codec | H.264 (libx264) |
| Audio Codec | AAC |
| Audio Bitrate | 128 kbps |
| CRF | 23 (good quality) |

### ASS Subtitle Format

Subtitles use Advanced SubStation Alpha (ASS) format for styling:

```ass
[Script Info]
Title: TikTok Style Captions
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Style: Default,Arial Black,64,&H00FFFFFF,&HEB6325,&H00000000,&HC0000000,1,0,0,0,100,100,0,0,1,4,2,2,20,20,560,1

[Events]
Dialogue: 0,0:00:01.50,0:00:02.30,Default,,0,0,0,,{\c&HEB6325&\fscx100\fscy100\t(0,80,\fscx130\fscy130)}Hello
```

### Subtitle Positioning

```
Frame height: 1920px
Video bottom: 1264px (centered 608px video)
Caption margin: 560px from bottom
Caption position: 1360px from top (96px below video)
```
