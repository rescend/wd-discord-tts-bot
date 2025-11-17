
# WD Discord TTS Bot v0.5.0 🔊🎙️

A powerful Discord Text-to-Speech bot built with ❤️ by the Wanton Destruction crew.  
Features **dual TTS engine support** with Kokoro-FastAPI (local GPU-powered AI) and AllTalk TTS, providing high-quality, low-latency voice synthesis without cloud dependencies.

**Latest Update (v0.5.0)**: Migrated from Gemini to Kokoro-FastAPI for local, GPU-accelerated TTS with the premium `af_heart` voice. Eliminates cloud dependencies, reduces latency, and provides consistent high-quality voice synthesis.

---

## ✨ Features

### 🎤 **Dual TTS Engine Support**
- 🎙️ **Kokoro TTS**: Local GPU-powered AI voice using Kokoro-FastAPI with premium `af_heart` voice
- 🗣️ **AllTalk TTS**: Local voice synthesis with customizable models (fallback)
- 🔄 **Dynamic Switching**: Change engines on-the-fly with simple commands
- 🏢 **Per-Server Settings**: Each Discord server remembers its preferred engine

### 🎯 **Core Features**
- ⛓️ **Queued Playback**: Orderly speech processing with queue management
- 🎙️ **Voice Channel Integration**: Automatic joining and connection management
- 🔁 **Auto-Recovery**: Robust reconnection and error handling
- 🌐 **Docker Ready**: Optimized for containerized deployment
- 📱 **Interactive Commands**: Easy-to-use command system with help

### 🛡️ **Reliability & Stability** (Enhanced in v0.4)
- 🔧 **Advanced Connection Handling**: Production-grade voice WebSocket management
- ⏱️ **Smart Retry Logic**: Exponential backoff with proper cleanup between attempts
- 🔍 **WebSocket Validation**: Pre-playback connection state verification
- 🛠️ **Error Recovery**: Specific handling for ConnectionClosed (4006) and other voice errors
- 📊 **Detailed Logging**: Comprehensive debug output with traceback support
- 🚦 **Connection State Monitoring**: Real-time validation of voice gateway status

---

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `!kokoro` | Switch to Kokoro TTS (Local AI voice) |
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
- Running instance of Kokoro-FastAPI (for Kokoro TTS)
- Optional: Running instance of AllTalk (for AllTalk TTS fallback)

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
   
   # Kokoro TTS Settings (Primary)
   KOKORO_BASE_URL = "http://your-kokoro-server:8880/v1"
   KOKORO_DEFAULT_VOICE = "af_heart"
   KOKORO_RESPONSE_FORMAT = "wav"
   KOKORO_TTS_TIMEOUT_MS = 8000
   KOKORO_SPEED = 1.0
   
   # Optional - for AllTalk TTS fallback
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

## 🎙️ Kokoro TTS Setup

Kokoro-FastAPI provides local, GPU-accelerated TTS with high-quality voices.

1. **Run Kokoro-FastAPI:**
   ```bash
   docker run -d \
     --gpus all \
     -p 8880:8880 \
     --name kokoro-fastapi \
     ghcr.io/remsky/kokoro-fastapi-gpu:latest
   ```

2. **Voice Configuration:**
   - Default voice: `af_heart` (premium quality female voice)
   - Supports multiple voices via the API
   - WAV output format for optimal Discord compatibility
   - Typically <1.5s latency for short texts on GPU

3. **Test the API:**
   ```bash
   curl -X POST http://localhost:8880/v1/audio/speech \
     -H "Content-Type: application/json" \
     -d '{"model":"kokoro","input":"Hello world","voice":"af_heart","response_format":"wav"}'
   ```

4. **Resources:**
   - [Kokoro-FastAPI GitHub](https://github.com/remsky/Kokoro-FastAPI)
   - [API Documentation](http://localhost:8880/docs) (after running)

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

# Kokoro TTS Settings (Primary)
KOKORO_BASE_URL = "http://localhost:8880/v1"
KOKORO_DEFAULT_VOICE = "af_heart"
KOKORO_RESPONSE_FORMAT = "wav"
KOKORO_TTS_TIMEOUT_MS = 8000
KOKORO_SPEED = 1.0

# Optional - AllTalk TTS Settings (Fallback)
ALLTALK_TTS_URL = "http://localhost:7851/api/tts-generate"
ALLTALK_API_URL = "http://localhost:7851"
```

### **Environment Variables** (Alternative)
You can also use environment variables instead of `config.py`:
```bash
export DISCORD_BOT_TOKEN="your_token"
export TTS_CHANNEL_ID="123456789012345678"
export KOKORO_BASE_URL="http://localhost:8880/v1"
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
DEFAULT_TTS_ENGINE = "kokoro"  # or "alltalk"
```

---

## 🔧 Technical Improvements (v0.4)

### **Voice Connection Architecture**
Based on extensive research of Discord.py 2.4.0+ documentation and best practices:

#### **WebSocket Error Handling**
- **4006 Error Resolution**: Proper session cleanup preventing "Session no longer valid" errors
- **Connection State Validation**: WebSocket state checking (`ws.open`) before audio playback
- **Cleanup Strategy**: Force-disconnect with 5s timeout before all retry attempts
- **Resource Release**: 2-second wait periods between disconnect and reconnect operations

#### **Retry & Backoff Strategy**
- **Exponential Backoff**: 5s → 10s → 15s for normal connection failures
- **Extended Backoff**: 10s per retry for `ConnectionClosed` errors (codes 4000-4015)
- **Smart Retries**: Up to 3 attempts with proper cleanup between each
- **Timeout Management**: 35s overall timeout wrapping 60s connection timeout

#### **Connection Lifecycle**
```
1. Detect stale connections → Force disconnect (5s timeout)
2. Wait for resource cleanup (2s)
3. Attempt fresh connection (60s internal, 35s wrapper)
4. Validate WebSocket state (ws.open check)
5. Stability wait period (1s)
6. Proceed with playback
```

#### **Error Categories & Handling**
| Error Type | Wait Time | Strategy |
|------------|-----------|----------|
| `asyncio.TimeoutError` | 5s × retry | Clean + exponential backoff |
| `ConnectionClosed` (4006) | 10s × retry | Extended wait for session release |
| `ClientException` | 5s × retry | Force cleanup existing connections |
| Unexpected errors | 5s × retry | Full traceback logging |

### **Connection Monitoring**
- **Pre-Playback Checks**: Validates both `is_connected()` and WebSocket state
- **During Playback**: Event-based callback system for accurate completion tracking
- **Post-Playback**: Connection health verification
- **Inactivity Monitor**: Runs every 2 minutes, checks for disconnected voice clients

### **User Feedback**
Clear, emoji-prefixed error messages for different scenarios:
- ⚠️ Recoverable errors (timeouts, connection issues)
- ❌ Fatal errors (missing permissions, invalid state)
- Contextual messages about what went wrong and how to fix it

### **Implementation Details**

The connection handling system uses several key techniques from Discord.py best practices:

1. **WebSocket State Validation**
   ```python
   # Check if underlying WebSocket is actually open
   if hasattr(voice_client, 'ws') and voice_client.ws and not voice_client.ws.open:
       # Connection appears established but WebSocket is closed
       # Prevent silent failures
   ```

2. **Proper Cleanup Sequence**
   ```python
   # Always force-disconnect with timeout
   await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
   # Wait for Discord to release resources
   await asyncio.sleep(2)
   # Now safe to reconnect
   ```

3. **Connection Parameters**
   ```python
   # Nested timeouts for reliability
   guild_vc = await asyncio.wait_for(
       vc.channel.connect(timeout=60.0, reconnect=True),  # Inner timeout
       timeout=35.0  # Outer timeout
   )
   ```

4. **Exception Hierarchy**
   - `ConnectionClosed` → Extended backoff (Discord session issues)
   - `ClientException` → Clean existing connections first
   - `TimeoutError` → Standard exponential backoff
   - Generic `Exception` → Full traceback for debugging

---

## � Troubleshooting

### **Common Issues:**

**Voice Connection Errors (WebSocket 4006):**
```
⚠️ If you see "Session no longer valid" errors:
1. Bot automatically retries with proper cleanup
2. Wait for retry sequence to complete (up to 30s)
3. If persistent, use !leave command and try again
4. Check Discord server status: https://discordstatus.com
```

**Connection Timeouts:**
- **Normal**: Bot retries automatically with increasing delays
- **Action**: Wait for full retry sequence (3 attempts)
- **If persistent**: Discord API may be experiencing issues
- **Solution**: Check logs for specific error codes

**"Unclosed connection" Warnings:**
- **Status**: Fixed in v0.4 with proper WebSocket lifecycle management
- **Impact**: No longer causes connection failures
- **If still occurring**: Check Discord.py version (should be 2.4.0+)

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
- Review `heartbeat_timeout` settings (default: 60s)

**Voice Connection Failures:**
- Verify user is in a voice channel
- Check bot has "Connect" and "Speak" permissions
- Try the `!leave` command and rejoin
- **New in v0.4**: Check logs for specific WebSocket error codes
- Allow retry sequence to complete before manual intervention

**TTS Generation Errors:**
- **Kokoro**: Verify server is running at configured URL and has GPU access
- **AllTalk**: Check server is running and accessible
- **Audio format errors**: Ensure WAV format is configured (not MP3)

**Bot Joins But Doesn't Speak:**
- **Fixed in v0.4**: Enhanced pre-playback validation
- Check FFmpeg is properly installed
- Verify audio files are being created (check logs for "WAV file validation")
- Ensure WebSocket connection is stable (new validation in v0.4)

---

## � Monitoring & Logs

The bot provides detailed logging for troubleshooting:

```bash
# View Docker logs
docker logs -f wd-discord-tts-bot

# Key log messages to watch for:
# "Opus loaded successfully" - Voice codec working
# "Using TTS engine: kokoro/alltalk" - Engine selection
# "Kokoro audio saved to..." - Audio file processing
# "Successfully connected to <channel>" - Voice connection established
# "Playback completed successfully" - Successful audio playback

# Connection troubleshooting logs (v0.4+):
# "Voice connection timeout (attempt X/3)" - Retry in progress
# "ConnectionClosed: Code=4006" - Session invalidation detected
# "Voice websocket is closed" - Connection validation failure
# "Stale VC found, cleaning up" - Automatic cleanup in progress
```

### **Understanding Error Codes**

| Code | Meaning | Resolution |
|------|---------|------------|
| 4006 | Session no longer valid | Automatic retry with cleanup |
| 4014 | Disconnected | Channel was deleted or bot was kicked |
| 4015 | Voice server crashed | Discord-side issue, automatic retry |

### **Debug Mode**
For more detailed debugging, the bot now includes comprehensive error tracking:
- Full exception tracebacks for unexpected errors
- WebSocket state logging
- Connection lifecycle timestamps
- Retry attempt tracking with backoff timings

---

## 📝 Changelog

### **v0.5.0** (November 2025) - Kokoro TTS Migration
**Major Feature: Local GPU-Powered TTS**

**Breaking Changes:**
- ❌ **REMOVED**: Google Gemini TTS integration (cloud dependency eliminated)
- ✅ **ADDED**: Kokoro-FastAPI integration (local GPU-powered TTS)
- 🔄 **CHANGED**: Command `!gemini` → `!kokoro`
- 📦 **REMOVED**: `google-genai` dependency

**New Features:**
- 🎙️ Kokoro TTS with premium `af_heart` voice as primary engine
- 🚀 Sub-1.5s latency for local GPU inference
- 🔄 Automatic fallback to AllTalk on Kokoro failure
- 📉 50 lines of code removed (simpler codebase)
- 🌐 Zero cloud dependencies for TTS

**Configuration Changes:**
- New `KOKORO_BASE_URL` setting (replaces `GEMINI_API_KEY`)
- New `KOKORO_DEFAULT_VOICE`, `KOKORO_RESPONSE_FORMAT`, etc.
- WAV format default for optimal Discord compatibility

**Migration Guide:**
1. Remove `GEMINI_API_KEY` from config
2. Add Kokoro configuration settings
3. Run Kokoro-FastAPI container with GPU support
4. Update dependencies: `pip install -r requirements.txt`

---

### **v0.4.1** (November 2025) - Voice Protocol v8 Upgrade
**Critical Fix for Persistent 4006 Errors**

**Major Fix:**
- ✅ **RESOLVED**: Persistent WebSocket 4006 errors during voice handshake
- ✅ Upgraded Discord.py from 2.4.0 → 2.6.4 (includes voice protocol v8)
- ✅ Updated PyNaCl to 1.6.0 for new AEAD encryption support
- ✅ Fixed region-specific failures (Singapore, US East, US West, Rotterdam)

**Root Cause:**
- Discord changed voice protocol from v7 to v8 in mid-2024
- Old library versions incompatible with new dynamic port discovery
- PR #10210 (merged June 30, 2024) fixed protocol upgrade in discord.py 2.5.3+

**Impact:**
This was a **library compatibility issue**, not a code issue. The connection retry logic in v0.4 was already correct - it just needed the updated library to work properly.

---

### **v0.4** (November 2025) - Connection Stability Overhaul
**Based on Discord.py 2.4.0+ Documentation Research**

**Major Fixes:**
- ✅ Enhanced connection retry logic and error handling
- ✅ Fixed "unclosed connection" warnings and resource leaks
- ✅ Eliminated "bot joins but doesn't speak" issues
- ⚠️ Note: 4006 errors persisted until v0.4.1 library upgrade

**Connection Improvements:**
- Enhanced retry logic with exponential backoff (5s → 10s → 15s)
- Pre-playback WebSocket state validation
- Proper session cleanup between retry attempts
- Extended backoff for ConnectionClosed errors (10s per retry)
- 2-second resource release delays between operations

**Error Handling:**
- Specific handlers for ConnectionClosed, TimeoutError, ClientException
- Full traceback logging for unexpected errors
- User-friendly emoji-prefixed error messages
- Automatic recovery from transient Discord API issues

**Monitoring:**
- Real-time WebSocket state checking
- Connection lifecycle logging
- Detailed error code documentation
- Enhanced debug output with retry tracking

### **v0.3** - Dual TTS Engine Support (Deprecated)
- Added Google Gemini 2.5 Flash TTS integration (removed in v0.5.0)
- Per-server engine preferences
- Dynamic engine switching commands

### **v0.2** - AllTalk Integration
- AllTalk TTS backend support
- Voice model customization
- Docker deployment optimization

### **v0.1** - Initial Release
- Basic TTS functionality
- Discord voice channel integration
- Queue management system

---

## 🧞 Roadmap

- [x] **Voice Connection Stability** - Production-grade error handling (v0.4)
- [x] **WebSocket Error Recovery** - Proper 4006 error handling (v0.4)
- [x] **Local GPU-Powered TTS** - Kokoro-FastAPI integration (v0.5.0)
- [ ] **Multiple Kokoro Voices**: Support for additional Kokoro voice models
- [ ] **Voice Cloning**: Integration with voice cloning APIs
- [ ] **Web Dashboard**: Browser-based control panel
- [ ] **Role-based Access**: Permission system for voice engines
- [ ] **Voice Emotion Control**: Mood and style modulation via Kokoro parameters
- [ ] **Multi-language Support**: International TTS engines
- [ ] **Audio Effects**: Post-processing and filters
- [ ] **Usage Analytics**: Voice usage statistics and insights

---

## 🤝 Credits & Technologies

### **Core Technologies:**
- [discord.py 2.6.4+](https://github.com/Rapptz/discord.py) - Discord API library with voice improvements
- [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) - Local GPU-accelerated TTS
- [AllTalk TTS](https://github.com/erew123/alltalk_tts) - Local voice synthesis backend
- [FFmpeg](https://ffmpeg.org/) - Audio processing and conversion

### **Research & Documentation:**
- [Discord.py Official Documentation](https://discordpy.readthedocs.io/en/stable/) - Voice client best practices
- [Discord API Documentation](https://discord.com/developers/docs) - WebSocket gateway specifications
- Voice connection stability improvements based on Discord.py 2.4.0 changelog

### **Special Thanks:**
- [Rapptz](https://github.com/Rapptz) and discord.py contributors for excellent documentation
- [remsky](https://github.com/remsky) for Kokoro-FastAPI wrapper
- [erew123](https://github.com/erew123) for AllTalk TTS
- [Kokoro-82M team](https://huggingface.co/hexgrad/Kokoro-82M) for the base TTS model
- [Wanton Destruction](https://wanton.wtf) community for testing and feedback

---

## 📄 License

MIT License - Do whatever you want, just don't be a dick about it.

### **Third-party Licenses:**
- Kokoro-FastAPI and Kokoro-82M follow their respective licensing terms
- AllTalk TTS follows its respective licensing terms
- Discord.py under MIT License
