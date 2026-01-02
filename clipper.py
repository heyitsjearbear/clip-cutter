#!/usr/bin/env python3
"""
Clip Cutter - Extract viral clips from YouTube videos for social media.

Interactive CLI tool - just run: python clipper.py
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from clip_cutter.models import Clip
from clip_cutter.utils import Spinner
from clip_cutter.render import check_ffmpeg, render_clip
from clip_cutter.seo import generate_seo_for_clips, save_all_seo_captions, SEOCaption

load_dotenv()

# Constants
SCRIPT_DIR = Path(__file__).parent
TMP_DIR = SCRIPT_DIR / "tmp"
OUTPUTS_DIR = SCRIPT_DIR / "outputs"
PROMPTS_DIR = SCRIPT_DIR / "prompts"


def clear_line():
    """Clear the current terminal line."""
    print("\r" + " " * 60 + "\r", end="")


def prompt_choice(question: str, options: list[str], default: int = 0) -> int:
    """
    Prompt user to select from a list of options.

    Returns the index of the selected option.
    """
    print(f"\n{question}")
    for i, option in enumerate(options):
        marker = "→" if i == default else " "
        print(f"  {marker} {i + 1}. {option}")

    while True:
        try:
            choice = input(f"\nEnter choice [1-{len(options)}] (default: {default + 1}): ").strip()
            if not choice:
                return default
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return idx
            print(f"Please enter a number between 1 and {len(options)}")
        except ValueError:
            print("Please enter a valid number")


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt user for yes/no answer."""
    default_str = "Y/n" if default else "y/N"
    while True:
        answer = input(f"\n{question} [{default_str}]: ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please enter 'y' or 'n'")


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
    """Convert timestamp string to seconds."""
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
    """Download YouTube video and transcript."""
    video_id = extract_video_id(youtube_url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {youtube_url}")

    TMP_DIR.mkdir(exist_ok=True)
    video_path = TMP_DIR / f"{video_id}.mp4"

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

    vtt_files = list(TMP_DIR.glob(f"{video_id}*.vtt"))
    if vtt_files:
        transcript = parse_vtt_to_transcript(vtt_files[0])
        spinner.stop(f"📝 Transcript loaded: {len(transcript)} chars")
        return video_path, transcript
    else:
        spinner.stop("⚠️  No transcript found")
        return video_path, ""


def parse_vtt_to_transcript(vtt_path: Path) -> str:
    """Parse VTT file into timestamped transcript."""
    content = vtt_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    transcript_lines = []
    current_time = None
    seen_text = set()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue

        if "-->" in line:
            start_time = line.split("-->")[0].strip()
            current_time = parse_timestamp(start_time)
            continue

        if line.isdigit() or line.startswith("align:") or line.startswith("position:"):
            continue

        text = re.sub(r"<[^>]+>", "", line).strip()

        if text and current_time is not None and text not in seen_text:
            seen_text.add(text)
            formatted_time = format_timestamp(current_time)
            transcript_lines.append(f"[{formatted_time}] {text}")

    return "\n".join(transcript_lines)


def find_clips(transcript: str) -> list[Clip]:
    """Use Gemini to identify viral clip opportunities."""
    import time
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    # 2 minute timeout to prevent runaway API costs
    http_options = types.HttpOptions(client_args={"timeout": 120.0})
    client = genai.Client(api_key=api_key, http_options=http_options)

    prompt_path = PROMPTS_DIR / "clip_extraction.txt"
    prompt = prompt_path.read_text(encoding="utf-8")

    spinner = Spinner("Analyzing transcript with AI...")
    spinner.start()

    start_time = time.time()
    try:
        response = client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=prompt + "\n\nTRANSCRIPT:\n" + transcript,
        )
        response_text = response.text.strip()
        elapsed = time.time() - start_time
        spinner.stop(f"✅ Analysis complete ({elapsed:.1f}s)")
    except Exception as e:
        elapsed = time.time() - start_time
        spinner.stop()
        print(f"\n❌ GEMINI API ERROR (clip extraction)")
        print(f"   Elapsed time: {elapsed:.1f}s before failure")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {e}")
        print(f"   Timeout was set to: 120s")
        if elapsed >= 115:
            print(f"   ⚠️  Likely a timeout - consider increasing timeout value")
        raise

    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    try:
        clips_data = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse AI response: {e}")
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

    print(f"✅ Found {len(clips)} potential clips")
    return clips


def select_clips(clips: list[Clip]) -> list[Clip]:
    """Interactive clip selection."""
    print("\n" + "─" * 60)
    print("📋 AVAILABLE CLIPS")
    print("─" * 60)

    for clip in clips:
        platform_label = f"[{clip.platform.upper():8}]"
        duration = f"{clip.duration:3}s"
        preview = clip.hook[:42] + "..." if len(clip.hook) > 42 else clip.hook
        print(f"  {clip.index}. {platform_label} {duration} │ \"{preview}\"")

    print("\n" + "─" * 60)

    while True:
        print("\nOptions:")
        print("  • Enter clip numbers (e.g., 1,3,5)")
        print("  • 'all' to process all clips")
        print("  • 'q' to quit")

        selection = input("\nYour selection: ").strip().lower()

        if selection == "q":
            print("Goodbye!")
            sys.exit(0)

        if selection == "all":
            return clips

        try:
            indices = [int(x.strip()) for x in selection.split(",")]
            selected = [c for c in clips if c.index in indices]
            if not selected:
                print("❌ No valid clips selected")
                continue
            print(f"✓ Selected {len(selected)} clip(s)")
            return selected
        except ValueError:
            print("❌ Invalid input")


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
    print("\n" + "═" * 60)
    print("🎬 CLIP CUTTER")
    print("   Extract viral clips from YouTube videos")
    print("═" * 60)

    # Check FFmpeg
    if not check_ffmpeg():
        print("\n❌ FFmpeg not found. Please install FFmpeg first.")
        sys.exit(1)

    # Step 1: Get YouTube URL
    print("\n📺 STEP 1: Enter YouTube URL")
    print("─" * 60)

    while True:
        url = input("\nPaste YouTube URL: ").strip()
        if not url:
            print("Please enter a URL")
            continue
        if extract_video_id(url):
            break
        print("❌ Invalid YouTube URL. Try again.")

    try:
        # Step 2: Download video
        print("\n⬇️  STEP 2: Downloading")
        print("─" * 60)
        video_path, transcript = download_video(url)

        if not transcript:
            if not prompt_yes_no("No transcript found. Continue anyway?", default=False):
                print("Exiting.")
                sys.exit(0)

        # Step 3: Analyze and select clips
        print("\n🔍 STEP 3: AI Analysis")
        print("─" * 60)
        clips = find_clips(transcript)
        selected = select_clips(clips)

        # Step 4: SEO Caption Generation
        print("\n🔎 STEP 4: SEO Caption Generation")
        print("─" * 60)

        seo_captions: dict[int, SEOCaption] = {}
        video_id = extract_video_id(url)
        output_dir = OUTPUTS_DIR / video_id

        if prompt_yes_no("Generate SEO-optimized captions with trending hashtags?", default=True):
            print("\nUsing Gemini with Google Search to research trending hashtags...")
            seo_captions = generate_seo_for_clips(selected)

            # Save SEO data as JSON sidecar files
            saved_paths = save_all_seo_captions(selected, seo_captions, output_dir)
            print(f"Saved {len(saved_paths)} SEO caption files to {output_dir}/")

            # Show preview of generated captions
            if prompt_yes_no("Preview SEO captions?", default=False):
                for clip in selected:
                    if clip.index in seo_captions:
                        seo = seo_captions[clip.index]
                        print(f"\n{'─' * 40}")
                        print(f"Clip {clip.index} ({clip.platform.upper()}):")
                        print(f"Keywords: {', '.join(seo.topic_keywords[:3])}")
                        print(f"Hashtags ({len(seo.hashtags)}): {' '.join('#' + h for h in seo.hashtags[:5])}...")
                        print(f"\nCaption:\n{seo.caption[:200]}{'...' if len(seo.caption) > 200 else ''}")
        else:
            print("Skipping SEO caption generation.")

        # Step 5: Video Caption options (subtitles)
        print("\n💬 STEP 5: Video Caption Options")
        print("─" * 60)

        caption_choice = prompt_choice(
            "How would you like to generate captions?",
            [
                "No captions (video only)",
                "AssemblyAI - Professional transcription with TikTok-style highlighting",
            ],
            default=0
        )

        use_assemblyai = caption_choice == 1
        caption_style = "standard"

        if use_assemblyai:
            # Check API key
            if not os.environ.get("ASSEMBLYAI_API_KEY"):
                print("\n⚠️  ASSEMBLYAI_API_KEY not found in .env")
                print("   Get your free key at: https://www.assemblyai.com/")
                if not prompt_yes_no("Continue without captions?", default=True):
                    sys.exit(0)
                use_assemblyai = False
            else:
                style_choice = prompt_choice(
                    "Caption style:",
                    [
                        "TikTok - Bold, word-by-word highlighting (recommended)",
                        "Standard - Simple white text",
                    ],
                    default=0
                )
                caption_style = "tiktok" if style_choice == 0 else "standard"

        # Step 6: Render clips
        print("\n🎬 STEP 6: Rendering Clips")
        print("─" * 60)

        for clip in selected:
            captions_path = None

            if use_assemblyai:
                from clip_cutter.captions import create_captions_for_clip

                print(f"\n📝 Generating captions for clip {clip.index}...")
                # Store .ass files in tmp (will be cleaned up later)
                captions_path = TMP_DIR / f"clip_{clip.index}_{clip.platform}.ass"
                captions_path.parent.mkdir(parents=True, exist_ok=True)

                create_captions_for_clip(
                    video_path=video_path,
                    clip_start=clip.start,
                    clip_end=clip.end,
                    output_path=captions_path,
                    style=caption_style,
                    chars_per_line=32,
                )

            render_clip(
                video_path=video_path,
                clip=clip,
                output_dir=output_dir,
                captions_path=captions_path,
            )

        # Cleanup
        cleanup_tmp()

        # Done!
        print("\n" + "═" * 60)
        print(f"🎉 DONE!")
        print(f"   Clips saved to: {output_dir}/")
        print("═" * 60 + "\n")

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
