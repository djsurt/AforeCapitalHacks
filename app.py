"""
Podcast Generator — FastAPI Backend
====================================
Orchestrates: Wikipedia/scraper (research) → Claude (script) → ElevenLabs (voice) → pydub (stitch)
"""

import os
import json
import re
import time
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional

import httpx
import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ALEX = os.getenv("ELEVENLABS_VOICE_ALEX", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_VOICE_SAM = os.getenv("ELEVENLABS_VOICE_SAM", "AZnzlk1XvdvUeBnXmlld")

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("podcast")

app = FastAPI(title="Podcast Generator", version="0.1.0")

# Serve generated audio files
app.mount("/output", StaticFiles(directory="output"), name="output")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# ---------------------------------------------------------------------------
# Shared HTTP client (connection pooling)
# ---------------------------------------------------------------------------
http_client: Optional[httpx.AsyncClient] = None


@app.on_event("startup")
async def startup():
    global http_client
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0))
    logger.info("=== ENV CHECK ===")
    logger.info(f"  ANTHROPIC_API_KEY:  {'SET (' + ANTHROPIC_API_KEY[:8] + '...)' if ANTHROPIC_API_KEY else 'NOT SET'}")
    logger.info(f"  ELEVENLABS_API_KEY: {'SET (' + ELEVENLABS_API_KEY[:8] + '...)' if ELEVENLABS_API_KEY else 'NOT SET'}")
    logger.info(f"  VOICE_ALEX:         {ELEVENLABS_VOICE_ALEX}")
    logger.info(f"  VOICE_SAM:          {ELEVENLABS_VOICE_SAM}")
    logger.info(f"  ANTHROPIC_MODEL:    {ANTHROPIC_MODEL}")
    logger.info("=================")


@app.on_event("shutdown")
async def shutdown():
    if http_client:
        await http_client.aclose()


# ===================================================================
# PHASE 2 — Research via Wikipedia + simple scraper
# ===================================================================

async def research_topic(topic: str) -> tuple[str, str | None]:
    """
    Search Wikipedia for the topic and return (research_brief, wikipedia_url).
    Uses Wikipedia's free OpenSearch + REST summary APIs — no key needed.
    """
    try:
        logger.info(f"[wikipedia] Searching for: {topic}")

        # Step 1: OpenSearch to find the best matching article title
        search_resp = await http_client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "opensearch",
                "search": topic,
                "limit": 1,
                "format": "json",
            },
            headers={"User-Agent": "PodcastGenerator/1.0 (https://github.com/local/podcastgen; contact@example.com) python-httpx"},
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()
        titles = search_data[1]

        if not titles:
            logger.warning(f"[wikipedia] No results for: {topic}")
            return f"Topic: {topic}. (No Wikipedia article found — generate from general knowledge.)", None

        article_title = titles[0]
        # Extract URL from OpenSearch results (index 3 contains URLs)
        urls = search_data[3] if len(search_data) > 3 else []
        wikipedia_url = urls[0] if urls else None
        logger.info(f"[wikipedia] Found article: {article_title} — {wikipedia_url}")

        # Step 2: Fetch full extract via the extracts API
        extract_resp = await http_client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": article_title,
                "prop": "extracts",
                "exintro": False,
                "explaintext": True,
                "exsectionformat": "plain",
                "exchars": 3000,
                "format": "json",
            },
            headers={"User-Agent": "PodcastGenerator/1.0 (https://github.com/local/podcastgen; contact@example.com) python-httpx"},
        )
        extract_resp.raise_for_status()
        extract_data = extract_resp.json()

        pages = extract_data.get("query", {}).get("pages", {})
        page = next(iter(pages.values()))
        extract = page.get("extract", "").strip()

        if extract:
            brief = f"Wikipedia — {article_title}\n\n{extract}"
            if wikipedia_url:
                brief += f"\n\nSource: {wikipedia_url}"
            logger.info(f"[wikipedia] Got extract ({len(brief)} chars)")
            return brief, wikipedia_url
        else:
            return f"Topic: {topic}. (Wikipedia extract was empty — generate from general knowledge.)", wikipedia_url

    except Exception as e:
        logger.error(f"[wikipedia] Error: {e}")
        return f"Topic: {topic}. (Wikipedia lookup failed — generate from general knowledge.)", None


async def research_url(url: str) -> tuple[str, str | None]:
    """
    Scrape a URL with httpx + BeautifulSoup and extract readable text.
    """
    try:
        from bs4 import BeautifulSoup

        logger.info(f"[scraper] Fetching URL: {url}")
        resp = await http_client.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PodcastGenerator/1.0)"},
            follow_redirects=True,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()

        # Try to get the article/main body first
        body = soup.find("article") or soup.find("main") or soup.body
        text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)

        # Collapse blank lines and trim
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        excerpt = "\n".join(lines[:120])  # ~first 120 non-empty lines

        if excerpt:
            logger.info(f"[scraper] Extracted {len(excerpt)} chars from {url}")
            return f"Source: {url}\n\n{excerpt}", url
        else:
            return f"Article URL: {url}. (Page content was empty — generate from general knowledge.)", url

    except Exception as e:
        logger.error(f"[scraper] Error fetching {url}: {e}")
        return f"Article URL: {url}. (Scraping failed — generate from general knowledge.)", url


# ===================================================================
# PHASE 3 — Script generation via Claude
# ===================================================================

SCRIPT_SYSTEM_PROMPT = """You are a podcast script writer. Write a 2-minute conversational
podcast between two hosts:
- Alex: curious, asks good questions, uses analogies
- Sam: the expert, explains things clearly, occasionally funny

Rules:
- Make it feel natural, not like a lecture
- Include a short intro and sign-off
- Write 16-22 exchanges total — each exchange should have substantive content (not one-liners)
- At ~6-8 seconds per spoken line, 20 exchanges yields roughly 2 minutes of audio
- Format output as a JSON array:
  [{"speaker": "Alex", "text": "..."}, {"speaker": "Sam", "text": "..."}, ...]
- Return ONLY the JSON array, no other text."""


async def generate_script(topic: str, research_brief: str, tone: str = "casual") -> list[dict]:
    """
    Call Claude to generate podcast script.
    Returns list of {"speaker": "Alex"|"Sam", "text": "..."} dicts.
    """
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — returning placeholder script")
        return _placeholder_script(topic)

    user_prompt = f"""Topic: {topic}
Tone: {tone}
Research Brief:
{research_brief}

Generate the podcast script now as a JSON array."""

    try:
        logger.info("[claude] Generating script...")
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=8192,
            system=SCRIPT_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.85,
        )

        content = message.content[0].text
        script = _parse_script_json(content)
        logger.info(f"[claude] Generated {len(script)} dialogue lines")
        return script

    except anthropic.APIStatusError as e:
        if "credit balance" in str(e).lower() or e.status_code == 402:
            logger.error(f"[claude] Billing error: {e}")
            raise HTTPException(
                status_code=402,
                detail=f"Anthropic API billing error: {e.message}. "
                       f"Check your balance or switch to a cheaper model via ANTHROPIC_MODEL env var (current: {ANTHROPIC_MODEL}).",
            )
        logger.error(f"[claude] API error: {e}")
        return _placeholder_script(topic)
    except Exception as e:
        logger.error(f"[claude] Script generation failed: {e}")
        return _placeholder_script(topic)


def _parse_script_json(text: str) -> list[dict]:
    """Try to parse JSON from LLM output, handling markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: find first [ ... ] block
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not parse script JSON from LLM response")


def _placeholder_script(topic: str) -> list[dict]:
    """Fallback script for when Claude API is not available."""
    return [
        {"speaker": "Alex", "text": f"Hey Sam, today we're diving into {topic}. I've been really curious about this!"},
        {"speaker": "Sam", "text": f"Yeah, {topic} is fascinating. Let me break it down for you."},
        {"speaker": "Alex", "text": "So what's the most surprising thing people don't know about this?"},
        {"speaker": "Sam", "text": f"Well, the thing about {topic} that most people miss is how interconnected it is with everyday life. It's not just some abstract concept."},
        {"speaker": "Alex", "text": "That's a great point. Can you give me an example?"},
        {"speaker": "Sam", "text": "Sure! Think of it this way — it's like how you don't notice gravity until you trip. The effects are everywhere once you start looking."},
        {"speaker": "Alex", "text": "Ha! I love that analogy. What should our listeners take away from this?"},
        {"speaker": "Sam", "text": f"I'd say the key takeaway is that {topic} matters more than most people realize. Start paying attention and you'll see it everywhere."},
        {"speaker": "Alex", "text": "Awesome. Thanks for breaking that down, Sam. Until next time, folks!"},
        {"speaker": "Sam", "text": "See you next episode!"},
    ]


# ===================================================================
# PHASE 4 — Voice generation via ElevenLabs
# ===================================================================

async def generate_voice_clips(script: list[dict], job_id: str) -> list[Path]:
    """
    Loop through script, call ElevenLabs TTS for each line.
    Returns list of paths to numbered audio clips.
    """
    clips_dir = OUTPUT_DIR / job_id / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    if not ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY not set — skipping voice generation")
        return []

    clip_paths = []
    for i, line in enumerate(script):
        speaker = line["speaker"]
        text = line["text"]
        voice_id = ELEVENLABS_VOICE_ALEX if speaker == "Alex" else ELEVENLABS_VOICE_SAM

        try:
            logger.info(f"[elevenlabs] Generating clip {i+1}/{len(script)} ({speaker})")
            resp = await http_client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text,
                    "model_id": "eleven_turbo_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                },
            )
            resp.raise_for_status()

            clip_path = clips_dir / f"{i:03d}_{speaker.lower()}.mp3"
            clip_path.write_bytes(resp.content)
            clip_paths.append(clip_path)

        except Exception as e:
            logger.error(f"[elevenlabs] Failed on clip {i+1}: {e}")
            continue

    logger.info(f"[elevenlabs] Generated {len(clip_paths)} clips")
    return clip_paths


# ===================================================================
# PHASE 5 — Stitching via pydub
# ===================================================================

def stitch_podcast(clip_paths: list[Path], jingle_path: Optional[Path], job_id: str) -> Path:
    """
    Use pydub to combine voice clips with silence gaps,
    optionally add intro/outro jingle, and bell chimes.
    Returns path to final podcast MP3.
    """
    from pydub import AudioSegment
    from pydub.generators import Sine

    final_path = OUTPUT_DIR / job_id / "podcast.mp3"

    if not clip_paths:
        logger.warning("No audio clips to stitch — creating silent placeholder")
        silence = AudioSegment.silent(duration=1000)
        silence.export(str(final_path), format="mp3")
        return final_path

    # Generate a bell chime sound (or load from file if available)
    def create_bell_chime() -> AudioSegment:
        """Generate a pleasant bell chime using sine waves."""
        # Try to load local bell sound first
        bell_file = Path("static/bell.mp3")
        if bell_file.exists() and bell_file.stat().st_size > 100:
            try:
                return AudioSegment.from_mp3(str(bell_file))
            except Exception as e:
                logger.warning(f"[stitch] Could not load bell.mp3, using synthetic: {e}")
        
        # Generate synthetic bell: E5 (659Hz) + harmonic overtones
        duration = 800
        bell = Sine(659).to_audio_segment(duration=duration).apply_gain(-6)
        bell += Sine(659 * 2).to_audio_segment(duration=duration).apply_gain(-12)  # octave
        bell += Sine(659 * 3).to_audio_segment(duration=duration).apply_gain(-15)  # overtone
        
        # Exponential fade out for natural bell decay
        bell = bell.fade_out(600)
        return bell

    # Build the conversation track
    silence = AudioSegment.silent(duration=400)  # 400ms gap between speakers
    podcast = AudioSegment.empty()

    for clip_path in sorted(clip_paths):
        clip = AudioSegment.from_mp3(str(clip_path))
        podcast += clip + silence

    # Create bell chime
    bell = create_bell_chime()
    
    # Add jingle intro/outro if available
    intro_section = AudioSegment.empty()
    outro_section = AudioSegment.empty()
    
    if jingle_path and jingle_path.exists():
        jingle = AudioSegment.from_mp3(str(jingle_path))
        # Intro: jingle + bell chime
        intro_jingle = jingle.fade_in(2000)[:12000].fade_out(2000)
        intro_section = intro_jingle + AudioSegment.silent(duration=300) + bell + AudioSegment.silent(duration=800)
        
        # Outro: bell + jingle
        outro_jingle = jingle.fade_in(1000)[:8000].fade_out(3000)
        outro_section = AudioSegment.silent(duration=500) + bell + AudioSegment.silent(duration=300) + outro_jingle
    else:
        # No jingle: just use bell chimes as intro/outro
        intro_section = bell + AudioSegment.silent(duration=1000)
        outro_section = AudioSegment.silent(duration=800) + bell
    
    # Combine: intro + conversation + outro
    podcast = intro_section + podcast + outro_section

    # Normalize volume
    podcast = podcast.normalize()

    podcast.export(str(final_path), format="mp3")
    logger.info(f"[stitch] Exported podcast with bells & jingles → {final_path}")
    return final_path


# ===================================================================
# API Routes
# ===================================================================

@app.get("/")
async def index(request: Request):
    """Serve the frontend."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/generate")
async def generate_podcast(request: Request):
    """
    Main endpoint. Accepts JSON:
    {
        "topic": "dinosaurs",          // required (or url)
        "url": "https://...",          // optional — scrape this article instead
        "tone": "casual"               // optional: casual | academic | comedic
    }
    Returns JSON with job_id, script, and audio URL.
    """
    body = await request.json()
    topic = body.get("topic", "").strip()
    url = body.get("url", "").strip()
    tone = body.get("tone", "casual").strip()

    if not topic and not url:
        raise HTTPException(status_code=400, detail="Provide a 'topic' or 'url'.")

    job_id = str(uuid.uuid4())[:8]
    (OUTPUT_DIR / job_id).mkdir(parents=True, exist_ok=True)

    # --- Phase 2: Research ---
    if url:
        research_brief, wikipedia_url = await research_url(url)
        if not topic:
            topic = f"Article from {url}"
    else:
        research_brief, wikipedia_url = await research_topic(topic)

    # --- Phase 3: Script ---
    script = await generate_script(topic, research_brief, tone)

    # --- Phase 4: Voice ---
    clip_paths = await generate_voice_clips(script, job_id)

    # --- Phase 5: Stitch ---
    final_path = stitch_podcast(clip_paths, None, job_id)

    # Build response
    audio_url = f"/output/{job_id}/podcast.mp3" if final_path.exists() else None

    return JSONResponse({
        "job_id": job_id,
        "topic": topic,
        "tone": tone,
        "script": script,
        "research_brief": research_brief[:500] + "..." if len(research_brief) > 500 else research_brief,
        "wikipedia_url": wikipedia_url,
        "audio_url": audio_url,
        "has_audio": bool(clip_paths),
        "clip_count": len(clip_paths),
    })


@app.get("/health")
async def health():
    """Health check — shows which API keys are configured."""
    return {
        "status": "ok",
        "keys_configured": {
            "anthropic": bool(ANTHROPIC_API_KEY),
            "elevenlabs": bool(ELEVENLABS_API_KEY),
        },
        "anthropic_model": ANTHROPIC_MODEL,
    }


# ===================================================================
# Entry point
# ===================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
