# Prompt Engineering Documentation

This document details the AI prompts used in Clip Cutter, their structure, and customization options.

## Table of Contents

- [Clip Extraction Prompt](#clip-extraction-prompt)
- [SEO Caption Prompt](#seo-caption-prompt)
- [Prompt Design Principles](#prompt-design-principles)
- [Customization Guide](#customization-guide)

---

## Clip Extraction Prompt

**File:** `prompts/clip_extraction.txt`

**Model:** Gemini 3 Pro

**Purpose:** Analyze a timestamped transcript to identify viral clip opportunities across multiple platforms.

### Structure

```
1. ROLE DEFINITION
   "You are a viral content strategist..."

2. INPUT SPECIFICATION
   "INPUT: A YouTube video transcript with timestamps"

3. TASK DEFINITION
   "YOUR TASK: Identify 8-12 clip opportunities..."

4. IDENTIFICATION CRITERIA
   - Complete micro-stories
   - Surprising statistics
   - Knowledge gaps
   - Mistakes + solutions
   - Contrarian takes
   - Pain points + fixes
   - Aha moments

5. PLATFORM REQUIREMENTS
   - TikTok: 21-34s, hook in 3s, casual
   - YouTube Shorts: 30-58s, searchable, polished
   - Instagram Reels: 15-30s, front-load result
   - LinkedIn: 45-90s, professional value

6. OUTPUT FORMAT
   JSON array specification with examples

7. RULES
   - Timestamp format
   - Context independence
   - Complete thoughts

8. CRITICAL BOUNDARY RULES
   - Never cut mid-word/sentence
   - Natural pause endings
   - Padding after last word
```

### Key Instructions

#### Virality Criteria

The prompt identifies moments that trigger engagement:

```
Look for moments that contain:
- A complete micro-story or point made in under 60 seconds
- Surprising statistics or counterintuitive reveals
- "Most people don't know this" knowledge gaps
- Mistakes followed by solutions
- Controversial or contrarian takes
- Specific pain points with immediate fixes
- Aha moments where complexity becomes simple
```

#### Platform-Specific Rules

Each platform has tailored requirements:

**TikTok (2-3 clips, 21-34 seconds):**
```
- Hook must land in first 3 seconds
- Lead with payoff, not setup
- Casual, direct language
```

**YouTube Shorts (2-3 clips, 30-58 seconds):**
```
- Strong hook in first 2-3 seconds
- More searchable/evergreen content works well
- Can be slightly more polished than TikTok
- Educational or tutorial moments perform great
```

**Instagram Reels (2-3 clips, 15-30 seconds):**
```
- Front-load the transformation or result
- Extreme brevity—one clear point only
```

**LinkedIn (2-3 clips, 45-90 seconds):**
```
- Start with a professional pain point
- Tie to career impact or business value
- More polished, complete thoughts
```

#### Clip Boundary Rules

Critical for quality output. The prompt is very explicit because auto-generated transcripts often have misleading punctuation:

```
CRITICAL - CLIP BOUNDARIES (READ CAREFULLY):

**DO NOT TRUST PUNCTUATION BLINDLY:**
- Auto-generated transcripts often have periods (.) in the middle of sentences
- A period does NOT always mean a sentence is complete
- You MUST read the actual meaning and context, not just punctuation

**LOOK AHEAD BEFORE CHOOSING AN END POINT:**
- Before finalizing any end timestamp, read 2-3 sentences AHEAD in the transcript
- Ask yourself: "Is the speaker about to continue this thought?"
- Ask yourself: "Does the next sentence connect to what was just said?"
- If the speaker is building to a point, DO NOT cut before the payoff
- If the next sentence starts with "So...", "And...", "Because...", "Which means...",
  the thought is NOT complete

**NATURAL ENDING CHECKLIST:**
- The speaker has fully made their point (not just started it)
- There is a clear conclusion, punchline, or "aha moment"
- The next sentence starts a NEW topic (not a continuation)
- Cutting here would NOT leave the viewer thinking "wait, what about...?"

**HARD RULES:**
- NEVER cut mid-word
- NEVER cut mid-sentence (regardless of periods in transcript)
- NEVER cut before a punchline or key insight
- NEVER cut when the speaker is listing things (wait for the list to finish)
```

**Why this matters:** YouTube auto-captions frequently insert periods at pauses, breaths, or filler words - not actual sentence endings. The AI must understand semantic meaning, not rely on punctuation.

### Output Schema

```json
[
  {
    "platform": "tiktok | youtube_shorts | reels | linkedin",
    "start": "M:SS",
    "end": "M:SS",
    "transcript": "exact words from segment",
    "hook": "attention-grabbing opening line",
    "caption": "null for most, LinkedIn caption for linkedin"
  }
]
```

---

## SEO Caption Prompt

**File:** `prompts/seo_captions.txt`

**Model:** Gemini 3 Flash with Google Search Grounding

**Purpose:** Generate platform-optimized captions with trending hashtags based on real-time web research.

### Structure

```
1. ROLE DEFINITION
   "You are a viral content strategist with access to web search..."

2. INPUT SPECIFICATION
   Clip details (platform, transcript, hook)

3. STEP 1: WEB SEARCH RESEARCH
   - Trending hashtags
   - Viral formats
   - SEO keywords
   - Current engagement patterns

4. STEP 2: CAPTION GENERATION
   Platform-specific formulas

5. OUTPUT FORMAT
   JSON object specification

6. CRITICAL RULES
   - Hashtag counts per platform
   - Research citation requirements
```

### Web Search Instructions

The prompt directs Gemini to perform specific searches:

```
Search queries to run for each clip:
- "[topic] trending hashtags [platform] 2025"
- "[topic] viral [platform] hooks"
- "best performing [platform] posts about [topic]"
- "[topic] SEO keywords"
```

### Platform Caption Formulas

**TikTok:**
```
Line 1: Hook that creates curiosity gap or FOMO
Line 2: Context or relatable statement
Line 3: Call-to-action (follow, save, comment)
Line 4-6: 5-8 hashtags (mix of high-volume 1M+ and niche 10K-500K)
```

**YouTube Shorts:**
```
Line 1: SEO-optimized title (include main keyword, under 100 chars)
Line 2-3: Description with context and value proposition
Line 4: Call-to-action (subscribe, like, comment)
Line 5+: 3-5 hashtags (YouTube uses these for discovery, #Shorts recommended)
```

**Instagram Reels:**
```
Line 1: Hook (question, bold statement, or "POV:")
Line 2-3: Value statement or mini-story
Line 4: CTA (save this, share with someone who needs it)
Line 5+: 20-30 hashtags (first 5 highly relevant, rest discovery-focused)
```

**LinkedIn:**
```
Paragraph 1: Scroll-stopping hook (pattern interrupt, contrarian take)
Paragraph 2-3: The insight with specific details/numbers
Paragraph 4: Why this matters for the reader's career/business
Paragraph 5: Engagement question or soft CTA
Final line: 3-5 hashtags MAX (LinkedIn penalizes hashtag stuffing)
```

### Hashtag Count Rules

```
Hashtag counts matter:
- LinkedIn: 3-5 MAX (algorithm penalizes more)
- TikTok: 5-8 (mix viral + niche)
- YouTube Shorts: 3-5 (include #Shorts for discovery)
- Instagram: 20-30 (maximize discovery)
```

### Output Schema

```json
{
  "platform": "tiktok",
  "topic_keywords": ["primary", "secondary", "tertiary"],
  "caption": "Full formatted caption with line breaks and hashtags",
  "hashtags": ["hashtag1", "hashtag2", "..."],
  "seo_notes": "Research findings explaining hashtag choices"
}
```

---

## Prompt Design Principles

### 1. Structured Output

Both prompts enforce JSON output:
- Explicit schema with examples
- "Return ONLY the JSON" instruction
- No prose before/after

### 2. Platform Awareness

Each platform has unique requirements:
- Duration constraints
- Tone and style
- Hashtag strategies
- Content format

### 3. Quality Guardrails

Boundary rules prevent common issues:
- Mid-sentence cuts
- Incomplete thoughts
- Abrupt endings

### 4. Research Integration

SEO prompt leverages Gemini's web search:
- Real-time trend data
- Current hashtag performance
- Platform-specific best practices

---

## Customization Guide

### Modifying Clip Criteria

Edit `prompts/clip_extraction.txt` to change what makes a good clip:

```
# Original
- Surprising statistics or counterintuitive reveals

# Customized for educational content
- Clear explanations of complex topics
- Step-by-step demonstrations
- Before/after comparisons
```

### Adjusting Platform Rules

Modify duration ranges or style guidelines:

```
# Original TikTok
**TikTok (identify 2-3 clips, 21-34 seconds each):**

# Extended for longer content
**TikTok (identify 2-3 clips, 30-45 seconds each):**
```

### Adding New Platforms

1. Add platform section in clip extraction prompt
2. Add caption formula in SEO prompt
3. Add hashtag count rule
4. Update fallback hashtags in `seo.py`
5. Update platform list in `models.py`

### Custom Caption Styles

Modify the formula in `prompts/seo_captions.txt`:

```
# Original TikTok formula
Line 1: Hook that creates curiosity gap or FOMO

# Brand-focused variation
Line 1: Brand mention + hook
Line 2: Product/service tie-in
```

### Testing Prompt Changes

1. Make changes to prompt file
2. Run on a test video
3. Check JSON output validity
4. Verify clip quality
5. Review caption relevance

---

## Prompt Versioning

When making significant changes, consider:

1. **Backup current prompts** before editing
2. **Test incrementally** - one change at a time
3. **Document changes** in commit messages
4. **Compare outputs** before/after changes

### Example Change Log

```
# Version 1.1 - Added YouTube Shorts
- Added youtube_shorts platform
- Duration: 30-58 seconds
- Searchable/evergreen focus

# Version 1.2 - Improved clip boundaries
- Added CRITICAL BOUNDARY RULES section
- Prevents mid-word/sentence cuts
- Requires natural pause endings
```
