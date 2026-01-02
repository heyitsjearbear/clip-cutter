# System Design Document

## Overview

Clip Cutter is a CLI tool that automates the process of extracting viral short-form video clips from long-form YouTube content. It uses AI to identify high-potential moments, generates SEO-optimized captions, and renders vertical videos ready for social media platforms.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INPUT                                      │
│                            (YouTube URL)                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DOWNLOAD STAGE                                     │
│  ┌─────────────────┐    ┌─────────────────┐                                 │
│  │    yt-dlp       │    │    yt-dlp       │                                 │
│  │  (video.mp4)    │    │  (captions.vtt) │                                 │
│  └────────┬────────┘    └────────┬────────┘                                 │
│           │                      │                                          │
│           ▼                      ▼                                          │
│      tmp/<id>.mp4          tmp/<id>.vtt                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AI ANALYSIS STAGE                                    │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Gemini 3 Pro (clip extraction)                     │   │
│  │                                                                       │   │
│  │  Input:  Timestamped transcript + clip_extraction.txt prompt          │   │
│  │  Output: JSON array of clip objects with timestamps                   │   │
│  │                                                                       │   │
│  │  Timeout: 120 seconds                                                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│                        List[Clip] objects                                    │
│              (platform, start, end, transcript, hook)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SEO GENERATION STAGE                                │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │            Gemini 3 Flash + Google Search Grounding                   │   │
│  │                                                                       │   │
│  │  For each clip:                                                       │   │
│  │    1. Web search for trending hashtags on target platform             │   │
│  │    2. Research current viral formats                                  │   │
│  │    3. Generate platform-optimized caption                             │   │
│  │                                                                       │   │
│  │  Timeout: 120 seconds per clip                                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│                     SEOCaption objects saved as JSON                         │
│                    outputs/<id>/clip_X_platform_seo.json                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SUBTITLE GENERATION STAGE (Optional)                    │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         AssemblyAI                                    │   │
│  │                                                                       │   │
│  │  For each clip:                                                       │   │
│  │    1. Extract audio segment (FFmpeg)                                  │   │
│  │    2. Transcribe with word-level timestamps                           │   │
│  │    3. Generate ASS subtitle file with karaoke styling                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│                          tmp/clip_X_platform.ass                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RENDER STAGE                                       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                           FFmpeg                                      │   │
│  │                                                                       │   │
│  │  Pipeline:                                                            │   │
│  │    1. Trim source video to clip timestamps                            │   │
│  │    2. Create blurred background (scale + blur)                        │   │
│  │    3. Overlay sharp 16:9 video centered                               │   │
│  │    4. Burn in ASS subtitles (if enabled)                              │   │
│  │    5. Encode to H.264/AAC                                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│                   outputs/<id>/clip_X_platform.mp4                           │
│                          (1080x1920, 9:16)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Input Processing

```
YouTube URL
    │
    ├── Extract video ID (regex)
    │
    ├── Download video (yt-dlp)
    │   └── tmp/<video_id>.mp4
    │
    └── Download captions (yt-dlp)
        └── tmp/<video_id>.en.vtt
            │
            └── Parse VTT to timestamped transcript
                └── "[0:15] First sentence here\n[0:18] Second sentence..."
```

### 2. Clip Identification

```
Transcript + Prompt
    │
    └── Gemini 3 Pro
        │
        └── JSON Array
            [
              {
                "platform": "tiktok",
                "start": "1:45",
                "end": "2:12",
                "transcript": "...",
                "hook": "..."
              },
              ...
            ]
            │
            └── Parse to List[Clip]
```

### 3. SEO Generation

```
For each Clip:
    │
    └── Gemini 3 Flash + Google Search
        │
        ├── Search: "[topic] trending hashtags [platform] 2025"
        ├── Search: "[topic] viral hooks"
        │
        └── Generate SEOCaption
            {
              "caption": "...",
              "hashtags": [...]
            }
            │
            └── Save to clip_X_platform_seo.json
```

### 4. Video Rendering

```
For each Clip:
    │
    ├── (Optional) Generate subtitles
    │   └── AssemblyAI → ASS file
    │
    └── FFmpeg render
        │
        ├── Input: source video
        ├── Trim: clip.start → clip.end
        ├── Filter: blur background + overlay sharp
        ├── Subtitles: burn in ASS (if exists)
        │
        └── Output: 1080x1920 MP4
```

## Component Details

### clipper.py (Main CLI)

**Responsibilities:**
- User interaction and prompts
- Orchestrate the pipeline
- Error handling and cleanup

**Key Functions:**
- `download_video()` - yt-dlp wrapper
- `parse_vtt_to_transcript()` - VTT parser
- `find_clips()` - Gemini API call
- `select_clips()` - Interactive selection
- `main()` - Pipeline orchestration

### clip_cutter/models.py

**Data Classes:**
```python
@dataclass
class Clip:
    index: int
    platform: str      # "tiktok" | "youtube_shorts" | "reels" | "linkedin"
    start: float       # seconds
    end: float         # seconds
    transcript: str
    hook: str
    caption: str | None
```

### clip_cutter/seo.py

**Responsibilities:**
- SEO caption generation with web search grounding
- Hashtag research
- Fallback handling

**Key Functions:**
- `generate_seo_caption()` - Single clip SEO
- `generate_seo_for_clips()` - Batch processing
- `save_seo_caption()` - JSON output

**API Configuration:**
- Model: `gemini-3-flash-preview`
- Tools: `GoogleSearch` grounding
- Timeout: 120 seconds

### clip_cutter/captions.py

**Responsibilities:**
- Audio extraction
- Speech-to-text transcription
- ASS subtitle generation

**Key Functions:**
- `extract_audio_segment()` - FFmpeg audio extraction
- `transcribe_with_assemblyai()` - API call
- `generate_ass_subtitles()` - ASS file generation
- `_generate_pop_karaoke_events()` - TikTok-style animation

**Subtitle Positioning:**
```
Frame: 1080x1920 (portrait)
Video: 1080x608 (16:9, centered)
Video bottom edge: 1264px from top
Caption position: 1360px from top (96px gap)
MarginV: 560 (from bottom)
```

### clip_cutter/render.py

**Responsibilities:**
- FFmpeg pipeline construction
- Video composition
- Progress reporting

**FFmpeg Filter Graph:**
```
[0:v] trim=start:end, setpts=PTS-STARTPTS [trimmed]
[trimmed] scale=1080:1920:force_original_aspect_ratio=increase,
          crop=1080:1920, boxblur=20:5 [bg]
[trimmed] scale=1080:-2 [fg]
[bg][fg] overlay=(W-w)/2:(H-h)/2 [comp]
[comp] subtitles=captions.ass [out]
```

## Error Handling

### API Timeouts

All API calls include:
- Timeout configuration
- Elapsed time tracking
- Detailed error logging

```python
try:
    response = client.models.generate_content(...)
except Exception as e:
    elapsed = time.time() - start_time
    print(f"❌ API ERROR")
    print(f"   Elapsed: {elapsed:.1f}s")
    print(f"   Error: {e}")
    if elapsed >= timeout * 0.95:
        print(f"   ⚠️ Likely timeout")
```

### Fallback Behavior

| Component | Failure Mode | Fallback |
|-----------|--------------|----------|
| Transcript download | No captions available | Continue without, warn user |
| Clip extraction | API error | Raise, stop pipeline |
| SEO generation | API error | Use default hashtags |
| Subtitle generation | API error | Render without subtitles |
| Video render | FFmpeg error | Raise, stop pipeline |

## File System

### Directory Structure

```
clip-cutter/
├── tmp/                    # Temporary (auto-cleaned)
│   ├── <video_id>.mp4      # Downloaded source
│   ├── <video_id>.en.vtt   # Downloaded captions
│   └── clip_X_platform.ass # Generated subtitles
│
├── outputs/                # Persistent (git-ignored)
│   └── <video_id>/
│       ├── clip_1_tiktok.mp4
│       ├── clip_1_tiktok_seo.json
│       ├── clip_2_youtube_shorts.mp4
│       └── ...
│
└── prompts/                # AI prompts
    ├── clip_extraction.txt
    └── seo_captions.txt
```

### Cleanup Policy

- `tmp/` is cleaned after successful run
- `tmp/` is cleaned on error/interrupt
- `outputs/` persists between runs
- `outputs/` is git-ignored

## Platform-Specific Rules

### Clip Duration

| Platform | Min | Max | Optimal |
|----------|-----|-----|---------|
| TikTok | 21s | 34s | 25-30s |
| YouTube Shorts | 30s | 58s | 45-55s |
| Instagram Reels | 15s | 30s | 20-25s |
| LinkedIn | 45s | 90s | 60-75s |

### Hashtag Counts

| Platform | Count | Strategy |
|----------|-------|----------|
| TikTok | 5-8 | Mix viral + niche |
| YouTube Shorts | 3-5 | Include #Shorts |
| Instagram Reels | 20-30 | Maximize discovery |
| LinkedIn | 3-5 | Professional only |

## Performance Characteristics

### Typical Timing

| Stage | Time | Notes |
|-------|------|-------|
| Download | 10-60s | Depends on video length |
| Clip extraction | 15-30s | Single API call |
| SEO (per clip) | 10-20s | Includes web search |
| Subtitles (per clip) | 20-40s | Depends on clip length |
| Render (per clip) | 30-120s | Depends on clip length |

### API Costs (Estimates)

| API | Model | Cost |
|-----|-------|------|
| Gemini (extraction) | gemini-3-pro-preview | Free tier |
| Gemini (SEO) | gemini-3-flash-preview | Free tier |
| AssemblyAI | - | $0.00025/second |

## Security Considerations

- API keys stored in `.env` (git-ignored)
- No user data persisted beyond video processing
- Temporary files cleaned automatically
- No network requests except to APIs

## Future Considerations

### Potential Enhancements

1. **Batch Processing** - Process multiple videos
2. **Custom Prompts** - User-defined extraction criteria
3. **Template System** - Custom subtitle styles
4. **Preview Mode** - Preview clips before render
5. **Resume Support** - Continue interrupted processing
