#!/usr/bin/env python3
"""
🐾 Yiff Downloader v2.0 🐾
Furry-themed e621 downloader with animated preview & skip.
"""

import os
import sys
import json
import time
import threading
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
import requests

# ============================================================
# 📌 APP INFO
# ============================================================
__version__ = "2.0.0"
GITHUB_REPO = "puppycat291/yiff-downloader"
VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/version.txt"
REPO_URL = f"https://github.com/{GITHUB_REPO}"

# ============================================================
# 🎨 THEMES
# ============================================================
THEMES = {
    "Furry Orange": {
        "primary": "#ff8c42", "primary_hover": "#ffa366",
        "secondary": "#5d4e6d", "secondary_hover": "#7a6890",
        "bg_dark": "#1a1625", "bg_mid": "#25203a", "bg_light": "#322b48",
    },
    "Purple Paws": {
        "primary": "#a78bfa", "primary_hover": "#c4b5fd",
        "secondary": "#5d4e6d", "secondary_hover": "#7a6890",
        "bg_dark": "#1a1625", "bg_mid": "#25203a", "bg_light": "#322b48",
    },
    "Blue Wolf": {
        "primary": "#60a5fa", "primary_hover": "#93c5fd",
        "secondary": "#3d5a80", "secondary_hover": "#547aa5",
        "bg_dark": "#0f1729", "bg_mid": "#1a2540", "bg_light": "#253356",
    },
    "Green Fox": {
        "primary": "#7bc67e", "primary_hover": "#a3d9a5",
        "secondary": "#4a6b4c", "secondary_hover": "#5d8560",
        "bg_dark": "#131a14", "bg_mid": "#1e2a1f", "bg_light": "#2a3a2c",
    },
}

TEXT = "#f5e6d3"
TEXT_DIM = "#a89bb8"
SUCCESS = "#7bc67e"
ERROR = "#e63946"
WARNING = "#f4a261"
INFO = "#89b4fa"


# ============================================================
# ⚙️ CONFIG
# ============================================================
class ConfigManager:
    CONFIG_DIR = Path.home() / ".config" / "yiff_downloader"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    HISTORY_FILE = CONFIG_DIR / "history.json"
    STATS_FILE = CONFIG_DIR / "stats.json"

    DEFAULT = {
        "username": "", "api_key": "",
        "download_dir": str(Path.home() / "YiffDownloads"),
        "safe_mode": False, "auto_convert": True, "delete_original": True,
        "video_quality": "High", "folder_structure": "none",
        "theme": "Furry Orange",
        "last_query": "", "last_limit": 100,
        "last_update_check": "", "auto_check_updates": True,
    }

    @classmethod
    def setup(cls):
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not cls.CONFIG_FILE.exists():
            cls._write(cls.CONFIG_FILE, cls.DEFAULT)
        if not cls.HISTORY_FILE.exists():
            cls._write(cls.HISTORY_FILE, {"tags": []})
        if not cls.STATS_FILE.exists():
            cls._write(cls.STATS_FILE, {
                "total_downloads": 0, "total_conversions": 0,
                "total_size_mb": 0, "total_time_seconds": 0,
            })
        Path(cls.load()["download_dir"]).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read(path, default=None):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    @staticmethod
    def _write(path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls):
        cfg = cls.DEFAULT.copy()
        cfg.update(cls._read(cls.CONFIG_FILE, {}))
        return cfg

    @classmethod
    def save(cls, cfg):
        cls._write(cls.CONFIG_FILE, cfg)

    @classmethod
    def update(cls, **kw):
        cfg = cls.load()
        cfg.update(kw)
        cls.save(cfg)
        return cfg

    @classmethod
    def add_history(cls, tags):
        if not tags.strip():
            return
        h = cls._read(cls.HISTORY_FILE, {"tags": []})
        if tags in h["tags"]:
            h["tags"].remove(tags)
        h["tags"].insert(0, tags)
        h["tags"] = h["tags"][:20]
        cls._write(cls.HISTORY_FILE, h)

    @classmethod
    def load_history(cls):
        return cls._read(cls.HISTORY_FILE, {"tags": []}).get("tags", [])

    @classmethod
    def load_stats(cls):
        return cls._read(cls.STATS_FILE, {})

    @classmethod
    def update_stats(cls, **kw):
        s = cls.load_stats()
        for k, v in kw.items():
            if k in s and isinstance(s[k], (int, float)):
                s[k] += v
            else:
                s[k] = v
        cls._write(cls.STATS_FILE, s)


# ============================================================
# 🛠️ UTILS
# ============================================================
class Utils:
    @staticmethod
    def find_ffmpeg():
        for p in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/bin/ffmpeg"]:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
        f = shutil.which("ffmpeg")
        return f if f and "termux" not in f.lower() else None

    @staticmethod
    def quality(level):
        return {
            "Low":    {"crf": "30", "preset": "ultrafast"},
            "Medium": {"crf": "26", "preset": "veryfast"},
            "High":   {"crf": "23", "preset": "fast"},
            "Ultra":  {"crf": "18", "preset": "medium"},
        }.get(level, {"crf": "23", "preset": "fast"})

    @staticmethod
    def fmt_size(mb):
        return f"{mb/1024:.2f} GB" if mb >= 1024 else f"{mb:.2f} MB"

    @staticmethod
    def fmt_time(s):
        if s < 60:
            return f"{int(s)}s"
        if s < 3600:
            return f"{int(s//60)}m {int(s%60)}s"
        return f"{int(s//3600)}h {int((s%3600)//60)}m"

    @staticmethod
    def sanitize(name):
        for c in '<>:"/\\|?*':
            name = name.replace(c, "_")
        return name.strip()[:200]


ConfigManager.setup()


# ============================================================
# 🌐 E621 API
# ============================================================
class E621API:
    MAX = 320
    UA = "YiffDownloader/2.0 (by user on e621)"

    def __init__(self, cfg):
        self.cfg = cfg
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": self.UA})
        if cfg.get("api_key") and cfg.get("username"):
            self.s.auth = (cfg["username"], cfg["api_key"])

    def _base(self):
        return "https://e926.net" if self.cfg.get("safe_mode") else "https://e621.net"

    def search(self, tags, limit=100, page=1):
        try:
            r = self.s.get(f"{self._base()}/posts.json",
                           params={"tags": tags, "limit": min(limit, self.MAX), "page": page},
                           timeout=30)
            if r.status_code == 200:
                return r.json().get("posts", [])
            if r.status_code == 401:
                return {"error": "Invalid API key or username"}
            if r.status_code == 403:
                return {"error": "Forbidden. Check API key / tags"}
            return {"error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def fetch_all(self, tags, total, progress_cb=None, stop_flag=None):
        posts = []
        pages = (total // self.MAX) + 1
        for p in range(1, pages + 1):
            if stop_flag and stop_flag.is_set():
                break
            if len(posts) >= total:
                break
            batch = min(total - len(posts), self.MAX)
            if progress_cb:
                progress_cb(f"Fetching page {p}... ({len(posts)}/{total})")
            res = self.search(tags, batch, p)
            if isinstance(res, dict) and "error" in res:
                return {"error": res["error"], "posts": posts}
            if not res:
                break
            posts.extend(res)
            if len(res) < batch:
                break
            time.sleep(0.5)
        return {"posts": posts[:total]}


# ============================================================
# 📥 DOWNLOADER
# ============================================================
class Downloader:
    CONVERT_EXTS = {".webm", ".gif", ".mkv", ".avi", ".mov", ".flv"}

    def __init__(self, cfg, log_cb=None, preview_cb=None,
                 progress_cb=None, stats_cb=None):
        self.cfg = cfg
        self.log = log_cb or (lambda m, l="info": None)
        self.preview = preview_cb or (lambda p: None)
        self.progress = progress_cb or (lambda c, t: None)
        self.stats_update = stats_cb or (lambda **kw: None)
        self.ffmpeg = Utils.find_ffmpeg()
        self.stop_flag = threading.Event()
        self.pause_flag = threading.Event()
        self.skip_flag = threading.Event()
        self.downloaded = 0
        self.converted = 0

    def stop(self):
        self.stop_flag.set()
        self.pause_flag.clear()

    def pause(self):
        self.pause_flag.set()

    def resume(self):
        self.pause_flag.clear()

    def skip(self):
        self.skip_flag.set()

    def _wait(self):
        while self.pause_flag.is_set() and not self.stop_flag.is_set():
            time.sleep(0.3)

    def _download_file(self, url, path):
        try:
            headers = {"User-Agent": E621API.UA}
            with requests.get(url, headers=headers, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if self.stop_flag.is_set() or self.skip_flag.is_set():
                            return False
                        self._wait()
                        if chunk:
                            f.write(chunk)
            return True
        except Exception as e:
            self.log(f"Download error: {e}", "error")
            return False

    def _convert(self, input_path):
        if not self.ffmpeg:
            return False
        input_path = Path(input_path)
        output = input_path.with_suffix(".mp4")
        if output.exists():
            if self.cfg.get("delete_original"):
                input_path.unlink()
            return True
        q = Utils.quality(self.cfg.get("video_quality", "High"))
        cmd = [
            self.ffmpeg, "-i", str(input_path),
            "-c:v", "libx264",
            "-preset", q["preset"],
            "-crf", q["crf"],
            "-profile:v", "baseline",
            "-level", "3.1",
            "-pix_fmt", "yuv420p",
            "-an",
            "-movflags", "+faststart",
            str(output), "-y", "-loglevel", "error",
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=600)
            if r.returncode == 0:
                if self.cfg.get("delete_original"):
                    input_path.unlink()
                return True
            self.log(f"Convert failed: {r.stderr.decode()[:80]}", "error")
            if output.exists():
                output.unlink()
            return False
        except Exception as e:
            self.log(f"Convert error: {e}", "error")
            return False

    def _folder(self, post):
        s = self.cfg.get("folder_structure", "none")
        if s == "none":
            return ""
        tags = post.get("tags", {})
        if s == "artist" and tags.get("artist"):
            return Utils.sanitize(tags["artist"][0])
        if s == "pool" and post.get("pools"):
            return f"pool_{post['pools'][0]}"
        if s == "tag" and tags.get("general"):
            return Utils.sanitize(tags["general"][0])
        return ""

    def process(self, posts, download_dir):
        base = Path(download_dir)
        total = len(posts)
        start = time.time()
        total_bytes = 0

        for i, post in enumerate(posts, 1):
            if self.stop_flag.is_set():
                self.log("🛑 Stopped", "warning")
                break
            self._wait()

            url = post.get("file", {}).get("url")
            if not url:
                continue

            sub = self._folder(post)
            target = base / sub if sub else base
            target.mkdir(parents=True, exist_ok=True)

            name = os.path.basename(url)
            save = target / name
            mp4 = save.with_suffix(".mp4")

            self.progress(i, total)

            if save.exists() or (mp4.exists() and self.cfg.get("auto_convert")):
                self.log(f"⏭️ Skipped (exists): {name}", "info")
                continue

            self.log(f"📥 [{i}/{total}] {name}", "info")
            self.skip_flag.clear()

            if not self._download_file(url, save):
                if self.skip_flag.is_set():
                    self.log(f"⏭️ Skipped: {name}", "warning")
                    if save.exists():
                        save.unlink()
                    continue
                self.log(f"❌ Failed: {name}", "error")
                continue

            self.downloaded += 1
            try:
                total_bytes += save.stat().st_size
            except Exception:
                pass

            # Preview
            self.preview(str(save))

            # Convert
            ext = save.suffix.lower()
            if self.cfg.get("auto_convert") and ext in self.CONVERT_EXTS:
                self.log(f"🔄 Converting: {name}", "info")
                if self._convert(save):
                    self.converted += 1
                    self.log(f"✅ Converted: {mp4.name}", "success")
                    self.preview(str(mp4))
                else:
                    self.log(f"⚠️ Failed to convert: {name}", "warning")
            else:
                self.log(f"✅ Downloaded: {name}", "success")

        elapsed = time.time() - start
        self.stats_update(
            total_downloads=self.downloaded,
            total_conversions=self.converted,
            total_size_mb=total_bytes / (1024 * 1024),
            total_time_seconds=elapsed,
        )
        self.log(f"🐾 Done! Downloaded: {self.downloaded} | Converted: {self.converted}", "success")
        self.log(f"⏱️ Time: {Utils.fmt_time(elapsed)}", "info")
# ============================================================
# 🎨 MAIN APPLICATION
# ============================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class YiffDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config = ConfigManager.load()
        self.theme = THEMES.get(self.config.get("theme", "Furry Orange"), THEMES["Furry Orange"])

        self.title("🐾 Yiff Downloader 🐾")
        self.geometry("1250x820")
        self.minsize(1050, 720)
        self.configure(fg_color=self.theme["bg_dark"])

        # Taskbar visibility + icon
        try:
            self.wm_attributes("-type", "normal")
        except Exception:
            pass
        self.lift()
        self.focus_force()

        icon_path = Path.home() / "YiffDownloader" / "icon.png"
        if icon_path.exists():
            try:
                icon_img = ImageTk.PhotoImage(Image.open(str(icon_path)))
                self.iconphoto(True, icon_img)
                self._icon_ref = icon_img
            except Exception:
                pass

        self.downloader = None
        self.download_thread = None
        self.preview_photo = None

        # Fonts
        self.font_title = ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        self.font_label = ctk.CTkFont(family="Segoe UI", size=13)
        self.font_button = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        self.font_small = ctk.CTkFont(family="Segoe UI", size=11)
        self.font_logo = ctk.CTkFont(family="Segoe UI", size=26, weight="bold")

        # Build UI
        self._build_header()
        self._build_tabs()


        # First-run warnings (inside app)
        self.after(800, self._startup_checks)
        # Auto-check updates (after 3s)
        self.after(3000, self._check_updates_auto)

    # ========================================================
    # HEADER
    # ========================================================
    def _build_header(self):
        self.header = ctk.CTkFrame(self, fg_color=self.theme["bg_mid"], height=70, corner_radius=0)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        # Animated GIF on the left
        gif_path = Path.home() / "YiffDownloader" / "header.gif"
        self.header_gif_frames = []
        self.header_gif_durations = []
        self.header_gif_index = 0
        self.header_gif_job = None
        self.header_gif_label = None

        if gif_path.exists():
            try:
                gif = Image.open(str(gif_path))
                for frame_idx in range(gif.n_frames):
                    gif.seek(frame_idx)
                    frame = gif.copy().convert("RGBA")
                    frame = frame.resize((48, 48), Image.LANCZOS)
                    self.header_gif_frames.append(ImageTk.PhotoImage(frame))
                    self.header_gif_durations.append(gif.info.get("duration", 100))
                if self.header_gif_frames:
                    self.header_gif_label = ctk.CTkLabel(
                        self.header, text="",
                        image=self.header_gif_frames[0],
                    )
                    self.header_gif_label.pack(side="left", padx=(15, 5), pady=10)
                    self._animate_header_gif()
            except Exception as e:
                print(f"Header GIF error: {e}")

        # Logo text
        ctk.CTkLabel(
            self.header, text="🐾 Yiff Downloader 🐾",
            font=self.font_logo, text_color=self.theme["primary"],
        ).pack(side="left", padx=(5, 25))

        self.status_label = ctk.CTkLabel(
            self.header, text="● Ready",
            font=self.font_label, text_color=SUCCESS,
        )
        self.status_label.pack(side="right", padx=25)

    def _animate_header_gif(self):
        """Animate the header GIF"""
        if not self.header_gif_frames or self.header_gif_label is None:
            return
        try:
            self.header_gif_label.configure(image=self.header_gif_frames[self.header_gif_index])
            delay = self.header_gif_durations[self.header_gif_index]
            self.header_gif_index = (self.header_gif_index + 1) % len(self.header_gif_frames)
            self.header_gif_job = self.after(delay, self._animate_header_gif)
        except Exception:
            pass

    # ========================================================
    # TABS
    # ========================================================
    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=self.theme["bg_mid"],
            segmented_button_fg_color=self.theme["bg_light"],
            segmented_button_selected_color=self.theme["primary"],
            segmented_button_selected_hover_color=self.theme["primary_hover"],
            segmented_button_unselected_color=self.theme["bg_light"],
            segmented_button_unselected_hover_color=self.theme["secondary"],
            text_color=TEXT,
        )
        self.tabview.pack(fill="both", expand=True, padx=15, pady=15)

        for name in ["📥 Download", "🖼️ Gallery", "⚙️ Settings", "ℹ️ About"]:
            self.tabview.add(name)

        self._build_download_tab()
        self._build_gallery_tab()
        self._build_settings_tab()
        self._build_about_tab()

    # ========================================================
    # TAB 1: DOWNLOAD
    # ========================================================
    def _build_download_tab(self):
        tab = self.tabview.tab("📥 Download")
        tab.configure(fg_color=self.theme["bg_dark"])

        container = ctk.CTkFrame(tab, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=8, pady=8)

        # ----- LEFT (controls) -----
        left = ctk.CTkFrame(container, fg_color=self.theme["bg_mid"], corner_radius=12)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Query
        ctk.CTkLabel(left, text="🔍 Query (tags)", font=self.font_label,
                     text_color=TEXT).pack(anchor="w", padx=15, pady=(15, 4))

        self.query_entry = ctk.CTkEntry(
            left, placeholder_text="e.g. dragon male/male order:score",
            fg_color=self.theme["bg_light"], text_color=TEXT,
            border_color=self.theme["secondary"], font=self.font_label, height=38,
        )
        self.query_entry.pack(fill="x", padx=15, pady=(0, 10))

        # Limit
        limit_row = ctk.CTkFrame(left, fg_color="transparent")
        limit_row.pack(fill="x", padx=15, pady=(0, 8))

        ctk.CTkLabel(limit_row, text="📊 Limit:", font=self.font_label,
                     text_color=TEXT).pack(side="left")

        self.limit_entry = ctk.CTkEntry(
            limit_row, width=100, fg_color=self.theme["bg_light"],
            text_color=TEXT, border_color=self.theme["secondary"],
            font=self.font_label, height=32,
        )
        self.limit_entry.insert(0, str(self.config.get("last_limit", 100)))
        self.limit_entry.pack(side="left", padx=10)

        ctk.CTkLabel(limit_row, text="(any number)", font=self.font_small,
                     text_color=TEXT_DIM).pack(side="left")

        # Safe Mode toggle
        self.safe_mode_var = ctk.BooleanVar(value=self.config.get("safe_mode", False))
        ctk.CTkSwitch(
            left, text="🛡️ Safe Mode (e926 only)",
            variable=self.safe_mode_var, font=self.font_small,
            text_color=TEXT, progress_color=SUCCESS,
        ).pack(anchor="w", padx=15, pady=(0, 8))

        # History
        ctk.CTkLabel(left, text="🕘 Recent searches:", font=self.font_label,
                     text_color=TEXT).pack(anchor="w", padx=15, pady=(8, 4))

        self.history_frame = ctk.CTkScrollableFrame(
            left, fg_color=self.theme["bg_light"], height=80, corner_radius=8,
        )
        self.history_frame.pack(fill="x", padx=15, pady=(0, 10))
        self._refresh_history()

        # Folder
        ctk.CTkLabel(left, text="📁 Download folder:", font=self.font_label,
                     text_color=TEXT).pack(anchor="w", padx=15, pady=(5, 4))

        dir_row = ctk.CTkFrame(left, fg_color="transparent")
        dir_row.pack(fill="x", padx=15, pady=(0, 10))

        self.dir_label = ctk.CTkLabel(
            dir_row, text=self.config["download_dir"], font=self.font_small,
            text_color=TEXT_DIM, anchor="w",
        )
        self.dir_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            dir_row, text="Browse", width=80, height=28,
            fg_color=self.theme["secondary"], hover_color=self.theme["secondary_hover"],
            font=self.font_small, command=self._choose_dir,
        ).pack(side="right")

        # Progress
        self.progress_label = ctk.CTkLabel(
            left, text="Progress: 0 / 0", font=self.font_small, text_color=TEXT_DIM,
        )
        self.progress_label.pack(anchor="w", padx=15, pady=(5, 2))

        self.progress_bar = ctk.CTkProgressBar(
            left, height=12, corner_radius=6,
            fg_color=self.theme["bg_light"], progress_color=self.theme["primary"],
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 12))

        # Buttons row 1: Start / Pause / Stop
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(0, 6))

        self.start_btn = ctk.CTkButton(
            btn_row, text="🐾 Start Download", height=42, font=self.font_button,
            fg_color=self.theme["primary"], hover_color=self.theme["primary_hover"],
            text_color="#1a1625", corner_radius=10, command=self._start_download,
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.pause_btn = ctk.CTkButton(
            btn_row, text="⏸️", width=50, height=42,
            fg_color=self.theme["secondary"], hover_color=self.theme["secondary_hover"],
            corner_radius=10, command=self._toggle_pause, state="disabled",
        )
        self.pause_btn.pack(side="left", padx=(0, 5))

        self.stop_btn = ctk.CTkButton(
            btn_row, text="⏹️", width=50, height=42,
            fg_color=ERROR, hover_color="#c5283a",
            corner_radius=10, command=self._stop_download, state="disabled",
        )
        self.stop_btn.pack(side="left")

        # Buttons row 2: Skip
        self.skip_btn = ctk.CTkButton(
            left, text="⏭️ Skip Current File", height=36, font=self.font_label,
            fg_color=WARNING, hover_color="#d98c3f",
            text_color="#1a1625", corner_radius=10,
            command=self._skip_current, state="disabled",
        )
        self.skip_btn.pack(fill="x", padx=15, pady=(0, 15))

        # ----- RIGHT (preview + log) -----
        right = ctk.CTkFrame(container, fg_color=self.theme["bg_mid"],
                             corner_radius=12, width=440)
        right.pack(side="right", fill="both", padx=(8, 0))
        right.pack_propagate(False)

        ctk.CTkLabel(right, text="👁️ Live Preview", font=self.font_label,
                     text_color=TEXT).pack(anchor="w", padx=15, pady=(15, 5))

        self.preview_frame = ctk.CTkFrame(
            right, fg_color=self.theme["bg_light"], corner_radius=10,
            width=400, height=300,
        )
        self.preview_frame.pack(padx=15, pady=(0, 8))
        self.preview_frame.pack_propagate(False)

        self.preview_label = ctk.CTkLabel(
            self.preview_frame, text="🐾\n\nNothing yet...",
            font=self.font_label, text_color=TEXT_DIM,
        )
        self.preview_label.pack(expand=True)

        self.preview_info = ctk.CTkLabel(
            right, text="", font=self.font_small, text_color=TEXT_DIM,
            wraplength=400, justify="left",
        )
        self.preview_info.pack(padx=15, pady=(0, 10))

        ctk.CTkLabel(right, text="📋 Log", font=self.font_label,
                     text_color=TEXT).pack(anchor="w", padx=15, pady=(0, 5))

        self.log_box = ctk.CTkTextbox(
            right, fg_color=self.theme["bg_light"], text_color=TEXT,
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8, wrap="word",
        )
        self.log_box.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.log_box.configure(state="disabled")

    # ========================================================
    # TAB 2: GALLERY
    # ========================================================
    def _build_gallery_tab(self):
        tab = self.tabview.tab("🖼️ Gallery")
        tab.configure(fg_color=self.theme["bg_dark"])

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(top, text="🖼️ Downloaded Files", font=self.font_title,
                     text_color=self.theme["primary"]).pack(side="left")

        ctk.CTkButton(
            top, text="🔄 Refresh", width=100, height=32,
            fg_color=self.theme["secondary"], hover_color=self.theme["secondary_hover"],
            font=self.font_small, command=self._refresh_gallery,
        ).pack(side="right")

        self.gallery_scroll = ctk.CTkScrollableFrame(
            tab, fg_color=self.theme["bg_mid"], corner_radius=10,
        )
        self.gallery_scroll.pack(fill="both", expand=True, padx=15, pady=15)

        self._refresh_gallery()

    # ========================================================
    # TAB 3: SETTINGS
    # ========================================================
    def _build_settings_tab(self):
        tab = self.tabview.tab("⚙️ Settings")
        tab.configure(fg_color=self.theme["bg_dark"])

        scroll = ctk.CTkScrollableFrame(tab, fg_color=self.theme["bg_mid"], corner_radius=10)
        scroll.pack(fill="both", expand=True, padx=15, pady=15)

        # --- API ---
        self._section(scroll, "🔑 API Credentials")

        self.username_entry = self._entry(scroll, "Username", self.config.get("username", ""))
        self.api_key_entry = self._entry(scroll, "API Key", self.config.get("api_key", ""), show="*")

        ctk.CTkButton(
            scroll, text="💾 Save API Credentials", height=36,
            fg_color=self.theme["primary"], hover_color=self.theme["primary_hover"],
            text_color="#1a1625", font=self.font_button, command=self._save_api,
        ).pack(anchor="w", padx=15, pady=(5, 10))

        ctk.CTkLabel(
            scroll,
            text="ℹ️  Get your API key: e621.net → My Account → Manage API Access\n"
                 "   ⚠️  Without API key: max ~320 posts per search",
            font=self.font_small, text_color=TEXT_DIM, justify="left",
        ).pack(anchor="w", padx=15, pady=(0, 15))

        # --- Download ---
        self._section(scroll, "📥 Download Settings")

        self.auto_convert_var = ctk.BooleanVar(value=self.config.get("auto_convert", True))
        self._switch(scroll, "Auto-convert videos to MP4", self.auto_convert_var)

        self.delete_original_var = ctk.BooleanVar(value=self.config.get("delete_original", True))
        self._switch(scroll, "Delete original after conversion", self.delete_original_var)

        ctk.CTkLabel(scroll, text="Video Quality:", font=self.font_label,
                     text_color=TEXT).pack(anchor="w", padx=15, pady=(10, 4))

        self.quality_var = ctk.StringVar(value=self.config.get("video_quality", "High"))
        ctk.CTkOptionMenu(
            scroll, values=["Low", "Medium", "High", "Ultra"],
            variable=self.quality_var,
            fg_color=self.theme["secondary"], button_color=self.theme["primary"],
            button_hover_color=self.theme["primary_hover"], font=self.font_small,
        ).pack(anchor="w", padx=15, pady=(0, 10))

        ctk.CTkLabel(scroll, text="Folder Structure:", font=self.font_label,
                     text_color=TEXT).pack(anchor="w", padx=15, pady=(10, 4))

        self.folder_var = ctk.StringVar(value=self.config.get("folder_structure", "none"))
        ctk.CTkOptionMenu(
            scroll, values=["none", "artist", "pool", "tag"],
            variable=self.folder_var,
            fg_color=self.theme["secondary"], button_color=self.theme["primary"],
            button_hover_color=self.theme["primary_hover"], font=self.font_small,
        ).pack(anchor="w", padx=15, pady=(0, 15))

        # --- Appearance ---
        self._section(scroll, "🎨 Appearance")

        ctk.CTkLabel(scroll, text="Theme:", font=self.font_label,
                     text_color=TEXT).pack(anchor="w", padx=15, pady=(10, 4))

        self.theme_var = ctk.StringVar(value=self.config.get("theme", "Furry Orange"))
        ctk.CTkOptionMenu(
            scroll, values=list(THEMES.keys()),
            variable=self.theme_var,
            fg_color=self.theme["secondary"], button_color=self.theme["primary"],
            button_hover_color=self.theme["primary_hover"], font=self.font_small,
            command=self._change_theme,
        ).pack(anchor="w", padx=15, pady=(0, 10))

        # --- Data ---
        self._section(scroll, "💾 Data & Backup")

        data_row = ctk.CTkFrame(scroll, fg_color="transparent")
        data_row.pack(fill="x", padx=15, pady=(10, 15))

        ctk.CTkButton(
            data_row, text="📤 Export", height=34, width=140,
            fg_color=self.theme["secondary"], hover_color=self.theme["secondary_hover"],
            font=self.font_small, command=self._export_settings,
        ).pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            data_row, text="📥 Import", height=34, width=140,
            fg_color=self.theme["secondary"], hover_color=self.theme["secondary_hover"],
            font=self.font_small, command=self._import_settings,
        ).pack(side="left")

        ctk.CTkButton(
            scroll, text="💾 Save All Settings", height=44,
            fg_color=self.theme["primary"], hover_color=self.theme["primary_hover"],
            text_color="#1a1625", font=self.font_button,
            command=self._save_all,
        ).pack(fill="x", padx=15, pady=(10, 20))

    # ========================================================
    # UPDATE CHECKER
    # ========================================================
    def _check_updates_auto(self):
        """Auto-check updates every 24h"""
        try:
            cfg = ConfigManager.load()
            if not cfg.get("auto_check_updates", True):
                return
            last = cfg.get("last_update_check", "")
            if last:
                try:
                    from datetime import datetime as dt
                    last_dt = dt.fromisoformat(last)
                    if (dt.now() - last_dt).total_seconds() < 86400:
                        return
                except Exception:
                    pass
            self._check_updates(silent=True)
            from datetime import datetime as dt
            ConfigManager.update(last_update_check=dt.now().isoformat())
        except Exception:
            pass

    def _check_updates(self, silent=False):
        """Check GitHub for new version"""
        try:
            if not silent:
                self.log("Checking for updates...")
            r = requests.get(VERSION_URL, timeout=10,
                             headers={"User-Agent": f"YiffDownloader/{__version__}"})
            if r.status_code != 200:
                if not silent:
                    self.log(f"Cannot check updates (HTTP {r.status_code})", "warning")
                    messagebox.showwarning("Update Check",
                        f"Could not reach GitHub. HTTP {r.status_code}")
                return
            latest = r.text.strip()
            current = __version__
            if latest == current:
                if not silent:
                    self.log(f"You're on latest version ({current})", "success")
                    messagebox.showinfo("Up to Date",
                        f"You are running the latest version! (v{current})")
                return
            self.log(f"New version available: {latest} (current: {current})", "success")
            result = messagebox.askyesno(
                "Update Available",
                f"A new version is available!\nCurrent: {current}\nLatest: {latest}\n\nOpen GitHub to download?",
            )
            if result:
                import webbrowser
                webbrowser.open(REPO_URL)
        except requests.exceptions.Timeout:
            if not silent:
                self.log("Update check timed out", "warning")
        except Exception as e:
            if not silent:
                self.log(f"Update check failed: {e}", "warning")

    # ========================================================
    # TAB 4: ABOUT
    # ========================================================
    def _build_about_tab(self):
        tab = self.tabview.tab("ℹ️ About")
        tab.configure(fg_color=self.theme["bg_dark"])

        scroll = ctk.CTkScrollableFrame(tab, fg_color=self.theme["bg_mid"], corner_radius=12)
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(scroll, text="🐾", font=ctk.CTkFont(size=60),
                     text_color=self.theme["primary"]).pack(pady=(20, 5))

        ctk.CTkLabel(scroll, text="Yiff Downloader", font=self.font_logo,
                     text_color=self.theme["primary"]).pack()

        ctk.CTkLabel(scroll, text=f"Version {__version__}", font=self.font_small,
                     text_color=TEXT_DIM).pack(pady=(0, 10))

        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(pady=(5, 15))

        ctk.CTkButton(
            btn_row, text="Check for Updates", height=36, width=170,
            fg_color=self.theme["primary"], hover_color=self.theme["primary_hover"],
            text_color="#1a1625", font=self.font_button,
            command=self._check_updates,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_row, text="Open GitHub", height=36, width=140,
            fg_color=self.theme["secondary"], hover_color=self.theme["secondary_hover"],
            font=self.font_button,
            command=lambda: __import__("webbrowser").open(REPO_URL),
        ).pack(side="left", padx=5)

        desc = (
            "A modern furry-themed downloader for e621.net" + chr(10) +
            "with auto MP4 conversion, live preview & more." + chr(10) + chr(10) +
            "Features:" + chr(10) +
            "  - Bulk download with pagination" + chr(10) +
            "  - Auto-convert videos to MP4" + chr(10) +
            "  - Live preview of downloads" + chr(10) +
            "  - Skip button to filter on-the-fly" + chr(10) +
            "  - Gallery of downloaded files" + chr(10) +
            "  - 4 Themes" + chr(10) +
            "  - Statistics & progress tracking"
        )
        ctk.CTkLabel(scroll, text=desc, font=self.font_label,
                     text_color=TEXT, justify="center").pack(pady=10)

        stats = ConfigManager.load_stats()
        stats_text = (
            "Your Stats:" + chr(10) +
            "   Downloads: " + str(stats.get("total_downloads", 0)) + chr(10) +
            "   Conversions: " + str(stats.get("total_conversions", 0)) + chr(10) +
            "   Total Size: " + Utils.fmt_size(stats.get("total_size_mb", 0)) + chr(10) +
            "   Total Time: " + Utils.fmt_time(stats.get("total_time_seconds", 0))
        )
        ctk.CTkLabel(scroll, text=stats_text, font=self.font_small,
                     text_color=TEXT_DIM, justify="center").pack(pady=15)

        ctk.CTkLabel(scroll, text="Made with love for the furry community",
                     font=self.font_small, text_color=TEXT_DIM).pack(pady=(5, 20))

    # ========================================================
    # HELPERS
    # ========================================================
    def _section(self, parent, text):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=15, pady=(15, 5))
        ctk.CTkLabel(f, text=text, font=self.font_title,
                     text_color=self.theme["primary"]).pack(anchor="w")

    def _entry(self, parent, label, value="", show=None):
        ctk.CTkLabel(parent, text=label, font=self.font_label,
                     text_color=TEXT).pack(anchor="w", padx=15, pady=(5, 2))
        e = ctk.CTkEntry(
            parent, fg_color=self.theme["bg_light"], text_color=TEXT,
            border_color=self.theme["secondary"], font=self.font_label,
            height=36, show=show,
        )
        e.insert(0, value)
        e.pack(fill="x", padx=15, pady=(0, 5))
        return e

    def _switch(self, parent, text, variable):
        ctk.CTkSwitch(
            parent, text=text, variable=variable,
            font=self.font_label, text_color=TEXT,
            progress_color=self.theme["primary"],
        ).pack(anchor="w", padx=15, pady=6)

    def _refresh_history(self):
        for w in self.history_frame.winfo_children():
            w.destroy()
        history = ConfigManager.load_history()
        if not history:
            ctk.CTkLabel(self.history_frame, text="(no history yet)",
                         font=self.font_small, text_color=TEXT_DIM).pack(pady=5)
            return
        for tags in history[:10]:
            ctk.CTkButton(
                self.history_frame, text=tags, height=26, anchor="w",
                fg_color="transparent", hover_color=self.theme["secondary"],
                text_color=TEXT_DIM, font=self.font_small,
                command=lambda t=tags: self._use_history(t),
            ).pack(fill="x", pady=1)

    def _use_history(self, tags):
        self.query_entry.delete(0, "end")
        self.query_entry.insert(0, tags)

    def _choose_dir(self):
        path = filedialog.askdirectory(initialdir=self.config["download_dir"])
        if path:
            self.config["download_dir"] = path
            ConfigManager.update(download_dir=path)
            self.dir_label.configure(text=path)
            self.log(f"📁 Download folder: {path}")

    # ========================================================
    # THEME
    # ========================================================
    def _change_theme(self, choice):
        ConfigManager.update(theme=choice)
        self.config["theme"] = choice
        self.theme = THEMES.get(choice, THEMES["Furry Orange"])
        self.log(f"🎨 Theme: {choice} (restart to apply fully)", "info")
        messagebox.showinfo("Theme", f"Theme '{choice}' saved.\nRestart the app to see full effect.")

    # ========================================================
    # STARTUP CHECKS - IN-APP WARNINGS
    # ========================================================
    def _startup_checks(self):
        cfg = ConfigManager.load()
        # API key warning
        if not cfg.get("api_key") or not cfg.get("username"):
            self.log("⚠️ No API key set!", "warning")
            self.log("   Max 320 posts per search without API key.", "warning")
            self.log("   Go to ⚙️ Settings → enter Username + API Key.", "warning")
            messagebox.showwarning(
                "🐾 API Key Missing",
                "You haven't set your e621 API credentials yet!\n\n"
                "Without an API key:\n"
                "  • Maximum 320 posts per search\n"
                "  • Some tags may be restricted\n\n"
                "Get your key: e621.net → My Account → Manage API Access\n\n"
                "Then go to Settings tab to enter it. 🐾"
            )
        else:
            self.log(f"✅ API credentials loaded for: {cfg.get('username')}")

        # ffmpeg check
        if not Utils.find_ffmpeg():
            self.log("⚠️ ffmpeg not found!", "error")
            messagebox.showerror(
                "🎬 ffmpeg Missing",
                "ffmpeg was not found on your system!\n\n"
                "Auto-conversion to MP4 will be disabled.\n\n"
                "Install it with:\n"
                "sudo apt install ffmpeg"
            )

    # ========================================================
    # LOG
    # ========================================================
    def log(self, message, level="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
        prefix = icons.get(level, "•")
        line = f"[{ts}] {prefix} {message}\n"

        self.log_box.configure(state="normal")
        self.log_box.insert("end", line)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

        if level == "error":
            self.status_label.configure(text="● Error", text_color=ERROR)
        elif level == "success":
            self.status_label.configure(text="● Success", text_color=SUCCESS)
        elif level == "warning":
            self.status_label.configure(text="● Warning", text_color=WARNING)

    # ========================================================
    # PREVIEW (ANIMATED GIF)
    # ========================================================
    def update_preview(self, filepath):
        try:
            path = Path(filepath)
            if not path.exists():
                return
            ext = path.suffix.lower()

            if ext == ".gif":
                self._show_animated_gif(path)
            elif ext in {".webm", ".mp4", ".mkv", ".avi", ".mov", ".flv"}:
                self._show_video_gif(path)
            elif ext in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
                img = Image.open(path)
                self._set_preview_image(img)

            size_mb = path.stat().st_size / (1024 * 1024)
            self.preview_info.configure(
                text=f"📄 {path.name}\n📦 {size_mb:.2f} MB\n📁 {path.parent}"
            )
        except Exception as e:
            self.log(f"Preview error: {e}", "error")

    def _set_preview_image(self, img):
        img.thumbnail((400, 300), Image.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(img)
        self.preview_label.configure(image=self.preview_photo, text="")

    def _show_animated_gif(self, gif_path):
        """Show animated GIF in preview box"""
        try:
            # Stop any previous animation
            self._stop_animation()

            self.gif_frames = []
            self.gif_durations = []
            gif = Image.open(gif_path)

            for frame in range(gif.n_frames):
                gif.seek(frame)
                frame_img = gif.copy().convert("RGBA")
                frame_img.thumbnail((400, 300), Image.LANCZOS)
                self.gif_frames.append(ImageTk.PhotoImage(frame_img))
                self.gif_durations.append(gif.info.get("duration", 100))

            self.gif_index = 0
            self._animate_gif()
        except Exception as e:
            self.log(f"GIF preview error: {e}", "error")

    def _animate_gif(self):
        if not hasattr(self, "gif_frames") or not self.gif_frames:
            return
        try:
            self.preview_label.configure(image=self.gif_frames[self.gif_index], text="")
            self.gif_index = (self.gif_index + 1) % len(self.gif_frames)
            delay = self.gif_durations[self.gif_index]
            self.gif_job = self.after(delay, self._animate_gif)
        except Exception:
            pass

    def _stop_animation(self):
        if hasattr(self, "gif_job") and self.gif_job:
            try:
                self.after_cancel(self.gif_job)
            except Exception:
                pass
            self.gif_job = None
        if hasattr(self, "gif_frames"):
            self.gif_frames = []

    def _show_video_gif(self, video_path):
        """Convert middle 10 seconds of video to animated GIF for preview"""
        try:
            self._stop_animation()
            ffmpeg = Utils.find_ffmpeg()
            if not ffmpeg:
                self.preview_label.configure(text="ffmpeg not found", image="")
                return

            duration = self._get_video_duration(video_path)
            PREVIEW_DURATION = 10

            if duration <= PREVIEW_DURATION:
                start_time = 0
            else:
                start_time = (duration - PREVIEW_DURATION) / 2

            tmp_gif = Path("/tmp") / "yiff_preview_anim.gif"
            cmd = [
                ffmpeg,
                "-ss", str(start_time),
                "-t", str(PREVIEW_DURATION),
                "-i", str(video_path),
                "-vf", "fps=10,scale=400:-1:flags=lanczos",
                "-loop", "0",
                str(tmp_gif), "-y", "-loglevel", "error",
            ]
            r = subprocess.run(cmd, capture_output=True, timeout=60)
            if r.returncode == 0 and tmp_gif.exists():
                self._show_animated_gif(tmp_gif)
            else:
                img = self._extract_video_frame(video_path)
                if img:
                    self._set_preview_image(img)
                else:
                    self.preview_label.configure(text="cannot preview", image="")
        except Exception as e:
            self.log(f"Video preview error: {e}", "error")

    def _get_video_duration(self, video_path):
        """Get video duration in seconds using ffprobe"""
        try:
            ffprobe = "/usr/bin/ffprobe"
            if not os.path.isfile(ffprobe):
                ffprobe = "ffprobe"
            cmd = [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ]
            r = subprocess.run(cmd, capture_output=True, timeout=10)
            if r.returncode == 0:
                return float(r.stdout.decode().strip())
        except Exception:
            pass
        return 0

    def _extract_video_frame(self, video_path):
        ffmpeg = Utils.find_ffmpeg()
        if not ffmpeg:
            return None
        tmp = Path("/tmp") / "yiff_frame.jpg"
        cmd = [
            ffmpeg, "-ss", "1", "-i", str(video_path),
            "-vframes", "1", "-vf", "scale=400:-1",
            str(tmp), "-y", "-loglevel", "error",
        ]
        try:
            subprocess.run(cmd, timeout=10, capture_output=True)
            if tmp.exists():
                return Image.open(tmp)
        except Exception:
            pass
        return None

    # ========================================================
    # GALLERY
    # ========================================================
    def _refresh_gallery(self):
        for w in self.gallery_scroll.winfo_children():
            w.destroy()
        d = Path(self.config["download_dir"])
        if not d.exists():
            ctk.CTkLabel(self.gallery_scroll, text="📁 Empty folder",
                         font=self.font_label, text_color=TEXT_DIM).pack(pady=20)
            return
        files = sorted(
            [f for f in d.rglob("*") if f.is_file() and
             f.suffix.lower() in {".mp4", ".webm", ".jpg", ".jpeg", ".png", ".gif", ".webp"}],
            key=lambda f: f.stat().st_mtime, reverse=True,
        )[:100]
        if not files:
            ctk.CTkLabel(self.gallery_scroll, text="🖼️ No files yet",
                         font=self.font_label, text_color=TEXT_DIM).pack(pady=20)
            return
        for f in files:
            row = ctk.CTkFrame(self.gallery_scroll, fg_color=self.theme["bg_light"], corner_radius=8)
            row.pack(fill="x", padx=5, pady=3)
            icon = "🎬" if f.suffix.lower() in {".mp4", ".webm"} else "🖼️"
            size_mb = f.stat().st_size / (1024 * 1024)
            ctk.CTkLabel(row, text=f"{icon}  {f.name}",
                         font=self.font_small, text_color=TEXT, anchor="w",
                         ).pack(side="left", padx=10, pady=8)
            ctk.CTkLabel(row, text=f"{size_mb:.2f} MB",
                         font=self.font_small, text_color=TEXT_DIM,
                         ).pack(side="right", padx=10)

    # ========================================================
    # SETTINGS ACTIONS
    # ========================================================
    def _save_api(self):
        ConfigManager.update(
            username=self.username_entry.get().strip(),
            api_key=self.api_key_entry.get().strip(),
        )
        self.config = ConfigManager.load()
        self.log("🔑 API credentials saved!", "success")
        messagebox.showinfo("Saved", "API credentials saved! 🐾")

    def _save_all(self):
        ConfigManager.update(
            username=self.username_entry.get().strip(),
            api_key=self.api_key_entry.get().strip(),
            auto_convert=self.auto_convert_var.get(),
            delete_original=self.delete_original_var.get(),
            video_quality=self.quality_var.get(),
            folder_structure=self.folder_var.get(),
            theme=self.theme_var.get(),
            safe_mode=self.safe_mode_var.get(),
        )
        self.config = ConfigManager.load()
        self.log("💾 All settings saved!", "success")
        messagebox.showinfo("Saved", "All settings saved! 🐾")

    def _export_settings(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")],
            initialfile="yiff_downloader_settings.json",
        )
        if p:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            self.log(f"📤 Exported: {os.path.basename(p)}", "success")

    def _import_settings(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if p:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    imported = json.load(f)
                ConfigManager.save(imported)
                self.config = ConfigManager.load()
                self.log("📥 Imported! Restart recommended.", "success")
            except Exception as e:
                self.log(f"Import error: {e}", "error")

    # ========================================================
    # DOWNLOAD ACTIONS
    # ========================================================
    def _start_download(self):
        tags = self.query_entry.get().strip()
        if not tags:
            messagebox.showwarning("Missing", "Please enter tags! 🐾")
            return

        try:
            limit = int(self.limit_entry.get().strip())
            if limit <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid", "Limit must be a positive number!")
            return

        # WARN: limit > 320 without API key
        if limit > 320 and (not self.config.get("api_key") or not self.config.get("username")):
            messagebox.showwarning(
                "⚠️ API Key Required",
                f"You requested {limit} posts, but without an API key\n"
                f"the maximum is 320 posts per search.\n\n"
                f"To download more:\n"
                f"1. Go to Settings tab\n"
                f"2. Add your Username and API Key\n"
                f"3. Try again\n\n"
                f"Download will continue with a limit of 320. 🐾"
            )
            limit = 320

        download_dir = self.config["download_dir"]
        try:
            os.makedirs(download_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot create folder:\n{e}")
            return

        ConfigManager.add_history(tags)
        ConfigManager.update(last_query=tags, last_limit=limit)
        self._refresh_history()

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        self.start_btn.configure(state="disabled", text="⏳ Working...")
        self.pause_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")
        self.skip_btn.configure(state="normal")
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progress: 0 / 0")
        self.status_label.configure(text="● Downloading", text_color=INFO)

        self.download_thread = threading.Thread(
            target=self._download_worker, args=(tags, limit, download_dir), daemon=True,
        )
        self.download_thread.start()

    def _download_worker(self, tags, limit, download_dir):
        try:
            self.downloader = Downloader(
                cfg=self.config,
                log_cb=self.log,
                preview_cb=lambda p: self.after(0, self.update_preview, p),
                progress_cb=lambda c, t: self.after(0, self._update_progress, c, t),
                stats_cb=lambda **kw: ConfigManager.update_stats(**kw),
            )
            self.log(f"🔍 Searching: {tags} (limit: {limit})")
            api = E621API(self.config)
            result = api.fetch_all(
                tags, limit,
                progress_cb=lambda m: self.log(m),
                stop_flag=self.downloader.stop_flag,
            )
            if isinstance(result, dict) and "error" in result:
                self.log(f"API Error: {result['error']}", "error")
                self.after(0, lambda: messagebox.showerror(
                    "❌ API Error",
                    f"Could not fetch posts:\n{result['error']}\n\n"
                    f"Check:\n• Your internet / VPN\n• Your API key\n• Tag spelling"
                ))
                return
            posts = result.get("posts", [])
            if not posts:
                self.log("No posts found!", "warning")
                self.after(0, lambda: messagebox.showwarning(
                    "No Results", "No posts found for these tags. 🐾"
                ))
                return
            self.log(f"Found {len(posts)} posts. Starting download...", "success")
            self.downloader.process(posts, download_dir)
        except Exception as e:
            self.log(f"Fatal error: {e}", "error")
        finally:
            self.after(0, self._on_finished)

    def _update_progress(self, cur, total):
        self.progress_label.configure(text=f"Progress: {cur} / {total}")
        if total > 0:
            self.progress_bar.set(cur / total)

    def _toggle_pause(self):
        if not self.downloader:
            return
        if self.downloader.pause_flag.is_set():
            self.downloader.resume()
            self.pause_btn.configure(text="⏸️")
            self.log("▶️ Resumed")
        else:
            self.downloader.pause()
            self.pause_btn.configure(text="▶️")
            self.log("⏸️ Paused", "warning")

    def _stop_download(self):
        if self.downloader:
            self.downloader.stop()
            self.log("🛑 Stopping...", "warning")

    def _skip_current(self):
        if self.downloader:
            self.downloader.skip()
            self.log("⏭️ Skipping current file...", "warning")

    def _on_finished(self):
        self.start_btn.configure(state="normal", text="🐾 Start Download")
        self.pause_btn.configure(state="disabled", text="⏸️")
        self.stop_btn.configure(state="disabled")
        self.skip_btn.configure(state="disabled")
        self.status_label.configure(text="● Ready", text_color=SUCCESS)
        self._stop_animation()
        self._refresh_gallery()


# ============================================================
# 🚀 MAIN
# ============================================================
def main():
    app = YiffDownloader()

    def on_close():
        if app.downloader and app.download_thread and app.download_thread.is_alive():
            if messagebox.askyesno("Quit", "Download in progress. Quit anyway? 🐾"):
                app.downloader.stop()
                app._stop_animation()
                app.destroy()
        else:
            app._stop_animation()
            app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
