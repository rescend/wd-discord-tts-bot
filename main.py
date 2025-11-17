import discord
import requests
import asyncio
import json
import os
import wave
import aiohttp

import config  # This should contain your DISCORD_BOT_TOKEN, TTS_CHANNEL_ID, and KOKORO_BASE_URL

# Load Opus codec for voice support
try:
    # Try common Linux paths first (for Docker/server environments)
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
                # macOS Homebrew path (for local development)
                discord.opus.load_opus('/opt/homebrew/lib/libopus.dylib')
                print("Opus loaded successfully with macOS Homebrew path")
            except discord.opus.OpusNotLoaded:
                try:
                    discord.opus.load_opus('libopus')
                    print("Opus loaded successfully with 'libopus'")
                except discord.opus.OpusNotLoaded:
                    print("WARNING: Could not load Opus codec. Voice features may not work.")
                    print("Make sure libopus is installed in the container/system.")
                    # Don't exit - let the bot try to continue without Opus

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

# Create bot with better connection settings
bot = discord.Client(
    intents=intents,
    heartbeat_timeout=60.0,  # Increase heartbeat timeout
    guild_ready_timeout=10.0,  # Increase guild ready timeout
    max_messages=None  # Disable message cache to save memory
)

TTS_TIMEOUT_SEC = 60 * 60  # 1 hour

# TTS Engine selection - per guild
current_tts_engine = {}  # guild_id -> "kokoro" or "alltalk"
DEFAULT_TTS_ENGINE = "kokoro"  # Default to Kokoro

# The queue will be created in the setup_hook to ensure it's on the right event loop.
# We will attach it to the bot instance to avoid using globals.
# queue = asyncio.Queue() 
last_activity = {} # Per-guild cache of last activity time



async def generate_kokoro_tts(text, message):
    """Generate TTS using Kokoro-FastAPI (OpenAI-compatible endpoint)."""
    try:
        print("Worker: Using Kokoro TTS")
        if not hasattr(config, 'KOKORO_BASE_URL') or not config.KOKORO_BASE_URL:
            await message.channel.send("Kokoro TTS URL is not configured.")
            print("Worker: KOKORO_BASE_URL not found in config.")
            return None
        
        payload = {
            "model": "kokoro",
            "input": text,
            "voice": getattr(config, 'KOKORO_DEFAULT_VOICE', 'af_heart'),
            "response_format": getattr(config, 'KOKORO_RESPONSE_FORMAT', 'mp3'),
            "speed": getattr(config, 'KOKORO_SPEED', 1.0)
        }
        
        print(f"Worker: Sending TTS request to Kokoro for text: '{text}'")
        
        timeout = aiohttp.ClientTimeout(total=getattr(config, 'KOKORO_TTS_TIMEOUT_MS', 8000) / 1000)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{config.KOKORO_BASE_URL}/audio/speech",
                json=payload
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    await message.channel.send(f"Kokoro TTS error: {error_text[:100]}")
                    print(f"Worker: Kokoro error {resp.status}: {error_text}")
                    return None
                
                audio_data = await resp.read()
        
        # Save audio file
        file_ext = getattr(config, 'KOKORO_RESPONSE_FORMAT', 'mp3')
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
            bot.queue.task_done()
            continue

        # (Re)join user's channel if needed with proper retry logic
        voice_client = None
        max_retries = 3
        retry_count = 0
        connection_successful = False
        
        while retry_count < max_retries and not connection_successful:
            try:
                # Clean up stale voice clients more aggressively
                guild_vc = discord.utils.get(bot.voice_clients, guild=message.guild)

                if guild_vc:
                    # If we have a voice client, verify it's truly connected
                    if guild_vc.is_connected():
                        # Check if we need to move channels
                        if guild_vc.channel != vc.channel:
                            print(f"Worker: Moving to voice channel: {vc.channel}")
                            try:
                                await asyncio.wait_for(guild_vc.move_to(vc.channel), timeout=10.0)
                                voice_client = guild_vc
                                connection_successful = True
                            except asyncio.TimeoutError:
                                print("Worker: Move timeout, will disconnect and reconnect")
                                await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
                                await asyncio.sleep(2)
                                # Continue to reconnect below
                            except Exception as move_error:
                                print(f"Worker: Error moving channels: {move_error}")
                                await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
                                await asyncio.sleep(2)
                                # Continue to reconnect below
                        else:
                            print("Worker: Already in the correct voice channel.")
                            voice_client = guild_vc
                            connection_successful = True
                    
                    # If we still don't have a successful connection, clean up and reconnect
                    if not connection_successful:
                        print("Worker: Stale or failed VC, cleaning up before reconnect.")
                        try:
                            await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
                        except Exception as cleanup_error:
                            print(f"Worker: Error during cleanup: {cleanup_error}")
                        
                        # Wait for cleanup and resources to release
                        await asyncio.sleep(2)
                        guild_vc = None
                
                # Connect fresh if we don't have a connection
                if not connection_successful:
                    print(f"Worker: Connecting fresh to {vc.channel}")
                    # Use connect with proper parameters - timeout is separate from channel.connect()
                    guild_vc = await asyncio.wait_for(
                        vc.channel.connect(timeout=60.0, reconnect=True),
                        timeout=35.0  # Overall timeout slightly longer than the connection timeout
                    )
                    voice_client = guild_vc
                    connection_successful = True
                    print(f"Worker: Successfully connected to {vc.channel}")
                
            except asyncio.TimeoutError:
                retry_count += 1
                print(f"Worker: Voice connection timeout (attempt {retry_count}/{max_retries})")
                
                # Clean up any partial connections
                try:
                    guild_vc = discord.utils.get(bot.voice_clients, guild=message.guild)
                    if guild_vc:
                        await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
                except Exception as cleanup_err:
                    print(f"Worker: Cleanup error: {cleanup_err}")
                
                if retry_count < max_retries:
                    wait_time = 5 * retry_count  # Exponential backoff: 5s, 10s, 15s
                    print(f"Worker: Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    await message.channel.send("⚠️ Voice connection timed out. Discord servers may be slow. Please try again.")
                    print("Worker: Voice connection failed after all retries")
                    
            except discord.errors.ClientException as e:
                print(f"Worker: ClientException during connection: {e}")
                retry_count += 1
                
                # Clean up any existing connections
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
                print(f"Worker: ConnectionClosed during voice connection: Code={e.code}, Reason={e.reason}")
                retry_count += 1
                
                # Clean up
                try:
                    guild_vc = discord.utils.get(bot.voice_clients, guild=message.guild)
                    if guild_vc:
                        await asyncio.wait_for(guild_vc.disconnect(force=True), timeout=5.0)
                except Exception as cleanup_err:
                    print(f"Worker: Cleanup error: {cleanup_err}")
                
                if retry_count < max_retries:
                    # Longer wait for connection closed errors
                    wait_time = 10 * retry_count
                    print(f"Worker: Connection closed, waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    await message.channel.send("⚠️ Discord voice connection was closed unexpectedly. Please try again.")
                    print(f"Worker: ConnectionClosed after all retries: {e}")
                    
            except Exception as e:
                retry_count += 1
                print(f"Worker: Unexpected voice connection error (attempt {retry_count}/{max_retries}): {e}")
                print(f"Worker: Error type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                
                # Clean up any partial connections
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
        guild_id = message.guild.id
        engine = current_tts_engine.get(guild_id, DEFAULT_TTS_ENGINE)
        print(f"Worker: Using TTS engine: {engine}")
        
        wav_path = None
        if engine == "kokoro":
            wav_path = await generate_kokoro_tts(text, message)
            # Fallback to alltalk if kokoro fails
            if wav_path is None and hasattr(config, 'ALLTALK_TTS_URL'):
                print("Worker: Kokoro failed, falling back to AllTalk")
                wav_path = await generate_alltalk_tts(text, message)
        elif engine == "alltalk":
            wav_path = await generate_alltalk_tts(text, message)
        else:
            await message.channel.send(f"Unknown TTS engine: {engine}")
            print(f"Worker: Unknown TTS engine: {engine}")
            bot.queue.task_done()
            continue
            
        if wav_path is None:
            print("Worker: TTS generation failed, skipping playback")
            bot.queue.task_done()
            continue

        # Play audio in VC with connection verification
        try:
            print(f"Worker: Starting playback of {wav_path}")
            
            # Verify voice client is still connected before playback
            if not voice_client or not voice_client.is_connected():
                await message.channel.send("⚠️ Lost voice connection before playback. Please try again.")
                print("Worker: Voice client disconnected before playback")
                bot.queue.task_done()
                continue
            
            # Wait a moment to ensure connection is stable after connecting
            await asyncio.sleep(1.0)
            
            # Check if the file exists and has content
            if not os.path.exists(wav_path):
                await message.channel.send("Audio file was not created properly.")
                print(f"Worker: Audio file {wav_path} does not exist.")
                bot.queue.task_done()
                continue
                
            file_size = os.path.getsize(wav_path)
            print(f"Worker: Audio file size: {file_size} bytes")
            
            if file_size == 0:
                await message.channel.send("Audio file is empty.")
                print(f"Worker: Audio file {wav_path} is empty.")
                bot.queue.task_done()
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
                
                # Add a callback to track when playback ends
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

                # Wait for audio to finish with connection monitoring
                max_wait = 60  # Maximum wait time in seconds
                try:
                    await asyncio.wait_for(playback_complete.wait(), timeout=max_wait)
                    
                    if playback_error:
                        print(f"Worker: Playback completed with error: {playback_error}")
                    else:
                        print("Worker: Playback completed successfully.")
                        
                except asyncio.TimeoutError:
                    print("Worker: Playback timeout, stopping audio")
                    voice_client.stop()
                
                # Verify connection is still alive
                if not voice_client.is_connected():
                    print("Worker: Voice connection lost during/after playback")
                
            except Exception as audio_error:
                print(f"Worker: Audio source creation failed: {audio_error}")
                # Try fallback with basic options
                try:
                    audio_src = discord.FFmpegPCMAudio(wav_path)
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
                    
                    max_wait = 60
                    try:
                        await asyncio.wait_for(playback_complete.wait(), timeout=max_wait)
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
            print(f"Worker: Error type: {type(e).__name__}")
        finally:
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                    print(f"Worker: Deleted {wav_path}")
                except Exception as cleanup_error:
                    print(f"Worker: Error deleting file: {cleanup_error}")

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
        await asyncio.sleep(120)  # Check every 2 minutes
        now = asyncio.get_event_loop().time()
        
        # Make a copy of voice_clients list to avoid issues during iteration
        voice_clients = list(bot.voice_clients)
        
        for vc in voice_clients:
            try:
                guild_id = vc.guild.id
                
                # Check if the voice client is actually connected
                if not vc.is_connected():
                    print(f"Monitor: Found disconnected voice client for {vc.guild.name}, cleaning up.")
                    try:
                        await asyncio.wait_for(vc.disconnect(force=True), timeout=5.0)
                    except:
                        pass
                    continue
                
                # Check if channel is empty (except the bot)
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
                print(f"Monitor: Error type: {type(e).__name__}")
                # Try to disconnect the problematic voice client
                try:
                    await asyncio.wait_for(vc.disconnect(force=True), timeout=5.0)
                except Exception as cleanup_error:
                    print(f"Monitor: Error during cleanup: {cleanup_error}")

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
    """Handle voice state updates to detect when bot is disconnected."""
    # Only care about the bot's own voice state
    if member.id != bot.user.id:
        return
    
    # If bot was disconnected from a voice channel
    if before.channel and not after.channel:
        print(f"VoiceState: Bot was disconnected from {before.channel.name}")
        guild_id = before.channel.guild.id
        
        # Clean up any stale voice clients
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
    print("Available commands: !kokoro, !alltalk, !voice, !leave, !help")
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

    # Command to switch to Kokoro TTS
    if message.content.strip().lower() == '!kokoro':
        current_tts_engine[message.guild.id] = "kokoro"
        await message.channel.send("🎙️ Switched to **Kokoro TTS** (Local AI voice)")
        print(f"on_message: Switched to Kokoro TTS in guild {message.guild.id}")
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
        engine_name = "Kokoro TTS (Local AI)" if current_engine == "kokoro" else "AllTalk TTS (Local synthesis)"
        icon = "🎙️" if current_engine == "kokoro" else "🗣️"
        await message.channel.send(f"{icon} Current voice engine: **{engine_name}**\n"
                                 f"Use `!kokoro` or `!alltalk` to switch engines.")
        print(f"on_message: Current voice engine query in guild {message.guild.id}: {current_engine}")
        return

    # Help command
    if message.content.strip().lower() == '!help':
        help_text = """
🤖 **TTS Bot Commands:**
• `!kokoro` - Switch to Kokoro TTS (Local AI voice)
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
