# Plan: Stock Videos, Photo Pop-ups & Sound Effects

## Summary
Add AI-driven stock video inserts, photo pop-ups with sound effects, and user-selectable tone styles to clip-cutter.

## User Requirements
- **Stock videos**: Both B-roll cuts AND PiP overlays (AI decides based on context)
- **Photo pop-ups**: Triggered by keywords, timed intervals, AND emotion/emphasis
- **Tone selection**: User picks the style (meme, professional, educational, hype)
- **SFX**: Pre-bundled library + optional AI-generated via ElevenLabs
- **Render engine**: Keep FFmpeg (complex filter_complex, but faster)
- **Stock API**: Pexels (free) + Shutterstock (paid, optional)

---

## New Files to Create

### 1. `clip_cutter/stock.py` - Stock Media Fetching
```python
# PexelsClient class with API key from .env
# - search_videos(query, orientation="portrait", count=5)
# - search_photos(query, count=5)
# - download_media(url, dest_path) -> Path
# - Cache downloaded assets in tmp/stock/
```

### 2. `clip_cutter/overlays.py` - Overlay Manager
```python
# OverlayEvent dataclass:
#   - type: "broll" | "pip" | "popup"
#   - start_time: float
#   - duration: float
#   - media_path: Path
#   - sfx_path: Path | None
#   - position: tuple (x, y) or "center"
#   - animation: "fade" | "scale" | "slide"

# generate_overlay_events(clip, transcript, tone) -> list[OverlayEvent]
#   - Calls Gemini to analyze transcript for overlay opportunities
#   - Fetches relevant stock media from Pexels
#   - Assigns SFX based on tone

# Tone presets: MEME, PROFESSIONAL, EDUCATIONAL, HYPE
#   Each defines: popup_style, sfx_set, broll_frequency
```

### 3. `clip_cutter/sfx.py` - Sound Effects Manager
```python
# get_bundled_sfx(category: str) -> Path
#   Categories: whoosh, pop, boom, ding, etc.

# generate_sfx_elevenlabs(description: str) -> Path
#   Optional AI generation for custom sounds

# SFX categories per tone:
#   MEME: vine_boom, bruh, airhorn
#   PROFESSIONAL: subtle_whoosh, soft_ding
#   EDUCATIONAL: marker_write, pointer_tap
#   HYPE: bass_drop, explosion, fire
```

### 4. `prompts/overlay_analysis.txt` - AI Prompt for Overlay Detection
```
Given a clip transcript, identify moments for:

1. B-roll cuts: When speaker mentions visual concepts (money, nature, city, etc.)
2. PiP overlays: When showing supplementary info while speaker continues
3. Photo pop-ups: Keywords, emphasis moments, punchlines

Output JSON format:
[
  {
    "timestamp": "0:15",
    "type": "broll",
    "media_query": "money cash dollars",
    "duration": 2.5,
    "reason": "Speaker says 'making money'"
  },
  {
    "timestamp": "0:32",
    "type": "popup",
    "media_query": "shocked face meme",
    "duration": 1.5,
    "emotion": "surprise",
    "reason": "Punchline delivery"
  }
]
```

### 5. `assets/sfx/` - Pre-bundled Sound Effects Directory
```
assets/sfx/
├── meme/
│   ├── vine_boom.mp3
│   ├── bruh.mp3
│   ├── airhorn.mp3
│   └── oof.mp3
├── professional/
│   ├── whoosh_soft.mp3
│   ├── ding.mp3
│   └── click.mp3
├── educational/
│   ├── marker.mp3
│   ├── pointer.mp3
│   └── page_turn.mp3
└── hype/
    ├── bass_drop.mp3
    ├── explosion.mp3
    ├── fire.mp3
    └── crowd_cheer.mp3
```

---

## Files to Modify

### 1. `clip_cutter/render.py`

Add new functions:
```python
def build_overlay_filter(
    base_filter: str,
    overlay_events: list[OverlayEvent],
    video_inputs: list[Path]
) -> tuple[str, list[str]]:
    """
    Generate FFmpeg filter_complex for overlays.

    Returns (filter_string, input_args)
    """

def mix_audio_with_sfx(
    main_audio: str,
    sfx_events: list[tuple[Path, float]]  # (sfx_path, start_time)
) -> str:
    """
    Generate FFmpeg audio filter for mixing SFX.
    """
```

Update `render_clip()`:
```python
def render_clip(
    video_path: Path,
    clip: Clip,
    output_dir: Path,
    captions_path: Path | None = None,
    overlay_events: list[OverlayEvent] | None = None,  # NEW
) -> Path:
```

### 2. `clipper.py`

Add new steps after clip selection:

```python
# STEP 3.5: Tone Selection
print("\n🎨 STEP 3.5: Select Tone")
print("─" * 60)

tone_choice = prompt_choice(
    "What vibe do you want for enhancements?",
    [
        "Meme/Comedy - Vine boom, ironic zooms, flashy effects",
        "Professional - Clean animations, subtle whoosh sounds",
        "Educational - Diagrams, pointers, marker sounds",
        "Hype/Energy - Explosions, fire, bass drops",
    ],
    default=0
)
tone = [Tone.MEME, Tone.PROFESSIONAL, Tone.EDUCATIONAL, Tone.HYPE][tone_choice]

# STEP 3.6: Enhancement Options
print("\n✨ STEP 3.6: Enhancement Options")
print("─" * 60)

enable_stock = prompt_yes_no("Enable stock video inserts (B-roll & PiP)?", default=True)
enable_popups = prompt_yes_no("Enable photo pop-ups?", default=True)

sfx_choice = prompt_choice(
    "Sound effects mode:",
    [
        "Bundled only (fast, no API calls)",
        "AI-generated (requires ElevenLabs key)",
        "Off (no sound effects)",
    ],
    default=0
)
```

### 3. `clip_cutter/models.py`

Add new types:
```python
from enum import Enum

class Tone(Enum):
    MEME = "meme"
    PROFESSIONAL = "professional"
    EDUCATIONAL = "educational"
    HYPE = "hype"

@dataclass
class OverlayConfig:
    tone: Tone
    enable_stock_video: bool = True
    enable_popups: bool = True
    enable_sfx: bool = True
    use_ai_sfx: bool = False
```

### 4. `.env.example`

Add:
```
# Pexels API (free) - https://www.pexels.com/api/
PEXELS_API_KEY=

# ElevenLabs (optional, for AI-generated SFX)
ELEVENLABS_API_KEY=
```

### 5. `requirements.txt`

Add:
```
requests>=2.31.0
elevenlabs>=0.2.0  # optional
```

---

## FFmpeg Filter Strategy

For a clip with B-roll at 5-7s and a popup at 10-12s:

```bash
# Input streams:
# [0] = main video (clip segment)
# [1] = broll.mp4 (stock video)
# [2] = popup.png (stock image)
# [3] = sfx.mp3 (sound effect)

ffmpeg -y \
  -ss 30 -t 28 -i source.mp4 \           # [0] main clip
  -i tmp/stock/money_broll.mp4 \          # [1] b-roll
  -i tmp/stock/shocked_popup.png \        # [2] popup image
  -i assets/sfx/meme/vine_boom.mp3 \      # [3] sfx
  -filter_complex "
    # Base vertical format (existing)
    [0:v]split=2[main][bg];
    [bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[blurred];
    [main]scale=1080:-1[fg];
    [blurred][fg]overlay=(W-w)/2:(H-h)/2[base];

    # B-roll cut at 5-7s
    [1:v]scale=1080:1920,setpts=PTS-STARTPTS[broll];
    [base][broll]overlay=0:0:enable='between(t,5,7)'[with_broll];

    # Photo popup at 10-12s (fade in, positioned bottom-right)
    [2:v]scale=250:-1,fade=in:st=0:d=0.3,fade=out:st=1.7:d=0.3[popup];
    [with_broll][popup]overlay=W-w-50:H-h-400:enable='between(t,10,12)'[final]
  " \
  -filter_complex "[0:a][3:a]amix=inputs=2:duration=first[aout]" \
  -map "[final]" -map "[aout]" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k \
  output.mp4
```

---

## Workflow Integration

### Current Flow
```
Download → AI Analysis → Select Clips → SEO → Captions → Render
```

### New Flow
```
Download → AI Analysis → Select Clips → TONE SELECT → OVERLAY ANALYSIS → SEO → Captions → Render
                                             ↓               ↓
                                        User picks      Gemini identifies
                                        meme/pro/       overlay moments,
                                        edu/hype        fetches stock media
```

---

## Example CLI Session (New Steps)

```
🎬 CLIP CUTTER
   Extract viral clips from YouTube videos
═══════════════════════════════════════════════════════

📺 STEP 1: Enter YouTube URL
────────────────────────────────────────────────────────
Paste YouTube URL: https://youtube.com/watch?v=abc123

⬇️  STEP 2: Downloading
────────────────────────────────────────────────────────
✅ Downloaded: abc123.mp4
📝 Transcript loaded: 15432 chars

🔍 STEP 3: AI Analysis
────────────────────────────────────────────────────────
✅ Found 9 potential clips

📋 AVAILABLE CLIPS
────────────────────────────────────────────────────────
  1. [TIKTOK  ]  28s │ "The biggest mistake I made was..."
  ...

Your selection: 1,3,5
✓ Selected 3 clip(s)

🎨 STEP 3.5: Select Tone                               # NEW
────────────────────────────────────────────────────────
What vibe do you want for enhancements?
  → 1. Meme/Comedy - Vine boom, ironic zooms, flashy effects
    2. Professional - Clean animations, subtle whoosh sounds
    3. Educational - Diagrams, pointers, marker sounds
    4. Hype/Energy - Explosions, fire, bass drops

Enter choice [1-4] (default: 1): 1

✨ STEP 3.6: Enhancement Options                        # NEW
────────────────────────────────────────────────────────
Enable stock video inserts (B-roll & PiP)? [Y/n]: y
Enable photo pop-ups? [Y/n]: y
Sound effects mode:
  → 1. Bundled only (fast, no API calls)
    2. AI-generated (requires ElevenLabs key)
    3. Off (no sound effects)

Enter choice [1-3] (default: 1): 1

🎬 STEP 3.7: Analyzing for Overlays                     # NEW
────────────────────────────────────────────────────────
⏳ Analyzing clip 1 for overlay opportunities...
   Found 3 B-roll moments, 2 popup moments
   📥 Fetching stock: "money cash"... ✅
   📥 Fetching stock: "surprised reaction"... ✅

🔎 STEP 4: SEO Caption Generation
────────────────────────────────────────────────────────
...
```

---

## Implementation Order

1. **Create `assets/sfx/`** - Bundle 12-15 royalty-free sound effects
2. **Create `clip_cutter/sfx.py`** - SFX manager with tone mappings
3. **Create `clip_cutter/stock.py`** - Pexels API client
4. **Create `prompts/overlay_analysis.txt`** - AI prompt for detection
5. **Create `clip_cutter/overlays.py`** - Overlay event generation
6. **Update `clip_cutter/models.py`** - Add Tone enum, OverlayConfig
7. **Update `clip_cutter/render.py`** - Add overlay filter building
8. **Update `clipper.py`** - Add tone/overlay selection steps
9. **Update `.env.example` and `requirements.txt`**
10. **Test end-to-end** with a sample video

---

## API Costs

| API | Cost | Usage Limits |
|-----|------|--------------|
| Pexels | **Free** | 200 requests/hour, 20,000/month |
| ElevenLabs SFX | Free tier | ~10 generations/month |
| Gemini (overlay analysis) | Free tier | 1 call per clip |

---

## Sources & References

- [Pexels API Documentation](https://www.pexels.com/api/documentation/)
- [MoviePy Compositing Guide](https://zulko.github.io/moviepy/getting_started/compositing.html)
- [SFX Engine](https://sfxengine.com/) - AI-powered sound effects
- [ElevenLabs Sound Effects](https://elevenlabs.io/sound-effects/whoosh)
- [Shutterstock API](https://api-reference.shutterstock.com/) (premium option)
