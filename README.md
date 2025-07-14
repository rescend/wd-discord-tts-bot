
# WD Discord TTS Bot v0.3 🔊🎙️

A powerful Discord Text-to-Speech bot built with ❤️ by the Wanton Destruction crew.  
Features **dual TTS engine support** with Google Gemini 2.5 Flash TTS and AllTalk TTS, allowing seamless switching between AI-powered and local voice synthesis.

---

## ✨ Features

### 🎤 **Dual TTS Engine Support**
- 🔮 **Gemini TTS**: AI-powered natural speech using Google's Gemini 2.5 Flash model
- 🗣️ **AllTalk TTS**: Local voice synthesis with customizable models
- 🔄 **Dynamic Switching**: Change engines on-the-fly with simple commands
- 🏢 **Per-Server Settings**: Each Discord server remembers its preferred engine

### 🎯 **Core Features**
- ⛓️ **Queued Playback**: Orderly speech processing with queue management
- 🎙️ **Voice Channel Integration**: Automatic joining and connection management
- 🔁 **Auto-Recovery**: Robust reconnection and error handling
- 🌐 **Docker Ready**: Optimized for containerized deployment
- 📱 **Interactive Commands**: Easy-to-use command system with help

### 🛡️ **Reliability & Stability**
- 🔧 **Connection Monitoring**: Advanced gateway and voice connection handling
- ⏱️ **Timeout Protection**: Prevents hanging connections and playback issues
- � **Retry Logic**: Automatic retries for failed operations
- 📊 **Detailed Logging**: Comprehensive debug output and error tracking

---

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `!gemini` | Switch to Gemini TTS (AI-powered voice) |
| `!alltalk` | Switch to AllTalk TTS (Local synthesis) |
| `!voice` | Check current voice engine |
| `!leave` | Make bot leave voice channel |
| `!help` | Show command help |

> **💬 Usage**: Simply type any message in the configured TTS channel and the bot will speak it aloud using the selected voice engine!

---

## 🧰 Prerequisites

### **Required:**
- Docker or Python 3.9+
- `ffmpeg` installed and accessible in `PATH`
- Google Gemini API key (for Gemini TTS)
- Running instance of `alltalk` (for AllTalk TTS - optional)

### **Voice Codec:**
- `libopus` (automatically installed in Docker)
- On macOS: `brew install opus`
- On Ubuntu/Debian: `apt-get install libopus0 libopus-dev`

---

## 🚀 Quickstart (Docker)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/rescend/wd-discord-tts-bot.git
   cd wd-discord-tts-bot
   ```

2. **Create your configuration:**
   ```python
   # config.py
   DISCORD_BOT_TOKEN = "your_discord_bot_token"
   TTS_CHANNEL_ID = 123456789012345678  # Your TTS channel ID
   GEMINI_API_KEY = "your_gemini_api_key"
   
   # Optional - for AllTalk TTS
   ALLTALK_TTS_URL = "http://your-alltalk-server:7851/api/tts-generate"
   ALLTALK_API_URL = "http://your-alltalk-server:7851"
   ```

3. **Build and run:**
   ```bash
   docker build -t wd-discord-tts-bot .
   docker run -d \
     --name wd-discord-tts-bot \
     -v $(pwd)/config.py:/app/config.py \
     wd-discord-tts-bot
   ```

---

## 🔮 Gemini TTS Setup

1. **Get API Key:**
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Create a new API key
   - Add it to your `config.py` as `GEMINI_API_KEY`

2. **Voice Configuration:**
   - Default voice: `Gacrux` (warm, mature female voice)
   - Style: Configured for warm, conversational tone
   - Automatically converts 24kHz mono PCM to Discord-compatible WAV

---

## 🗣️ AllTalk TTS Setup

This bot can connect to [alltalk](https://github.com/erew123/alltalk_tts) for local voice synthesis.

**Run AllTalk with Docker:**
```bash
docker run -d \
  --restart unless-stopped \
  --gpus all \
  -p 7851:7851 -p 7852:7852 \
  --name alltalk \
  erew123/alltalk_tts
```

**Configuration:**
```python
ALLTALK_TTS_URL = "http://localhost:7851/api/tts-generate"
ALLTALK_API_URL = "http://localhost:7851"
```

---

## 🎨 Voice Models & Samples

### **Gemini TTS Voices**
Gemini TTS includes several high-quality prebuilt voices:
- `Gacrux` (default): Warm, mature female voice
- Additional voices available via API configuration

### **AllTalk Voice Models**
Voice `.wav` files and matching `.reference.txt` files should be placed inside the configured `voices/` directory.

> Example structure:
> ```
> voices/
> ├── Morgan_Freeman.wav
> └── Morgan_Freeman.reference.txt
> ```

Ensure filenames match exactly. Restart the bot to load new voices.

---

## � Manual Setup (Non-Docker)

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install ffmpeg libopus0 libopus-dev

# Install Python dependencies
pip install -r requirements.txt

# Run bot
python3 main.py
```

> **Note**: You must have PyNaCl, ffmpeg, libopus, and valid API keys for voice backends.

---

## 🛠️ Configuration

Create a `config.py` file with the following settings:

```python
# Required Settings
DISCORD_BOT_TOKEN = "your_discord_bot_token_here"
TTS_CHANNEL_ID = 123456789012345678  # Channel ID where TTS works
GEMINI_API_KEY = "your_gemini_api_key_here"

# Optional - AllTalk TTS Settings  
ALLTALK_TTS_URL = "http://localhost:7851/api/tts-generate"
ALLTALK_API_URL = "http://localhost:7851"
```

### **Environment Variables** (Alternative)
You can also use environment variables instead of `config.py`:
```bash
export DISCORD_BOT_TOKEN="your_token"
export TTS_CHANNEL_ID="123456789012345678"
export GEMINI_API_KEY="your_gemini_key"
```

---

## 🔧 Advanced Configuration

### **Docker Compose**
```yaml
version: '3.8'
services:
  discord-tts-bot:
    build: .
    restart: unless-stopped
    volumes:
      - ./config.py:/app/config.py
    depends_on:
      - alltalk

  alltalk:
    image: erew123/alltalk_tts
    restart: unless-stopped
    ports:
      - "7851:7851"
      - "7852:7852"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### **Voice Engine Defaults**
To change the default TTS engine, modify `main.py`:
```python
DEFAULT_TTS_ENGINE = "alltalk"  # or "gemini"
```

---

## � Troubleshooting

### **Common Issues:**

**Opus Codec Errors:**
```bash
# Docker: Rebuild with updated Dockerfile
docker build --no-cache -t wd-discord-tts-bot .

# Local: Install opus
# macOS: brew install opus
# Ubuntu: sudo apt-get install libopus0 libopus-dev
```

**Gateway Connection Issues:**
- Check internet connectivity to Discord
- Verify bot token is valid
- Ensure bot has proper permissions in Discord server

**Voice Connection Failures:**
- Verify user is in a voice channel
- Check bot has "Connect" and "Speak" permissions
- Try the `!leave` command and rejoin

**TTS Generation Errors:**
- **Gemini**: Verify API key and quota
- **AllTalk**: Check server is running and accessible

---

## � Monitoring & Logs

The bot provides detailed logging for troubleshooting:

```bash
# View Docker logs
docker logs -f wd-discord-tts-bot

# Key log messages to watch for:
# "Opus loaded successfully" - Voice codec working
# "Using TTS engine: gemini/alltalk" - Engine selection
# "WAV file validation" - Audio file processing
# "Finished playback" - Successful audio playback
```

---

## 🧞 Roadmap

- [ ] **Multiple Gemini Voices**: Support for additional Gemini voice models
- [ ] **Voice Cloning**: Integration with voice cloning APIs
- [ ] **Web Dashboard**: Browser-based control panel
- [ ] **Role-based Access**: Permission system for voice engines
- [ ] **Voice Emotion Control**: Mood and style modulation
- [ ] **Multi-language Support**: International TTS engines
- [ ] **Audio Effects**: Post-processing and filters
- [ ] **Usage Analytics**: Voice usage statistics and insights

---

## 🤝 Credits & Technologies

### **Core Technologies:**
- [Google Gemini 2.5 Flash TTS](https://deepmind.google/technologies/gemini/) - AI-powered voice synthesis
- [AllTalk TTS](https://github.com/erew123/alltalk_tts) - Local voice synthesis backend
- [discord.py](https://github.com/Rapptz/discord.py) - Discord API library
- [FFmpeg](https://ffmpeg.org/) - Audio processing and conversion

### **Special Thanks:**
- [erew123](https://github.com/erew123) for AllTalk TTS
- [Coqui.ai](https://github.com/coqui-ai/TTS) for TTS research
- [Wanton Destruction](https://wanton.wtf) community for testing and feedback

---

## 📄 License

MIT License - Do whatever you want, just don't be a dick about it.

### **Third-party Licenses:**
- Gemini API usage subject to [Google AI Terms](https://ai.google.dev/terms)
- AllTalk TTS follows its respective licensing terms
- Discord.py under MIT License
