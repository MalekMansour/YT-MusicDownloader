<p align="center">
  <img src="logo.png" width="120" alt="YTDownloader logo">
</p>

# YTDownloader

A Python desktop app that downloads YouTube audio as MP3 files and embeds album cover art. It can also add cover art to audio files you already have on your computer.

Built with:

* Python
* Tkinter
* yt-dlp
* FFmpeg
* Pillow (optional, for cover previews and square cropping)

---

## Features

* Download audio from one or many YouTube links at once
* Convert everything to MP3
* Embed your own cover art, or use each video's thumbnail automatically
* Add cover art to your own audio files (MP3, WAV, FLAC, M4A, OGG, OPUS, AAC)
* Non-MP3 files are converted to 320 kbps MP3 with the cover inside
* Cover images are cropped to a clean square so they display properly in music players
* Song title and uploader are written into the file's tags
* Clean, safe filenames
* Live progress bar and a log that shows exactly what worked and what failed
* Failed links stay in the box after a run, so retrying is one click
* Automatic retry when YouTube blocks a download
* One-click **Update yt-dlp** button
* Warns you at startup if your yt-dlp is too old to work with YouTube
* Choose your own save folder and open it straight from the app
* Sharp text and a layout that scales properly with Windows display scaling (125%, 150% and up)
* Black and dark purple interface with your logo in the header and taskbar

---

## Requirements

* Python 3.11 or newer (3.10 may work, but yt-dlp recommends 3.11+)
* yt-dlp **2026.08.19 or newer** (older versions get blocked by YouTube)
* FFmpeg
* Deno (YouTube requires a JavaScript runtime for downloads)

### 1. Install the Python packages

```bash
python -m pip install -U "yt-dlp[default]" pillow
```

Use `python -m pip` instead of plain `pip`. If you have more than one Python installed, plain `pip` can update a different copy than the one that runs the app.

If you get **"Access is denied"**, your Python is installed in a protected folder (like `C:\Python312`). Either run PowerShell as administrator and try again, or install just for your user:

```bash
python -m pip install -U --user "yt-dlp[default]" pillow
```

Pillow is optional. Without it the app still works, but there's no cover preview and no automatic square crop.

### 2. Install Deno

On Windows:

```bash
winget install DenoLand.Deno
```

On macOS:

```bash
brew install deno
```

Restart your terminal (or your computer) after installing so the app can find it.

### 3. Install FFmpeg

On Windows:

```bash
winget install Gyan.FFmpeg
```

Or download a build manually and extract it anywhere.

### 4. Check your yt-dlp version

```bash
python -c "import yt_dlp.version as v; print(v.__version__)"
```

It should print `2026.08.19` or newer.

---

## FFmpeg Setup

The app finds FFmpeg in this order:

1. The folder set in `DEFAULT_FFMPEG_FOLDER` at the top of the script
2. FFmpeg on your system PATH
3. Any folder you pick with the **Locate FFmpeg** button inside the app

To set the path in the script, update this line:

```python
DEFAULT_FFMPEG_FOLDER = r"C:\Path\To\ffmpeg\bin"
```

The folder should contain `ffmpeg.exe` (and `ffprobe.exe`).

The **Save to** section shows a green dot when FFmpeg and Deno are found, and a warning when they're missing.

---

## Project Files

```text
YTDownloader/
├── YTDownloader.py
├── logo.png
├── screenshot.png
└── README.md
```

`logo.png` is optional. If it's in the same folder as the script, it shows next to the title and as the window icon. To change its size next to the title, edit `LOGO_SIZE` near the top of the script.

---

## Running the App

```bash
python YTDownloader.py
```

---

## How It Works

The window has four sections from top to bottom, with the **Download all** button always pinned at the bottom. On smaller screens the middle part scrolls, so nothing gets cut off.

### 1. Paste YouTube links

Paste one or more YouTube URLs into the links box, one per line. You can also use the **Paste** button.

```text
https://youtube.com/watch?v=example1
https://youtube.com/watch?v=example2
```

Links from playlists are fine, but only the single video gets downloaded, not the whole playlist.

### 2. Choose cover art (optional for YouTube)

Click **Choose image** and pick a JPG, PNG, WEBP or BMP file.

* If you choose an image, it gets embedded into every track.
* If you leave it empty, each YouTube download uses its own video thumbnail.
* Your own audio files always need a cover image.

### 3. Add your own audio files (optional)

Click **Add files** to queue audio from your computer. You can remove selected files or clear the list at any time.

### 4. Pick where to save

By default, files go to:

```text
Downloads/YTDownloader
```

Click **Change folder** to save somewhere else, or **Open folder** to see your files.

### 5. Press Download all

For each YouTube link, the app will:

1. Download the best available audio
2. Convert it to MP3
3. Add title and uploader tags
4. Embed the cover art
5. Save it with a clean filename

For each local file, it embeds the cover and saves a new MP3 copy in your output folder. Your original files are never changed.

When it's done, the app shows a summary and offers to open the folder.

---

## Troubleshooting

**Every YouTube link fails with "HTTP Error 403: Forbidden"**
YouTube is blocking your version of yt-dlp. This happens every few months when YouTube changes something.

1. Click **Update yt-dlp** in the app (or run `python -m pip install -U "yt-dlp[default]"`)
2. Close and reopen the app
3. Make sure the Save to section says **Deno found**

The log shows your yt-dlp version at startup and turns red if it's too old.

**"Access is denied" when updating**
Your Python is in a protected folder. Run PowerShell as administrator, or add `--user` to the install command. The in-app **Update yt-dlp** button does this automatically.

**The update said it worked, but nothing changed**
Close and reopen the app. Python only loads the new version on startup. If it still shows the old version, you may have more than one Python installed, so always use `python -m pip`.

**"Deno missing" even after installing it**
Restart your computer so Windows picks up the new PATH.

**"FFmpeg not found"**
Click **Locate FFmpeg** and choose the folder that contains `ffmpeg.exe`.

**No cover preview**
Install Pillow with `python -m pip install pillow`.

**Some videos won't download**
Age-restricted, private or region-locked videos may not be available.

---

## A Note on Audio Quality

YouTube's best audio is usually around 128 to 160 kbps. Files are saved at 320 kbps so nothing is lost in conversion, but this makes files bigger without making them sound better. To save space, change `"320"` to `"192"` in the `_download_one` function.

---

## Disclaimer

This project is for personal use. Only download content you have the right to download, and respect YouTube's Terms of Service and the rights of creators.

---

## Author

Made by Malek Mansour
