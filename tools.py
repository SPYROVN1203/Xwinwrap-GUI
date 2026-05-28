import os
import re
import time
import json
import shlex
import signal
import shutil
import logging
import threading
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field, asdict
 
logger = logging.getLogger("xwinwrap-tools")


@dataclass
class XwinwrapConfig:
    video_path: str = ""
    mode: str = "fs"
    geometry: str = "1920x1080+0+0"
    fps: int = 30
    brightness: int = 100
    speed: int = 100
    scale: str = ""
    audio: bool = False
    loop: bool = True
    hwdec: bool = True
    fullscreen_pause: bool = True
    maximize_pause: bool = True
    sticky: bool = True
    argb: bool = False
    override_redirect: bool = False
    fdt_type: int = -1
    screen: str = ""
    autostart: bool = False

    def build_xwinwrap_args(self) -> List[str]:
        args: List[str] = []
        if self.mode == "fs":
            args.append("-fs")
            if self.fdt_type >= 0:
                args.append(f"-fdt={self.fdt_type}")
            else:
                args.append("-fdt")
        else:
            args.extend(["-g", self.geometry])
        args.extend(["-ni", "-b", "-nf", "-d"])
        if self.sticky:
            args.append("-s")
        if self.argb:
            args.append("-argb")
        if self.override_redirect:
            args.append("-ov")
        if self.screen:
            screen_val = self.screen.replace("--screen=", "").strip()
            if screen_val:
                args.append(f"--screen={screen_val}")
        return args

    def build_mpv_args(self) -> List[str]:
        args: List[str] = ["-wid", "WID"]
        if self.loop:
            args.append("--loop")
        if not self.audio:
            args.append("--no-audio")
        args.append("--no-osc")
        args.append("--no-osd-bar")
        if self.hwdec:
            args.append("--hwdec=vaapi")
        args.append(f"--display-fps-override={self.fps}")
        if self.scale:
            args.append(f"--vf=scale={self.scale}")
        if self.brightness != 100:
            args.append(f"--brightness={self.brightness - 100}")
        if self.speed != 100:
            args.append(f"--speed={self.speed / 100:.2f}")
        if self.fullscreen_pause or self.maximize_pause:
            args.append("--input-ipc-server=/tmp/xwinwrap-mpv.sock")
        return args

    def build_command_list(self) -> List[str]:
        xw = self.build_xwinwrap_args()
        mpv = self.build_mpv_args()
        return ["xwinwrap"] + xw + ["--", "mpv"] + mpv + [self.video_path]

    def build_command_str(self) -> str:
        parts = self.build_command_list()
        return " ".join(shlex.quote(p) for p in parts)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "XwinwrapConfig":
        valid = set(cls.__dataclass_fields__.keys())
        kwargs = {k: v for k, v in d.items() if k in valid}
        return cls(**kwargs)


class WallpaperManager:
    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._monitor: Optional["FullscreenMonitor"] = None
        self._config: Optional[XwinwrapConfig] = None
        self._on_status_changed = None

    def set_status_callback(self, callback):
        self._on_status_changed = callback

    @property
    def is_running(self) -> bool:
        if self._find_xwinwrap_pid():
            return True
        self._process = None
        return False

    def start(self, config: XwinwrapConfig) -> Tuple[bool, str]:
        if self.is_running:
            self.stop()

        cmd = config.build_command_list()
        logger.info("Starting: %s", " ".join(shlex.quote(p) for p in cmd))

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                preexec_fn=os.setpgrp,
            )
        except FileNotFoundError:
            return False, "Không tìm thấy lệnh xwinwrap hoặc mpv"
        except Exception as e:
            return False, str(e)

        # xwinwrap -d daemonizes → parent exits, child keeps running
        # Wait briefly then check by pgrep
        time.sleep(1.0)
        proc.stderr.read()
        proc.poll()

        if not self._find_xwinwrap_pid():
            return False, (
                "Không tìm thấy tiến trình xwinwrap. "
                "Kiểm tra: file video tồn tại? xwinwrap có chạy được?"
            )

        self._process = proc
        self._config = config

        self._config = config

        if config.fullscreen_pause or config.maximize_pause:
            self._monitor = FullscreenMonitor(
                ipc_path="/tmp/xwinwrap-mpv.sock",
                check_fullscreen=config.fullscreen_pause,
                check_maximize=config.maximize_pause,
            )
            self._monitor.start()

        if self._on_status_changed:
            self._on_status_changed(True)
        return True, ""

    def stop(self) -> None:
        if self._monitor:
            self._monitor.stop()
            self._monitor = None

        subprocess.run(
            ["pkill", "-f", "xwinwrap.*mpv"],
            capture_output=True,
        )
        subprocess.run(
            ["pkill", "-f", r"mpv\s+-wid"],
            capture_output=True,
        )
        self._process = None

        if self._on_status_changed:
            self._on_status_changed(False)

    def toggle(self) -> bool:
        if self.is_running:
            self.stop()
            return False
        else:
            if self._config:
                self.start(self._config)
            return True

    def get_stats(self) -> Dict[str, str]:
        if not self.is_running:
            return {"ram": "—", "cpu": "—"}
        try:
            mpv_pid = self._find_mpv_pid()
            if not mpv_pid:
                return {"ram": "—", "cpu": "—"}
            ram = self._get_ram(mpv_pid)
            cpu = self._get_cpu(mpv_pid)
            return {"ram": ram, "cpu": cpu}
        except Exception:
            return {"ram": "—", "cpu": "—"}

    def _find_mpv_pid(self) -> Optional[int]:
        try:
            result = subprocess.run(
                ["pgrep", "-f", r"mpv\s+-wid"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split()[0])
        except Exception:
            pass
        return None

    def _find_xwinwrap_pid(self) -> Optional[int]:
        try:
            result = subprocess.run(
                ["pgrep", "-f", "xwinwrap.*mpv"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split()[0])
        except Exception:
            pass
        return None

    def _get_ram(self, pid: int) -> str:
        try:
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        kb = int(line.split()[1])
                        if kb > 1024:
                            return f"{kb / 1024:.1f}MB"
                        return f"{kb}KB"
        except Exception:
            pass
        return "—"

    def _get_cpu(self, pid: int) -> str:
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "%cpu="],
                capture_output=True, text=True, timeout=3,
            )
            if result.stdout.strip():
                val = float(result.stdout.strip())
                return f"{val:.1f}%"
        except Exception:
            pass
        return "—"


class FullscreenMonitor:
    def __init__(
        self,
        ipc_path: str = "/tmp/xwinwrap-mpv.sock",
        check_fullscreen: bool = True,
        check_maximize: bool = True,
        poll_interval: float = 0.5,
    ):
        self._ipc_path = ipc_path
        self._check_fullscreen = check_fullscreen
        self._check_maximize = check_maximize
        self._poll_interval = poll_interval
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._was_paused = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        self._was_paused = False

    def _run(self):
        while self._running:
            try:
                paused = self._check_should_pause()
                if paused and not self._was_paused:
                    self._send_mpv_command("set pause yes")
                    self._was_paused = True
                elif not paused and self._was_paused:
                    self._send_mpv_command("set pause no")
                    self._was_paused = False
            except Exception:
                pass
            time.sleep(self._poll_interval)

    def _check_should_pause(self) -> bool:
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return False
            win_id = result.stdout.strip()
        except Exception:
            return False

        if self._check_fullscreen:
            try:
                r = subprocess.run(
                    ["xprop", "-id", win_id, "_NET_WM_STATE"],
                    capture_output=True, text=True, timeout=2,
                )
                if "_NET_WM_STATE_FULLSCREEN" in r.stdout:
                    return True
            except Exception:
                pass

        if self._check_maximize:
            try:
                r = subprocess.run(
                    ["xprop", "-id", win_id, "_NET_WM_STATE"],
                    capture_output=True, text=True, timeout=2,
                )
                if "_NET_WM_STATE_MAXIMIZED" in r.stdout:
                    return True
            except Exception:
                pass

        return False

    def _send_mpv_command(self, command: str):
        try:
            payload = json.dumps({"command": command.split()}) + "\n"
            sock_path = f"UNIX-CONNECT:{self._ipc_path}"
            subprocess.run(
                ["socat", "-", sock_path],
                input=payload,
                capture_output=True,
                timeout=2,
            )
        except Exception:
            try:
                subprocess.run(
                    ["bash", "-c", f'echo "{command}" | socat - UNIX-CONNECT:{self._ipc_path}'],
                    capture_output=True,
                    timeout=2,
                )
            except Exception:
                pass


class AutostartManager:
    AUTOSTART_DIR = Path.home() / ".config" / "autostart"
    DESKTOP_FILE = AUTOSTART_DIR / "xwinwrap-wallpaper.desktop"
    SCRIPT_PATH = Path.home() / ".local" / "bin" / "xwinwrap-wallpaper.sh"

    def is_enabled(self) -> bool:
        return self.DESKTOP_FILE.exists()

    def enable(self, command: str) -> Tuple[bool, str]:
        try:
            self.SCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
            script = (
                "#!/bin/bash\n"
                "# xwinwrap-gui autostart\n"
                "sleep 5\n"
                f"{command}\n"
            )
            self.SCRIPT_PATH.write_text(script)
            self.SCRIPT_PATH.chmod(0o755)

            self.AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
            desktop = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=xwinwrap Wallpaper\n"
                "Exec=bash -c 'sleep 5 && "
                + command.replace("'", "'\\''")
                + "'\n"
                "NoDisplay=true\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            self.DESKTOP_FILE.write_text(desktop)
            return True, ""
        except Exception as e:
            return False, str(e)

    def disable(self) -> Tuple[bool, str]:
        try:
            if self.DESKTOP_FILE.exists():
                self.DESKTOP_FILE.unlink()
            if self.SCRIPT_PATH.exists():
                self.SCRIPT_PATH.unlink()
            return True, ""
        except Exception as e:
            return False, str(e)


@dataclass
class HistoryItem:
    path: str
    name: str = ""
    added: str = ""
    thumbnail: str = ""
    kind: str = "video"  # "video" or "image"


class WallpaperHistory:
    DIR = Path.home() / ".config" / "xwinwrap-gui"
    HISTORY_FILE = DIR / "history.json"
    THUMBS_DIR = DIR / "thumbnails"

    def __init__(self):
        self._items: List[HistoryItem] = []
        self._ensure_dirs()
        self.load()

    def _ensure_dirs(self):
        self.DIR.mkdir(parents=True, exist_ok=True)
        self.THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    def load(self):
        self._items.clear()
        if not self.HISTORY_FILE.exists():
            return
        try:
            data = json.loads(self.HISTORY_FILE.read_text())
            for d in data:
                self._items.append(HistoryItem(**d))
        except Exception:
            self._items = []

    def save(self):
        data = [
            {
                "path": it.path,
                "name": it.name,
                "added": it.added,
                "thumbnail": it.thumbnail,
                "kind": it.kind,
            }
            for it in self._items
        ]
        self.HISTORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def get_all(self) -> List[HistoryItem]:
        return list(self._items)

    def search(self, query: str) -> List[HistoryItem]:
        if not query:
            return self.get_all()
        q = query.lower()
        return [it for it in self._items if q in it.name.lower() or q in it.path.lower()]

    def add(self, path: str) -> HistoryItem:
        path_str = str(Path(path).resolve())
        existing = next((it for it in self._items if it.path == path_str), None)
        if existing:
            return existing

        import hashlib
        import datetime

        ext = Path(path_str).suffix.lower()
        kind = "image" if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif") else "video"

        name = Path(path_str).name
        path_hash = hashlib.md5(path_str.encode()).hexdigest()[:12]
        thumb_file = f"{path_hash}.jpg"
        thumb_path = self.THUMBS_DIR / thumb_file

        self._generate_thumbnail(path_str, str(thumb_path))

        item = HistoryItem(
            path=path_str,
            name=name,
            added=datetime.datetime.now().isoformat(timespec="seconds"),
            thumbnail=thumb_file if thumb_path.exists() else "",
            kind=kind,
        )
        self._items.insert(0, item)
        self.save()
        return item

    def regenerate_thumbnails(self):
        for item in self._items:
            if not item.path or not os.path.isfile(item.path):
                continue
            import hashlib
            path_hash = hashlib.md5(item.path.encode()).hexdigest()[:12]
            thumb_file = f"{path_hash}.jpg"
            thumb_path = self.THUMBS_DIR / thumb_file
            self._generate_thumbnail(item.path, str(thumb_path))
            if thumb_path.exists():
                item.thumbnail = thumb_file
        self.save()

    def remove(self, path: str):
        self._items = [it for it in self._items if it.path != path]
        self.save()

    def get_thumbnail_path(self, item: HistoryItem) -> str:
        if item.thumbnail:
            p = self.THUMBS_DIR / item.thumbnail
            if p.exists():
                return str(p)
        return ""

    def _generate_thumbnail(self, video_path: str, output_path: str):
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-ss", "00:00:00",
                    "-i", video_path,
                    "-vframes", "1",
                    "-s", "320x180",
                    "-q:v", "3",
                    output_path,
                ],
                capture_output=True,
                timeout=15,
            )
        except Exception:
            try:
                from PIL import Image, ImageDraw
                img = Image.new("RGB", (320, 180), (30, 30, 50))
                draw = ImageDraw.Draw(img)
                draw.text((100, 80), "No preview", fill=(150, 150, 150))
                img.save(output_path, "JPEG", quality=60)
            except Exception:
                pass


def generate_script(command: str, path: Optional[str] = None) -> str:
    script = (
        "#!/bin/bash\n"
        "# Generated by xwinwrap-gui\n"
        "# Kill any existing xwinwrap/mpv wallpaper\n"
        "pkill -f 'xwinwrap.*mpv' 2>/dev/null\n"
        "sleep 1\n"
        f"{command}\n"
    )
    if path:
        Path(path).write_text(script)
        Path(path).chmod(0o755)
    return script


def kill_all() -> None:
    subprocess.run(["pkill", "-f", "xwinwrap.*mpv"], capture_output=True)
    subprocess.run(["pkill", "-f", r"mpv\s+-wid"], capture_output=True)


def check_dependencies() -> List[str]:
    missing = []
    for cmd in ["xwinwrap", "mpv", "xdotool", "xprop"]:
        if not shutil.which(cmd):
            missing.append(cmd)
    if not shutil.which("socat"):
        missing.append("socat")
    return missing
