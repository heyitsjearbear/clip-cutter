#!/usr/bin/env python3
"""
Clip Cutter - Extract viral clips from videos for social media.

Interactive CLI tool - just run: python clipper.py
Supports both YouTube URLs and local video file uploads.
"""

import json
import os
import re
import subprocess
import sys
import time
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


def upload_video_to_gemini(video_path: Path):
    """Upload a video file to Gemini Files API and wait for processing."""
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    http_options = types.HttpOptions(client_args={"timeout": 600.0})
    client = genai.Client(api_key=api_key, http_options=http_options)

    spinner = Spinner(f"Uploading {video_path.name} to Gemini...")
    spinner.start()

    try:
        uploaded_file = client.files.upload(file=str(video_path))
        spinner.stop(f"✅ Uploaded: {uploaded_file.name}")
    except Exception as e:
        spinner.stop()
        raise RuntimeError(f"Failed to upload video: {e}")

    # Poll until the file is processed
    spinner = Spinner("Processing video (this may take a few minutes)...")
    spinner.start()

    while not uploaded_file.state or uploaded_file.state.name != "ACTIVE":
        time.sleep(5)
        uploaded_file = client.files.get(name=uploaded_file.name)
        if uploaded_file.state and uploaded_file.state.name == "FAILED":
            spinner.stop()
            raise RuntimeError("Video processing failed on Gemini servers")

    spinner.stop("✅ Video processed and ready")
    return client, uploaded_file


def find_clips_from_video(client, uploaded_file) -> list[Clip]:
    """Use Gemini to identify viral clip opportunities by analyzing the actual video."""
    from google.genai import types

    prompt_path = PROMPTS_DIR / "clip_extraction.txt"
    prompt = prompt_path.read_text(encoding="utf-8")

    # Modify prompt to indicate we're analyzing video directly
    video_prompt = prompt.replace(
        "TRANSCRIPT:",
        "VIDEO CONTENT (analyze both visual and audio):"
    )
    video_prompt += "\n\nAnalyze the video above and identify viral clips. Pay attention to both what is said AND visual elements like facial expressions, gestures, and on-screen action."

    spinner = Spinner("Analyzing video with AI (visual + audio)...")
    spinner.start()

    start_time = time.time()
    try:
        response = client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=[uploaded_file, video_prompt],
        )
        response_text = response.text.strip()
        elapsed = time.time() - start_time
        spinner.stop(f"✅ Analysis complete ({elapsed:.1f}s)")
    except Exception as e:
        elapsed = time.time() - start_time
        spinner.stop()
        print(f"\n❌ GEMINI API ERROR (video analysis)")
        print(f"   Elapsed time: {elapsed:.1f}s before failure")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {e}")
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


def get_video_id_from_path(video_path: Path) -> str:
    """Generate a unique ID from a local video file path."""
    return video_path.stem.replace(" ", "_")[:50]


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
    print("   Extract viral clips from videos")
    print("═" * 60)

    # Check FFmpeg
    if not check_ffmpeg():
        print("\n❌ FFmpeg not found. Please install FFmpeg first.")
        sys.exit(1)

    # Step 1: Choose video source
    print("\n📺 STEP 1: Choose Video Source")
    print("─" * 60)

    source_choice = prompt_choice(
        "How would you like to provide your video?",
        [
            "YouTube URL - Download and extract transcript",
            "Local File - Upload video to Gemini for visual + audio analysis",
        ],
        default=0
    )

    use_local_file = source_choice == 1
    video_path = None
    transcript = ""
    video_id = None
    gemini_client = None
    uploaded_file = None

    if use_local_file:
        # Local file upload flow
        print("\n📁 Local Video Upload")
        print("─" * 60)
        print("Supported formats: MP4, MOV, AVI, MKV, WEBM")
        print("Note: Large files may take several minutes to upload and process.\n")

        while True:
            file_input = input("Enter path to video file: ").strip()
            # Remove quotes if user wrapped path in them
            file_input = file_input.strip("\"'")

            if not file_input:
                print("Please enter a file path")
                continue

            video_path = Path(file_input).expanduser().resolve()

            if not video_path.exists():
                print(f"❌ File not found: {video_path}")
                continue

            if not video_path.is_file():
                print(f"❌ Not a file: {video_path}")
                continue

            valid_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
            if video_path.suffix.lower() not in valid_extensions:
                print(f"❌ Unsupported format: {video_path.suffix}")
                print(f"   Supported: {', '.join(valid_extensions)}")
                continue

            break

        video_id = get_video_id_from_path(video_path)
        print(f"\n✅ Selected: {video_path.name}")
        print(f"   Size: {video_path.stat().st_size / (1024*1024):.1f} MB")

    else:
        # YouTube URL flow
        while True:
            url = input("\nPaste YouTube URL: ").strip()
            if not url:
                print("Please enter a URL")
                continue
            if extract_video_id(url):
                video_id = extract_video_id(url)
                break
            print("❌ Invalid YouTube URL. Try again.")

    try:
        # Step 2: Download/Upload video
        print("\n⬇️  STEP 2: " + ("Uploading to Gemini" if use_local_file else "Downloading"))
        print("─" * 60)

        if use_local_file:
            # Upload to Gemini Files API
            gemini_client, uploaded_file = upload_video_to_gemini(video_path)
        else:
            # Download from YouTube
            video_path, transcript = download_video(url)

        if not use_local_file and not transcript:
            if not prompt_yes_no("No transcript found. Continue anyway?", default=False):
                print("Exiting.")
                sys.exit(0)

        # Step 3: Analyze and select clips
        print("\n🔍 STEP 3: AI Analysis")
        print("─" * 60)

        if use_local_file:
            # Analyze video directly with Gemini vision
            clips = find_clips_from_video(gemini_client, uploaded_file)
        else:
            # Analyze transcript only
            clips = find_clips(transcript)

        selected = select_clips(clips)

        # Step 4: SEO Caption Generation
        print("\n🔎 STEP 4: SEO Caption Generation")
        print("─" * 60)

        seo_captions: dict[int, SEOCaption] = {}
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
