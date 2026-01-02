# Clip Cutter

A Python CLI tool that extracts viral clips from YouTube videos and reformats them for vertical social media platforms (TikTok, Instagram Reels, LinkedIn).

## What It Does

1. Downloads a YouTube video + auto-generated transcript
2. Uses Gemini AI to analyze the transcript and identify viral clip opportunities
3. Lets you select which clips to process
4. Renders each clip as a vertical (9:16) video with:
   - Blurred background filling the full frame
   - Sharp 16:9 video centered in the middle
5. Outputs MP4 files ready for upload
6. Cleans up temporary files when done

## Requirements

- Python 3.11+
- FFmpeg (with libx264 and AAC support)
- A Gemini API key

## Installation

1. Clone this repository:
   ```bash
   cd ~/projects
   git clone <repo-url> clip-cutter
   cd clip-cutter
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/Scripts/activate
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install FFmpeg:
   ```bash
   winget install FFmpeg
   ```
   Then restart your terminal.

5. Set up your Gemini API key:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your API key from: https://aistudio.google.com/apikey

## Usage

1. Activate the virtual environment:
   ```bash
   cd ~/projects/clip-cutter
   source venv/Scripts/activate
   ```

2. Run the script:
   ```bash
   py clipper.py <youtube_url> [options]
   ```

### Options

- `--all` - Process all identified clips without prompting
- `--output DIR` - Output directory (default: ./outputs)

### Example

```bash
py clipper.py "https://youtube.com/watch?v=abc123"
```

This will:
1. Download the video and transcript
2. Analyze with Gemini AI to find 6-10 viral clip opportunities
3. Show you the clips and let you select which to process
4. Render the selected clips as vertical videos
5. Clean up temporary files

Output files are saved to `outputs/<video_id>/`.

## Output Format

Each clip is rendered at 1080x1920 (9:16 portrait) with:
- Blurred background (gaussian blur of the original video)
- Sharp foreground video (1080px wide, centered)

## License

MIT
