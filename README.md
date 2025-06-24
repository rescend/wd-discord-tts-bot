# WD Discord TTS Bot V0.1 🔊🎙️

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
