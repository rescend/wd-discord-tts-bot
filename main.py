import discord
import requests
import asyncio
import json
import os

import config  # This should contain your DISCORD_BOT_TOKEN, TTS_CHANNEL_ID, and COQUI_TTS_URL

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = discord.Client(intents=intents)

TTS_TIMEOUT_SEC = 60 * 60  # 1 hour

queue = asyncio.Queue()
last_activity = None
voice_client = None

async def tts_worker():
    global voice_client, last_activity
    while True:
        print("Worker: waiting for next TTS job...")
        user, text, message = await queue.get()
        print(f"Worker: Got message from {user} ({user.id}) in channel {message.channel.id}: '{text}'")
        last_activity = asyncio.get_event_loop().time()

        # Find which VC the user is in
        vc = getattr(user, "voice", None)
        print(f"Worker: User.voice = {vc}")
        if not vc or not vc.channel:
            await message.channel.send(f"{user.mention} Please join a voice channel to use TTS.")
            print("Worker: User not in voice channel, skipping job.")
            continue

        # (Re)join user's channel if needed
        try:
            if not voice_client or not voice_client.is_connected() or voice_client.channel != vc.channel:
                print(f"Worker: Connecting to voice channel: {vc.channel}")
                if voice_client:
                    await voice_client.disconnect(force=True)
                voice_client = await vc.channel.connect()
        except Exception as e:
            await message.channel.send(f"Bot could not join your voice channel: {e}")
            print(f"Worker: Failed to join VC: {e}")
            continue

        # Query AllTalk TTS for WAV audio
        try:
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
            print(f"Worker: Sending TTS request to AllTalk with payload: {payload}")
            resp = requests.post(config.ALLTALK_TTS_URL, data=payload, timeout=30)
            print(f"Worker: AllTalk response status: {resp.status_code}")
            if resp.status_code != 200:
                await message.channel.send(f"TTS server error: {resp.text[:100]}")
                print(f"Worker: TTS server error: {resp.text}")
                continue

    # 2. Parse the JSON for the output_file_url
            result = resp.json()
            wav_url = f"http://10.69.69.28:7851{result['output_file_url']}"
            print(f"Worker: Downloading generated audio from {wav_url}")

    # 3. Download the actual WAV
            wav_resp = requests.get(wav_url)
            wav_path = f"tts_{message.id}.wav"
            with open(wav_path, "wb") as f:
                f.write(wav_resp.content)
            print(f"Worker: Audio saved to {wav_path}")
        except Exception as e:
         await message.channel.send(f"Failed to fetch TTS: {e}")
         print(f"Worker: Exception during TTS fetch: {e}")
         continue

        # Play audio in VC
        try:
            print(f"Worker: Starting playback of {wav_path}")
            audio_src = discord.FFmpegPCMAudio(wav_path)
            voice_client.stop()  # Stop anything already playing
            voice_client.play(audio_src)

            # Wait for audio to finish
            while voice_client.is_playing():
                await asyncio.sleep(0.5)
            print("Worker: Finished playback.")
        except Exception as e:
            await message.channel.send(f"Playback error: {e}")
            print(f"Worker: Playback error: {e}")
        finally:
            pass
            if os.path.exists(wav_path):
                os.remove(wav_path)
                print(f"Worker: Deleted {wav_path}")

        # Optionally, delete message after playing (per PRD)
        try:
            await message.delete()
            print(f"Worker: Deleted message {message.id}")
        except Exception as e:
            print(f"Worker: Could not delete message: {e}")

        queue.task_done()
        print("Worker: Job done, waiting for next.")

async def inactivity_monitor():
    global voice_client, last_activity
    while True:
        await asyncio.sleep(60)
        if voice_client and voice_client.is_connected():
            now = asyncio.get_event_loop().time()
            # Check if channel is empty (except the bot)
            humans = [m for m in voice_client.channel.members if not m.bot]
            print(f"Monitor: Members in VC: {[m.name for m in voice_client.channel.members]}")
            if not humans:
                print("Monitor: Channel empty, disconnecting bot.")
                await voice_client.disconnect(force=True)
                voice_client = None
            elif last_activity and (now - last_activity) > TTS_TIMEOUT_SEC:
                print("Monitor: Inactivity timeout reached, disconnecting bot.")
                await voice_client.disconnect(force=True)
                voice_client = None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(tts_worker())
    bot.loop.create_task(inactivity_monitor())

@bot.event
async def on_message(message):
    print(f"on_message: Received message in channel {message.channel.id} from {message.author}: '{message.content}'")

    # Only in your chosen channel, and ignore bots
    if message.channel.id != config.TTS_CHANNEL_ID:
        print("on_message: Not the TTS channel, ignoring.")
        return
    if message.author.bot:
        print("on_message: Message from bot, ignoring.")
        return

    # Simple anti-spam: 1 job per user at a time, cap queue length
    if queue.qsize() > 50:
        await message.channel.send("TTS queue is full. Please try again in a moment.")
        print("on_message: Queue full.")
        return

    await queue.put((message.author, message.content, message))
    print("on_message: Job queued.")

# Run the bot
bot.run(config.DISCORD_BOT_TOKEN)
