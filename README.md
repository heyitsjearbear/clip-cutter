# Clip Cutter

A Python CLI tool that extracts viral clips from YouTube videos and reformats them for vertical social media platforms (TikTok, YouTube Shorts, Instagram Reels, LinkedIn).

## Features

- **AI-Powered Clip Detection** - Gemini AI analyzes transcripts to find viral moments across 4 platforms
- **SEO-Optimized Captions** - Gemini with Google Search grounding researches trending hashtags in real-time
- **Vertical Video Rendering** - 9:16 format with blurred background + sharp centered video
- **Professional Subtitles** - AssemblyAI transcription with TikTok-style word-by-word highlighting
- **Interactive CLI** - Step-by-step guided experience, no flags to memorize

## Supported Platforms

| Platform | Clip Duration | Hashtags |
|----------|---------------|----------|
| TikTok | 21-34 seconds | 5-8 |
| YouTube Shorts | 30-58 seconds | 3-5 |
| Instagram Reels | 15-30 seconds | 20-30 |
| LinkedIn | 45-90 seconds | 3-5 |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up API keys
cp .env.example .env
# Edit .env with your keys

# 3. Run it!
python clipper.py
```

## Requirements

- Python 3.11+
- FFmpeg (with libx264 and AAC support)
- yt-dlp (installed via requirements.txt)

## Installation

### 1. Clone and setup

```bash
git clone <repo-url> clip-cutter
cd clip-cutter
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Install FFmpeg

**Windows:**
```bash
winget install FFmpeg
```

**Mac:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

Restart your terminal after installing.

### 3. Get API Keys

Copy the example env file:
```bash
cp .env.example .env
```

Then add your API keys:

#### Gemini API Key (Required)

Used for AI analysis to identify viral clips and generate SEO captions.

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Click "Create API Key"
3. Copy the key to your `.env` file:
   ```
   GEMINI_API_KEY=your_key_here
   ```

**Cost:** Free tier available (60 requests/minute)

#### AssemblyAI API Key (Optional)

Used for professional subtitle generation with word-level timestamps.

1. Go to [AssemblyAI](https://www.assemblyai.com/)
2. Sign up for a free account
3. Go to Dashboard > API Keys
4. Copy the key to your `.env` file:
   ```
   ASSEMBLYAI_API_KEY=your_key_here
   ```

**Cost:** Free tier includes 100 hours of transcription

## Usage

Run the interactive CLI:
```bash
python clipper.py
```

### Workflow Steps

```
Step 1: Enter YouTube URL
Step 2: Download video + transcript
Step 3: AI Analysis (find viral clips)
Step 4: SEO Caption Generation (trending hashtags)
Step 5: Video Subtitle Options (AssemblyAI)
Step 6: Render Clips
Done!
```

### Example Session

```
════════════════════════════════════════════════════════════
🎬 CLIP CUTTER
   Extract viral clips from YouTube videos
════════════════════════════════════════════════════════════

📺 STEP 1: Enter YouTube URL
────────────────────────────────────────────────────────────
Paste YouTube URL: https://youtube.com/watch?v=abc123

⬇️  STEP 2: Downloading
────────────────────────────────────────────────────────────
✅ Downloaded: abc123.mp4
📝 Transcript loaded: 15432 chars

🔍 STEP 3: AI Analysis
────────────────────────────────────────────────────────────
✅ Analysis complete (18.3s)
✅ Found 9 potential clips

📋 AVAILABLE CLIPS
────────────────────────────────────────────────────────────
  1. [TIKTOK  ]  28s │ "The biggest mistake I made was..."
  2. [TIKTOK  ]  31s │ "Here's what nobody tells you..."
  3. [YT_SHORT]  45s │ "Let me show you exactly how..."
  4. [REELS   ]  24s │ "I spent 3 years learning this..."
  5. [LINKEDIN]  67s │ "The real reason most people fail..."

Your selection: all

🔎 STEP 4: SEO Caption Generation
────────────────────────────────────────────────────────────
Generate SEO-optimized captions with trending hashtags? [Y/n]: y

Using Gemini with Google Search to research trending hashtags...
   Clip 1 (tiktok): ✅ (12.4s)
   Clip 2 (tiktok): ✅ (14.1s)
   ...
Saved 9 SEO caption files to outputs/abc123/

💬 STEP 5: Video Caption Options
────────────────────────────────────────────────────────────
  → 1. No captions (video only)
    2. AssemblyAI - Professional transcription with TikTok-style highlighting

🎬 STEP 6: Rendering Clips
────────────────────────────────────────────────────────────
   🎬 Rendering clip 1 (tiktok)...
   ✅ Saved: clip_1_tiktok.mp4

════════════════════════════════════════════════════════════
🎉 DONE!
   Clips saved to: outputs/abc123/
════════════════════════════════════════════════════════════
```

## Output Files

Clips are saved to `outputs/<video_id>/`:

```
outputs/abc123/
├── clip_1_tiktok.mp4           # Rendered vertical video
├── clip_1_tiktok_seo.json      # SEO caption + hashtags
├── clip_2_youtube_shorts.mp4
├── clip_2_youtube_shorts_seo.json
├── clip_3_reels.mp4
├── clip_3_reels_seo.json
└── ...
```

### SEO JSON Format

Each `*_seo.json` file contains:
```json
{
  "caption": "The hook line that stops the scroll\n\nThis changed everything...\n\nFollow for more\n\n#hashtag1 #hashtag2 #hashtag3",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"]
}
```

## Video Output Format

Each clip is rendered at **1080x1920** (9:16 portrait):

```
┌────────────────────────────┐
│     [Blurred Background]   │
│                            │
│   ┌────────────────────┐   │
│   │                    │   │
│   │   Sharp 16:9 Video │   │
│   │                    │   │
│   └────────────────────┘   │
│                            │
│     Subtitles appear here  │
│    (word-by-word highlight)│
│                            │
└────────────────────────────┘
```

## Subtitle Styles

When using AssemblyAI, choose between:

| Style | Description |
|-------|-------------|
| **TikTok** | Bold text, word-by-word pop animation (blue highlight) |
| **Standard** | Simple white text, no animation |

## API Cost Estimates

| API | Cost | Typical Usage |
|-----|------|---------------|
| Gemini (clip analysis) | Free tier | 1 call per video |
| Gemini (SEO per clip) | Free tier | 1 call per clip |
| AssemblyAI | $0.00025/sec | ~$0.01-0.02 per clip |

## Troubleshooting

**"FFmpeg not found"**
- Make sure FFmpeg is installed and in your PATH
- Restart your terminal after installing

**"GEMINI_API_KEY not set"**
- Create a `.env` file with your key
- Check that the key has no extra spaces

**"No transcript found"**
- The video may not have auto-generated captions
- You can still continue without captions

**API Timeout errors**
- Gemini calls have 2-minute timeout
- AssemblyAI has no timeout (charged per audio second)
- Error logs show elapsed time to help diagnose

## Project Structure

```
clip-cutter/
├── clipper.py              # Main interactive CLI
├── clip_cutter/            # Core modules
│   ├── models.py           # Data classes (Clip)
│   ├── utils.py            # Spinner, progress bar
│   ├── render.py           # FFmpeg video rendering
│   ├── captions.py         # AssemblyAI subtitle generation
│   └── seo.py              # SEO caption generation with Gemini
├── prompts/                # AI prompt templates
│   ├── clip_extraction.txt # Viral clip identification
│   └── seo_captions.txt    # SEO caption generation
├── outputs/                # Rendered clips (git-ignored)
└── tmp/                    # Temporary downloads (auto-cleaned)
```

## License

MIT
