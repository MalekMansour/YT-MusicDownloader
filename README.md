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
* Choose your own save folder and open it straight from the app
* The window stays responsive while downloading
* Black and dark purple interface

---

## Requirements

* Python 3.10 or newer
* FFmpeg
* Deno (YouTube now requires a JavaScript runtime for downloads)

### 1. Install the Python packages

```bash
pip install -U "yt-dlp[default]" pillow
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

On Windows you can use:

```bash
winget install Gyan.FFmpeg
```

Or download a build manually and extract it anywhere.

---

## FFmpeg Setup

The app finds FFmpeg in this order:

1. The folder set in `DEFAULT_FFMPEG_FOLDER` at the top of the script
2. FFmpeg on your system PATH
3. Any folder you pick with the **Locate** button inside the app

If you'd like to set the path in the script, update this line:

```python
DEFAULT_FFMPEG_FOLDER = r"C:\Path\To\ffmpeg\bin"
```

The folder should contain `ffmpeg.exe` (and `ffprobe.exe`).

The "Save to" panel shows a green dot when FFmpeg and Deno are found, and a warning when they're missing.

---

## Running the App

```bash
python YTDownloader.py
```

---

## How It Works

### 1. Paste YouTube links

Paste one or more YouTube URLs into the links box, one per line. You can also use the **Paste** button.

```text
https://youtube.com/watch?v=example1
https://youtube.com/watch?v=example2
```

Playlist links download only the single video, not the whole playlist.

### 2. Add your own audio files (optional)

Click **Add files** to queue audio from your computer. You can remove selected files or clear the list at any time.

### 3. Choose cover art (optional for YouTube)

Click **Choose image** and pick a JPG, PNG, WEBP or BMP file.

* If you choose an image, it gets embedded into every track.
* If you leave it empty, each YouTube download uses its own video thumbnail.
* Your own audio files always need a cover image.

### 4. Pick where to save

By default, files go to:

```text
Downloads/YTDownloader
```

Click **Change folder** to save somewhere else.

### 5. Press Start

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

**Every YouTube link fails**
Update yt-dlp and make sure Deno is installed, then restart the app.

```bash
pip install -U "yt-dlp[default]"
```

YouTube changes often, so updating yt-dlp fixes most problems.

**"FFmpeg not found"**
Click **Locate** and choose the folder that contains `ffmpeg.exe`.

**No cover preview**
Install Pillow with `pip install pillow`.

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
