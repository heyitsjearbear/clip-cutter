#!/usr/bin/env python3
"""
Clip Cutter - Extract viral clips from YouTube videos for social media.
"""

import argparse
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class Spinner:
    """Animated spinner for long-running operations."""

    def __init__(self, message: str = ""):
        self.message = message
        self.running = False
        self.thread = None
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def _spin(self):
        for frame in itertools.cycle(self.frames):
            if not self.running:
                break
            print(f"\r{frame} {self.message}", end="", flush=True)
            time.sleep(0.1)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.start()

    def stop(self, final_message: str = ""):
        self.running = False
        if self.thread:
            self.thread.join()
        # Clear the line and print final message
        print(f"\r{' ' * (len(self.message) + 5)}\r", end="")
        if final_message:
            print(final_message)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()


class ProgressBar:
    """Progress bar for operations with known duration."""

    def __init__(self, total: float, width: int = 30, prefix: str = ""):
        self.total = total
        self.width = width
        self.prefix = prefix
        self.current = 0

    def update(self, current: float):
        self.current = min(current, self.total)
        percent = self.current / self.total if self.total > 0 else 0
        filled = int(self.width * percent)
        bar = "█" * filled + "░" * (self.width - filled)
        percent_str = f"{percent * 100:5.1f}%"
        print(f"\r   {self.prefix}[{bar}] {percent_str}", end="", flush=True)

    def finish(self):
        self.update(self.total)
        print()

load_dotenv()

# Constants
SCRIPT_DIR = Path(__file__).parent
TMP_DIR = SCRIPT_DIR / "tmp"
OUTPUTS_DIR = SCRIPT_DIR / "outputs"
PROMPTS_DIR = SCRIPT_DIR / "prompts"


@dataclass
class Clip:
    index: int
    platform: str  # "tiktok" | "linkedin" | "reels"
    start: float  # seconds
    end: float  # seconds
    transcript: str  # the words in this clip
    hook: str  # the attention-grabbing opener
    caption: str | None  # LinkedIn caption (only for linkedin clips)

    @property
    def duration(self) -> int:
        return int(self.end - self.start)


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def extract_video_id(url: str) -> str | None:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def parse_timestamp(ts: str) -> float:
    """Convert timestamp string to seconds. Handles M:SS, MM:SS, H:MM:SS, HH:MM:SS.mmm"""
    ts = ts.strip()
    parts = ts.replace(",", ".").split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    elif len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    else:
        return float(ts)


def format_timestamp(seconds: float) -> str:
    """Convert seconds to M:SS format."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def download_video(youtube_url: str) -> tuple[Path, str]:
    """
    Download YouTube video and transcript.
    Returns: (video_path, transcript_text)
    """
    video_id = extract_video_id(youtube_url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {youtube_url}")

    TMP_DIR.mkdir(exist_ok=True)
    video_path = TMP_DIR / f"{video_id}.mp4"

    # Download video with progress
    spinner = Spinner(f"Downloading video {video_id}...")
    spinner.start()

    video_cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best",
        "--merge-output-format", "mp4",
        "-o", str(video_path),
        youtube_url,
    ]
    subprocess.run(video_cmd, check=True, capture_output=True)
    spinner.stop(f"✅ Downloaded: {video_path.name}")

    # Download captions for transcript
    spinner = Spinner("Fetching transcript...")
    spinner.start()

    captions_cmd = [
        "yt-dlp",
        "--write-auto-sub",
        "--sub-lang", "en",
        "--convert-subs", "vtt",
        "--skip-download",
        "-o", str(TMP_DIR / video_id),
        youtube_url,
    ]
    subprocess.run(captions_cmd, capture_output=True)

    # Look for captions file (might have different naming)
    vtt_files = list(TMP_DIR.glob(f"{video_id}*.vtt"))
    if vtt_files:
        transcript = parse_vtt_to_transcript(vtt_files[0])
        spinner.stop(f"📝 Transcript loaded: {len(transcript)} chars")
        return video_path, transcript
    else:
        spinner.stop("⚠️  No transcript found for this video")
        return video_path, ""


def parse_vtt_to_transcript(vtt_path: Path) -> str:
    """Parse VTT file into timestamped transcript for Gemini."""
    content = vtt_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    transcript_lines = []
    current_time = None
    seen_text = set()

    for line in lines:
        line = line.strip()
        # Skip header lines and empty
        if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue

        # Check for timestamp line
        if "-->" in line:
            start_time = line.split("-->")[0].strip()
            current_time = parse_timestamp(start_time)
            continue

        # Skip cue identifiers (lines that are just numbers or contain positioning)
        if line.isdigit() or line.startswith("align:") or line.startswith("position:"):
            continue

        # Remove VTT formatting tags
        text = re.sub(r"<[^>]+>", "", line)
        text = text.strip()

        if text and current_time is not None and text not in seen_text:
            seen_text.add(text)
            formatted_time = format_timestamp(current_time)
            transcript_lines.append(f"[{formatted_time}] {text}")

    return "\n".join(transcript_lines)


def find_clips(transcript: str) -> list[Clip]:
    """Use Gemini to identify viral clip opportunities."""
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    client = genai.Client(api_key=api_key)

    prompt_path = PROMPTS_DIR / "clip_extraction.txt"
    prompt = prompt_path.read_text(encoding="utf-8")

    spinner = Spinner("Analyzing transcript with AI...")
    spinner.start()

    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        contents=prompt + "\n\nTRANSCRIPT:\n" + transcript,
    )
    response_text = response.text.strip()
    spinner.stop()

    # Extract JSON from response (handle markdown code blocks)
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    try:
        clips_data = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse Gemini response: {e}")
        print(f"Raw response:\n{response.text[:500]}")
        raise

    clips = []
    for i, data in enumerate(clips_data, 1):
        clip = Clip(
            index=i,
            platform=data["platform"].lower(),
            start=parse_timestamp(data["start"]),
            end=parse_timestamp(data["end"]),
            transcript=data["transcript"],
            hook=data["hook"],
            caption=data.get("caption"),
        )
        clips.append(clip)

    print(f"✅ Found {len(clips)} clips")
    return clips


def select_clips(clips: list[Clip], select_all: bool = False) -> list[Clip]:
    """Interactive terminal UI for selecting clips."""
    if select_all:
        return clips

    print("\n" + "-" * 60)
    print("📋 SELECT CLIPS TO PROCESS")
    print("-" * 60)
    print("Enter clip numbers (comma-separated), 'all', or 'q' to quit:\n")

    for clip in clips:
        platform_label = f"[{clip.platform.upper():8}]"
        duration = f"{clip.duration:3}s"
        preview = clip.hook[:45] + "..." if len(clip.hook) > 45 else clip.hook
        print(f"  {clip.index}. {platform_label} {duration} | \"{preview}\"")

    while True:
        print()
        selection = input("> ").strip().lower()

        if selection == "q":
            print("Quitting...")
            sys.exit(0)

        if selection == "all":
            return clips

        try:
            indices = [int(x.strip()) for x in selection.split(",")]
            selected = [c for c in clips if c.index in indices]
            if not selected:
                print("❌ No valid clips selected. Try again.")
                continue
            return selected
        except ValueError:
            print("❌ Invalid input. Enter numbers separated by commas, 'all', or 'q'.")


def parse_ffmpeg_time(time_str: str) -> float:
    """Parse FFmpeg time string (HH:MM:SS.ms) to seconds."""
    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 0


def render_clip(video_path: Path, clip: Clip, output_dir: Path) -> Path:
    """Render a single vertical clip with FFmpeg."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"clip_{clip.index}_{clip.platform}.mp4"

    print(f"\nClip {clip.index} ({clip.platform}):")

    # Build filter complex: blurred background + sharp foreground centered
    filter_complex = ";".join([
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg]",
        "[0:v]scale=1080:-1[fg]",
        "[bg][fg]overlay=(W-w)/2:(H-h)/2",
    ])

    clip_duration = clip.end - clip.start
    cmd = [
        "ffmpeg", "-y",
        "-accurate_seek",
        "-ss", str(clip.start),
        "-i", str(video_path),
        "-t", str(clip_duration),
        "-filter_complex", filter_complex,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        str(output_path),
    ]

    duration = clip.end - clip.start
    progress_bar = ProgressBar(duration, prefix="🎬 ")
    progress_bar.update(0)  # Show initial 0% progress

    # Collect stderr in background thread to prevent deadlock
    stderr_output = []

    def drain_stderr(pipe):
        for line in pipe:
            stderr_output.append(line)

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        # Start background thread to drain stderr (prevents deadlock)
        stderr_thread = threading.Thread(target=drain_stderr, args=(process.stderr,))
        stderr_thread.daemon = True
        stderr_thread.start()

        # Parse FFmpeg progress output from stdout
        for line in process.stdout:
            if line.startswith("out_time="):
                time_str = line.split("=")[1].strip()
                if time_str and time_str != "N/A":
                    current_time = parse_ffmpeg_time(time_str)
                    progress_bar.update(current_time)

        process.wait()
        stderr_thread.join(timeout=5)
        progress_bar.finish()

        if process.returncode != 0:
            stderr_str = "".join(stderr_output)
            raise subprocess.CalledProcessError(process.returncode, cmd, stderr=stderr_str.encode())

        print(f"   ✅ Saved: {output_path.name}")

    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "".join(stderr_output)
        print(f"\n   ❌ FFmpeg error: {stderr[-500:]}")
        raise

    # Save LinkedIn caption if present
    if clip.caption and clip.platform == "linkedin":
        caption_path = output_dir / f"clip_{clip.index}_caption.txt"
        caption_path.write_text(clip.caption, encoding="utf-8")
        print(f"   📝 Caption saved: {caption_path.name}")

    return output_path


def cleanup_tmp():
    """Delete all files in the tmp directory."""
    if TMP_DIR.exists():
        for file in TMP_DIR.iterdir():
            try:
                file.unlink()
            except Exception:
                pass
        print("🧹 Cleaned up temporary files")


def main():
    parser = argparse.ArgumentParser(
        description="Extract viral clips from YouTube videos for social media."
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--all", action="store_true", help="Process all clips without prompting")
    parser.add_argument("--output", type=Path, default=OUTPUTS_DIR, help="Output directory")
    args = parser.parse_args()

    # Check dependencies
    if not check_ffmpeg():
        print("❌ FFmpeg not found. Please install FFmpeg and add it to your PATH.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🎬 CLIP CUTTER")
    print("=" * 60)

    try:
        # Download video and transcript
        video_path, transcript = download_video(args.url)

        if not transcript:
            response = input("\n⚠️  No transcript found. Continue anyway? (y/n): ").strip().lower()
            if response != "y":
                print("Exiting.")
                sys.exit(0)

        # Find clips with Gemini
        clips = find_clips(transcript)

        # Select clips
        selected = select_clips(clips, select_all=args.all)

        # Render clips
        video_id = extract_video_id(args.url)
        output_dir = args.output / video_id

        print("\n" + "-" * 60)
        print(f"🎬 PROCESSING {len(selected)} CLIPS")
        print("-" * 60)

        for clip in selected:
            render_clip(video_path, clip, output_dir)

        # Cleanup tmp directory
        cleanup_tmp()

        print("\n" + "=" * 60)
        print(f"🎉 DONE! Clips saved to: {output_dir}/")
        print("=" * 60 + "\n")

    except KeyboardInterrupt:
        print("\n\nCancelled.")
        cleanup_tmp()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        cleanup_tmp()
        sys.exit(1)


if __name__ == "__main__":
    main()
