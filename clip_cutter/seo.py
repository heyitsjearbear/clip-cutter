"""SEO caption and hashtag generation using Gemini with Google Search grounding."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .models import Clip
from .utils import Spinner

# Prompts directory
SCRIPT_DIR = Path(__file__).parent.parent
PROMPTS_DIR = SCRIPT_DIR / "prompts"


@dataclass
class SEOCaption:
    """SEO-optimized caption data for a clip."""

    platform: str
    topic_keywords: list[str]
    caption: str
    hashtags: list[str]
    seo_notes: str


def generate_seo_caption(clip: Clip) -> SEOCaption:
    """
    Generate SEO-optimized caption for a clip using Gemini with Google Search grounding.

    Args:
        clip: The clip to generate a caption for

    Returns:
        SEOCaption with optimized caption, hashtags, and research notes
    """
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    # 2 minute timeout per clip to prevent runaway API costs
    http_options = types.HttpOptions(client_args={"timeout": 120.0})
    client = genai.Client(api_key=api_key, http_options=http_options)

    # Load prompt template
    prompt_path = PROMPTS_DIR / "seo_captions.txt"
    prompt_template = prompt_path.read_text(encoding="utf-8")

    # Build the clip context
    clip_context = f"""
CLIP DETAILS:
- Platform: {clip.platform}
- Duration: {clip.duration} seconds
- Hook: {clip.hook}
- Transcript: {clip.transcript}
"""

    full_prompt = prompt_template + "\n\n" + clip_context

    spinner = Spinner(f"Researching SEO for {clip.platform} clip {clip.index}...")
    spinner.start()

    import time
    start_time = time.time()

    try:
        # Use Gemini with Google Search grounding for real-time trend research
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=full_prompt,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(google_search=types.GoogleSearch())
                ]
            ),
        )

        response_text = response.text.strip()
        elapsed = time.time() - start_time
        spinner.stop(f"✅ ({elapsed:.1f}s)")

        # Parse JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            print(f"   Warning: Failed to parse SEO response, using defaults")
            return _create_fallback_caption(clip)

        return SEOCaption(
            platform=data.get("platform", clip.platform),
            topic_keywords=data.get("topic_keywords", []),
            caption=data.get("caption", clip.hook),
            hashtags=data.get("hashtags", []),
            seo_notes=data.get("seo_notes", ""),
        )

    except Exception as e:
        elapsed = time.time() - start_time
        spinner.stop()
        print(f"\n   ❌ GEMINI API ERROR (SEO for clip {clip.index})")
        print(f"      Elapsed time: {elapsed:.1f}s before failure")
        print(f"      Error type: {type(e).__name__}")
        print(f"      Error message: {e}")
        print(f"      Timeout was set to: 120s")
        if elapsed >= 115:
            print(f"      ⚠️  Likely a timeout - consider increasing timeout value")
        print(f"      Using fallback caption instead...")
        return _create_fallback_caption(clip)


def _create_fallback_caption(clip: Clip) -> SEOCaption:
    """Create a basic fallback caption when SEO generation fails."""
    default_hashtags = {
        "tiktok": ["fyp", "viral", "trending", "foryou", "foryoupage"],
        "youtube_shorts": ["Shorts", "viral", "trending", "subscribe"],
        "reels": ["reels", "viral", "explore", "trending", "instagram"],
        "linkedin": ["leadership", "business", "growth"],
    }

    return SEOCaption(
        platform=clip.platform,
        topic_keywords=[],
        caption=clip.hook,
        hashtags=default_hashtags.get(clip.platform, []),
        seo_notes="Fallback caption - SEO research unavailable",
    )


def generate_seo_for_clips(clips: list[Clip]) -> dict[int, SEOCaption]:
    """
    Generate SEO captions for multiple clips.

    Args:
        clips: List of clips to process

    Returns:
        Dict mapping clip index to SEOCaption
    """
    results = {}

    print("\n" + "-" * 60)
    print("Generating SEO-optimized captions with web research...")
    print("-" * 60)

    for clip in clips:
        try:
            seo_caption = generate_seo_caption(clip)
            results[clip.index] = seo_caption
            print(f"   Clip {clip.index} ({clip.platform}): {len(seo_caption.hashtags)} hashtags")
        except Exception as e:
            print(f"   Clip {clip.index}: Failed - {e}")
            results[clip.index] = _create_fallback_caption(clip)

    print(f"Generated SEO captions for {len(results)} clips")
    return results


def save_seo_caption(
    clip: Clip,
    seo_caption: SEOCaption,
    output_dir: Path,
) -> Path:
    """
    Save SEO caption data to a JSON sidecar file.

    Args:
        clip: The clip metadata
        seo_caption: The generated SEO caption
        output_dir: Directory to save the file

    Returns:
        Path to the saved JSON file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"clip_{clip.index}_{clip.platform}_seo.json"

    # Only save caption and hashtags - keep it simple
    data = {
        "caption": seo_caption.caption,
        "hashtags": seo_caption.hashtags,
    }

    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def save_all_seo_captions(
    clips: list[Clip],
    seo_captions: dict[int, SEOCaption],
    output_dir: Path,
) -> list[Path]:
    """
    Save all SEO captions to JSON sidecar files.

    Args:
        clips: List of clips
        seo_captions: Dict mapping clip index to SEOCaption
        output_dir: Directory to save files

    Returns:
        List of paths to saved JSON files
    """
    saved_paths = []

    for clip in clips:
        if clip.index in seo_captions:
            path = save_seo_caption(clip, seo_captions[clip.index], output_dir)
            saved_paths.append(path)

    return saved_paths
