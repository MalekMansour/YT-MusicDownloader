# YouTube Music Downloader

A Python desktop application that downloads YouTube audio as high-quality MP3 files and automatically embeds custom album cover art using FFmpeg.

Built with:

* Python
* Tkinter
* yt-dlp
* FFmpeg

---

# Features

* Download audio from YouTube links
* Convert audio to MP3 format
* Automatically clean song filenames
* Embed custom album art into MP3 files
* Modern dark-red themed GUI
* Supports downloading multiple songs at once

---

# Requirements

Install Python packages:

```bash
pip install yt-dlp
```

You also need:

* FFmpeg installed
* Python 3.10+

---

# FFmpeg Setup

Download FFmpeg and extract it somewhere on your computer.

Update this line in the script:

```python
FFMPEG_FOLDER = r'C:\Path\To\ffmpeg\bin'
```

Make sure the folder contains:

```text
ffmpeg.exe
```

---

# How It Works

## 1. Paste YouTube Links

The textbox allows you to paste one or multiple YouTube URLs.

Each link should be on its own line.

Example:

```text
https://youtube.com/watch?v=example1
https://youtube.com/watch?v=example2
```

---

## 2. Select Cover Art

Click:

```text
Select Cover Art
```

Choose an image file:

* JPG
* PNG
* WEBP
* BMP

This image will be embedded into every downloaded MP3 file.

---

## 3. Download Songs

Click:

```text
Download All
```

The program will:

1. Download the best audio quality
2. Convert audio to MP3
3. Rename the file safely
4. Embed the selected album art
5. Save everything into:

```text
Downloads/Downloaded Music
```

---

# GUI Design

The application uses a custom dark-red theme with:

* hover button effects
* modern typography
* centered card layout
* responsive resizing

---

# Notes

* Internet connection is required
* Some videos may not be downloadable due to restrictions
* FFmpeg must be correctly configured

---

# Author
Made by Malek Mansour
