# xwinwrap-gui — Project Context

## Overview
GTK3 GUI for managing xwinwrap + mpv video wallpapers.
Inspired by Lively Wallpaper / Wallpaper Engine.

## File Structure
| File | Purpose |
|---|---|
| `gui.py` | GTK3 interface — sidebar nav, library grid, settings tab, statusbar |
| `tools.py` | Core engine — config builder, process manager, auto-start, wallpaper history, thumbnail gen |
| `lang.py` | EN/VI translations — 68 keys each |

## Architecture

### gui.py
- `XwinwrapGUI(Gtk.ApplicationWindow)` — main window
  - Titlebar (custom Box, 38px) + lang switch button
  - Sidebar (160px) — nav buttons (Library / Settings), bottom actions (Add, Now Playing, Pause)
  - `Gtk.Stack` — Library page + Settings page
  - Statusbar (26px) — dot + status + engine + RAM
- `Lang` — wraps `lang._()` with toggle `en` ↔ `vi`
- `XwinwrapApp(Gtk.Application)` — app entry

### Library Page
- Toolbar: search `Gtk.Entry` + grid view button
- `Gtk.FlowBox` — wallpaper cards (max 4 cols, homogeneous)
- Card: `Gtk.EventBox` → overlay (thumbnail + badge) + info (name + parent dir + menu button)
- Add card: dashed border "+ Thêm mới"
- Card context menu: `Gtk.Popover` → Apply now / Remove

### Settings Page
- `Gtk.ScrolledWindow` with sections:
  - Status + Start/Stop/Restart buttons + RAM/CPU
  - Video mode: combo (FS/Window) + geometry entry
  - FPS slider (10-165)
  - Brightness slider (0-100%)
  - Speed slider (25-200%)
  - Scale combo (auto/1080p/720p/540p)
  - Behavior toggles: fullscreen pause, maximize pause, audio, loop, hwdec, autostart
  - Advanced: sticky, argb, override redirect, screen, desktop type
  - Command preview + Copy / Save script / Kill all buttons

### tools.py
- `XwinwrapConfig` — dataclass: video_path, mode, geometry, fps, brightness, speed, scale, audio, loop, hwdec, fullscreen_pause, maximize_pause, sticky, argb, override_redirect, screen, fdt_type
  - `build_xwinwrap_args()`, `build_mpv_args()`, `build_command_list()`, `build_command_str()`
  - Key mpv option: `--display-fps-override` (not `--display-fps` for mpv ≥ 0.37)
- `WallpaperManager` — process lifecycle
  - `start()` → pgrep verify (not Popen poll, since xwinwrap daemonizes with `-d`)
  - `stop()` → `pkill -f "xwinwrap.*mpv"`
  - `is_running` → `_find_xwinwrap_pid()` via pgrep
  - Stats: `_find_mpv_pid()` → `/proc/PID/status` (VmRSS) + `ps -p PID -o %cpu=`
- `FullscreenMonitor` — threading, xdotool + xprop → mpv IPC socket pause
- `AutostartManager` — `~/.config/autostart/xwinwrap-wallpaper.desktop`
- `WallpaperHistory` — `~/.config/xwinwrap-gui/history.json`
  - Thumbnails: `~/.config/xwinwrap-gui/thumbnails/<md5[:12]>.jpg`
  - `HistoryItem`: path, name, added, thumbnail, kind (video/image)
  - `add()` → generates thumbnail via ffmpeg (frame at 00:01, 320×180)
  - `search(query)` → filter by name/path
- `generate_script()` — bash script with pkill preamble
- `kill_all()` — pkill
- `check_dependencies()` — xwinwrap, mpv, xdotool, xprop, socat

### lang.py
- `STRINGS["en"]` and `STRINGS["vi"]` — 68 matching keys
- `_(key, lang)` — fallback to English

## Wallpaper Storage
- History: `~/.config/xwinwrap-gui/history.json`
- Thumbnails: `~/.config/xwinwrap-gui/thumbnails/`

## Dependencies (system)
- `xwinwrap`, `mpv`, `xdotool`, `xprop`, `socat`, `ffmpeg`, `python3-gi` (GTK3)

## GTK3 CSS Limitations
- No `display`, `align-items`, `gap`, `justify-content`, `position`, `width`/`height` on widgets
- `text-align`, `text-transform`, `line-height`, `word-break` not supported
- `margin_right` deprecated → use `margin_end`
- Widget `set_font_size()` does NOT exist → use CSS class or Pango markup
- `Gtk.Label.set_margin()` does NOT exist → use `set_margin_top/start/end/bottom`

## Session History

### 2026-05-28 — Vietnamese i18n + lang switch fix + build-deb icon.ico

**build-deb.sh**
- Added `icon.ico` → PNG conversion (pick largest frame, resize 128×128)
- Fallback `icon.png` → copy, then gen placeholder
- Renamed app: `Name=Xwinwrap Manager`, `GenericName=Xwinwrap Manager`

**lang.py** (70 keys each language)
- Added `grid_tooltip`, `media_filter` keys
- Full Vietnamese rewrite: thuần Việt, bỏ pha tiếng Anh
  - "wallpaper" → "hình nền", "file" → "tập tin"
  - "fullscreen/maximize" → "toàn màn hình/phóng to"
  - "copy/kill" → "sao chép/kết thúc", "native" → "gốc"

**gui.py**
- Renamed display name: "Wallpaper Engine" → "Xwinwrap Manager"
- `Lang._on_switch_lang()`: cập nhật label trực tiếp (không rebuild page)
  - Lưu `self._lang_labels` = list `(widget, key)` cho Label/Entry placeholder
  - Lưu `self._cmd_btns` = list `(button, key)` cho command buttons
  - Update nav buttons, search placeholder, sidebar buttons, combos, status
- Hardcoded strings: "Grid" tooltip → `self._tr("grid_tooltip")`, "Media" filter → `self._tr("media_filter")`

### 2026-05-28 — Remember last selected wallpaper + build-deb icon.png

**gui.py**
- Bug: `_get_last_path()` trả về `items[0]` (item mới thêm gần nhất) thay vì wallpaper đã chọn trước đó
- `_save_settings()`: thêm `"selected_path": self._selected_path` vào dict lưu settings
- `_load_settings()`: khôi phục `self._selected_path` từ file settings.json
- `__init__`: khởi tạo `_config` rỗng → gọi `_load_settings()` → chọn path theo thứ tự ưu tiên:
  1. `_selected_path` nếu file còn tồn tại
  2. `config.video_path` từ settings cũ nếu còn
  3. Fallback về `_get_last_path()` (item đầu history)

**build-deb.sh**
- Dùng `icon.png` trực tiếp (resize 128×128) thay vì placeholder
- Build manual khi không có sudo

### 2026-05-28 — Auto-update autostart on wallpaper switch/config change

**gui.py**
- Added `_update_autostart()` — updates autostart .desktop file with current command if autostart is enabled (không cần toggle lại)
- Gọi `_update_autostart()` trong:
  - `_on_start()` sau khi start thành công (bao gồm Apply now)
  - `_on_any_change()` mỗi khi config thay đổi (FPS, brightness, video path, v.v.)

### 2026-05-28 — Bundle xwinwrap into .deb package

**build-deb.sh**
- Clone & build xwinwrap từ `mmhobi7/xwinwrap` trong lúc build .deb
- Copy binary `xwinwrap` vào `$PKG_DIR/usr/bin/` (đóng gói trong package)
- Xoá `Recommends: xwinwrap`, thêm `Suggests: nitrogen, feh`
- Xoá `xwinwrap` khỏi postinst dependency check
- `sudo apt` chỉ chạy nếu có passwordless sudo, nếu không thì skip

## Common Pitfalls (FIXED)
- `--display-fps` removed in mpv ≥ 0.37 → use `--display-fps-override`
- xwinwrap `-d` daemonizes → parent Popen exits → use pgrep to check running
- `button-press-event` connect: extra `None` arg overrides lambda default
- `remove_class()` takes single arg only
