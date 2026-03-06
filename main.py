# music_bot.py

import discord
from discord.ext import commands
import youtube_dl
import asyncio
from collections import deque
import os

# FFmpeg options for audio streaming
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# YouTube DL options
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'ignoreerrors': True,
}

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionary to store queues for each guild
queues = {}

class MusicPlayer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.queue = deque()
        self.current = None
        self.vc = None
        
    async def connect_voice(self):
        if not self.ctx.author.voice:
            await self.ctx.send("Madarchod pehle voice channel mein toh join kar!")
            return False
        
        channel = self.ctx.author.voice.channel
        if self.ctx.voice_client:
            self.vc = self.ctx.voice_client
            if self.vc.channel != channel:
                await self.vc.move_to(channel)
        else:
            self.vc = await channel.connect()
        return True
    
    async def play_next(self):
        if len(self.queue) > 0:
            self.current = self.queue.popleft()
            
            # Extract audio URL
            with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(self.current['url'], download=False)
                url2 = info['formats'][0]['url']
                
            source = discord.FFmpegPCMAudio(url2, **FFMPEG_OPTIONS)
            
            def after_playing(error):
                if error:
                    print(f"Error: {error}")
                asyncio.run_coroutine_threadsafe(self.play_next(), self.ctx.bot.loop)
            
            self.vc.play(source, after=after_playing)
            await self.ctx.send(f"**Ab baj raha hai:** {self.current['title']}")
        else:
            self.current = None
            await self.ctx.send("Queue khatam! Naya gana daal madarchod.")
    
    async def add_to_queue(self, url):
        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                if 'entries' in info:  # Playlist hai toh
                    for entry in info['entries']:
                        if entry:
                            self.queue.append({
                                'url': entry['webpage_url'],
                                'title': entry['title']
                            })
                    await self.ctx.send(f"**{len(info['entries'])}** gaane queue mein daal diye bhosdiwale!")
                else:  # Single video
                    self.queue.append({
                        'url': url,
                        'title': info['title']
                    })
                    await self.ctx.send(f"**{info['title']}** queue mein daal diya!")
            except Exception as e:
                await self.ctx.send(f"Kuch gadbad hui: {str(e)}")

@bot.event
async def on_ready():
    print(f'{bot.user} naam ka bot join ho gaya!')

@bot.command(name='play')
async def play(ctx, *, url):
    """!play <youtube_url> - Gana bajao"""
    
    if not url.startswith(('http://', 'https://')):
        await ctx.send("Behenchod sahi URL daal! YouTube ka link daal.")
        return
    
    # Get or create player for this guild
    if ctx.guild.id not in queues:
        queues[ctx.guild.id] = MusicPlayer(ctx)
    
    player = queues[ctx.guild.id]
    
    # Connect to voice
    if not await player.connect_voice():
        return
    
    # Add to queue
    await player.add_to_queue(url)
    
    # Start playing if not already
    if not player.vc.is_playing():
        await player.play_next()

@bot.command(name='skip')
async def skip(ctx):
    """!skip - Current gana skip kar"""
    
    if ctx.guild.id in queues:
        player = queues[ctx.guild.id]
        if player.vc and player.vc.is_playing():
            player.vc.stop()
            await ctx.send("Gana skip kiya! Agla laa raha hoon...")
        else:
            await ctx.send("Kuch nahi baj raha behenchod!")
    else:
        await ctx.send("Pehle gana toh daal!")

@bot.command(name='queue')
async def show_queue(ctx):
    """!queue - Queue dikhao"""
    
    if ctx.guild.id in queues:
        player = queues[ctx.guild.id]
        if len(player.queue) > 0:
            queue_list = "\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(list(player.queue)[:10])])
            await ctx.send(f"**Current Queue:**\n{queue_list}")
            if len(player.queue) > 10:
                await ctx.send(f"Aur {len(player.queue)-10} gaane baaki hain.")
        else:
            await ctx.send("Queue khaali hai, naye gaane daal!")
    else:
        await ctx.send("Queue khaali hai!")

@bot.command(name='stop')
async def stop(ctx):
    """!stop - Gana band kar aur leave kar"""
    
    if ctx.guild.id in queues:
        player = queues[ctx.guild.id]
        if player.vc:
            player.queue.clear()
            if player.vc.is_playing():
                player.vc.stop()
            await player.vc.disconnect()
            del queues[ctx.guild.id]
            await ctx.send("Bot ne leave kar diya! Phir aana...")
        else:
            await ctx.send("Main toh voice channel mein hoon hi nahi!")

@bot.command(name='pause')
async def pause(ctx):
    """!pause - Gana temporarily rok"""
    
    if ctx.guild.id in queues:
        player = queues[ctx.guild.id]
        if player.vc and player.vc.is_playing():
            player.vc.pause()
            await ctx.send("Gana pause kar diya! !resume se chala lena.")

@bot.command(name='resume')
async def resume(ctx):
    """!resume - Paused gana chala"""
    
    if ctx.guild.id in queues:
        player = queues[ctx.guild.id]
        if player.vc and player.vc.is_paused():
            player.vc.resume()
            await ctx.send("Gana chala diya!")

@bot.command(name='nowplaying')
async def nowplaying(ctx):
    """!nowplaying - Current gana dikhao"""
    
    if ctx.guild.id in queues:
        player = queues[ctx.guild.id]
        if player.current:
            await ctx.send(f"**Ab baj raha hai:** {player.current['title']}")
        else:
            await ctx.send("Kuch nahi baj raha!")
    else:
        await ctx.send("Kuch nahi baj raha!")

# Bot token daal apna
bot.run('MTQyMjkwOTgxMjExMDUyNDQ0Ng.GxUDVh.P5PHLSe1UX2TgNpSDt_uXzK54RVteT8GJYntgI')
