# Clip Cutter - Technical Specification

A Python CLI tool that extracts viral clips from YouTube videos and reformats them for vertical social media platforms (TikTok, Instagram Reels, LinkedIn).

---

## Overview

### What It Does

1. Downloads a YouTube video + auto-generated captions
2. Uses Gemini AI to analyze the transcript and identify viral clip opportunities
3. Lets user select which clips to process
4. Renders each clip as a vertical (9:16) video with:
   - Blurred background filling the full frame
   - Sharp 16:9 video centered in the middle
   - Burned-in captions positioned just below the video
5. Outputs MP4 files ready for upload

### Tech Stack

- **Python 3.13**
- **yt-dlp** - YouTube downloading
- **google-generativeai** - Gemini API for transcript analysis
- **opencv-python** - Video frame extraction (if needed)
- **Pillow** - Image processing (if needed)
- **FFmpeg** - Video rendering (called via subprocess)
- **python-dotenv** - Environment variable management

---

## Project Structure

```
clip-cutter/
├── clipper.py              # Main CLI script (single file, ~300 lines)
├── prompts/
│   └── clip_extraction.txt # Prompt for Gemini to find clips
├── tmp/                    # Downloaded videos (gitignored)
├── outputs/                # Processed clips go here
├── .env                    # GEMINI_API_KEY (gitignored)
├── .env.example            # Template for .env
├── .gitignore
├── requirements.txt
├── README.md
└── SPEC.md                 # This file
```

---

## Video Output Format

### Final Composition (9:16 Portrait - 1080x1920)

```
┌─────────────────────────┐
│░░░░░░░░░░░░░░░░░░░░░░░░░│
│░░░░░░░░░░░░░░░░░░░░░░░░░│  ← LAYER 1: Blurred background (top)
│░░░░░░░░░░░░░░░░░░░░░░░░░│
├─────────────────────────┤
│                         │
│   ORIGINAL 16:9 VIDEO   │  ← LAYER 2: Sharp video (1080x608, centered)
│       (1080x608)        │
│                         │
├─────────────────────────┤
│░░░░░░░░░░░░░░░░░░░░░░░░░│
│░░ "Captions go here" ░░░│  ← LAYER 3: Captions (just below video)
│░░░░░░░░░░░░░░░░░░░░░░░░░│
│░░░░░░░░░░░░░░░░░░░░░░░░░│  ← Blurred background continues (bottom)
│░░░░░░░░░░░░░░░░░░░░░░░░░│
└─────────────────────────┘
```

### Layer Details

**Layer 1 - Blurred Background:**
- Take original 16:9 video
- Scale UP to fill 1080x1920 (will crop sides)
- Apply gaussian blur (boxblur 20:5 in FFmpeg)
- This fills the entire frame

**Layer 2 - Sharp Foreground:**
- Take original 16:9 video
- Scale to width 1080, maintain aspect ratio → 1080x608
- Center vertically on the frame
- NO blur, sharp/crisp

**Layer 3 - Captions:**
- Extract from .vtt subtitle file
- Position: Just below the sharp video area
- Style: White text, black outline, bold sans-serif font
- Synced to timestamps from .vtt

### FFmpeg Filter Graph

```
[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];
[0:v]scale=1080:-1[fg];
[bg][fg]overlay=(W-w)/2:(H-h)/2,
subtitles=captions.vtt:force_style='Alignment=2,MarginV=250,FontSize=24,FontName=Arial Bold,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2'
```

**Caption positioning note:**
- `Alignment=2` = bottom center
- `MarginV=250` = pixels from bottom (adjust so it sits just below the 16:9 video)
- The sharp video is 608px tall, centered in 1920px frame
- Video top edge: (1920-608)/2 = 656px from top
- Video bottom edge: 656 + 608 = 1264px from top
- So captions should start around y=1280-1350 (MarginV of ~570-640 from bottom)

---

## CLI Interface

### Usage

```bash
python clipper.py <youtube_url> [options]

Options:
  --all         Process all identified clips without prompting
  --output DIR  Output directory (default: ./outputs)
```

### Example Session

```
$ python clipper.py "https://youtube.com/watch?v=abc123"

============================================================
🎬 CLIP CUTTER
============================================================

⬇️  Downloading abc123...
✅ Downloaded: abc123.mp4
📝 Transcript: 4523 chars

🔍 Analyzing transcript for clips...
✅ Found 6 clips

------------------------------------------------------------
📋 SELECT CLIPS TO PROCESS
------------------------------------------------------------
Enter clip numbers (comma-separated), 'all', or 'q' to quit:

  1. [TIKTOK  ]   27s | "The biggest mistake I made was..."
  2. [TIKTOK  ]   31s | "Here's what actually works when..."
  3. [LINKEDIN]   68s | "Most developers don't realize..."
  4. [REELS   ]   18s | "Quick tip: always start with..."
  5. [TIKTOK  ]   24s | "I wasted 6 months because..."
  6. [LINKEDIN]   55s | "The framework I use now is..."

> 1,2,3

------------------------------------------------------------
🎬 PROCESSING 3 CLIPS
------------------------------------------------------------

Clip 1 (tiktok):
   🎬 Rendering vertical video...
   ✅ Saved: clip_1_tiktok.mp4

Clip 2 (tiktok):
   🎬 Rendering vertical video...
   ✅ Saved: clip_2_tiktok.mp4

Clip 3 (linkedin):
   🎬 Rendering vertical video...
   ✅ Saved: clip_3_linkedin.mp4
   📝 Caption saved: clip_3_caption.txt

============================================================
🎉 DONE! Clips saved to: outputs/abc123/
============================================================
```

---

## Core Functions

### 1. download_video(youtube_url: str) -> tuple[Path, str, Path]

Downloads the YouTube video and captions.

**Input:** YouTube URL (any format: youtube.com/watch?v=, youtu.be/, etc.)

**Process:**
1. Extract video ID from URL using regex
2. Run yt-dlp to download video:
   ```bash
   yt-dlp -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best" \
     --merge-output-format mp4 \
     -o "tmp/{video_id}.mp4" \
     "{url}"
   ```
3. Run yt-dlp to download captions:
   ```bash
   yt-dlp --write-auto-sub --sub-lang en --convert-subs vtt \
     --skip-download \
     -o "tmp/{video_id}" \
     "{url}"
   ```
4. Parse .vtt file to extract plain text transcript with timestamps

**Output:** 
- `video_path`: Path to downloaded MP4
- `transcript`: String with timestamped text for Gemini
- `captions_path`: Path to .vtt file for FFmpeg subtitles

**Transcript format for Gemini:**
```
[0:00:05] Hey everyone, welcome back to the channel
[0:00:08] Today I want to talk about something important
[0:00:12] The biggest mistake I made when starting out...
```

---

### 2. find_clips(transcript: str) -> list[Clip]

Uses Gemini to identify viral clip opportunities.

**Input:** Timestamped transcript string

**Process:**
1. Load prompt from `prompts/clip_extraction.txt`
2. Send to Gemini: prompt + transcript
3. Parse JSON response into Clip objects

**Clip dataclass:**
```python
@dataclass
class Clip:
    index: int
    platform: str      # "tiktok" | "linkedin" | "reels"
    start: float       # seconds
    end: float         # seconds
    transcript: str    # the words in this clip
    hook: str          # the attention-grabbing opener
    caption: str | None  # LinkedIn caption (only for linkedin clips)
```

**Output:** List of Clip objects

---

### 3. select_clips(clips: list[Clip]) -> list[Clip]

Interactive terminal UI for selecting clips.

**Input:** All identified clips

**Process:**
1. Display numbered list with platform, duration, preview text
2. Prompt user for selection (comma-separated numbers, "all", or "q")
3. Validate input

**Output:** Selected clips only

---

### 4. render_clip(video_path: Path, captions_path: Path, clip: Clip, output_dir: Path) -> Path

Renders a single vertical clip with FFmpeg.

**Input:**
- `video_path`: Source MP4
- `captions_path`: Source VTT
- `clip`: Clip object with start/end times
- `output_dir`: Where to save output

**Process:**
1. Create temp VTT file with only captions for this clip's time range (adjust timestamps to start at 0)
2. Build FFmpeg command:
   ```bash
   ffmpeg -y \
     -ss {start} -to {end} \
     -i {video_path} \
     -filter_complex "
       [0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];
       [0:v]scale=1080:-1[fg];
       [bg][fg]overlay=(W-w)/2:(H-h)/2,
       subtitles={temp_vtt}:force_style='Alignment=2,MarginV=600,FontSize=28,FontName=Arial,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Bold=1'
     " \
     -c:v libx264 -preset fast -crf 23 \
     -c:a aac -b:a 128k \
     -movflags +faststart \
     {output_path}
   ```
3. Run FFmpeg via subprocess
4. Clean up temp VTT file

**Output:** Path to rendered MP4

**Caption MarginV Calculation:**
- Output frame: 1080x1920
- Sharp video height: 1080 * (9/16) = 607.5 ≈ 608px
- Video is centered: top at (1920-608)/2 = 656px
- Video bottom at: 656 + 608 = 1264px
- Want captions just below video, say 20px gap: y = 1284px
- MarginV is from BOTTOM: 1920 - 1284 = 636px
- Round to ~600-650 for MarginV

---

### 5. extract_clip_captions(vtt_path: Path, start: float, end: float) -> Path

Creates a temporary VTT file with only the captions for a specific clip.

**Input:**
- `vtt_path`: Full video's captions
- `start`: Clip start time in seconds
- `end`: Clip end time in seconds

**Process:**
1. Parse original VTT
2. Filter to only captions within start-end range
3. Adjust timestamps so clip starts at 0:00
4. Write to temp file

**Output:** Path to temp VTT file

---

## Gemini Prompt (prompts/clip_extraction.txt)

```
You are a viral content strategist analyzing YouTube video transcripts to extract high-performing short-form clips for TikTok, Instagram Reels, and LinkedIn.

INPUT: A YouTube video transcript with timestamps

YOUR TASK: Identify 6-10 clip opportunities from this transcript that maximize virality potential across platforms.

CLIP IDENTIFICATION CRITERIA:
Look for moments that contain:
- A complete micro-story or point made in under 60 seconds
- Surprising statistics or counterintuitive reveals
- "Most people don't know this" knowledge gaps
- Mistakes followed by solutions
- Controversial or contrarian takes
- Specific pain points with immediate fixes
- Aha moments where complexity becomes simple

PLATFORM REQUIREMENTS:

**TikTok (identify 3-4 clips, 21-34 seconds each):**
- Hook must land in first 3 seconds
- Lead with payoff, not setup
- Casual, direct language

**LinkedIn (identify 2-3 clips, 45-90 seconds each):**
- Start with a professional pain point
- Tie to career impact or business value
- More polished, complete thoughts

**Instagram Reels (identify 2-3 clips, 15-30 seconds each):**
- Front-load the transformation or result
- Extreme brevity—one clear point only

OUTPUT FORMAT:
Return ONLY a valid JSON array with this exact structure:

[
  {
    "platform": "tiktok",
    "start": "1:45",
    "end": "2:12",
    "transcript": "exact words from this segment",
    "hook": "the attention-grabbing opening line",
    "caption": null
  },
  {
    "platform": "linkedin",
    "start": "5:30",
    "end": "6:45",
    "transcript": "exact words from this segment",
    "hook": "the attention-grabbing opening line",
    "caption": "Write a 2-3 paragraph LinkedIn caption:\n- Open with a scroll-stopping hook\n- Tie to career/business value\n- End with an engagement question"
  }
]

RULES:
- Use exact timestamps from the transcript (format: M:SS or MM:SS)
- Clips must stand alone without previous context
- Each clip needs clear beginning, middle, and payoff
- LinkedIn clips MUST include a caption, others set caption to null
- Return ONLY the JSON array, no other text
```

---

## Environment Variables

**.env file:**
```
GEMINI_API_KEY=your_api_key_here
```

Get API key from: https://aistudio.google.com/apikey

---

## Dependencies

**requirements.txt:**
```
google-generativeai>=0.8.0
opencv-python>=4.8.0
pillow>=10.0.0
python-dotenv>=1.0.0
yt-dlp>=2024.1.0
```

**System dependencies (must be installed separately):**
- FFmpeg (with libx264 and AAC support)

---

## Error Handling

### No captions available
- Warn user: "No captions found for this video"
- Offer to continue without captions (clips will have no subtitles)
- Future enhancement: Whisper transcription fallback

### FFmpeg not installed
- Check for FFmpeg at startup: `ffmpeg -version`
- Exit with helpful error message if not found

### Gemini API errors
- Catch rate limits, display retry message
- Catch invalid responses, show raw response for debugging

### Invalid clip selection
- Re-prompt user on invalid input
- Allow 'q' to quit gracefully

---

## File Outputs

For each processed video, creates:
```
outputs/
└── {video_id}/
    ├── clip_1_tiktok.mp4
    ├── clip_2_tiktok.mp4
    ├── clip_3_linkedin.mp4
    ├── clip_3_caption.txt    # LinkedIn post copy
    └── clip_4_reels.mp4
```

---

## Testing

### Manual test flow:
1. Find a YouTube video with auto-captions
2. Run: `python clipper.py "https://youtube.com/watch?v=..."`
3. Select 1-2 clips
4. Verify output:
   - Is it 1080x1920?
   - Is background blurred?
   - Is center video sharp?
   - Are captions positioned just below video?
   - Is audio synced?

### Test video suggestions:
- Any talking-head video with clear speech
- Videos with auto-generated English captions
- 5-15 minute length (enough content for clips)

---

## Implementation Notes

### Timestamp Parsing
Transcript timestamps can be in multiple formats:
- `0:45` (M:SS)
- `1:23:45` (H:MM:SS)  
- `00:01:23.456` (HH:MM:SS.mmm from VTT)

Normalize all to float seconds.

### VTT Parsing
VTT files have this structure:
```
WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:03.500
Hey everyone welcome back

00:00:03.500 --> 00:00:07.200
Today I want to talk about something
```

Skip header lines, parse timestamp --> timestamp, extract text.

### Gemini Model
Use `gemini-2.0-flash` or `gemini-1.5-flash` for cost efficiency.
When Gemini 3 Pro is widely available, can upgrade for better analysis.

```python
import google.generativeai as genai
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")
response = model.generate_content(prompt + transcript)
```

---

## Future Enhancements (Out of Scope for V1)

- [ ] Whisper fallback for videos without captions
- [ ] Face-tracking crop (center on speaker's face)
- [ ] Multiple caption styles (word-by-word highlight, karaoke)
- [ ] Batch processing multiple URLs
- [ ] Web UI (Next.js frontend)
- [ ] Auto-upload to platforms via APIs
