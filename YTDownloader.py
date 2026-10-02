"""
YTDownloader
Download YouTube audio as MP3 with cover art, or add cover art to your own audio files.

Setup (run once in a terminal):
    pip install -U "yt-dlp[default]" pillow
    winget install DenoLand.Deno        <- YouTube now needs a JavaScript runtime
    FFmpeg: keep your existing build, or install with: winget install Gyan.FFmpeg
"""

import os
import re
import sys
import queue
import shutil
import tempfile
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from yt_dlp import YoutubeDL
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------

# Your old FFmpeg folder. If it isn't there, the app falls back to FFmpeg on PATH,
# and you can also point it somewhere else with the "Locate" button.
DEFAULT_FFMPEG_FOLDER = r"C:\Users\Malek\Downloads\ffmpeg-8.1.1-essentials_build\ffmpeg-8.1.1-essentials_build\bin"
DEFAULT_OUTPUT = os.path.join(os.path.expanduser("~"), "Downloads", "YTDownloader")

IS_WINDOWS = os.name == "nt"
FFMPEG_NAME = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0

# The logo sits next to the script. sys._MEIPASS covers the case where
# the app is bundled into an .exe with PyInstaller.
APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
LOGO_FILE = os.path.join(APP_DIR, "logo.png")
LOGO_SIZE = 46  # height in pixels next to the title

AUDIO_TYPES = "*.mp3 *.wav *.flac *.m4a *.ogg *.opus *.aac"
IMAGE_TYPES = "*.jpg *.jpeg *.png *.webp *.bmp"

# ----------------------------------------------------------------------------
# Palette: black and dark purple
# ----------------------------------------------------------------------------

BG = "#000000"
CARD = "#0d0a12"
BORDER = "#22182e"
INPUT = "#15101c"
PURPLE = "#3f1764"
PURPLE_HOVER = "#56208a"
ACCENT = "#9d5cff"
SECONDARY = "#1c1526"
SECONDARY_HOVER = "#2a1f3a"
TEXT = "#efe9f7"
SUBTEXT = "#a496b8"
MUTED = "#665a75"
DISABLED = "#18131f"
OK = "#a8e6bf"
ERR = "#ff6b8f"
WARN = "#f0c46c"

FONT = "Segoe UI" if IS_WINDOWS else "Helvetica"
MONO = "Consolas" if IS_WINDOWS else "Courier"


# ----------------------------------------------------------------------------
# Helpers (no UI in here, safe to call from the worker thread)
# ----------------------------------------------------------------------------

def clean_filename(name):
    name = re.sub(r"[\[\]\(\)\{\}]", "", name)
    name = re.sub(r"[^a-zA-Z0-9\s-]", "", name)
    name = name.replace(" ", "-")
    name = re.sub(r"-+", "-", name)
    return name.strip("-")


def unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{base}-{i}{ext}"):
        i += 1
    return f"{base}-{i}{ext}"


def find_ffmpeg():
    if os.path.isfile(os.path.join(DEFAULT_FFMPEG_FOLDER, FFMPEG_NAME)):
        return DEFAULT_FFMPEG_FOLDER
    found = shutil.which("ffmpeg")
    return os.path.dirname(found) if found else None


def short_error(err):
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(err))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    msg = lines[0] if lines else "Unknown error"
    msg = msg.replace("ERROR: ", "")
    return msg[:180]


def prepare_cover(cover_path, work_dir):
    """Turn any image into a clean square JPEG so every player shows it properly."""
    if not HAS_PIL:
        return cover_path
    img = Image.open(cover_path).convert("RGB")
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    if side > 1000:
        img = img.resize((1000, 1000), Image.LANCZOS)
    out = os.path.join(work_dir, "cover.jpg")
    img.save(out, "JPEG", quality=92)
    return out


def embed_cover(input_file, cover, output_file, ffmpeg_exe):
    """Write an MP3 with the cover embedded. Non-MP3 input gets converted to MP3."""
    is_mp3 = input_file.lower().endswith(".mp3")
    audio = ["-c:a", "copy"] if is_mp3 else ["-c:a", "libmp3lame", "-b:a", "320k"]
    tmp_out = output_file + ".part.mp3"

    cmd = [
        ffmpeg_exe, "-y", "-hide_banner", "-loglevel", "error",
        "-i", input_file,
        "-i", cover,
        "-map", "0:a:0", "-map", "1:v:0",
        *audio,
        "-c:v", "mjpeg",
        "-disposition:v:0", "attached_pic",
        "-id3v2_version", "3",
        "-metadata:s:v", "title=Album cover",
        "-metadata:s:v", "comment=Cover (front)",
        tmp_out,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    if result.returncode != 0:
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
        raise RuntimeError(short_error(result.stderr) if result.stderr else "FFmpeg failed")
    os.replace(tmp_out, output_file)
    return output_file


def load_logo(size):
    """Load logo.png scaled to the given height. Returns None if it's missing or broken."""
    if not os.path.isfile(LOGO_FILE):
        return None
    try:
        if HAS_PIL:
            img = Image.open(LOGO_FILE).convert("RGBA")
            w, h = img.size
            new_w = max(1, round(w * size / h))
            img = img.resize((new_w, size), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        # Without Pillow, Tk can still read PNGs but only shrink by whole steps
        img = tk.PhotoImage(file=LOGO_FILE)
        step = max(1, img.height() // size)
        return img.subsample(step, step)
    except Exception:
        return None


def open_folder(path):
    if IS_WINDOWS:
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ----------------------------------------------------------------------------
# Small custom widgets
# ----------------------------------------------------------------------------

class FlatButton(tk.Label):
    """A flat button whose colors look the same on every OS."""

    def __init__(self, master, text, command, primary=False, big=False, **kw):
        self._bg = PURPLE if primary else SECONDARY
        self._hover = PURPLE_HOVER if primary else SECONDARY_HOVER
        size = 13 if big else 10
        super().__init__(
            master, text=text, bg=self._bg, fg=TEXT,
            font=(FONT, size, "bold" if (primary or big) else "normal"),
            padx=22 if big else 14, pady=12 if big else 6, cursor="hand2", **kw
        )
        self.command = command
        self.enabled = True
        self.bind("<Enter>", lambda e: self.enabled and self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.enabled and self.config(bg=self._bg))
        self.bind("<Button-1>", self._click)

    def _click(self, _):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, on):
        self.enabled = on
        self.config(bg=self._bg if on else DISABLED,
                    fg=TEXT if on else MUTED,
                    cursor="hand2" if on else "arrow")


def make_card(parent, title):
    """A panel with a thin purple border and a title. Returns (outer, body, header)."""
    outer = tk.Frame(parent, bg=BORDER)
    inner = tk.Frame(outer, bg=CARD, padx=18, pady=16)
    inner.pack(fill="both", expand=True, padx=1, pady=1)

    header = tk.Frame(inner, bg=CARD)
    header.pack(fill="x", pady=(0, 10))
    tk.Frame(header, bg=ACCENT, width=3, height=18).pack(side="left", padx=(0, 10))
    tk.Label(header, text=title, bg=CARD, fg=TEXT, font=(FONT, 12, "bold")).pack(side="left")

    body = tk.Frame(inner, bg=CARD)
    body.pack(fill="both", expand=True)
    return outer, body, header


# ----------------------------------------------------------------------------
# The app
# ----------------------------------------------------------------------------

class YTDownloader:
    PLACEHOLDER = "Paste YouTube links here, one per line"

    def __init__(self, root):
        self.root = root
        self.local_files = []
        self.cover_path = ""
        self.cover_preview = None
        self.output_dir = DEFAULT_OUTPUT
        self.ffmpeg_dir = find_ffmpeg()
        self.running = False
        self.q = queue.Queue()

        root.title("YTDownloader")
        root.geometry("1000x800")
        root.minsize(900, 740)
        root.configure(bg=BG)

        # Keep references to the images, or Tkinter throws them away and they go blank
        self.logo_small = load_logo(LOGO_SIZE)
        self.logo_icon = load_logo(64)
        if self.logo_icon:
            root.iconphoto(True, self.logo_icon)  # title bar and taskbar icon

        self._setup_styles()
        self._build_ui()
        self._startup_checks()
        self.root.after(80, self._poll)

    # ---------- styles ----------

    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Purple.Horizontal.TProgressbar",
            troughcolor=INPUT, background=ACCENT,
            bordercolor=BORDER, lightcolor=ACCENT, darkcolor=PURPLE, thickness=10,
        )
        style.configure(
            "Dark.Vertical.TScrollbar",
            background=SECONDARY, troughcolor=INPUT, bordercolor=INPUT,
            arrowcolor=SUBTEXT, lightcolor=SECONDARY, darkcolor=SECONDARY,
        )
        style.map("Dark.Vertical.TScrollbar", background=[("active", SECONDARY_HOVER)])

    # ---------- layout ----------

    def _build_ui(self):
        page = tk.Frame(self.root, bg=BG, padx=28, pady=22)
        page.pack(fill="both", expand=True)

        # Header: the one loud thing on the screen
        header = tk.Frame(page, bg=BG)
        header.pack(fill="x")
        title_row = tk.Frame(header, bg=BG)
        title_row.pack(anchor="w")
        if self.logo_small:
            tk.Label(title_row, image=self.logo_small, bg=BG).pack(side="left", padx=(0, 12))
        tk.Label(title_row, text="YTDownloader", bg=BG, fg=TEXT,
                 font=(FONT, 30, "bold")).pack(side="left")
        tk.Frame(header, bg=PURPLE, height=3).pack(fill="x", pady=(8, 6))
        tk.Label(header, text="Grab audio from YouTube as MP3 and give every track its cover art.",
                 bg=BG, fg=SUBTEXT, font=(FONT, 10)).pack(anchor="w")

        # Body: two columns
        body = tk.Frame(page, bg=BG)
        body.pack(fill="both", expand=True, pady=(18, 0))
        body.columnconfigure(0, weight=3, uniform="col")
        body.columnconfigure(1, weight=2, uniform="col")
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)

        self._build_links_card(body).grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        self._build_files_card(body).grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self._build_cover_card(body).grid(row=0, column=1, sticky="nsew", pady=(0, 10))
        self._build_output_card(body).grid(row=1, column=1, sticky="nsew")

        # Footer: start button, progress, log
        footer = tk.Frame(page, bg=BG)
        footer.pack(fill="x", pady=(16, 0))

        action_row = tk.Frame(footer, bg=BG)
        action_row.pack(fill="x")
        self.start_btn = FlatButton(action_row, "Start", self.start, primary=True, big=True)
        self.start_btn.pack(side="left")

        prog_box = tk.Frame(action_row, bg=BG)
        prog_box.pack(side="left", fill="x", expand=True, padx=(18, 0))
        self.status_label = tk.Label(prog_box, text="Ready", bg=BG, fg=SUBTEXT,
                                     font=(FONT, 10), anchor="w")
        self.status_label.pack(fill="x")
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(prog_box, variable=self.progress_var, maximum=100,
                        style="Purple.Horizontal.TProgressbar").pack(fill="x", pady=(6, 0))

        log_outer = tk.Frame(footer, bg=BORDER)
        log_outer.pack(fill="x", pady=(14, 0))
        log_inner = tk.Frame(log_outer, bg=INPUT)
        log_inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.log_box = tk.Text(log_inner, height=7, bg=INPUT, fg=SUBTEXT, font=(MONO, 9),
                               relief="flat", bd=0, padx=12, pady=10, wrap="word",
                               state="disabled", cursor="arrow")
        log_scroll = ttk.Scrollbar(log_inner, orient="vertical", command=self.log_box.yview,
                                   style="Dark.Vertical.TScrollbar")
        self.log_box.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.log_box.pack(side="left", fill="both", expand=True)
        for tag, color in (("ok", OK), ("err", ERR), ("warn", WARN), ("info", SUBTEXT), ("dim", MUTED)):
            self.log_box.tag_configure(tag, foreground=color)

    def _build_links_card(self, parent):
        outer, body, _ = make_card(parent, "YouTube links")

        box = tk.Frame(body, bg=BORDER)
        box.pack(fill="both", expand=True)
        self.links_text = tk.Text(box, bg=INPUT, fg=MUTED, insertbackground=ACCENT,
                                  font=(MONO, 10), relief="flat", bd=0, padx=12, pady=10,
                                  wrap="none", undo=True, selectbackground=PURPLE)
        self.links_text.pack(fill="both", expand=True, padx=1, pady=1)
        self.links_text.insert("1.0", self.PLACEHOLDER)
        self.links_placeholder = True
        self.links_text.bind("<FocusIn>", self._placeholder_in)
        self.links_text.bind("<FocusOut>", self._placeholder_out)

        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x", pady=(10, 0))
        FlatButton(row, "Paste", self._paste_links).pack(side="left")
        FlatButton(row, "Clear", self._clear_links).pack(side="left", padx=(8, 0))
        return outer

    def _build_files_card(self, parent):
        outer, body, header = make_card(parent, "Your audio files")
        self.files_count = tk.Label(header, text="none added", bg=CARD, fg=MUTED, font=(FONT, 9))
        self.files_count.pack(side="right")

        box = tk.Frame(body, bg=BORDER)
        box.pack(fill="both", expand=True)
        inner = tk.Frame(box, bg=INPUT)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.files_list = tk.Listbox(inner, bg=INPUT, fg=TEXT, font=(FONT, 10), relief="flat",
                                     bd=0, highlightthickness=0, selectbackground=PURPLE,
                                     selectforeground=TEXT, activestyle="none",
                                     selectmode="extended", height=4)
        files_scroll = ttk.Scrollbar(inner, orient="vertical", command=self.files_list.yview,
                                     style="Dark.Vertical.TScrollbar")
        self.files_list.configure(yscrollcommand=files_scroll.set)
        files_scroll.pack(side="right", fill="y")
        self.files_list.pack(side="left", fill="both", expand=True, padx=8, pady=6)

        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x", pady=(10, 0))
        FlatButton(row, "Add files", self.add_local_files).pack(side="left")
        FlatButton(row, "Remove selected", self._remove_selected).pack(side="left", padx=(8, 0))
        FlatButton(row, "Clear", self._clear_files).pack(side="left", padx=(8, 0))
        return outer

    def _build_cover_card(self, parent):
        outer, body, _ = make_card(parent, "Cover art")

        self.cover_canvas = tk.Canvas(body, width=170, height=170, bg=INPUT,
                                      highlightthickness=1, highlightbackground=BORDER)
        self.cover_canvas.pack(pady=(0, 10))
        self._draw_empty_cover()

        self.cover_name = tk.Label(body, text="No image chosen", bg=CARD, fg=SUBTEXT,
                                   font=(FONT, 9), wraplength=260)
        self.cover_name.pack()

        row = tk.Frame(body, bg=CARD)
        row.pack(pady=(10, 8))
        FlatButton(row, "Choose image", self.select_cover).pack(side="left")
        FlatButton(row, "Remove", self._clear_cover).pack(side="left", padx=(8, 0))

        tk.Label(body, text="Leave empty to use each video's own thumbnail. "
                            "Your own audio files need an image.",
                 bg=CARD, fg=MUTED, font=(FONT, 9), wraplength=280, justify="center").pack()
        return outer

    def _build_output_card(self, parent):
        outer, body, _ = make_card(parent, "Save to")

        self.output_label = tk.Label(body, text=self.output_dir, bg=CARD, fg=SUBTEXT,
                                     font=(FONT, 9), wraplength=300, justify="left", anchor="w")
        self.output_label.pack(fill="x")
        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x", pady=(8, 14))
        FlatButton(row, "Change folder", self._change_output).pack(side="left")
        FlatButton(row, "Open folder", self._open_output).pack(side="left", padx=(8, 0))

        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(0, 12))

        ff_row = tk.Frame(body, bg=CARD)
        ff_row.pack(fill="x")
        self.ffmpeg_dot = tk.Label(ff_row, text="●", bg=CARD, font=(FONT, 10))
        self.ffmpeg_dot.pack(side="left")
        self.ffmpeg_label = tk.Label(ff_row, bg=CARD, fg=SUBTEXT, font=(FONT, 9))
        self.ffmpeg_label.pack(side="left", padx=(6, 0))
        FlatButton(ff_row, "Locate", self._locate_ffmpeg).pack(side="right")
        self._refresh_ffmpeg_status()

        deno_row = tk.Frame(body, bg=CARD)
        deno_row.pack(fill="x", pady=(8, 0))
        has_deno = shutil.which("deno") is not None
        tk.Label(deno_row, text="●", bg=CARD, fg=OK if has_deno else WARN,
                 font=(FONT, 10)).pack(side="left")
        tk.Label(deno_row, text="Deno found" if has_deno else "Deno not found (needed for YouTube)",
                 bg=CARD, fg=SUBTEXT, font=(FONT, 9)).pack(side="left", padx=(6, 0))
        return outer

    # ---------- link box ----------

    def _placeholder_in(self, _):
        if self.links_placeholder:
            self.links_text.delete("1.0", "end")
            self.links_text.config(fg=TEXT)
            self.links_placeholder = False

    def _placeholder_out(self, _):
        if not self.links_text.get("1.0", "end").strip():
            self.links_text.insert("1.0", self.PLACEHOLDER)
            self.links_text.config(fg=MUTED)
            self.links_placeholder = True

    def _get_links(self):
        if self.links_placeholder:
            return []
        lines = self.links_text.get("1.0", "end").splitlines()
        return [ln.strip() for ln in lines if ln.strip()]

    def _set_links(self, links):
        self.links_text.delete("1.0", "end")
        if links:
            self.links_text.config(fg=TEXT)
            self.links_text.insert("1.0", "\n".join(links))
            self.links_placeholder = False
        else:
            self.links_placeholder = False
            self._placeholder_out(None)

    def _paste_links(self):
        try:
            clip = self.root.clipboard_get().strip()
        except tk.TclError:
            return
        if not clip:
            return
        current = self._get_links()
        self._set_links(current + clip.splitlines())

    def _clear_links(self):
        self._set_links([])

    # ---------- local files ----------

    def add_local_files(self):
        files = filedialog.askopenfilenames(title="Choose audio files",
                                            filetypes=[("Audio files", AUDIO_TYPES)])
        for f in files:
            if f not in self.local_files:
                self.local_files.append(f)
                self.files_list.insert("end", os.path.basename(f))
        self._update_file_count()

    def _remove_selected(self):
        for i in reversed(self.files_list.curselection()):
            self.files_list.delete(i)
            del self.local_files[i]
        self._update_file_count()

    def _clear_files(self):
        self.local_files.clear()
        self.files_list.delete(0, "end")
        self._update_file_count()

    def _update_file_count(self):
        n = len(self.local_files)
        self.files_count.config(text="none added" if n == 0 else f"{n} file{'s' if n != 1 else ''}")

    # ---------- cover ----------

    def _draw_empty_cover(self):
        c = self.cover_canvas
        c.delete("all")
        c.create_rectangle(14, 14, 158, 158, outline=BORDER, dash=(4, 4))
        c.create_text(86, 86, text="No cover", fill=MUTED, font=(FONT, 10))

    def select_cover(self):
        f = filedialog.askopenfilename(title="Choose cover art",
                                       filetypes=[("Images", IMAGE_TYPES)])
        if not f:
            return
        self.cover_path = f
        self.cover_name.config(text=os.path.basename(f))
        c = self.cover_canvas
        c.delete("all")
        if HAS_PIL:
            try:
                img = Image.open(f).convert("RGB")
                w, h = img.size
                side = min(w, h)
                img = img.crop(((w - side) // 2, (h - side) // 2,
                                (w - side) // 2 + side, (h - side) // 2 + side))
                img = img.resize((170, 170), Image.LANCZOS)
                self.cover_preview = ImageTk.PhotoImage(img)
                c.create_image(0, 0, anchor="nw", image=self.cover_preview)
                return
            except Exception:
                pass
        c.create_text(86, 86, text="Image chosen", fill=ACCENT, font=(FONT, 10, "bold"))

    def _clear_cover(self):
        self.cover_path = ""
        self.cover_preview = None
        self.cover_name.config(text="No image chosen")
        self._draw_empty_cover()

    # ---------- output / ffmpeg ----------

    def _change_output(self):
        d = filedialog.askdirectory(title="Choose where to save", initialdir=self.output_dir)
        if d:
            self.output_dir = d
            self.output_label.config(text=d)

    def _open_output(self):
        os.makedirs(self.output_dir, exist_ok=True)
        open_folder(self.output_dir)

    def _locate_ffmpeg(self):
        d = filedialog.askdirectory(title="Choose the folder that contains ffmpeg.exe")
        if not d:
            return
        if os.path.isfile(os.path.join(d, FFMPEG_NAME)):
            self.ffmpeg_dir = d
            self._refresh_ffmpeg_status()
            self.log(f"Using FFmpeg from {d}", "ok")
        else:
            messagebox.showerror("FFmpeg not found", f"There is no {FFMPEG_NAME} in that folder.")

    def _refresh_ffmpeg_status(self):
        found = bool(self.ffmpeg_dir)
        self.ffmpeg_dot.config(fg=OK if found else ERR)
        self.ffmpeg_label.config(text="FFmpeg found" if found else "FFmpeg not found")

    def _startup_checks(self):
        self.log("Ready. Add links or files, pick a cover, then press Start.", "dim")
        if not HAS_YTDLP:
            self.log('yt-dlp is not installed. Run: pip install -U "yt-dlp[default]"', "err")
        if not self.ffmpeg_dir:
            self.log("FFmpeg was not found. Use Locate to point to the folder with ffmpeg.exe.", "err")
        if not shutil.which("deno"):
            self.log("Deno was not found. YouTube downloads will likely fail without it. "
                     "Run: winget install DenoLand.Deno (then restart this app).", "warn")
        if not HAS_PIL:
            self.log("Pillow is not installed, so there's no cover preview or auto square crop. "
                     "Run: pip install pillow", "warn")

    # ---------- log / status (main thread only) ----------

    def log(self, text, tag="info"):
        self.log_box.config(state="normal")
        self.log_box.insert("end", text + "\n", tag)
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def post(self, *msg):
        """Called from the worker thread. The UI reads these in _poll."""
        self.q.put(msg)

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self.log(msg[1], msg[2])
                elif kind == "status":
                    self.status_label.config(text=msg[1])
                elif kind == "progress":
                    self.progress_var.set(msg[1])
                elif kind == "done":
                    self._finish(msg[1], msg[2], msg[3])
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    # ---------- run ----------

    def start(self):
        if self.running:
            return
        links = self._get_links()
        files = list(self.local_files)

        if not HAS_YTDLP and links:
            messagebox.showerror("Missing yt-dlp", 'Install it with:\npip install -U "yt-dlp[default]"')
            return
        if not self.ffmpeg_dir:
            messagebox.showerror("Missing FFmpeg", "Use Locate to point to the folder with ffmpeg.exe.")
            return
        if not links and not files:
            messagebox.showinfo("Nothing to do", "Paste at least one link or add some audio files.")
            return
        if files and not self.cover_path:
            messagebox.showinfo("Cover needed", "Your own audio files need a cover image. Choose one first.")
            return

        os.makedirs(self.output_dir, exist_ok=True)
        self.running = True
        self.start_btn.set_enabled(False)
        self.start_btn.config(text="Working...")
        self.progress_var.set(0)
        self.log(f"Starting {len(links)} link(s) and {len(files)} file(s).", "dim")

        threading.Thread(
            target=self._worker,
            args=(links, files, self.cover_path, self.output_dir, self.ffmpeg_dir),
            daemon=True,
        ).start()

    def _worker(self, links, files, cover, out_dir, ffmpeg_dir):
        ffmpeg_exe = os.path.join(ffmpeg_dir, FFMPEG_NAME)
        total = len(links) + len(files)
        done = 0
        ok = 0
        failed_links = []
        work_dir = tempfile.mkdtemp(prefix="ytdownloader_")

        try:
            ready_cover = None
            if cover:
                try:
                    ready_cover = prepare_cover(cover, work_dir)
                except Exception as e:
                    self.post("log", f"Couldn't read the cover image: {short_error(e)}", "err")
                    if files:
                        self.post("done", 0, links, total)
                        return

            for link in links:
                self.post("status", f"Downloading {done + 1} of {total}")
                try:
                    path, title = self._download_one(link, out_dir, ffmpeg_dir,
                                                     use_thumbnail=ready_cover is None,
                                                     index=done, total=total)
                    if ready_cover:
                        self.post("status", f"Adding cover {done + 1} of {total}")
                        embed_cover(path, ready_cover, path, ffmpeg_exe)
                    self.post("log", f"✓ {title}", "ok")
                    ok += 1
                except Exception as e:
                    failed_links.append(link)
                    self.post("log", f"✗ {link}\n    {short_error(e)}", "err")
                done += 1
                self.post("progress", done / total * 100)

            for f in files:
                name = os.path.basename(f)
                self.post("status", f"Adding cover {done + 1} of {total}")
                try:
                    out_name = os.path.splitext(name)[0] + ".mp3"
                    out_path = unique_path(os.path.join(out_dir, out_name))
                    embed_cover(f, ready_cover, out_path, ffmpeg_exe)
                    self.post("log", f"✓ {name}", "ok")
                    ok += 1
                except Exception as e:
                    self.post("log", f"✗ {name}\n    {short_error(e)}", "err")
                done += 1
                self.post("progress", done / total * 100)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        self.post("done", ok, failed_links, total)

    def _download_one(self, link, out_dir, ffmpeg_dir, use_thumbnail, index, total):
        def hook(d):
            if d.get("status") == "downloading":
                size = d.get("total_bytes") or d.get("total_bytes_estimate")
                if size:
                    frac = min(d.get("downloaded_bytes", 0) / size, 1.0)
                    self.post("progress", (index + frac * 0.9) / total * 100)
            elif d.get("status") == "finished":
                self.post("status", f"Converting {index + 1} of {total}")

        postprocessors = []
        if use_thumbnail:
            postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})
        postprocessors.append({"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"})
        postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
        if use_thumbnail:
            postprocessors.append({"key": "EmbedThumbnail"})

        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
            "ffmpeg_location": ffmpeg_dir,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [hook],
            "writethumbnail": use_thumbnail,
            "postprocessors": postprocessors,
        }

        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=True)
            if info.get("entries"):
                info = info["entries"][0]
            path = None
            downloads = info.get("requested_downloads") or []
            if downloads:
                path = downloads[-1].get("filepath")
            if not path or not os.path.exists(path):
                path = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp3"

        if not os.path.exists(path):
            raise RuntimeError("Download finished but the MP3 file wasn't found")

        title = info.get("title") or info.get("id", "Song")
        final = unique_path(os.path.join(out_dir, (clean_filename(title) or info.get("id", "song")) + ".mp3"))
        os.replace(path, final)
        return final, title

    def _finish(self, ok, failed_links, total):
        self.running = False
        self.start_btn.set_enabled(True)
        self.start_btn.config(text="Start")
        self.progress_var.set(100)

        failed = total - ok
        if failed == 0:
            self.status_label.config(text=f"Done. {ok} of {total} saved.")
            self.log(f"Finished. Everything saved to {self.output_dir}", "ok")
        else:
            self.status_label.config(text=f"Done with problems. {ok} saved, {failed} failed.")
            self.log(f"Finished with {failed} problem(s). Failed links were left in the box so you can retry.", "warn")

        # Keep only the links that failed, so a retry is one click
        self._set_links(failed_links)
        if ok:
            self._clear_files()
            if messagebox.askyesno("YTDownloader", f"{ok} track(s) saved.\n\nOpen the folder?"):
                open_folder(self.output_dir)


if __name__ == "__main__":
    root = tk.Tk()
    YTDownloader(root)
    root.mainloop()
