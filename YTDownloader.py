import os
import re
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from yt_dlp import YoutubeDL

cover_path = ""

FFMPEG_FOLDER = r'C:\Users\Malek\Downloads\ffmpeg-8.1.1-essentials_build\ffmpeg-8.1.1-essentials_build\bin'

FFMPEG_EXE = os.path.join(
    FFMPEG_FOLDER,
    "ffmpeg.exe"
)

# Colors
BG = "#120707"
CARD = "#1b0b0b"
RED = "#8b0000"
HOVER = "#b30000"
TEXT = "#ffffff"
SUBTEXT = "#c9b3b3"
BOX = "#2a1111"

# Clean File Name
def clean_filename(name):

    name = re.sub(r'[\[\]\(\)\{\}]', '', name)
    name = re.sub(r'[^a-zA-Z0-9\s-]', '', name)
    name = name.replace(" ", "-")
    name = re.sub(r'-+', '-', name)
    name = name.strip("-")

    return name

# Hover Effect
def on_enter(e):
    e.widget['background'] = HOVER

def on_leave(e):
    e.widget['background'] = RED

# Cover Art
def select_cover():

    global cover_path

    file = filedialog.askopenfilename(
        title="Choose Cover Art",
        filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp")]
    )

    if file:

        cover_path = file

        cover_label.config(
            text=f"Selected Cover:\n{os.path.basename(file)}"
        )

# --------------------------------
# DOWNLOAD MUSIC
# --------------------------------
def download_music():

    global cover_path

    text = url_text.get("1.0", tk.END).strip()

    if not text:

        messagebox.showerror(
            "Error",
            "Please paste at least one YouTube link."
        )

        return

    if not cover_path:

        messagebox.showerror(
            "Error",
            "Please select cover art first."
        )

        return

    links = text.splitlines()

    download_folder = os.path.join(
        os.path.expanduser("~"),
        "Downloads",
        "Downloaded Music"
    )

    os.makedirs(download_folder, exist_ok=True)

    downloaded_count = 0

    try:

        for link in links:

            link = link.strip()

            if not link:
                continue

            status_label.config(
                text=f"Downloading...\n{link}"
            )

            root.update()

            # --------------------------------
            # GET VIDEO INFO
            # --------------------------------
            with YoutubeDL({
                'noplaylist': True,
                'quiet': True,
                'ffmpeg_location': FFMPEG_FOLDER
            }) as ydl:

                info = ydl.extract_info(
                    link,
                    download=False
                )

            title = info.get("title", "Unknown Song")

            clean_title = clean_filename(title)

            output_template = os.path.join(
                download_folder,
                clean_title + ".%(ext)s"
            )

            # --------------------------------
            # DOWNLOAD SETTINGS
            # --------------------------------
            ydl_opts = {

                'format': 'bestaudio/best',

                'outtmpl': output_template,

                'ffmpeg_location': FFMPEG_FOLDER,

                'noplaylist': True,

                'quiet': False,

                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            }

            # --------------------------------
            # DOWNLOAD SONG
            # --------------------------------
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])

            mp3_file = os.path.join(
                download_folder,
                clean_title + ".mp3"
            )

            temp_output = os.path.join(
                download_folder,
                clean_title + "_cover.mp3"
            )

            # --------------------------------
            # EMBED COVER ART
            # --------------------------------
            command = [
                FFMPEG_EXE,
                "-y",
                "-i", mp3_file,
                "-i", cover_path,
                "-map", "0:a",
                "-map", "1:v",
                "-c:a", "libmp3lame",
                "-b:a", "320k",
                "-c:v", "mjpeg",
                "-id3v2_version", "3",
                "-metadata:s:v", "title=Album cover",
                "-metadata:s:v", "comment=Cover (front)",
                temp_output
            ]

            subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # --------------------------------
            # REPLACE OLD FILE
            # --------------------------------
            if os.path.exists(temp_output):

                os.remove(mp3_file)

                os.rename(
                    temp_output,
                    mp3_file
                )

            downloaded_count += 1

        status_label.config(
            text="Finished downloading!"
        )

        messagebox.showinfo(
            "Success",
            f"Downloaded {downloaded_count} song(s) successfully!\n\nSaved in:\n{download_folder}"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )

# --------------------------------
# GUI
# --------------------------------
root = tk.Tk()

root.title("YouTube Music Downloader")
root.geometry("1000x1000")
root.configure(bg=BG)
root.resizable(True, True)

# --------------------------------
# MAIN CARD
# --------------------------------
main_frame = tk.Frame(
    root,
    bg=CARD,
    padx=30,
    pady=25
)

main_frame.place(
    relx=0.5,
    rely=0.5,
    anchor="center"
)

# --------------------------------
# LOGO
# --------------------------------
logo_path = "logo.png"

if os.path.exists(logo_path):

    logo_image = tk.PhotoImage(file=logo_path)

    # MAKE LOGO SMALLER
    logo_image = logo_image.subsample(5, 5)

    logo_label = tk.Label(
        main_frame,
        image=logo_image,
        bg=CARD
    )

    logo_label.pack(pady=(0, 1))

# --------------------------------
# TITLE
# --------------------------------
title_label = tk.Label(
    main_frame,
    text="YouTube Music Downloader",
    font=("Segoe UI", 24, "bold"),
    bg=CARD,
    fg=TEXT
)

title_label.pack()

# --------------------------------
# SUBTITLE
# --------------------------------
subtitle = tk.Label(
    main_frame,
    text="Paste YouTube links and automatically embed custom album art",
    font=("Segoe UI", 10),
    bg=CARD,
    fg=SUBTEXT
)

subtitle.pack(pady=(0, 20))

# --------------------------------
# TEXTBOX
# --------------------------------
url_text = tk.Text(
    main_frame,
    width=80,
    height=16,
    font=("Consolas", 11),
    bg=BOX,
    fg=TEXT,
    insertbackground=TEXT,
    relief="flat",
    padx=15,
    pady=15
)

url_text.pack(pady=10)

# --------------------------------
# BUTTON STYLE
# --------------------------------
def create_button(text, command):

    btn = tk.Button(
        main_frame,
        text=text,
        command=command,
        font=("Segoe UI", 11, "bold"),
        bg=RED,
        fg="white",
        activebackground=HOVER,
        activeforeground="white",
        relief="flat",
        bd=0,
        padx=25,
        pady=12,
        cursor="hand2"
    )

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)

    return btn

# --------------------------------
# COVER BUTTON
# --------------------------------
cover_button = create_button(
    "Select Cover Art",
    select_cover
)

cover_button.pack(pady=(15, 8))

# --------------------------------
# COVER LABEL
# --------------------------------
cover_label = tk.Label(
    main_frame,
    text="No cover selected",
    font=("Segoe UI", 10),
    bg=CARD,
    fg=SUBTEXT
)

cover_label.pack(pady=(0, 15))

# --------------------------------
# DOWNLOAD BUTTON
# --------------------------------
download_button = create_button(
    "Download All",
    download_music
)

download_button.pack(pady=10)

# --------------------------------
# STATUS LABEL
# --------------------------------
status_label = tk.Label(
    main_frame,
    text="",
    font=("Segoe UI", 10),
    bg=CARD,
    fg=TEXT
)

status_label.pack(pady=(20, 0))

# --------------------------------
# RUN APP
# --------------------------------
root.mainloop()
