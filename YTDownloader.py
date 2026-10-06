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
    from yt_dlp.version import __version__ as YTDLP_VERSION
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False
    YTDLP_VERSION = None

# YouTube blocked older yt-dlp versions in August 2026 (HTTP 403 errors).
# 2026.08.19 is the first release with the fix. Versions are dates, so they compare as text.
MIN_YTDLP = "2026.08.19"

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
LOGO_SIZE = 40  # height next to the title (before screen scaling)

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
# Screen scaling
# Windows scales text up on high-res screens (125%, 150%...). Fonts grow with it,
# so every pixel size (padding, boxes, the logo) has to grow by the same amount,
# otherwise text overflows its space and gets cut off. px() does that.
# ----------------------------------------------------------------------------

SCALE = 1.0


def enable_sharp_text():
    """Ask Windows for crisp, non-blurry text. Must run before tk.Tk()."""
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def px(n):
    return max(1, int(round(n * SCALE)))


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
        super().__init__(
            master, text=text, bg=self._bg, fg=TEXT,
            font=(FONT, 12 if big else 10, "bold" if (primary or big) else "normal"),
            padx=px(26 if big else 14), pady=px(10 if big else 5), cursor="hand2", **kw
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


def auto_wrap(label):
    """Make a label wrap to whatever width it's given, so text never runs off the edge."""
    label.bind("<Configure>", lambda e: label.config(wraplength=max(50, e.width - 4)))
    return label


def make_card(parent, title):
    """A full-width panel with a thin purple border and a title. Returns (outer, body, header)."""
    outer = tk.Frame(parent, bg=BORDER)
    inner = tk.Frame(outer, bg=CARD, padx=px(16), pady=px(12))
    inner.pack(fill="both", expand=True, padx=1, pady=1)

    header = tk.Frame(inner, bg=CARD)
    header.pack(fill="x", pady=(0, px(8)))
    tk.Frame(header, bg=ACCENT, width=px(3), height=px(16)).pack(side="left", padx=(0, px(10)))
    tk.Label(header, text=title, bg=CARD, fg=TEXT, font=(FONT, 11, "bold")).pack(side="left")

    body = tk.Frame(inner, bg=CARD)
    body.pack(fill="both", expand=True)
    return outer, body, header


def button_row(parent, pady_top=8):
    row = tk.Frame(parent, bg=CARD)
    row.pack(fill="x", pady=(px(pady_top), 0))
    return row


# ----------------------------------------------------------------------------
# The app
# ----------------------------------------------------------------------------

class YTDownloader:
    PLACEHOLDER = "Paste YouTube links here, one per line"

    def __init__(self, root):
        global SCALE
        self.root = root
        SCALE = max(1.0, root.winfo_fpixels("1i") / 96.0)

        self.local_files = []
        self.cover_path = ""
        self.cover_preview = None
        self.output_dir = DEFAULT_OUTPUT
        self.ffmpeg_dir = find_ffmpeg()
        self.running = False
        self.q = queue.Queue()

        root.title("YTDownloader")
        root.configure(bg=BG)

        # Keep references to the images, or Tkinter throws them away and they go blank
        self.logo_small = load_logo(px(LOGO_SIZE))
        self.logo_icon = load_logo(64)
        if self.logo_icon:
            root.iconphoto(True, self.logo_icon)

        self._setup_styles()
        self._build_ui()
        self._fit_window()
        self._startup_checks()
        self.root.after(80, self._poll)

    # ---------- styles ----------

    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Purple.Horizontal.TProgressbar",
            troughcolor=INPUT, background=ACCENT,
            bordercolor=BORDER, lightcolor=ACCENT, darkcolor=PURPLE, thickness=px(8),
        )
        style.configure(
            "Dark.Vertical.TScrollbar",
            background=SECONDARY, troughcolor=BG, bordercolor=BG,
            arrowcolor=SUBTEXT, lightcolor=SECONDARY, darkcolor=SECONDARY,
        )
        style.map("Dark.Vertical.TScrollbar", background=[("active", SECONDARY_HOVER)])

    # ---------- layout ----------
    #
    #   [logo] YTDownloader                  <- fixed at the top
    #   ------------------------------------
    #   | YouTube links                    |
    #   | Cover art                        |  <- scrolls if the window is short,
    #   | Your audio files                 |     so nothing is ever cut off
    #   | Save to                          |
    #   ------------------------------------
    #   [Download all]  status / progress    <- fixed at the bottom, always visible
    #   log

    def _build_ui(self):
        page = tk.Frame(self.root, bg=BG, padx=px(22), pady=px(16))
        page.pack(fill="both", expand=True)

        self._build_header(page)
        self._build_footer(page)

        # Middle: a scrollable column of sections
        middle = tk.Frame(page, bg=BG)
        middle.pack(side="top", fill="both", expand=True, pady=(px(12), 0))

        self.scroll_canvas = tk.Canvas(middle, bg=BG, highlightthickness=0, bd=0, height=px(200))
        vsb = ttk.Scrollbar(middle, orient="vertical", command=self.scroll_canvas.yview,
                            style="Dark.Vertical.TScrollbar")
        self.scroll_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(px(6), 0))
        self.scroll_canvas.pack(side="left", fill="both", expand=True)

        content = tk.Frame(self.scroll_canvas, bg=BG)
        window_id = self.scroll_canvas.create_window(0, 0, window=content, anchor="nw")
        content.bind("<Configure>", lambda e: self.scroll_canvas.configure(
            scrollregion=self.scroll_canvas.bbox("all")))
        self.scroll_canvas.bind("<Configure>", lambda e: self.scroll_canvas.itemconfigure(
            window_id, width=e.width))
        self.content = content
        self.root.bind_all("<MouseWheel>", self._on_wheel)
        self.root.bind_all("<Button-4>", self._on_wheel)
        self.root.bind_all("<Button-5>", self._on_wheel)

        gap = px(10)
        self._build_links_card(content).pack(fill="x", pady=(0, gap))
        self._build_cover_card(content).pack(fill="x", pady=(0, gap))
        self._build_files_card(content).pack(fill="x", pady=(0, gap))
        self._build_output_card(content).pack(fill="x")

    def _fit_window(self):
        """Open the window just tall enough to show everything, but never bigger than the screen."""
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        needed = (self.root.winfo_reqheight()
                  - self.scroll_canvas.winfo_reqheight()
                  + self.content.winfo_reqheight())
        w = min(px(720), sw - px(40))
        h = min(needed, sh - px(100))
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2 - px(30))
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(min(px(560), w), min(px(480), h))

    def _on_wheel(self, e):
        # Let the link box, file list and log scroll themselves
        if isinstance(e.widget, (tk.Text, tk.Listbox)):
            return
        if not str(e.widget).startswith(str(self.scroll_canvas)):
            return
        if self.content.winfo_height() <= self.scroll_canvas.winfo_height():
            return
        if getattr(e, "num", None) == 4 or getattr(e, "delta", 0) > 0:
            self.scroll_canvas.yview_scroll(-1, "units")
        else:
            self.scroll_canvas.yview_scroll(1, "units")

    def _build_header(self, page):
        header = tk.Frame(page, bg=BG)
        header.pack(side="top", fill="x")

        title_row = tk.Frame(header, bg=BG)
        title_row.pack(fill="x")
        if self.logo_small:
            tk.Label(title_row, image=self.logo_small, bg=BG).pack(side="left", padx=(0, px(12)))
        text_box = tk.Frame(title_row, bg=BG)
        text_box.pack(side="left", fill="x", expand=True)
        tk.Label(text_box, text="YTDownloader", bg=BG, fg=TEXT, font=(FONT, 22, "bold"),
                 anchor="w").pack(fill="x")
        auto_wrap(tk.Label(text_box, text="Grab audio from YouTube as MP3 and give every track its cover art.",
                           bg=BG, fg=SUBTEXT, font=(FONT, 10), anchor="w", justify="left")).pack(fill="x")

        tk.Frame(header, bg=PURPLE, height=px(2)).pack(fill="x", pady=(px(10), 0))

    def _build_footer(self, page):
        footer = tk.Frame(page, bg=BG)
        footer.pack(side="bottom", fill="x", pady=(px(14), 0))

        action_row = tk.Frame(footer, bg=BG)
        action_row.pack(fill="x")
        self.start_btn = FlatButton(action_row, "Download all", self.start, primary=True, big=True)
        self.start_btn.pack(side="left")

        prog_box = tk.Frame(action_row, bg=BG)
        prog_box.pack(side="left", fill="x", expand=True, padx=(px(16), 0))
        self.status_label = tk.Label(prog_box, text="Ready", bg=BG, fg=SUBTEXT,
                                     font=(FONT, 10), anchor="w")
        self.status_label.pack(fill="x")
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(prog_box, variable=self.progress_var, maximum=100,
                        style="Purple.Horizontal.TProgressbar").pack(fill="x", pady=(px(5), 0))

        log_outer = tk.Frame(footer, bg=BORDER)
        log_outer.pack(fill="x", pady=(px(12), 0))
        log_inner = tk.Frame(log_outer, bg=INPUT)
        log_inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.log_box = tk.Text(log_inner, height=4, bg=INPUT, fg=SUBTEXT, font=(MONO, 9),
                               relief="flat", bd=0, padx=px(10), pady=px(8), wrap="word",
                               state="disabled", cursor="arrow", highlightthickness=0)
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
        box.pack(fill="x")
        self.links_text = tk.Text(box, height=4, bg=INPUT, fg=MUTED, insertbackground=ACCENT,
                                  font=(MONO, 10), relief="flat", bd=0, padx=px(10), pady=px(8),
                                  wrap="none", undo=True, selectbackground=PURPLE,
                                  highlightthickness=0)
        self.links_text.pack(fill="x", padx=1, pady=1)
        self.links_text.insert("1.0", self.PLACEHOLDER)
        self.links_placeholder = True
        self.links_text.bind("<FocusIn>", self._placeholder_in)
        self.links_text.bind("<FocusOut>", self._placeholder_out)

        row = button_row(body)
        FlatButton(row, "Paste", self._paste_links).pack(side="left")
        FlatButton(row, "Clear", self._clear_links).pack(side="left", padx=(px(8), 0))
        return outer

    def _build_cover_card(self, parent):
        outer, body, _ = make_card(parent, "Cover art")

        side = px(96)
        self.cover_side = side
        self.cover_canvas = tk.Canvas(body, width=side, height=side, bg=INPUT,
                                      highlightthickness=1, highlightbackground=BORDER)
        self.cover_canvas.pack(side="left", anchor="n")
        self._draw_empty_cover()

        info = tk.Frame(body, bg=CARD)
        info.pack(side="left", fill="both", expand=True, padx=(px(14), 0))
        self.cover_name = auto_wrap(tk.Label(info, text="No image chosen", bg=CARD, fg=TEXT,
                                             font=(FONT, 10), anchor="w", justify="left"))
        self.cover_name.pack(fill="x")
        auto_wrap(tk.Label(info, text="Leave empty to use each video's own thumbnail. "
                                      "Your own audio files need an image.",
                           bg=CARD, fg=MUTED, font=(FONT, 9), anchor="w", justify="left")
                  ).pack(fill="x", pady=(px(2), 0))

        row = tk.Frame(info, bg=CARD)
        row.pack(fill="x", pady=(px(10), 0))
        FlatButton(row, "Choose image", self.select_cover).pack(side="left")
        FlatButton(row, "Remove", self._clear_cover).pack(side="left", padx=(px(8), 0))
        return outer

    def _build_files_card(self, parent):
        outer, body, header = make_card(parent, "Your audio files")
        self.files_count = tk.Label(header, text="none added", bg=CARD, fg=MUTED, font=(FONT, 9))
        self.files_count.pack(side="right")

        box = tk.Frame(body, bg=BORDER)
        box.pack(fill="x")
        inner = tk.Frame(box, bg=INPUT)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.files_list = tk.Listbox(inner, height=3, bg=INPUT, fg=TEXT, font=(FONT, 10),
                                     relief="flat", bd=0, highlightthickness=0,
                                     selectbackground=PURPLE, selectforeground=TEXT,
                                     activestyle="none", selectmode="extended")
        files_scroll = ttk.Scrollbar(inner, orient="vertical", command=self.files_list.yview,
                                     style="Dark.Vertical.TScrollbar")
        self.files_list.configure(yscrollcommand=files_scroll.set)
        files_scroll.pack(side="right", fill="y")
        self.files_list.pack(side="left", fill="both", expand=True, padx=px(8), pady=px(6))

        row = button_row(body)
        FlatButton(row, "Add files", self.add_local_files).pack(side="left")
        FlatButton(row, "Remove", self._remove_selected).pack(side="left", padx=(px(8), 0))
        FlatButton(row, "Clear", self._clear_files).pack(side="left", padx=(px(8), 0))
        return outer

    def _build_output_card(self, parent):
        outer, body, _ = make_card(parent, "Save to")

        self.output_label = auto_wrap(tk.Label(body, text=self.output_dir, bg=CARD, fg=SUBTEXT,
                                               font=(FONT, 9), anchor="w", justify="left"))
        self.output_label.pack(fill="x")

        row = button_row(body)
        FlatButton(row, "Change folder", self._change_output).pack(side="left")
        FlatButton(row, "Open folder", self._open_output).pack(side="left", padx=(px(8), 0))

        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(px(10), px(8)))

        status_row = tk.Frame(body, bg=CARD)
        status_row.pack(fill="x")
        self.ffmpeg_dot = tk.Label(status_row, text="●", bg=CARD, font=(FONT, 10))
        self.ffmpeg_dot.pack(side="left")
        self.ffmpeg_label = tk.Label(status_row, bg=CARD, fg=SUBTEXT, font=(FONT, 9))
        self.ffmpeg_label.pack(side="left", padx=(px(6), px(20)))
        self._refresh_ffmpeg_status()

        has_deno = shutil.which("deno") is not None
        tk.Label(status_row, text="●", bg=CARD, fg=OK if has_deno else WARN,
                 font=(FONT, 10)).pack(side="left")
        tk.Label(status_row, text="Deno found" if has_deno else "Deno missing",
                 bg=CARD, fg=SUBTEXT, font=(FONT, 9)).pack(side="left", padx=(px(6), 0))
        FlatButton(status_row, "Locate FFmpeg", self._locate_ffmpeg).pack(side="right")
        self.update_btn = FlatButton(status_row, "Update yt-dlp", self._update_ytdlp)
        self.update_btn.pack(side="right", padx=(0, px(8)))
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

    def _draw_empty_cover(self):
        c, s = self.cover_canvas, self.cover_side
        c.delete("all")
        m = px(8)
        c.create_rectangle(m, m, s - m, s - m, outline=BORDER, dash=(4, 4))
        c.create_text(s // 2, s // 2, text="No cover", fill=MUTED, font=(FONT, 9))

    def select_cover(self):
        f = filedialog.askopenfilename(title="Choose cover art",
                                       filetypes=[("Images", IMAGE_TYPES)])
        if not f:
            return
        self.cover_path = f
        self.cover_name.config(text=os.path.basename(f))
        c, s = self.cover_canvas, self.cover_side
        c.delete("all")
        if HAS_PIL:
            try:
                img = Image.open(f).convert("RGB")
                w, h = img.size
                side = min(w, h)
                img = img.crop(((w - side) // 2, (h - side) // 2,
                                (w - side) // 2 + side, (h - side) // 2 + side))
                img = img.resize((s, s), Image.LANCZOS)
                self.cover_preview = ImageTk.PhotoImage(img)
                c.create_image(0, 0, anchor="nw", image=self.cover_preview)
                return
            except Exception:
                pass
        c.create_text(s // 2, s // 2, text="Chosen", fill=ACCENT, font=(FONT, 9, "bold"))

    def _clear_cover(self):
        self.cover_path = ""
        self.cover_preview = None
        self.cover_name.config(text="No image chosen")
        self._draw_empty_cover()

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

    def _update_ytdlp(self):
        """Update yt-dlp for the exact Python that is running this app."""
        if self.running:
            return
        self.running = True
        self.update_btn.set_enabled(False)
        self.start_btn.set_enabled(False)
        self.status_label.config(text="Updating yt-dlp...")
        self.log("Updating yt-dlp, this takes a few seconds...", "dim")

        def work():
            base = [sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]"]
            try:
                r = subprocess.run(base, capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", creationflags=NO_WINDOW)
                out = (r.stderr or "") + (r.stdout or "")
                if r.returncode != 0 and ("Access is denied" in out or "Permission" in out):
                    # Python lives in a protected folder (like C:\Python312), so install
                    # for this Windows user instead. No admin rights needed.
                    r = subprocess.run(base + ["--user"], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
                    out = (r.stderr or "") + (r.stdout or "")
                ok = r.returncode == 0
                detail = "" if ok else short_error(out)
            except Exception as e:
                ok, detail = False, short_error(e)
            self.post("updated", ok, detail)

        threading.Thread(target=work, daemon=True).start()

    def _startup_checks(self):
        self.log("Ready. Add links or files, pick a cover, then press Download all.", "dim")
        if HAS_YTDLP:
            if YTDLP_VERSION < MIN_YTDLP:
                self.log(f"yt-dlp {YTDLP_VERSION} is too old and YouTube will block it (HTTP 403). "
                         "Click Update yt-dlp, then restart the app.", "err")
            else:
                self.log(f"yt-dlp {YTDLP_VERSION}", "dim")
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
                elif kind == "updated":
                    self.running = False
                    self.update_btn.set_enabled(True)
                    self.start_btn.set_enabled(True)
                    if msg[1]:
                        self.status_label.config(text="yt-dlp updated. Restart the app.")
                        self.log("yt-dlp updated. Close and reopen YTDownloader to use the new version.", "ok")
                        messagebox.showinfo("YTDownloader", "yt-dlp is updated.\n\nClose and reopen the app to use it.")
                    else:
                        self.status_label.config(text="Update failed")
                        self.log(f"Update failed: {msg[2]}", "err")
                elif kind == "done":
                    self._finish(msg[1], msg[2], msg[3])
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

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

        try:
            info, path = self._run_ytdlp(link, opts)
        except Exception as e:
            if "403" not in str(e):
                raise
            # YouTube refused the download. Try once more with a fresh cache and
            # without the android_vr client, which is the one YouTube most often blocks.
            self.post("log", "  YouTube blocked that one (403), retrying another way...", "warn")
            retry = dict(opts)
            retry["cachedir"] = False
            retry["extractor_args"] = {"youtube": {"player_client": ["default", "-android_vr"]}}
            try:
                info, path = self._run_ytdlp(link, retry)
            except Exception as e2:
                if "403" in str(e2):
                    raise RuntimeError("YouTube blocked the download (403). Click Update yt-dlp, "
                                       "restart the app, and make sure Deno is installed.") from e2
                raise

        if not os.path.exists(path):
            raise RuntimeError("Download finished but the MP3 file wasn't found")

        title = info.get("title") or info.get("id", "Song")
        final = unique_path(os.path.join(out_dir, (clean_filename(title) or info.get("id", "song")) + ".mp3"))
        os.replace(path, final)
        return final, title

    @staticmethod
    def _run_ytdlp(link, opts):
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
        return info, path

    def _finish(self, ok, failed_links, total):
        self.running = False
        self.start_btn.set_enabled(True)
        self.start_btn.config(text="Download all")
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
    enable_sharp_text()
    root = tk.Tk()
    YTDownloader(root)
    root.mainloop()
