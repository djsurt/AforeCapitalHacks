# 🎙️ PodGen: AI-Powered Podcast Generator

> Transform any topic or article into a professional, broadcast-ready podcast in minutes.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**PodGen** is an intelligent podcast generation system that orchestrates multiple AI services to create engaging, conversational audio content. Simply provide a topic or URL, and get back a complete podcast episode with natural dialogue, professional voice acting, background music, and polished production.

---

## ✨ Features

### 🧠 **Intelligent Research Pipeline**
- **Wikipedia Integration**: Automatic article discovery and content extraction via OpenSearch + REST APIs
- **Web Scraping**: Smart HTML parsing with BeautifulSoup for any URL
- **Content Filtering**: Removes noise (nav, footer, scripts) to extract clean, relevant text

### 🎭 **Natural Script Generation**
- **MiniMax LLM Integration**: Generates conversational dialogue between two distinct personas
  - **Alex**: The curious questioner who uses analogies and keeps things relatable
  - **Sam**: The knowledgeable expert with clear explanations and occasional humor
- **Structured Output**: Enforces JSON format with robust parsing (handles markdown fences)
- **Tone Control**: Supports casual, academic, and comedic styles
- **Graceful Fallback**: Placeholder scripts when API unavailable

### 🗣️ **Professional Voice Acting**
- **ElevenLabs TTS**: High-quality neural voice synthesis
- **Multi-Voice Support**: Distinct voices for each host (Alex & Sam)
- **Configurable Settings**: Adjustable stability and similarity boost
- **Per-Line Rendering**: Individual clip generation with error resilience

### 🎵 **Production-Quality Audio**
- **MiniMax Music Generation**: AI-composed intro/outro jingles (15s upbeat acoustic)
- **Synthetic Bell Chimes**: Pleasant E5 harmonic transitions
- **Smart Audio Stitching**: 
  - 400ms silence gaps between speakers
  - Normalized volume levels
  - Professional fade-in/fade-out transitions
  - Intro: Jingle → Bell → Content
  - Outro: Content → Bell → Jingle
- **pydub Mastering**: Export-ready MP3s

### 🚀 **Production-Ready Architecture**
- **Async FastAPI**: Non-blocking I/O for concurrent operations
- **Connection Pooling**: Shared `httpx.AsyncClient` with 300s timeout
- **Structured Logging**: Comprehensive phase-by-phase tracking
- **Job Management**: UUID-based output organization
- **Static File Serving**: Direct MP3 playback via `/output` endpoint
- **Health Checks**: API key validation and status monitoring

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI | Async web framework |
| **LLM** | MiniMax Text-01 | Script generation |
| **TTS** | ElevenLabs API | Voice synthesis |
| **Music** | MiniMax Music-01 | Jingle composition |
| **HTTP Client** | httpx | Async requests with pooling |
| **Audio Processing** | pydub | MP3 stitching & mastering |
| **Web Scraping** | BeautifulSoup4 | HTML parsing |
| **Research** | Wikipedia API | Knowledge base |
| **Templates** | Jinja2 | Frontend rendering |

---

## 📋 Prerequisites

- **Python 3.12+**
- **API Keys**:
  - [MiniMax API](https://www.minimaxi.com/) (for LLM + Music)
  - [ElevenLabs API](https://elevenlabs.io/) (for TTS)
- **FFmpeg** (for pydub audio processing):
  ```bash
  # macOS
  brew install ffmpeg
  
  # Ubuntu/Debian
  sudo apt-get install ffmpeg
  
  # Windows
  choco install ffmpeg
  ```

---

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/podcastGenerator.git
cd podcastGenerator
```

### 2. Create Virtual Environment
```bash
python3 -m venv myEnv
source myEnv/bin/activate  # On Windows: myEnv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the project root:

```bash
# MiniMax Configuration
MINIMAX_API_KEY=your_minimax_api_key_here
MINIMAX_GROUP_ID=your_group_id_here

# ElevenLabs Configuration
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ALEX=21m00Tcm4TlvDq8ikWAM  # Default: Rachel
ELEVENLABS_VOICE_SAM=AZnzlk1XvdvUeBnXmlld   # Default: Domi
```

> 💡 **Tip**: Get voice IDs from [ElevenLabs Voice Library](https://elevenlabs.io/voice-library)

---

## 🎬 Usage

### Start the Server
```bash
python app.py
```

The server will start at `http://localhost:8000`

### Web Interface
1. Open your browser to `http://localhost:8000`
2. Enter a topic (e.g., "Quantum Computing") or paste a URL
3. Select tone: casual, academic, or comedic
4. Click **Generate Podcast**
5. Listen to your AI-generated episode!

### API Endpoint

#### `POST /generate`

**Request Body:**
```json
{
  "topic": "The History of Jazz",
  "tone": "casual"
}
```

**Or with URL:**
```json
{
  "url": "https://en.wikipedia.org/wiki/Machine_learning",
  "tone": "academic"
}
```

**Response:**
```json
{
  "job_id": "a3f8c2d1",
  "topic": "The History of Jazz",
  "tone": "casual",
  "script": [
    {"speaker": "Alex", "text": "Hey Sam, let's talk about jazz..."},
    {"speaker": "Sam", "text": "Great topic! Jazz originated in..."}
  ],
  "research_brief": "Wikipedia — Jazz\n\nJazz is a music genre...",
  "audio_url": "/output/a3f8c2d1/podcast.mp3",
  "has_audio": true,
  "clip_count": 10
}
```

#### `GET /health`

Check API configuration status:
```json
{
  "status": "ok",
  "keys_configured": {
    "minimax": true,
    "elevenlabs": true
  }
}
```

---

## 📁 Project Structure

```
podcastGenerator/
├── app.py                  # Main FastAPI application
├── requirements.txt        # Python dependencies
├── .env                    # API keys (gitignored)
├── .gitignore             # Git exclusions
│
├── templates/
│   └── index.html         # Web interface
│
├── static/
│   ├── style.css          # Frontend styles
│   └── bell.mp3           # Optional bell sound (falls back to synthetic)
│
├── output/                # Generated podcasts (gitignored)
│   └── {job_id}/
│       ├── clips/         # Individual voice clips
│       │   ├── 000_alex.mp3
│       │   ├── 001_sam.mp3
│       │   └── ...
│       ├── jingle.mp3     # Generated intro/outro
│       └── podcast.mp3    # Final stitched output
│
└── myEnv/                 # Virtual environment (gitignored)
```

---

## 🎯 How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                      🎙️ PODCAST PIPELINE                    │
└─────────────────────────────────────────────────────────────┘

  📥 INPUT: Topic or URL
       ↓
  🔍 PHASE 1: Research
       │ → Wikipedia OpenSearch API
       │ → Web scraping with BeautifulSoup
       │ → Content extraction & cleaning
       ↓
  📝 PHASE 2: Script Generation (MiniMax LLM)
       │ → System prompt: conversational podcast format
       │ → JSON structured output [{"speaker": "...", "text": "..."}]
       │ → 8-12 exchanges between Alex & Sam
       ↓
  🗣️ PHASE 3: Voice Synthesis (ElevenLabs)
       │ → Loop through script
       │ → Generate MP3 for each line with appropriate voice
       │ → Save to clips/ directory
       ↓
  🎵 PHASE 4: Music Generation (MiniMax Music)
       │ → Generate 15s upbeat jingle
       │ → Poll for completion (async)
       │ → Download and save
       ↓
  🎚️ PHASE 5: Audio Mastering (pydub)
       │ → Generate bell chimes (E5 + harmonics)
       │ → Stitch: Intro jingle → Bell → Clips → Bell → Outro
       │ → Add 400ms silence gaps between clips
       │ → Normalize volume & export MP3
       ↓
  ✅ OUTPUT: Broadcast-ready podcast.mp3
```

---

## 🔧 Configuration Options

### Voice Customization
Replace the voice IDs in `.env` with your preferred ElevenLabs voices:

```bash
# Find voices at https://elevenlabs.io/voice-library
ELEVENLABS_VOICE_ALEX=your_custom_voice_id
ELEVENLABS_VOICE_SAM=another_voice_id
```

### Timeout Settings
Adjust in `app.py`:
```python
http_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0))
```

### Script Length
Modify `SCRIPT_SYSTEM_PROMPT` in `app.py`:
```python
- Keep it to 8-12 exchanges total  # Change these numbers
```

### Audio Gaps
In `stitch_podcast()`:
```python
silence = AudioSegment.silent(duration=400)  # Adjust milliseconds
```

---

## 📊 Performance

- **Average Generation Time**: 45-90 seconds (depends on script length)
  - Research: 1-3s
  - Script: 5-15s
  - Voice: 2-5s per clip
  - Music: 15-45s
  - Stitching: 1-2s

- **Output Quality**:
  - Format: MP3
  - Bitrate: 128 kbps (configurable)
  - Sample Rate: 44.1 kHz
  - Channels: Stereo

---

## 🐛 Troubleshooting

### No Audio Generated
```bash
# Check API keys are set
curl http://localhost:8000/health

# Check logs for specific errors
python app.py  # Look for [elevenlabs] or [minimax] errors
```

### FFmpeg Not Found
```bash
# Verify installation
ffmpeg -version

# If missing, install per your OS (see Prerequisites)
```

### Port Already in Use
```bash
# Change port in app.py
uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
```

### Memory Issues
Large transcripts may require more RAM. Consider:
- Reducing `exchars` in Wikipedia extraction
- Limiting `lines[:120]` in web scraping
- Adjusting `max_tokens` in MiniMax payload

---

## 🤝 Contributing

Contributions are welcome! Areas for improvement:

- [ ] Add more TTS provider options (Azure, Google, AWS)
- [ ] Implement background music mixing during dialogue
- [ ] Support for multiple languages
- [ ] Batch processing for multiple topics
- [ ] Web UI enhancements (progress bar, waveform visualization)
- [ ] Podcast RSS feed generation
- [ ] Export to multiple formats (WAV, OGG, M4A)

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **MiniMax AI** for powerful LLM and music generation capabilities
- **ElevenLabs** for industry-leading voice synthesis
- **FastAPI** for excellent async web framework
- **Wikipedia API** for free knowledge access
- **Open Source Community** for the amazing audio processing libraries

---

## 📧 Contact

**Author**: Dhananjay Surti  
**Project Link**: [https://github.com/djsurt/podcastGenerator](https://github.com/djsurt/podcastGenerator)

---

<div align="center">

**⭐ Star this repo if you found it helpful!**

Made with ❤️ and lots of ☕

</div>
