import os
import re
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from yt_dlp import YoutubeDL

# --------------------------------
# GLOBALS
# --------------------------------
cover_path = ""
local_files = [] # Added to track local audio files

# --------------------------------
# FFMPEG PATH
# --------------------------------
FFMPEG_FOLDER = r'C:\Users\Malek\Downloads\ffmpeg-8.1.1-essentials_build\ffmpeg-8.1.1-essentials_build\bin'
FFMPEG_EXE = os.path.join(FFMPEG_FOLDER, "ffmpeg.exe")

# --------------------------------
# COLORS & STYLING (Same as yours)
# --------------------------------
BG = "#120707"
CARD = "#1b0b0b"
RED = "#8b0000"
HOVER = "#b30000"
TEXT = "#ffffff"
SUBTEXT = "#c9b3b3"
BOX = "#2a1111"

# --------------------------------
# HELPERS
# --------------------------------
def clean_filename(name):
    name = re.sub(r'[\[\]\(\)\{\}]', '', name)
    name = re.sub(r'[^a-zA-Z0-9\s-]', '', name)
    name = name.replace(" ", "-")
    name = re.sub(r'-+', '-', name)
    return name.strip("-")

def apply_cover_to_file(input_file, cover_art, output_folder):
    """Reusable logic to embed art using FFmpeg."""
    filename = os.path.basename(input_file)
    output_path = os.path.join(output_folder, f"Art_{filename}")
    
    command = [
        FFMPEG_EXE, "-y",
        "-i", input_file,
        "-i", cover_art,
        "-map", "0:a", "-map", "1:v",
        "-c:a", "copy", # Using copy is faster if original is mp3
        "-c:v", "mjpeg",
        "-id3v2_version", "3",
        "-metadata:s:v", "title=Album cover",
        "-metadata:s:v", "comment=Cover (front)",
        output_path
    ]
    
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

# --------------------------------
# GUI ACTIONS
# --------------------------------
def select_cover():
    global cover_path
    file = filedialog.askopenfilename(title="Choose Cover Art", filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp")])
    if file:
        cover_path = file
        cover_label.config(text=f"Cover: {os.path.basename(file)}")

def add_local_files():
    global local_files
    files = filedialog.askopenfilenames(title="Select Audio Files", filetypes=[("Audio Files", "*.mp3 *.wav")])
    if files:
        local_files.extend(list(files))
        files_label.config(text=f"{len(local_files)} files queued")

def process_queue():
    global cover_path, local_files
    
    links = url_text.get("1.0", tk.END).strip().splitlines()
    
    if not cover_path:
        messagebox.showerror("Error", "Please select cover art first.")
        return

    if not links and not local_files:
        messagebox.showerror("Error", "Nothing to process!")
        return

    output_dir = os.path.join(os.path.expanduser("~"), "Downloads", "Processed_Music")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Process YouTube Links
    for link in links:
        link = link.strip()
        if not link: continue
        
        status_label.config(text=f"Downloading: {link[:30]}...")
        root.update()
        
        # Enforce single-video mode during metadata extraction
        with YoutubeDL({'noplaylist': True, 'extract_flat': 'in_playlist', 'quiet': True, 'ffmpeg_location': FFMPEG_FOLDER}) as ydl:
            info = ydl.extract_info(link, download=False)
            title = clean_filename(info.get("title", "Song"))
            
        # Enforce single-video mode during download process
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(output_dir, f"{title}.%(ext)s"),
            'ffmpeg_location': FFMPEG_FOLDER,
            'noplaylist': True,
            'extract_flat': 'in_playlist',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'}]
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])
            
        apply_cover_to_file(os.path.join(output_dir, f"{title}.mp3"), cover_path, output_dir)

    # 2. Process Local Files
    for file_path in local_files:
        status_label.config(text=f"Processing: {os.path.basename(file_path)}")
        root.update()
        apply_cover_to_file(file_path, cover_path, output_dir)

    status_label.config(text="Finished!")
    messagebox.showinfo("Success", f"All files processed in:\n{output_dir}")
    # Reset queue
    local_files = []
    files_label.config(text="0 local files queued")

# --------------------------------
# GUI SETUP
# --------------------------------
root = tk.Tk()
root.title("Music Processor")
root.geometry("600x700")
root.configure(bg=BG)

main_frame = tk.Frame(root, bg=CARD, padx=30, pady=25)
main_frame.place(relx=0.5, rely=0.5, anchor="center")

tk.Label(main_frame, text="Music Processor", font=("Segoe UI", 24, "bold"), bg=CARD, fg=TEXT).pack()
url_text = tk.Text(main_frame, width=50, height=8, bg=BOX, fg=TEXT, insertbackground=TEXT, relief="flat")
url_text.pack(pady=10)

# Buttons
cover_btn = tk.Button(main_frame, text="1. Select Cover Art", command=select_cover, bg=RED, fg="white", bd=0, padx=20, pady=5)
cover_btn.pack(pady=5)
cover_label = tk.Label(main_frame, text="No cover selected", bg=CARD, fg=SUBTEXT)
cover_label.pack()

local_btn = tk.Button(main_frame, text="2. Add Local Files (MP3/WAV)", command=add_local_files, bg=RED, fg="white", bd=0, padx=20, pady=5)
local_btn.pack(pady=5)
files_label = tk.Label(main_frame, text="0 local files queued", bg=CARD, fg=SUBTEXT)
files_label.pack()

proc_btn = tk.Button(main_frame, text="3. Process All", command=process_queue, bg=RED, fg="white", bd=0, padx=20, pady=10)
proc_btn.pack(pady=20)

status_label = tk.Label(main_frame, text="", bg=CARD, fg=TEXT)
status_label.pack()

root.mainloop()
