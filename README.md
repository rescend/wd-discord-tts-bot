
# WD Discord TTS Bot 🔊🎙️

A Discord Text-to-Speech bot built with ❤️ by the Wanton Destruction crew.  
Supports multi-voice synthesis via [alltalk](https://github.com/erew123/alltalk_tts) and optional integration with [xtts-v2-server](https://github.com/daswer123/xtts-v2-server) or other RVC-compatible backends.

---

## ✨ Features

- ⛓️ Queued speech playback
- 🗣️ Multiple voices with dynamic switching
- 🧠 Memory of user voice preferences
- 🪄 Supports both text and `@username` as input
- 🔁 Auto-reconnects on disconnect
- 💻 Docker-ready deployment

---

## 🧰 Prerequisites

- Docker or Python 3.9+
- `ffmpeg` installed and accessible in `PATH`
- Running instance of `alltalk` (see below)

---

## 🚀 Quickstart (Docker)

1. Clone this repo:
   ```bash
   git clone https://github.com/rescend/wd-discord-tts-bot.git
   cd wd-discord-tts-bot
   ```

2. Create your `config.py` file. See `config.template.py` for reference.

3. Build and run the container:
   ```bash
   docker build -t wd-discord-tts-bot .
   docker run -d \
     --name wd-discord-tts-bot \
     -v /mnt/user/appdata/wd-discord-tts-bot/config.py:/app/config.py \
     wd-discord-tts-bot
   ```

---

## 🧠 Voice Models & Samples

Voice `.wav` files and matching `.reference.txt` files should be placed inside the configured `voices/` directory.

> Example structure:
> ```
> voices/
> ├── Morgan_Freeman.wav
> └── Morgan_Freeman.reference.txt
> ```

Ensure filenames match exactly. Restart the bot to load new voices.

---

## 🔄 Alltalk Backend

This bot connects to [alltalk](https://github.com/erew123/alltalk_tts) over ports `7851` and `7852`.

Run it like this (example with auto-restart and GPU enabled):

```bash
docker run -d \
  --restart unless-stopped \
  --gpus all \
  -p 7851:7851 -p 7852:7852 \
  --name alltalk \
  erew123/alltalk_tts
```

---

## 🐍 Manual Setup (Non-Docker)

```bash
# Install requirements
pip install -r requirements.txt

# Run bot
python3 main.py
```

> Note: You must have PyNaCl, ffmpeg, and a working voice backend for audio playback.

---

## 🛠️ Configuration

Edit `config.py` to set your:
- Discord bot token
- Voice backend endpoint (usually `http://localhost:7851`)
- Default voice model
- Command prefix and queue settings

---

## 🧞 Roadmap

- [ ] Add Web UI for voice management
- [ ] Role-based voice access
- [ ] Voice emotion control (via XTTS or Bark)
- [ ] Memory-based voice cloning?

---

## 🤝 Credits

- [erew123/alltalk_tts](https://github.com/erew123/alltalk_tts)
- [Coqui.ai](https://github.com/coqui-ai/TTS)
- [Pycord / discord.py](https://github.com/Rapptz/discord.py)
- [Wanton Destruction](https://wanton.wtf)

---

## 🧼 License

MIT. Do whatever you want, just don't be a dick about it.
