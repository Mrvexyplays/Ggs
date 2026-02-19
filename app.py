import os
import subprocess
import time
import threading
from datetime import datetime
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.text import Text
import yt_dlp

# ===== CONFIGURATION =====
class Config:
    STREAM_KEY = "dmgc-g5vj-bpa2-6g5m-exwx"
    VIDEO_DIR = "/home/container/videos"
    PLAYLIST_FILE = "/home/container/playlist.txt"
    YOUTUBE_URL = "rtmp://a.rtmp.youtube.com/live2/"

os.makedirs(Config.VIDEO_DIR, exist_ok=True)
console = Console()
logs = ["System Started..."]
current_download_pct = "0%"
download_active = False

def add_log(msg):
    global logs
    timestamp = datetime.now().strftime("%H:%M:%S")
    logs.append(f"[{timestamp}] {msg}")
    if len(logs) > 10: logs.pop(0)

def progress_hook(d):
    global current_download_pct
    if d['status'] == 'downloading':
        current_download_pct = d.get('_percent_str', '0%')
    elif d['status'] == 'finished':
        current_download_pct = "100%"

# ===== DOWNLOADER (FIXED FOR ERROR VOP) =====
def download_worker(url):
    global download_active, current_download_pct
    download_active = True
    try:
        add_log("Bypassing YouTube restrictions...")
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': f'{Config.VIDEO_DIR}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [progress_hook],
            # --- BYPASS SETTINGS ---
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            # -----------------------
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        add_log("Download Success!")
        update_playlist()
    except Exception as e:
        add_log(f"Error: Bypass Failed ({str(e)[:15]})")
    
    download_active = False
    current_download_pct = "0%"

def update_playlist():
    files = sorted([f for f in os.listdir(Config.VIDEO_DIR) if f.lower().endswith('.mp4')])
    with open(Config.PLAYLIST_FILE, "w") as f:
        for file in files:
            f.write(f"file '{os.path.join(Config.VIDEO_DIR, file)}'\n")

class StreamBot:
    def __init__(self):
        self.process = None
        self.start_time = "OFFLINE"

    def start(self):
        update_playlist()
        cmd = [
            "ffmpeg", "-re", "-stream_loop", "-1", "-f", "concat", "-safe", "0",
            "-i", Config.PLAYLIST_FILE, "-c:v", "copy", "-c:a", "aac", "-f", "flv",
            f"{Config.YOUTUBE_URL}{Config.STREAM_KEY}"
        ]
        self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        self.start_time = datetime.now().strftime("%H:%M:%S")

bot = StreamBot()

# ===== UI SETUP =====
def make_layout():
    layout = Layout()
    layout.split_column(Layout(name="top", ratio=3), Layout(name="bottom", ratio=1))
    layout["top"].split_row(Layout(name="stats", ratio=1), Layout(name="logs", ratio=2))
    return layout

def refresh_ui(layout):
    stats = Table.grid(padding=1)
    stats.add_row("Status:", "[bold red]LIVE 🔴[/]")
    stats.add_row("Uptime:", bot.start_time)
    stats.add_row("Videos:", str(len(os.listdir(Config.VIDEO_DIR))))
    stats.add_row("Progress:", f"[bold yellow]{current_download_pct}[/]")
    layout["stats"].update(Panel(stats, title="Stats", border_style="cyan"))
    layout["logs"].update(Panel(Text("\n".join(logs)), title="System Logs", border_style="green"))
    layout["bottom"].update(Panel("ENTER LINK BELOW:", border_style="magenta"))

if __name__ == "__main__":
    bot.start()
    layout = make_layout()
    threading.Thread(target=lambda: (Live(layout, refresh_per_second=4, screen=True).start(), 
                                    [refresh_ui(layout) or time.sleep(0.25) for _ in iter(int, 1)]), daemon=True).start()

    while True:
        link = console.input()
        if link.strip() and not download_active:
            threading.Thread(target=download_worker, args=(link.strip(),), daemon=True).start()