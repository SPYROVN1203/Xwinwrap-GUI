# xwinwrap Wallpaper Manager

A GTK3 GUI for managing **video/live wallpapers** on Linux using `xwinwrap` + `mpv`.  
Inspired by Lively Wallpaper / Wallpaper Engine for Windows.

![screenshot](https://img.shields.io/badge/GTK3-Python-blue)
![platform](https://img.shields.io/badge/platform-Linux-lightgrey)

---

## Features

- **Library** — Browse, search, and manage your wallpaper collection in a grid view
- **Video Thumbnails** — Auto-generated thumbnails from the first frame of each video
- **Playback Controls** — Start, Restart, and Stop wallpapers directly from the sidebar
- **Dark / Light Theme** — Toggle between dark and light interface themes
- **Smart Pause** — Automatically pause video playback when a fullscreen or maximized window is active
- **Rich Settings**:
  - Display mode: Fullscreen or custom window with geometry
  - FPS limit (10–165)
  - Brightness adjustment (0–100%)
  - Playback speed (25–200%)
  - Scale quality (auto / 1080p / 720p / 540p)
  - Audio toggle, looping, GPU decoding (vaapi)
  - Auto-start with system
  - Advanced: sticky workspaces, ARGB transparency, override redirect, screen/output, desktop type
- **Command Preview** — View the generated `xwinwrap` + `mpv` command in real time
- **Export** — Copy command to clipboard or save as a `.sh` script
- **History** — Remembers your wallpapers across sessions with persistent storage
- **Language** — English / Vietnamese (Tiếng Việt) interface

---

## Dependencies

### System Packages

```bash
# Required
xwinwrap    # Window layer wrapper
mpv         # Video player (≥ 0.37 recommended)
xdotool     # Window state detection
xprop       # X11 property inspection
socat       # MPV IPC communication
ffmpeg      # Thumbnail generation

# Python
python3-gi  # GTK3 bindings for Python
```

### Install on Debian / Ubuntu

```bash
sudo apt install xwinwrap mpv xdotool xprop socat ffmpeg python3-gi
```

### Install on Arch Linux

```bash
sudo pacman -S xwinwrap mpv xdotool xprop socat ffmpeg python-gobject
```

> **Note:** `xwinwrap` may need to be built from source on some distributions.  
> See [ujjwal96/xwinwrap](https://github.com/ujjwal96/xwinwrap).

---

## Installation

```bash
git clone https://github.com/yourusername/xwinwrap-gui.git
cd xwinwrap-gui
python3 gui.py
```

No pip install required — pure Python with GTK3.

---

## Usage

### Adding Wallpapers
1. Click **Add wallpaper** in the sidebar
2. Select a video file (`.mp4`, `.mkv`, `.webm`, `.avi`, `.mov`, `.gif`, `.png`, `.jpg`)
3. A thumbnail is auto-generated and the wallpaper appears in the Library grid

### Applying a Wallpaper
- **Click** a card in the Library to select it, then click **Start** in the sidebar
- Or right-click (menu button) and choose **Apply now**

### Managing Playback
| Action | Button | Description |
|---|---|---|
| Start | ▶ Start | Launch the selected wallpaper |
| Restart | ⟳ Restart | Stop and re-launch the current wallpaper |
| Stop | ■ Stop | Terminate the wallpaper process |

### Settings
Navigate to the **Settings** tab to configure:
- Display mode and geometry
- FPS, brightness, speed
- Scale quality
- Smart behavior (pause on fullscreen/maximize, audio, loop, GPU decode)
- Auto-start with system
- Advanced X11 options
- View, copy, or export the generated command

### Keyboard & Interface
- **Library** — Browse all added wallpapers in a 3-column grid
- **Search** — Filter wallpapers by name or path
- **Language** — Toggle English / Vietnamese via the titlebar button
- **Theme** — Toggle dark / light theme via the titlebar button

---

## File Structure

| File | Purpose |
|---|---|
| `gui.py` | GTK3 interface — sidebar, library grid, settings, status bar |
| `tools.py` | Core engine — config builder, process manager, auto-start, history, thumbnails |
| `lang.py` | English / Vietnamese translations |
| `AGENTS.md` | Project context for AI assistants |

### Data Storage

| Path | Contents |
|---|---|
| `~/.config/xwinwrap-gui/history.json` | Wallpaper history (JSON array) |
| `~/.config/xwinwrap-gui/thumbnails/` | Generated thumbnail images (JPEG) |
| `~/.config/autostart/xwinwrap-wallpaper.desktop` | Auto-start desktop entry |

---

## Technical Details

### How It Works

The application builds a command in the form:

```
xwinwrap [options] -- mpv [mpv-options] /path/to/video.mp4
```

- `xwinwrap` creates a transparent window as a desktop wallpaper layer
- `mpv` renders the video into that window via the `--wid` (window ID) parameter
- The `-d` flag causes xwinwrap to daemonize, so process tracking uses `pgrep`

### Thumbnail Generation

Thumbnails are generated with `ffmpeg` (frame at `00:00`, scaled to 320×180) and cached in `~/.config/xwinwrap-gui/thumbnails/`. If `ffmpeg` is unavailable, a fallback "No preview" image is created via Pillow.

### Mpv Display FPS

Uses `--display-fps-override` instead of the deprecated `--display-fps` (removed in mpv ≥ 0.37).

### Wallpaper History

Wallpapers are tracked in `~/.config/xwinwrap-gui/history.json`. The `WallpaperHistory` class manages add, remove, search, and thumbnail regeneration.

---

## License

MIT

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.
