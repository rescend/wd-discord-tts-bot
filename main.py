import discord
import requests
import asyncio
import re
import json
import os
import wave
import aiohttp

import config  # This should contain your DISCORD_BOT_TOKEN, TTS_CHANNEL_ID, and KOKORO_BASE_URL

# Load Opus codec for voice support
try:
    discord.opus.load_opus('libopus.so.0')
    print("Opus loaded successfully with 'libopus.so.0' (Linux)")
except discord.opus.OpusNotLoaded:
    try:
        discord.opus.load_opus('libopus.so')
        print("Opus loaded successfully with 'libopus.so' (Linux)")
    except discord.opus.OpusNotLoaded:
        try:
            discord.opus.load_opus('opus')
            print("Opus loaded successfully with 'opus'")
        except discord.opus.OpusNotLoaded:
            try:
                discord.opus.load_opus('/opt/homebrew/lib/libopus.dylib')
                print("Opus loaded successfully with macOS Homebrew path")
            except discord.opus.OpusNotLoaded:
                try:
                    discord.opus.load_opus('libopus')
                    print("Opus loaded successfully with 'libopus'")
                except discord.opus.OpusNotLoaded:
                    print("WARNING: Could not load Opus codec. Voice features may not work.")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = discord.Client(
    intents=intents,
    heartbeat_timeout=60.0,
    guild_ready_timeout=10.0,
    max_messages=None
)

TTS_TIMEOUT_SEC = 60 * 60  # 1 hour

# TTS Engine selection - per guild
current_tts_engine = {}   # guild_id -> "kokoro", "alltalk", or "chatterbox"
DEFAULT_TTS_ENGINE = "kokoro"

# Chatterbox voice selection - per guild
current_chatterbox_voice = {}  # guild_id -> voice name string

last_activity = {}  # guild_id -> last activity time


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def preprocess_text(text):
    """Strip Discord mentions and URLs before sending to any TTS engine."""
    text = re.sub(r'<@!?\d+>', '', text)   # user mentions
    text = re.sub(r'<@&\d+>', '', text)    # role mentions
    text = re.sub(r'<#\d+>', '', text)     # channel mentions
    text = re.sub(r'https?://\S+', '', text)  # URLs
    return ' '.join(text.split())


def compute_chatterbox_exaggeration(text):
    """
    Derive an exaggeration value from the message content.
    Base value comes from config (default 0.5).
    - Repeated characters (boooooo, lmaooooo) → big boost, let it rip
    - ALL CAPS majority                        → noticeable boost
    - Lots of !!! or ???                       → mild boost
    """
    base = getattr(config, 'CHATTERBOX_EXAGGERATION', 0.5)

    # Repeated characters — 4+ in a row (boooooo, noooooo, lmaooooo)
    if re.search(r'(.)\1{3,}', text):
        base = min(base + 0.7, 2.0)

    # ALL CAPS — more than half the words (ignoring short words)
    words = text.split()
    if words:
        caps_words = [w for w in words if len(w) > 2 and w.isupper()]
        if len(caps_words) / len(words) > 0.5:
            base = min(base + 0.5, 2.0)
        elif len(caps_words) / len(words) > 0.25:
            base = min(base + 0.25, 2.0)

    # Lots of exclamation / question marks
    if text.count('!') >= 3 or text.count('?') >= 3:
        base = min(base + 0.2, 2.0)

    return round(base, 2)


# ---------------------------------------------------------------------------
# TTS engines
# ---------------------------------------------------------------------------

async def generate_kokoro_tts(text, message):
    """Generate TTS using Kokoro-FastAPI (OpenAI-compatible endpoint)."""
    try:
        print("Worker: Using Kokoro TTS")
        if not hasattr(config, 'KOKORO_BASE_URL') or not config.KOKORO_BASE_URL:
            await message.channel.send("Kokoro TTS URL is not configured.")
            return None

        payload = {
            "model": "kokoro",
            "input": text,
            "voice": getattr(config, 'KOKORO_DEFAULT_VOICE', 'af_heart'),
            "response_format": getattr(config, 'KOKORO_RESPONSE_FORMAT', 'wav'),
            "speed": getattr(config, 'KOKORO_SPEED', 1.0)
        }

        print(f"Worker: Sending TTS request to Kokoro for text: '{text}'")
        timeout = aiohttp.ClientTimeout(total=getattr(config, 'KOKORO_TTS_TIMEOUT_MS', 8000) / 1000)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{config.KOKORO_BASE_URL}/audio/speech", json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    await message.channel.send(f"Kokoro TTS error: {error_text[:100]}")
                    print(f"Worker: Kokoro error {resp.status}: {error_text}")
                    return None
                audio_data = await resp.read()

        file_ext = getattr(config, 'KOKORO_RESPONSE_FORMAT', 'wav')
        audio_path = f"tts_{message.id}.{file_ext}"
        with open(audio_path, "wb") as f:
            f.write(audio_data)
        print(f"Worker: Kokoro audio saved to {audio_path} ({len(audio_data)} bytes)")
        return audio_path

    except asyncio.TimeoutError:
        await message.channel.send("⚠️ Kokoro TTS timeout. Trying fallback...")
        print("Worker: Kokoro TTS timeout")
        return None
    except Exception as e:
        await message.channel.send(f"Kokoro TTS error: {e}")
        print(f"Worker: Exception during Kokoro TTS: {e}")
        return None


async def generate_alltalk_tts(text, message):
    """Generate TTS using AllTalk API."""
    try:
        print("Worker: Using AllTalk TTS")
        if not hasattr(config, 'ALLTALK_TTS_URL') or not config.ALLTALK_TTS_URL:
            await message.channel.send("AllTalk TTS URL is not configured.")
            return None

        payload = {
            "text_input": text,
            "text_filtering": "standard",
            "character_voice_gen": "female_07.wav",
            "rvccharacter_voice_gen": "Disabled",
            "rvccharacter_pitch": 0,
            "narrator_enabled": 'false',
            "narrator_voice_gen": "",
            "rvcnarrator_voice_gen": "Disabled",
            "rvcnarrator_pitch": 0,
            "text_not_inside": "character",
            "language": "en",
            "output_file_name": f"tts_{message.id}",
            "output_file_timestamp": False,
            "autoplay": False,
            "autoplay_volume": 0.5,
            "speed": 1.0,
            "pitch": 1,
            "temperature": 1.0,
            "repetition_penalty": 9.0
        }

        print(f"Worker: Sending TTS request to AllTalk")
        resp = requests.post(config.ALLTALK_TTS_URL, data=payload, timeout=30)
        print(f"Worker: AllTalk response status: {resp.status_code}")

        if resp.status_code != 200:
            await message.channel.send(f"TTS server error: {resp.text[:100]}")
            return None

        result = resp.json()
        wav_url = f"{config.ALLTALK_API_URL}{result['output_file_url']}"
        print(f"Worker: Downloading generated audio from {wav_url}")

        wav_resp = requests.get(wav_url)
        wav_path = f"tts_{message.id}.wav"
        with open(wav_path, "wb") as f:
            f.write(wav_resp.content)
        print(f"Worker: AllTalk audio saved to {wav_path}")
        return wav_path

    except Exception as e:
        await message.channel.send(f"Failed to fetch TTS from AllTalk: {e}")
        print(f"Worker: Exception during AllTalk TTS fetch: {e}")
        return None


async def generate_chatterbox_tts(text, message):
    """
    Generate TTS using Chatterbox (travisvn/chatterbox-tts-api).
    - Strips mentions and URLs from text before sending
    - Auto-adjusts exaggeration based on message style (caps, repeated chars, !!!)
    - Respects per-guild voice selection
    """
    try:
        print("Worker: Using Chatterbox TTS")
        if not hasattr(config, 'CHATTERBOX_BASE_URL') or not config.CHATTERBOX_BASE_URL:
            await message.channel.send("Chatterbox TTS URL is not configured.")
            print("Worker: CHATTERBOX_BASE_URL not found in config.")
            return None

        clean_text = preprocess_text(text)
        if not clean_text:
            print("Worker: Text was empty after preprocessing, skipping.")
            return None

        exaggeration = compute_chatterbox_exaggeration(text)  # use original for detection
        guild_id = message.guild.id
        voice = current_chatterbox_voice.get(guild_id, getattr(config, 'CHATTERBOX_DEFAULT_VOICE', 'alloy'))

        payload = {
            "model": "chatterbox",
            "input": clean_text,
            "voice": voice,
            "response_format": "wav",
            "speed": getattr(config, 'CHATTERBOX_SPEED', 1.0),
            "exaggeration": exaggeration,
            "cfg_weight": getattr(config, 'CHATTERBOX_CFG_WEIGHT', 0.5),
            "temperature": getattr(config, 'CHATTERBOX_TEMPERATURE', 0.8),
        }

        print(f"Worker: Chatterbox request — voice={voice}, exaggeration={exaggeration}, text='{clean_text}'")
        timeout = aiohttp.ClientTimeout(total=getattr(config, 'CHATTERBOX_TTS_TIMEOUT_SEC', 30))

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{config.CHATTERBOX_BASE_URL}/v1/audio/speech", json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    await message.channel.send(f"Chatterbox TTS error: {error_text[:100]}")
                    print(f"Worker: Chatterbox error {resp.status}: {error_text}")
                    return None
                audio_data = await resp.read()

        audio_path = f"tts_{message.id}.wav"
        with open(audio_path, "wb") as f:
            f.write(audio_data)
        print(f"Worker: Chatterbox audio saved to {audio_path} ({len(audio_data)} bytes)")
        return audio_path

    except asyncio.TimeoutError:
        await message.channel.send("⚠️ Chatterbox TTS timeout.")
        print("Worker: Chatterbox TTS timeout")
        return None
    except Exception as e:
        await message.channel.send(f"Chatterbox TTS error: {e}")
        print(f"Worker: Exception during Chatterbox TTS: {e}")
        return None


async def fetch_chatterbox_voices():
    """Fetch the list of uploaded voices from the Chatterbox API."""
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{config.CHATTERBOX_BASE_URL}/voices") as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                # API returns {"voices": [...], "count": N}
                return data.get("voices", [])
    except Exception as e:
        print(f"fetch_chatterbox_voices error: {e}")
        return None


# ---------------------------------------------------------------------------
# TTS worker
# ---------------------------------------------------------------------------

async def tts_worker(bot):
    while True:
        print("Worker: waiting for next TTS job...")
        user, text, message = await bot.queue.get()
        guild_id = message.guild.id
        print(f"Worker: Got message from {user} ({user.id}) in channel {message.channel.id}: '{text}'")
        last_activity[guild_id] = asyncio.get_event_loop().time()

        # Find which VC the user is in
        vc = getattr(user, "voice", None)
        if not vc or not vc.channel:
            await message.channel.send(f"{user.mention} Please join a voice channel to use TTS.")
            print("Worker: User not in voice channel, skipping job.")
            bot.queue.task_done()
            continue

        # (Re)join user's channel if needed with proper retry logic
        voice_client = None
        max_retries = 3
        retry_count = 0
        connection_successful = False

        while retry_count < max_retries and not connection_successful:
            try:
                guild_vc = discord.utils.get(bot.voice_clients, guild=message.guild)

                if guild_vc:
                    if guild_vc.is_connected():
                        if guild_vc.channel != vc.channel:
                            print(f"Worker: Moving to voice channel: {vc.channel}")
                            try:
                                await asyncio.wait_for(guild_vc.move_to(vc.channel), timeout=10.0)
                                voice_client = guild_vc
                                connection_successful = True
                            except Exception as move_error:
                                print(f"Worker: Error moving channels: {move_error}, will reconnect")
                                try:
                                    await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
                                except asyncio.CancelledError:
                                    raise
                                except Exception as disconnect_error:
                                    print(f"Worker: Error during move cleanup disconnect: {disconnect_error}")
                                await asyncio.sleep(2)
                        else:
                            print("Worker: Already in the correct voice channel.")
                            voice_client = guild_vc
                            connection_successful = True

                    if not connection_successful:
                        print("Worker: Stale or failed VC, cleaning up before reconnect.")
                        try:
                            await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
                        except Exception as cleanup_error:
                            print(f"Worker: Error during cleanup: {cleanup_error}")
                        await asyncio.sleep(2)
                        guild_vc = None

                if not connection_successful:
                    print(f"Worker: Connecting fresh to {vc.channel} (attempt {retry_count + 1}/{max_retries})")
                    # reconnect=False: let our retry loop handle failures, not discord.py internally.
                    # This prevents two competing retry loops and the timeout inversion bug where
                    # the outer wait_for(70s) could fire during discord.py's own internal retries.
                    # Outer timeout (70s) > inner timeout (60s), so on timeout the inner is expected to fire first.
                    guild_vc = await asyncio.wait_for(
                        vc.channel.connect(timeout=60.0, reconnect=False, self_deaf=True),
                        timeout=70.0
                    )
                    voice_client = guild_vc
                    connection_successful = True
                    print(f"Worker: Successfully connected to {vc.channel}")

            except asyncio.TimeoutError:
                retry_count += 1
                print(f"Worker: Voice connection timeout (attempt {retry_count}/{max_retries})")
                try:
                    guild_vc = discord.utils.get(bot.voice_clients, guild=message.guild)
                    if guild_vc:
                        await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
                except Exception as cleanup_err:
                    print(f"Worker: Cleanup error: {cleanup_err}")
                if retry_count < max_retries:
                    wait_time = 5 * retry_count
                    print(f"Worker: Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    await message.channel.send("⚠️ Voice connection timed out. Discord servers may be slow. Please try again.")
                    print("Worker: Voice connection failed after all retries")

            except discord.errors.ClientException as e:
                print(f"Worker: ClientException during connection: {e}")
                retry_count += 1
                try:
                    guild_vc = discord.utils.get(bot.voice_clients, guild=message.guild)
                    if guild_vc:
                        await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
                except Exception as cleanup_err:
                    print(f"Worker: Cleanup error: {cleanup_err}")
                if retry_count < max_retries:
                    wait_time = 5 * retry_count
                    print(f"Worker: Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    await message.channel.send("⚠️ Voice connection failed. The bot may already be connected elsewhere.")
                    print(f"Worker: Failed to join VC after all retries: {e}")

            except discord.errors.ConnectionClosed as e:
                retry_count += 1
                print(f"Worker: ConnectionClosed during voice connection: Code={e.code}, Reason={e.reason}")
                try:
                    guild_vc = discord.utils.get(bot.voice_clients, guild=message.guild)
                    if guild_vc:
                        await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
                except Exception as cleanup_err:
                    print(f"Worker: Cleanup error: {cleanup_err}")
                if retry_count < max_retries:
                    # 4017 = Discord voice server rejected SELECT_PROTOCOL (transient server-side issue).
                    # Needs a longer wait since retrying immediately hits the same overloaded server.
                    if e.code == 4017:
                        wait_time = 15 * retry_count
                        print(f"Worker: Code 4017 (Discord voice server issue), waiting {wait_time}s before retry...")
                    else:
                        wait_time = 10 * retry_count
                        print(f"Worker: Connection closed (code {e.code}), waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    if e.code == 4017:
                        await message.channel.send("⚠️ Discord's voice servers are having issues right now (4017). Please try again in a moment.")
                    else:
                        await message.channel.send("⚠️ Discord voice connection was closed unexpectedly. Please try again.")
                    print(f"Worker: ConnectionClosed after all retries: {e}")

            except Exception as e:
                retry_count += 1
                print(f"Worker: Unexpected voice connection error (attempt {retry_count}/{max_retries}): {e}")
                print(f"Worker: Error type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                try:
                    guild_vc = discord.utils.get(bot.voice_clients, guild=message.guild)
                    if guild_vc:
                        await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
                except Exception as cleanup_err:
                    print(f"Worker: Cleanup error: {cleanup_err}")
                if retry_count < max_retries:
                    wait_time = 5 * retry_count
                    print(f"Worker: Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    await message.channel.send(f"❌ Could not join voice channel: {str(e)[:100]}")
                    print(f"Worker: Failed to join VC after all retries: {e}")

        # If we couldn't establish connection, skip this job
        if not connection_successful or not voice_client:
            print("Worker: Could not establish voice connection, skipping job")
            bot.queue.task_done()
            continue

        # Generate TTS audio using the selected engine
        engine = current_tts_engine.get(guild_id, DEFAULT_TTS_ENGINE)
        print(f"Worker: Using TTS engine: {engine}")

        audio_path = None
        if engine == "kokoro":
            audio_path = await generate_kokoro_tts(text, message)
            if audio_path is None and hasattr(config, 'ALLTALK_TTS_URL'):
                print("Worker: Kokoro failed, falling back to AllTalk")
                audio_path = await generate_alltalk_tts(text, message)
        elif engine == "alltalk":
            audio_path = await generate_alltalk_tts(text, message)
        elif engine == "chatterbox":
            audio_path = await generate_chatterbox_tts(text, message)
        else:
            await message.channel.send(f"Unknown TTS engine: {engine}")
            print(f"Worker: Unknown TTS engine: {engine}")
            bot.queue.task_done()
            continue

        if audio_path is None:
            print("Worker: TTS generation failed, skipping playback")
            bot.queue.task_done()
            continue

        # Play audio in VC with connection verification
        try:
            print(f"Worker: Starting playback of {audio_path}")

            if not voice_client or not voice_client.is_connected():
                await message.channel.send("⚠️ Lost voice connection before playback. Please try again.")
                print("Worker: Voice client disconnected before playback")
                bot.queue.task_done()
                continue

            await asyncio.sleep(1.0)

            if not os.path.exists(audio_path):
                await message.channel.send("Audio file was not created properly.")
                print(f"Worker: Audio file {audio_path} does not exist.")
                bot.queue.task_done()
                continue

            file_size = os.path.getsize(audio_path)
            print(f"Worker: Audio file size: {file_size} bytes")

            if file_size == 0:
                await message.channel.send("Audio file is empty.")
                print(f"Worker: Audio file {audio_path} is empty.")
                bot.queue.task_done()
                continue

            try:
                audio_src = discord.FFmpegPCMAudio(
                    audio_path,
                    options='-vn -ar 48000 -ac 2 -f s16le'
                )

                voice_client.stop()

                playback_complete = asyncio.Event()
                playback_error = None

                def after_playback(error):
                    nonlocal playback_error
                    if error:
                        playback_error = error
                        print(f"Worker: Playback error in callback: {error}")
                    playback_complete.set()

                voice_client.play(audio_src, after=after_playback)
                print("Worker: Playback started, waiting for completion...")

                try:
                    await asyncio.wait_for(playback_complete.wait(), timeout=60)
                    if playback_error:
                        print(f"Worker: Playback completed with error: {playback_error}")
                    else:
                        print("Worker: Playback completed successfully.")
                except asyncio.TimeoutError:
                    print("Worker: Playback timeout, stopping audio")
                    voice_client.stop()

                if not voice_client.is_connected():
                    print("Worker: Voice connection lost during/after playback")

            except Exception as audio_error:
                print(f"Worker: Audio source creation failed: {audio_error}")
                try:
                    audio_src = discord.FFmpegPCMAudio(audio_path)
                    voice_client.stop()

                    playback_complete = asyncio.Event()
                    playback_error = None

                    def after_playback_fallback(error):
                        nonlocal playback_error
                        if error:
                            playback_error = error
                            print(f"Worker: Fallback playback error: {error}")
                        playback_complete.set()

                    voice_client.play(audio_src, after=after_playback_fallback)

                    try:
                        await asyncio.wait_for(playback_complete.wait(), timeout=60)
                        print("Worker: Fallback playback completed.")
                    except asyncio.TimeoutError:
                        print("Worker: Fallback playback timeout")
                        voice_client.stop()

                except Exception as fallback_error:
                    print(f"Worker: Fallback audio playback also failed: {fallback_error}")
                    raise fallback_error

        except discord.opus.OpusNotLoaded as e:
            await message.channel.send("Audio codec error: Opus not loaded. Please install opus codec.")
            print(f"Worker: Opus codec error: {e}")
        except Exception as e:
            await message.channel.send(f"Playback error: {str(e)}")
            print(f"Worker: Playback error: {e}")
        finally:
            if os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    print(f"Worker: Deleted {audio_path}")
                except Exception as cleanup_error:
                    print(f"Worker: Error deleting file: {cleanup_error}")

        try:
            await message.delete()
            print(f"Worker: Deleted message {message.id}")
        except Exception as e:
            print(f"Worker: Could not delete message: {e}")

        bot.queue.task_done()
        print("Worker: Job done, waiting for next.")


# ---------------------------------------------------------------------------
# Inactivity monitor
# ---------------------------------------------------------------------------

async def inactivity_monitor(bot):
    while True:
        await asyncio.sleep(120)
        now = asyncio.get_event_loop().time()

        for vc in list(bot.voice_clients):
            try:
                guild_id = vc.guild.id

                if not vc.is_connected():
                    print(f"Monitor: Found disconnected voice client for {vc.guild.name}, cleaning up.")
                    try:
                        await asyncio.wait_for(vc.disconnect(force=True), timeout=5.0)
                    except Exception:
                        pass
                    continue

                humans = [m for m in vc.channel.members if not m.bot]
                print(f"Monitor: Members in VC {vc.channel.name} ({guild_id}): {[m.name for m in vc.channel.members]}")

                if not humans:
                    print(f"Monitor: Channel empty in {vc.guild.name}, disconnecting bot.")
                    try:
                        await asyncio.wait_for(vc.disconnect(force=True), timeout=5.0)
                    except Exception as disc_error:
                        print(f"Monitor: Error disconnecting from empty channel: {disc_error}")
                elif guild_id in last_activity and (now - last_activity[guild_id]) > TTS_TIMEOUT_SEC:
                    print(f"Monitor: Inactivity timeout in {vc.guild.name}, disconnecting bot.")
                    try:
                        await asyncio.wait_for(vc.disconnect(force=True), timeout=5.0)
                    except Exception as disc_error:
                        print(f"Monitor: Error disconnecting after inactivity: {disc_error}")

            except Exception as e:
                print(f"Monitor: Error checking voice client: {e}")
                try:
                    await asyncio.wait_for(vc.disconnect(force=True), timeout=5.0)
                except Exception as cleanup_error:
                    print(f"Monitor: Error during cleanup: {cleanup_error}")


# ---------------------------------------------------------------------------
# Discord events
# ---------------------------------------------------------------------------

@bot.event
async def on_disconnect():
    print("Bot disconnected from Discord")

@bot.event
async def on_resumed():
    print("Bot connection resumed")

@bot.event
async def on_connect():
    print("Bot connected to Discord")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id != bot.user.id:
        return
    if before.channel and not after.channel:
        print(f"VoiceState: Bot was disconnected from {before.channel.name}")
        guild_vc = discord.utils.get(bot.voice_clients, guild=before.channel.guild)
        if guild_vc:
            print(f"VoiceState: Cleaning up voice client for {before.channel.guild.name}")
            try:
                await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
            except Exception as e:
                print(f"VoiceState: Error during cleanup: {e}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Default TTS engine: {DEFAULT_TTS_ENGINE}")
    print("Available commands: !kokoro, !alltalk, !chatterbox, !voice, !cbvoice, !cbvoices, !leave, !help")

async def setup_hook():
    bot.queue = asyncio.Queue()
    bot.loop.create_task(tts_worker(bot))
    bot.loop.create_task(inactivity_monitor(bot))

bot.setup_hook = setup_hook

@bot.event
async def on_message(message):
    print(f"on_message: Received message in channel {message.channel.id} from {message.author}: '{message.content}'")

    if message.author.bot:
        return

    content = message.content.strip()
    content_lower = content.lower()

    # --- !leave ---
    if content_lower == '!leave':
        guild_vc = discord.utils.get(bot.voice_clients, guild=message.guild)
        if guild_vc and guild_vc.is_connected():
            await guild_vc.disconnect()
            await message.channel.send("Left the voice channel.")
        else:
            await message.channel.send("I'm not in a voice channel.")
        return

    # --- !kokoro ---
    if content_lower == '!kokoro':
        current_tts_engine[message.guild.id] = "kokoro"
        await message.channel.send("🎙️ Switched to **Kokoro TTS** (Local AI voice)")
        return

    # --- !alltalk ---
    if content_lower == '!alltalk':
        current_tts_engine[message.guild.id] = "alltalk"
        await message.channel.send("🗣️ Switched to **AllTalk TTS** (Local voice synthesis)")
        return

    # --- !chatterbox ---
    if content_lower == '!chatterbox':
        if not hasattr(config, 'CHATTERBOX_BASE_URL') or not config.CHATTERBOX_BASE_URL:
            await message.channel.send("❌ Chatterbox is not configured. Add `CHATTERBOX_BASE_URL` to config.py.")
            return
        current_tts_engine[message.guild.id] = "chatterbox"
        voice = current_chatterbox_voice.get(message.guild.id, getattr(config, 'CHATTERBOX_DEFAULT_VOICE', 'alloy'))
        await message.channel.send(f"🤖 Switched to **Chatterbox TTS** (current voice: `{voice}`)")
        return

    # --- !cbvoices — list available Chatterbox voices ---
    if content_lower == '!cbvoices':
        if not hasattr(config, 'CHATTERBOX_BASE_URL') or not config.CHATTERBOX_BASE_URL:
            await message.channel.send("❌ Chatterbox is not configured.")
            return
        voices = await fetch_chatterbox_voices()
        if voices is None:
            await message.channel.send("❌ Could not reach Chatterbox API.")
        elif not voices:
            await message.channel.send("No voices uploaded yet. Upload a voice sample to the Chatterbox API first.")
        else:
            names = ", ".join(f"`{v}`" for v in voices)
            await message.channel.send(f"🎤 Available Chatterbox voices: {names}")
        return

    # --- !cbvoice <name> — switch Chatterbox voice ---
    if content_lower.startswith('!cbvoice'):
        parts = content.split(None, 1)
        if len(parts) < 2:
            current_voice = current_chatterbox_voice.get(message.guild.id, getattr(config, 'CHATTERBOX_DEFAULT_VOICE', 'alloy'))
            await message.channel.send(f"Current Chatterbox voice: `{current_voice}`\nUsage: `!cbvoice <name>`")
            return
        voice_name = parts[1].strip()
        current_chatterbox_voice[message.guild.id] = voice_name
        await message.channel.send(f"🎤 Chatterbox voice set to `{voice_name}`")
        print(f"on_message: Chatterbox voice set to '{voice_name}' in guild {message.guild.id}")
        return

    # --- !voice — show current engine status ---
    if content_lower == '!voice':
        engine = current_tts_engine.get(message.guild.id, DEFAULT_TTS_ENGINE)
        engine_labels = {
            "kokoro": ("🎙️", "Kokoro TTS (Local AI)"),
            "alltalk": ("🗣️", "AllTalk TTS (Local synthesis)"),
            "chatterbox": ("🤖", "Chatterbox TTS (Local AI)"),
        }
        icon, name = engine_labels.get(engine, ("❓", engine))
        reply = f"{icon} Current engine: **{name}**"
        if engine == "chatterbox":
            voice = current_chatterbox_voice.get(message.guild.id, getattr(config, 'CHATTERBOX_DEFAULT_VOICE', 'alloy'))
            reply += f" | Voice: `{voice}`"
        reply += "\nUse `!kokoro`, `!alltalk`, or `!chatterbox` to switch."
        await message.channel.send(reply)
        return

    # --- !help ---
    if content_lower == '!help':
        help_text = """
🤖 **TTS Bot Commands:**

**Engines:**
• `!kokoro` - Switch to Kokoro TTS (Local AI voice)
• `!alltalk` - Switch to AllTalk TTS (Local synthesis)
• `!chatterbox` - Switch to Chatterbox TTS (Local AI, emotion-aware)
• `!voice` - Show current engine and voice

**Chatterbox voices:**
• `!cbvoices` - List available voices
• `!cbvoice <name>` - Switch to a named voice

**Other:**
• `!leave` - Make bot leave voice channel
• `!help` - Show this help message

💬 **How to use:** Just type any message in this channel and I'll speak it aloud!
🎭 **Chatterbox tip:** ALL CAPS and repeated letters (boooooo!) will sound more dramatic automatically.
        """
        await message.channel.send(help_text)
        return

    # Only process TTS in the configured channel
    if message.channel.id != config.TTS_CHANNEL_ID:
        return

    if bot.queue.qsize() > 50:
        await message.channel.send("TTS queue is full. Please try again in a moment.")
        return

    await bot.queue.put((message.author, message.content, message))
    print("on_message: Job queued.")

# Run the bot
bot.run(config.DISCORD_BOT_TOKEN)
