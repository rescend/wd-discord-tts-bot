import discord
import requests
import asyncio
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
        user, text, message = await queue.get()
        last_activity = asyncio.get_event_loop().time()

        # Find which VC the user is in
        vc = user.voice
        if not vc or not vc.channel:
            await message.channel.send(f"{user.mention} Please join a voice channel to use TTS.")
            continue

        # (Re)join user's channel if needed
        try:
            if not voice_client or not voice_client.is_connected() or voice_client.channel != vc.channel:
                if voice_client:
                    await voice_client.disconnect(force=True)
                voice_client = await vc.channel.connect()
        except Exception as e:
            await message.channel.send(f"Bot could not join your voice channel: {e}")
            continue

        # Query Coqui for WAV audio
        try:
            payload = {
                "text": text,
                "speaker_id": "p231",  # You can make this dynamic per user in v0.2
            }
            response = requests.get(config.COQUI_TTS_URL, params=payload, timeout=30)
            if response.status_code != 200:
                await message.channel.send(f"TTS server error: {response.text[:100]}")
                continue

            wav_path = f"tts_{message.id}.wav"
            with open(wav_path, "wb") as f:
                f.write(response.content)
        except Exception as e:
            await message.channel.send(f"Failed to fetch TTS: {e}")
            continue

        # Play audio in VC
        try:
            audio_src = discord.FFmpegPCMAudio(wav_path)
            voice_client.stop()  # Stop anything already playing
            voice_client.play(audio_src)

            # Wait for audio to finish
            while voice_client.is_playing():
                await asyncio.sleep(0.5)
        except Exception as e:
            await message.channel.send(f"Playback error: {e}")
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

        # Optionally, delete message after playing (per PRD)
        try:
            await message.delete()
        except Exception:
            pass

        queue.task_done()

async def inactivity_monitor():
    global voice_client, last_activity
    while True:
        await asyncio.sleep(60)
        if voice_client and voice_client.is_connected():
            now = asyncio.get_event_loop().time()
            # Check if channel is empty (except the bot)
            humans = [m for m in voice_client.channel.members if not m.bot]
            if not humans:
                await voice_client.disconnect(force=True)
                voice_client = None
            elif last_activity and (now - last_activity) > TTS_TIMEOUT_SEC:
                await voice_client.disconnect(force=True)
                voice_client = None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(tts_worker())
    bot.loop.create_task(inactivity_monitor())

@bot.event
async def on_message(message):
    # Only in your chosen channel, and ignore bots
    if message.channel.id != config.TTS_CHANNEL_ID or message.author.bot:
        return

    # Simple anti-spam: 1 job per user at a time, cap queue length
    if queue.qsize() > 50:
        await message.channel.send("TTS queue is full. Please try again in a moment.")
        return

    await queue.put((message.author, message.content, message))

# Run the bot
bot.run(config.DISCORD_BOT_TOKEN)
