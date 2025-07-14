import discord
import requests
import asyncio
import json
import os
import wave
from google import genai
from google.genai import types

import config  # This should contain your DISCORD_BOT_TOKEN, TTS_CHANNEL_ID, and COQUI_TTS_URL

# Load Opus codec for voice support
try:
    discord.opus.load_opus('/opt/homebrew/lib/libopus.dylib')
    print("Opus loaded successfully with full path")
except discord.opus.OpusNotLoaded:
    try:
        discord.opus.load_opus('libopus')
        print("Opus loaded successfully with 'libopus'")
    except discord.opus.OpusNotLoaded:
        try:
            discord.opus.load_opus('opus')
            print("Opus loaded successfully with 'opus'")
        except discord.opus.OpusNotLoaded:
            print("WARNING: Could not load Opus codec. Voice features may not work.")
            print("Available Opus libraries:")
            import subprocess
            try:
                result = subprocess.run(['find', '/opt/homebrew', '-name', '*opus*'], 
                                      capture_output=True, text=True)
                print(result.stdout)
            except:
                pass

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

# Create bot with better connection settings
bot = discord.Client(
    intents=intents,
    heartbeat_timeout=60.0,  # Increase heartbeat timeout
    guild_ready_timeout=10.0  # Increase guild ready timeout
)

TTS_TIMEOUT_SEC = 60 * 60  # 1 hour

# TTS Engine selection - per guild
current_tts_engine = {}  # guild_id -> "gemini" or "alltalk"
DEFAULT_TTS_ENGINE = "gemini"  # Default to Gemini

# The queue will be created in the setup_hook to ensure it's on the right event loop.
# We will attach it to the bot instance to avoid using globals.
# queue = asyncio.Queue() 
last_activity = {} # Per-guild cache of last activity time

def save_pcm_as_wav(pcm_data, filename, channels=1, sample_rate=24000, sample_width=2):
    """Convert raw PCM data to WAV format and save to file."""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)

def validate_wav_file(filepath):
    """Validate WAV file and return its properties."""
    try:
        with wave.open(filepath, 'rb') as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            frames = wf.getnframes()
            duration = frames / framerate
            
            print(f"WAV file validation - Channels: {channels}, Sample width: {sample_width}, "
                  f"Frame rate: {framerate}, Frames: {frames}, Duration: {duration:.2f}s")
            return True, {
                'channels': channels,
                'sample_width': sample_width,
                'framerate': framerate,
                'frames': frames,
                'duration': duration
            }
    except Exception as e:
        print(f"WAV file validation failed: {e}")
        return False, str(e)

async def generate_gemini_tts(text, message):
    """Generate TTS using Gemini API."""
    try:
        print("Worker: Using Gemini TTS")
        if not hasattr(config, 'GEMINI_API_KEY') or not config.GEMINI_API_KEY:
            await message.channel.send("Gemini API key is not configured.")
            print("Worker: GEMINI_API_KEY not found in config.")
            return None
        
        # Initialize the Gemini client
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        
        print(f"Worker: Sending TTS request to Gemini for text: '{text}'")
        
        # Define a style prompt to control the speech output
        style_prompt = "Speak in a warm, mature, and reassuring tone—like a gentle big sister or caring mentor. Your voice should sound confident, calm, and inviting, depending on context it can be very slightly flirty. Speak at a normal, conversational pace.: "
        full_text = f"{style_prompt}{text}"

        # Generate the audio using the correct API structure
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=full_text,
            config={
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": "Gacrux"
                        }
                    }
                }
            }
        )

        # Extract the audio data from the response
        audio_data = response.candidates[0].content.parts[0].inline_data.data

        # Save the audio file as proper WAV format
        wav_path = f"tts_{message.id}.wav"
        save_pcm_as_wav(audio_data, wav_path)
        print(f"Worker: Gemini audio saved to {wav_path}")
        
        # Validate the WAV file
        is_valid, wav_info = validate_wav_file(wav_path)
        if not is_valid:
            await message.channel.send(f"Generated audio file is invalid: {wav_info}")
            print(f"Worker: WAV validation failed: {wav_info}")
            return None
            
        return wav_path

    except Exception as e:
        await message.channel.send(f"Failed to fetch TTS from Gemini: {e}")
        print(f"Worker: Exception during Gemini TTS fetch: {e}")
        return None

async def generate_alltalk_tts(text, message):
    """Generate TTS using AllTalk API."""
    try:
        print("Worker: Using AllTalk TTS")
        if not hasattr(config, 'ALLTALK_TTS_URL') or not config.ALLTALK_TTS_URL:
            await message.channel.send("AllTalk TTS URL is not configured.")
            print("Worker: ALLTALK_TTS_URL not found in config.")
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
        
        print(f"Worker: Sending TTS request to AllTalk with payload: {payload}")
        resp = requests.post(config.ALLTALK_TTS_URL, data=payload, timeout=30)
        print(f"Worker: AllTalk response status: {resp.status_code}")
        
        if resp.status_code != 200:
            await message.channel.send(f"TTS server error: {resp.text[:100]}")
            print(f"Worker: TTS server error: {resp.text}")
            return None

        # Parse the JSON for the output_file_url
        result = resp.json()
        wav_url = f"{config.ALLTALK_API_URL}{result['output_file_url']}"
        print(f"Worker: Downloading generated audio from {wav_url}")

        # Download the actual WAV
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
            continue

        # (Re)join user's channel if needed with retry logic
        voice_client = None
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Clean up stale voice clients
                guild_vc = discord.utils.get(bot.voice_clients, guild=message.guild)

                if guild_vc:
                    if guild_vc.is_connected():
                        if guild_vc.channel != vc.channel:
                            print(f"Worker: Moving to voice channel: {vc.channel}")
                            await guild_vc.move_to(vc.channel)
                        else:
                            print("Worker: Already in the correct voice channel.")
                    else:
                        print("Worker: Stale VC found, disconnecting.")
                        try:
                            await guild_vc.disconnect(force=True)
                        except:
                            pass  # Ignore disconnect errors
                        print(f"Worker: Connecting fresh to {vc.channel}")
                        guild_vc = await asyncio.wait_for(vc.channel.connect(), timeout=30.0)
                else:
                    print(f"Worker: Connecting to voice channel: {vc.channel}")
                    guild_vc = await asyncio.wait_for(vc.channel.connect(), timeout=30.0)

                voice_client = guild_vc
                break  # Success, exit retry loop
                
            except asyncio.TimeoutError:
                retry_count += 1
                print(f"Worker: Voice connection timeout (attempt {retry_count}/{max_retries})")
                if retry_count < max_retries:
                    await asyncio.sleep(2)  # Wait before retry
                else:
                    await message.channel.send("Voice connection timed out. Please try again.")
                    print("Worker: Voice connection failed after all retries")
                    continue
            except Exception as e:
                retry_count += 1
                print(f"Worker: Voice connection error (attempt {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(2)  # Wait before retry
                else:
                    await message.channel.send(f"Bot could not join your voice channel: {e}")
                    print(f"Worker: Failed to join VC after all retries: {e}")
                    continue

        # Generate TTS audio using the selected engine
        guild_id = message.guild.id
        engine = current_tts_engine.get(guild_id, DEFAULT_TTS_ENGINE)
        print(f"Worker: Using TTS engine: {engine}")
        
        if engine == "gemini":
            wav_path = await generate_gemini_tts(text, message)
        elif engine == "alltalk":
            wav_path = await generate_alltalk_tts(text, message)
        else:
            await message.channel.send(f"Unknown TTS engine: {engine}")
            print(f"Worker: Unknown TTS engine: {engine}")
            continue
            
        if wav_path is None:
            print("Worker: TTS generation failed, skipping playback")
            continue

        # Play audio in VC with connection verification
        try:
            print(f"Worker: Starting playback of {wav_path}")
            
            # Verify voice client is still connected before playback
            if not voice_client or not voice_client.is_connected():
                await message.channel.send("Lost voice connection. Please try again.")
                print("Worker: Voice client disconnected before playback")
                continue
            
            # Check if the file exists and has content
            if not os.path.exists(wav_path):
                await message.channel.send("Audio file was not created properly.")
                print(f"Worker: Audio file {wav_path} does not exist.")
                continue
                
            file_size = os.path.getsize(wav_path)
            print(f"Worker: Audio file size: {file_size} bytes")
            
            if file_size == 0:
                await message.channel.send("Audio file is empty.")
                print(f"Worker: Audio file {wav_path} is empty.")
                continue
            
            # Create audio source with explicit options for better compatibility
            # First try with explicit WAV format options
            try:
                # Use more explicit FFmpeg options for WAV playback
                audio_src = discord.FFmpegPCMAudio(
                    wav_path,
                    before_options='-f wav',
                    options='-vn -ar 48000 -ac 2 -f s16le'  # Convert to Discord's expected format
                )
                
                voice_client.stop()  # Stop anything already playing
                voice_client.play(audio_src)

                # Wait for audio to finish with connection monitoring
                max_wait = 60  # Maximum wait time in seconds
                wait_time = 0
                while voice_client.is_playing() and voice_client.is_connected() and wait_time < max_wait:
                    await asyncio.sleep(0.5)
                    wait_time += 0.5
                    
                if wait_time >= max_wait:
                    print("Worker: Playback timeout, stopping audio")
                    voice_client.stop()
                elif not voice_client.is_connected():
                    print("Worker: Voice connection lost during playback")
                else:
                    print("Worker: Finished playback.")
                
            except Exception as audio_error:
                print(f"Worker: Audio source creation failed: {audio_error}")
                # Try fallback with basic options
                try:
                    audio_src = discord.FFmpegPCMAudio(wav_path)
                    voice_client.stop()
                    voice_client.play(audio_src)
                    
                    # Wait for audio to finish with connection monitoring
                    max_wait = 60
                    wait_time = 0
                    while voice_client.is_playing() and voice_client.is_connected() and wait_time < max_wait:
                        await asyncio.sleep(0.5)
                        wait_time += 0.5
                    print("Worker: Finished playback (fallback).")
                    
                except Exception as fallback_error:
                    print(f"Worker: Fallback audio playback also failed: {fallback_error}")
                    raise fallback_error
            
        except discord.opus.OpusNotLoaded as e:
            await message.channel.send("Audio codec error: Opus not loaded. Please install opus codec.")
            print(f"Worker: Opus codec error: {e}")
        except Exception as e:
            await message.channel.send(f"Playback error: {str(e)}")
            print(f"Worker: Playback error: {e}")
            print(f"Worker: Error type: {type(e).__name__}")
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)
                print(f"Worker: Deleted {wav_path}")

        # Optionally, delete message after playing (per PRD)
        try:
            await message.delete()
            print(f"Worker: Deleted message {message.id}")
        except Exception as e:
            print(f"Worker: Could not delete message: {e}")

        bot.queue.task_done()
        print("Worker: Job done, waiting for next.")

async def inactivity_monitor(bot):
    while True:
        await asyncio.sleep(120)  # Increased from 60 to 120 seconds to reduce API calls
        now = asyncio.get_event_loop().time()
        
        # Make a copy of voice_clients list to avoid issues during iteration
        voice_clients = list(bot.voice_clients)
        
        for vc in voice_clients:
            try:
                guild_id = vc.guild.id
                # Check if channel is empty (except the bot)
                humans = [m for m in vc.channel.members if not m.bot]
                print(f"Monitor: Members in VC {vc.channel.name} ({guild_id}): {[m.name for m in vc.channel.members]}")
                
                if not humans:
                    print(f"Monitor: Channel empty in {vc.guild.name}, disconnecting bot.")
                    await vc.disconnect(force=True)
                elif guild_id in last_activity and (now - last_activity[guild_id]) > TTS_TIMEOUT_SEC:
                    print(f"Monitor: Inactivity timeout in {vc.guild.name}, disconnecting bot.")
                    await vc.disconnect(force=True)
            except Exception as e:
                print(f"Monitor: Error checking voice client: {e}")
                # Try to disconnect the problematic voice client
                try:
                    await vc.disconnect(force=True)
                except:
                    pass

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
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Default TTS engine: {DEFAULT_TTS_ENGINE}")
    print("Available commands: !gemini, !alltalk, !voice, !leave, !help")
    # Background tasks are now started in setup_hook
    # bot.loop.create_task(tts_worker())
    # bot.loop.create_task(inactivity_monitor())

async def setup_hook():
    # This is the recommended place for async setup logic.
    # It ensures that it runs on the same loop as the bot.
    bot.queue = asyncio.Queue()
    bot.loop.create_task(tts_worker(bot))
    bot.loop.create_task(inactivity_monitor(bot))

bot.setup_hook = setup_hook

@bot.event
async def on_message(message):
    print(f"on_message: Received message in channel {message.channel.id} from {message.author}: '{message.content}'")

    # Ignore bots
    if message.author.bot:
        print("on_message: Message from bot, ignoring.")
        return

    # Command to leave the voice channel
    if message.content.strip().lower() == '!leave':
        guild_vc = discord.utils.get(bot.voice_clients, guild=message.guild)
        if guild_vc and guild_vc.is_connected():
            print(f"on_message: Received !leave command, disconnecting from {guild_vc.channel.name}")
            await guild_vc.disconnect()
            await message.channel.send("Left the voice channel.")
        else:
            print("on_message: Received !leave command, but not in a voice channel.")
            await message.channel.send("I'm not in a voice channel.")
        return

    # Command to switch to Gemini TTS
    if message.content.strip().lower() == '!gemini':
        current_tts_engine[message.guild.id] = "gemini"
        await message.channel.send("🔮 Switched to **Gemini TTS** (AI-powered voice)")
        print(f"on_message: Switched to Gemini TTS in guild {message.guild.id}")
        return

    # Command to switch to AllTalk TTS
    if message.content.strip().lower() == '!alltalk':
        current_tts_engine[message.guild.id] = "alltalk"
        await message.channel.send("🗣️ Switched to **AllTalk TTS** (Local voice synthesis)")
        print(f"on_message: Switched to AllTalk TTS in guild {message.guild.id}")
        return

    # Command to check current voice engine
    if message.content.strip().lower() == '!voice':
        current_engine = current_tts_engine.get(message.guild.id, DEFAULT_TTS_ENGINE)
        engine_name = "Gemini TTS (AI-powered)" if current_engine == "gemini" else "AllTalk TTS (Local synthesis)"
        icon = "🔮" if current_engine == "gemini" else "🗣️"
        await message.channel.send(f"{icon} Current voice engine: **{engine_name}**\n"
                                 f"Use `!gemini` or `!alltalk` to switch engines.")
        print(f"on_message: Current voice engine query in guild {message.guild.id}: {current_engine}")
        return

    # Help command
    if message.content.strip().lower() == '!help':
        help_text = """
🤖 **TTS Bot Commands:**
• `!gemini` - Switch to Gemini TTS (AI-powered voice)
• `!alltalk` - Switch to AllTalk TTS (Local synthesis)
• `!voice` - Check current voice engine
• `!leave` - Make bot leave voice channel
• `!help` - Show this help message

💬 **How to use:** Just type any message in this channel and I'll speak it aloud!
        """
        await message.channel.send(help_text)
        print(f"on_message: Help command in guild {message.guild.id}")
        return

    # Only in your chosen channel, and ignore bots
    if message.channel.id != config.TTS_CHANNEL_ID:
        print("on_message: Not the TTS channel, ignoring.")
        return
    if message.author.bot:
        print("on_message: Message from bot, ignoring.")
        return

    # Simple anti-spam: 1 job per user at a time, cap queue length
    if bot.queue.qsize() > 50:
        await message.channel.send("TTS queue is full. Please try again in a moment.")
        print("on_message: Queue full.")
        return

    await bot.queue.put((message.author, message.content, message))
    print("on_message: Job queued.")

# Run the bot
bot.run(config.DISCORD_BOT_TOKEN)
