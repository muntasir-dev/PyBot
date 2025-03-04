import os
import discord
from discord.ext import commands
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import asyncio
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Discord Bot Configuration
TOKEN = os.getenv('DISCORD_TOKEN')  # Your Discord bot token
GUILD_ID = os.getenv('GUILD_ID')    # Your Discord server ID
OWNER_ID = int(os.getenv('OWNER_ID'))  # Your Discord user ID

# Spotify Configuration
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')  # Usually http://localhost:8888/callback

# Initialize bot with command prefix "="
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='=', intents=intents)

# Spotify client setup
sp = None

# Voice client dictionary to keep track of connections
voice_clients = {}

# Current track information
current_track = {
    "title": None,
    "artist": None,
    "uri": None,
    "is_playing": False,
    "device_id": None
}

@bot.event
async def on_ready():
    """Event triggered when the bot is ready and connected to Discord."""
    global sp
    
    print(f'{bot.user} has connected to Discord!')
    print(f'Connected to the following guild: {bot.get_guild(int(GUILD_ID)).name}')
    
    # Initialize Spotify client with user authentication
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="user-read-playback-state,user-modify-playback-state,user-read-currently-playing"
        ))
        
        # Check if user is logged in and has active devices
        devices = sp.devices()
        if devices['devices']:
            print("Spotify connected! Available devices:")
            for device in devices['devices']:
                print(f"- {device['name']} ({device['id']})")
            
            # Set default device to the first active one
            for device in devices['devices']:
                if device['is_active']:
                    current_track['device_id'] = device['id']
                    print(f"Using active device: {device['name']}")
                    break
            
            # If no active device, use the first available
            if not current_track['device_id'] and devices['devices']:
                current_track['device_id'] = devices['devices'][0]['id']
                print(f"Using device: {devices['devices'][0]['name']}")
        else:
            print("No Spotify devices found. Please open Spotify on your device.")
    except Exception as e:
        print(f"Error connecting to Spotify: {e}")
        print("Please make sure your Spotify credentials are correct and you have authorized the application.")

@bot.command(name='play', aliases=['p'])
async def play(ctx, *, query=None):
    """Play a song from Spotify. Usage: =play <song name or Spotify URL>"""
    if not sp:
        await ctx.send("Spotify connection not established. Please check your credentials.")
        return
    
    if not query:
        # If no query is provided, resume playback if paused
        if current_track['uri'] and not current_track['is_playing']:
            try:
                sp.start_playback(device_id=current_track['device_id'])
                current_track['is_playing'] = True
                await ctx.send(f"▶️ Resumed playing: {current_track['title']} by {current_track['artist']}")
            except Exception as e:
                await ctx.send(f"Error resuming playback: {str(e)}")
        else:
            await ctx.send("Please provide a song name or Spotify URL. Usage: =play <song name or Spotify URL>")
        return
    
    # Check if the query is a Spotify URL
    if "spotify.com" in query:
        try:
            if "track" in query:
                track_uri = query
                track_info = sp.track(track_uri)
                track_name = track_info['name']
                artist_name = track_info['artists'][0]['name']
            elif "playlist" in query:
                await ctx.send(f"Loading playlist: {query}")
                sp.start_playback(device_id=current_track['device_id'], context_uri=query)
                current_track['is_playing'] = True
                await ctx.send("▶️ Playing playlist")
                return
            elif "album" in query:
                await ctx.send(f"Loading album: {query}")
                sp.start_playback(device_id=current_track['device_id'], context_uri=query)
                current_track['is_playing'] = True
                await ctx.send("▶️ Playing album")
                return
            else:
                await ctx.send("Unsupported Spotify URL. Please provide a track, playlist, or album URL.")
                return
        except Exception as e:
            await ctx.send(f"Error processing Spotify URL: {str(e)}")
            return
    else:
        # Search for the track
        await ctx.send(f"🔍 Searching for: {query}")
        try:
            results = sp.search(q=query, limit=1, type='track')
            if not results['tracks']['items']:
                await ctx.send(f"No results found for: {query}")
                return
            
            track = results['tracks']['items'][0]
            track_uri = track['uri']
            track_name = track['name']
            artist_name = track['artists'][0]['name']
        except Exception as e:
            await ctx.send(f"Error searching for track: {str(e)}")
            return
    
    # Play the track
    try:
        sp.start_playback(device_id=current_track['device_id'], uris=[track_uri])
        current_track['uri'] = track_uri
        current_track['title'] = track_name
        current_track['artist'] = artist_name
        current_track['is_playing'] = True
        
        await ctx.send(f"▶️ Now playing: {track_name} by {artist_name}")
    except Exception as e:
        await ctx.send(f"Error playing track: {str(e)}")

@bot.command(name='pause', aliases=['pa'])
async def pause(ctx):
    """Pause the currently playing song."""
    if not sp:
        await ctx.send("Spotify connection not established.")
        return
    
    try:
        if current_track['is_playing']:
            sp.pause_playback(device_id=current_track['device_id'])
            current_track['is_playing'] = False
            await ctx.send("⏸️ Playback paused")
        else:
            await ctx.send("Nothing is currently playing.")
    except Exception as e:
        await ctx.send(f"Error pausing playback: {str(e)}")

@bot.command(name='skip', aliases=['s'])
async def skip(ctx):
    """Skip to the next song."""
    if not sp:
        await ctx.send("Spotify connection not established.")
        return
    
    try:
        sp.next_track(device_id=current_track['device_id'])
        
        # Wait a moment for Spotify to update
        await asyncio.sleep(1)
        
        # Get the new current track
        current_playing = sp.current_playback()
        if current_playing and current_playing.get('item'):
            track = current_playing['item']
            current_track['uri'] = track['uri']
            current_track['title'] = track['name']
            current_track['artist'] = track['artists'][0]['name']
            current_track['is_playing'] = current_playing['is_playing']
            
            await ctx.send(f"⏭️ Skipped to: {current_track['title']} by {current_track['artist']}")
        else:
            await ctx.send("⏭️ Skipped to next track")
    except Exception as e:
        await ctx.send(f"Error skipping track: {str(e)}")

@bot.command(name='previous', aliases=['pr'])
async def previous(ctx):
    """Go back to the previous song."""
    if not sp:
        await ctx.send("Spotify connection not established.")
        return
    
    try:
        sp.previous_track(device_id=current_track['device_id'])
        
        # Wait a moment for Spotify to update
        await asyncio.sleep(1)
        
        # Get the new current track
        current_playing = sp.current_playback()
        if current_playing and current_playing.get('item'):
            track = current_playing['item']
            current_track['uri'] = track['uri']
            current_track['title'] = track['name']
            current_track['artist'] = track['artists'][0]['name']
            current_track['is_playing'] = current_playing['is_playing']
            
            await ctx.send(f"⏮️ Went back to: {current_track['title']} by {current_track['artist']}")
        else:
            await ctx.send("⏮️ Went back to previous track")
    except Exception as e:
        await ctx.send(f"Error going to previous track: {str(e)}")

@bot.command(name='forward', aliases=['fr'])
async def forward(ctx, seconds: int = 15):
    """Fast forward the current song by a specified number of seconds (default: 15)."""
    if not sp:
        await ctx.send("Spotify connection not established.")
        return
    
    try:
        # Get current playback position
        current_playback = sp.current_playback()
        if not current_playback:
            await ctx.send("Nothing is currently playing.")
            return
        
        current_position_ms = current_playback['progress_ms']
        new_position_ms = current_position_ms + (seconds * 1000)
        
        # Seek to the new position
        sp.seek_track(position_ms=new_position_ms, device_id=current_track['device_id'])
        await ctx.send(f"⏩ Forwarded {seconds} seconds")
    except Exception as e:
        await ctx.send(f"Error forwarding: {str(e)}")

@bot.command(name='help', aliases=['h'])
async def help_command(ctx, command=None):
    """Display help information for bot commands."""
    embed = discord.Embed(
        title="Spotify Discord Bot Help",
        description="Here are the available commands:",
        color=discord.Color.green()
    )
    
    commands_info = {
        "play (p)": "Play a song from Spotify. Usage: =play <song name or Spotify URL>",
        "pause (pa)": "Pause the currently playing song.",
        "skip (s)": "Skip to the next song.",
        "previous (pr)": "Go back to the previous song.",
        "forward (fr)": "Fast forward the current song by a specified number of seconds (default: 15).",
        "help (h)": "Display this help message."
    }
    
    if command:
        # Show help for a specific command
        command = command.lower()
        for cmd, desc in commands_info.items():
            if command in cmd:
                embed.add_field(name=f"={cmd}", value=desc, inline=False)
                break
        else:
            embed.add_field(name="Command not found", value=f"No help available for '{command}'", inline=False)
    else:
        # Show help for all commands
        for cmd, desc in commands_info.items():
            embed.add_field(name=f"={cmd}", value=desc, inline=False)
    
    embed.set_footer(text="Prefix: =")
    await ctx.send(embed=embed)

@bot.command(name='now', aliases=['np'])
async def now_playing(ctx):
    """Display information about the currently playing track."""
    if not sp:
        await ctx.send("Spotify connection not established.")
        return
    
    try:
        current_playback = sp.current_playback()
        if not current_playback or not current_playback.get('item'):
            await ctx.send("Nothing is currently playing.")
            return
        
        track = current_playback['item']
        track_name = track['name']
        artist_name = track['artists'][0]['name']
        album_name = track['album']['name']
        duration_ms = track['duration_ms']
        progress_ms = current_playback['progress_ms']
        
        # Convert milliseconds to minutes:seconds format
        duration_min = duration_ms // 60000
        duration_sec = (duration_ms % 60000) // 1000
        progress_min = progress_ms // 60000
        progress_sec = (progress_ms % 60000) // 1000
        
        # Create progress bar
        bar_length = 20
        progress_ratio = progress_ms / duration_ms
        filled_length = int(bar_length * progress_ratio)
        bar = '▓' * filled_length + '░' * (bar_length - filled_length)
        
        embed = discord.Embed(
            title="Now Playing",
            description=f"**{track_name}**\nby {artist_name}",
            color=discord.Color.green()
        )
        
        if track['album'].get('images') and len(track['album']['images']) > 0:
            embed.set_thumbnail(url=track['album']['images'][0]['url'])
        
        embed.add_field(
            name="Progress", 
            value=f"`{progress_min:02d}:{progress_sec:02d} {bar} {duration_min:02d}:{duration_sec:02d}`", 
            inline=False
        )
        embed.add_field(name="Album", value=album_name, inline=True)
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"Error getting current track info: {str(e)}")

# Run the bot
if __name__ == "__main__":
    bot.run(TOKEN)