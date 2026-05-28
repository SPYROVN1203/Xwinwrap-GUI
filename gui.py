import os
import re
from pathlib import Path
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango
 
from tools import (
    XwinwrapConfig,
    WallpaperManager,
    AutostartManager,
    WallpaperHistory,
    HistoryItem,
    generate_script,
    kill_all,
    check_dependencies,
)
from lang import STRINGS, _


class Lang:
    def __init__(self):
        self._lang = "en"

    @property
    def current(self):
        return self._lang

    def toggle(self):
        self._lang = "vi" if self._lang == "en" else "en"
        return self._lang

    def get(self, key):
        return _(key, self._lang)

    def fmt(self, key, **kw):
        return self.get(key).format(**kw)


CARD_W = 280
CARD_H = 280
THUMB_H = 200


class XwinwrapGUI(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self._lang = Lang()
        self._manager = WallpaperManager()
        self._autostart = AutostartManager()
        self._history = WallpaperHistory()
        self._config = XwinwrapConfig(video_path=self._get_last_path())

        self._manager.set_status_callback(self._on_status_changed)
        self._stats_timer_id = None
        self._search_query = ""
        self._selected_path = ""
        self._dark_theme = True
        self._lang_labels = []
        self._cmd_btns = []

        self.set_default_size(1248, 702)
        self.set_title(self._tr("app_title"))
        self._setup_css()
        self._build_ui()

        self._update_cmd_preview()
        self._on_status_changed(False)
        GLib.timeout_add(500, self._regenerate_thumbs)
        self.connect("destroy", lambda w: self._stop_stats_timer())

    # ── helpers ──────────────────────────────────────────
    def _tr(self, key):
        return self._lang.get(key)

    def _get_last_path(self):
        items = self._history.get_all()
        return items[0].path if items else ""

    def _show_error(self, msg):
        d = Gtk.MessageDialog(parent=self, modal=True,
                              message_type=Gtk.MessageType.ERROR,
                              buttons=Gtk.ButtonsType.OK, text=msg)
        d.run()
        d.destroy()

    # ── CSS ──────────────────────────────────────────────
    def _get_css(self):
        if self._dark_theme:
            return b"""
            window, .background { background: #0d0d1a; }
            .sidebar { background: #13132a; border-right: 1px solid #1e1e3a; }
            .nav-btn { padding:12px 18px; font-size:14px; color:#888;
                       background:transparent; border-left:3px solid transparent;
                       border-bottom:1px solid rgba(255,255,255,0.04); }
            .nav-btn:hover { background:#1e1e3a; color:#eee;
                             border-left-color:#4ecdc4; }
            .nav-btn.active { color:#fff; border-left-color:#4ecdc4;
                              background:#1e1e3a; font-weight:700; }
            .side-action { padding:10px 14px; font-size:13px; color:#aaa;
                           background:rgba(78,205,196,0.06);
                           border:1px solid #2a2a5a;
                           border-radius:6px; margin-bottom:8px;
                           font-weight:600; }
            .side-action:hover { background:rgba(78,205,196,0.15); color:#fff;
                                 border-color:#4ecdc4; }
            .side-cmd { padding:10px 14px; font-size:13px; font-weight:700;
                        border-radius:6px; border:1px solid #2a2a5a;
                        background:transparent; color:#ccc; margin-bottom:4px; }
            .side-cmd:hover { background:#1e1e3a; border-color:#4ecdc4; }
            .search-box { background:#13132a; border:1px solid #1e1e3a;
                           border-radius:5px; padding:0 10px; }
            .search-box entry { background:transparent; border:none; color:#ccc; }
            .toolbar-btn { border-radius:5px; border:1px solid #1e1e3a;
                            background:transparent; color:#888; }
            .toolbar-btn:hover { background:#13132a; color:#ccc; }
            .wp-card { border-radius:6px; border:1px solid #1e1e3a;
                       background:#13132a; }
            .wp-card:hover { border-color:#2a2a5a; }
            .wp-card.selected { border:2px solid #4ecdc4; box-shadow: 0 0 8px rgba(78,205,196,0.3); }
            .wp-thumb { background:#0d0d1a; color:#555; }
            .badge { background:#13132a; border:1px solid #1e1e3a;
                     border-radius:4px; padding:2px 6px; font-size:10px; color:#888; }
            .wp-name { font-size:13px; font-weight:500; color:#ccc; }
            .wp-desc { font-size:11px; color:#666; }
            .wp-menu { background:transparent; border:none; color:#555; }
            .wp-menu:hover { background:#1a1a2e; color:#888; }
            .section { background:#13132a; border:1px solid #1e1e3a;
                       border-radius:6px; padding:10px 14px; margin-bottom:8px; }
            .section-title { font-size:11px; font-weight:600; color:#666;
                             margin-bottom:6px; }
            .label { font-size:13px; color:#888; }
            .val { font-size:13px; font-weight:500; color:#ccc; }
            .status-stopped { color:#888; font-size:12px; }
            .status-running { color:#4ecdc4; font-size:12px; font-weight:600; }
            .statusbar-box { background:#0d0d1a; border-top:1px solid #1e1e3a;
                              padding:0 14px; font-size:11px; color:#555; }
            .btn { background:transparent; border:1px solid #1e1e3a;
                   border-radius:5px; padding:6px 14px; font-size:13px; color:#ccc; }
            .btn:hover { background:#1a1a2e; }
            .btn-primary { background:#4ecdc4; border-color:#4ecdc4; color:#0d0d1a;
                           font-weight:700; }
            .btn-primary:hover { background:#3dbdb5; }
            .btn-danger { border-color:#ff6b6b; color:#ff6b6b; font-weight:700; }
            .btn-danger:hover { background:#2a1a1a; }
            .btn-sm { padding:4px 10px; font-size:12px; }
            .lang-btn { font-size:11px; padding:2px 6px; }
            .add-plus { font-size:24px; color:#555; }
            """
        else:
            return b"""
            window, .background { background: #e8e8ec; }
            .sidebar { background: #ffffff; border-right: 1px solid #d0d0d8; }
            .nav-btn { padding:12px 18px; font-size:14px; color:#666;
                       background:transparent; border-left:3px solid transparent;
                       border-bottom:1px solid rgba(0,0,0,0.04); }
            .nav-btn:hover { background:#e0e0e8; color:#222;
                             border-left-color:#4ecdc4; }
            .nav-btn.active { color:#000; border-left-color:#4ecdc4;
                              background:#e0e0e8; font-weight:700; }
            .side-action { padding:10px 14px; font-size:13px; color:#555;
                           background:rgba(78,205,196,0.06);
                           border:1px solid #c0c0c8;
                           border-radius:6px; margin-bottom:8px;
                           font-weight:600; }
            .side-action:hover { background:rgba(78,205,196,0.15); color:#000;
                                 border-color:#4ecdc4; }
            .side-cmd { padding:10px 14px; font-size:13px; font-weight:700;
                        border-radius:6px; border:1px solid #c0c0c8;
                        background:transparent; color:#333; margin-bottom:4px; }
            .side-cmd:hover { background:#e0e0e8; border-color:#4ecdc4; }
            .search-box { background:#ffffff; border:1px solid #d0d0d8;
                           border-radius:5px; padding:0 10px; }
            .search-box entry { background:transparent; border:none; color:#333; }
            .toolbar-btn { border-radius:5px; border:1px solid #d0d0d8;
                            background:transparent; color:#666; }
            .toolbar-btn:hover { background:#ffffff; color:#333; }
            .wp-card { border-radius:6px; border:1px solid #d0d0d8;
                       background:#ffffff; }
            .wp-card:hover { border-color:#a0a0b0; }
            .wp-card.selected { border:2px solid #4ecdc4; box-shadow: 0 0 8px rgba(78,205,196,0.3); }
            .wp-thumb { background:#e8e8ec; color:#888; }
            .badge { background:#ffffff; border:1px solid #d0d0d8;
                     border-radius:4px; padding:2px 6px; font-size:10px; color:#666; }
            .wp-name { font-size:13px; font-weight:500; color:#222; }
            .wp-desc { font-size:11px; color:#777; }
            .wp-menu { background:transparent; border:none; color:#888; }
            .wp-menu:hover { background:#f0f0f4; color:#555; }
            .section { background:#ffffff; border:1px solid #d0d0d8;
                       border-radius:6px; padding:10px 14px; margin-bottom:8px; }
            .section-title { font-size:11px; font-weight:600; color:#888;
                             margin-bottom:6px; }
            .label { font-size:13px; color:#555; }
            .val { font-size:13px; font-weight:500; color:#222; }
            .status-stopped { color:#666; font-size:12px; }
            .status-running { color:#4ecdc4; font-size:12px; font-weight:600; }
            .statusbar-box { background:#ffffff; border-top:1px solid #d0d0d8;
                              padding:0 14px; font-size:11px; color:#888; }
            .btn { background:transparent; border:1px solid #d0d0d8;
                   border-radius:5px; padding:6px 14px; font-size:13px; color:#333; }
            .btn:hover { background:#f0f0f4; }
            .btn-primary { background:#4ecdc4; border-color:#4ecdc4; color:#fff;
                           font-weight:700; }
            .btn-primary:hover { background:#3dbdb5; }
            .btn-danger { border-color:#ff6b6b; color:#ff6b6b; font-weight:700; }
            .btn-danger:hover { background:#ffe8e8; }
            .btn-sm { padding:4px 10px; font-size:12px; }
            .lang-btn { font-size:11px; padding:2px 6px; }
            .add-plus { font-size:24px; color:#999; }
            """

    def _setup_css(self):
        if hasattr(self, '_css_provider'):
            Gtk.StyleContext.remove_provider_for_screen(
                Gdk.Screen.get_default(), self._css_provider
            )
        css = self._get_css()
        self._css_provider = Gtk.CssProvider()
        self._css_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # ── LANG helpers ─────────────────────────────────────
    def _rebuild_lang_combos(self):
        mode = self._mode_combo.get_active_id()
        self._mode_combo.remove_all()
        self._mode_combo.append("fs", self._tr("fullscreen"))
        self._mode_combo.append("window", self._tr("window"))
        self._mode_combo.set_active_id(mode or "fs")

        scale = self._scale_combo.get_active_id()
        self._scale_combo.remove_all()
        self._scale_combo.append("", self._tr("scale_auto"))
        self._scale_combo.append("1920:1080", self._tr("scale_1080p"))
        self._scale_combo.append("1280:720", self._tr("scale_720p"))
        self._scale_combo.append("960:540", self._tr("scale_540p"))
        self._scale_combo.set_active_id(scale or "")

        fdt = self._fdt_combo.get_active_id()
        self._fdt_combo.remove_all()
        self._fdt_combo.append("-1", self._tr("fdt_default"))
        self._fdt_combo.append("0", self._tr("fdt_normal"))
        self._fdt_combo.append("1", self._tr("fdt_desktop"))
        self._fdt_combo.set_active_id(fdt or "-1")

    # ── BUILD UI ─────────────────────────────────────────
    def _build_ui(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(vbox)

        # Title bar
        hb = Gtk.Box(spacing=0)
        hb.set_size_request(-1, 38)
        hb.set_name("titlebar-box")
        Gtk.StyleContext.add_class(hb.get_style_context(), "titlebar-box")

        left = Gtk.Box(spacing=6)
        icon = Gtk.Image.new_from_icon_name("video-display-symbolic", Gtk.IconSize.MENU)
        left.pack_start(icon, False, False, 0)
        title = Gtk.Label(label="Xwinwrap Manager")
        title.get_style_context().add_class("label")
        left.pack_start(title, False, False, 0)
        hb.pack_start(left, False, False, 0)

        right = Gtk.Box(spacing=4)
        self._theme_btn = Gtk.Button(label="☀")
        self._theme_btn.get_style_context().add_class("lang-btn")
        self._theme_btn.connect("clicked", lambda b: self._toggle_theme())
        right.pack_end(self._theme_btn, False, False, 0)
        self._lang_btn = Gtk.Button(label=self._tr("switch_lang"))
        self._lang_btn.get_style_context().add_class("lang-btn")
        self._lang_btn.connect("clicked", lambda b: self._on_switch_lang())
        right.pack_end(self._lang_btn, False, False, 0)
        hb.pack_end(right, False, False, 0)
        vbox.pack_start(hb, False, False, 0)

        # Body
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        vbox.pack_start(body, True, True, 0)

        # Sidebar
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        side.set_size_request(200, -1)
        Gtk.StyleContext.add_class(side.get_style_context(), "sidebar")
        body.pack_start(side, False, False, 0)

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        body.pack_start(self._stack, True, True, 0)

        # Pages
        lib_page = self._build_library_page()
        self._stack.add_titled(lib_page, "library", "Library")

        set_page = self._build_settings_page()
        self._stack.add_titled(set_page, "settings", "Settings")
        self._settings_page = set_page

        # Sidebar nav
        nav_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        side.pack_start(nav_box, False, False, 0)

        self._nav_btns = []
        self._nav_pages = []
        for icon_name, label_key, page_name in [
            ("folder-videos-symbolic", "library_btn", "library"),
            ("emblem-system-symbolic", "settings_btn", "settings"),
        ]:
            btn = Gtk.Button()
            h = Gtk.Box(spacing=8)
            ico = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            h.pack_start(ico, False, False, 0)
            lbl = Gtk.Label(label=self._tr(label_key), xalign=0)
            h.pack_start(lbl, False, False, 0)
            btn.add(h)
            btn.get_style_context().add_class("nav-btn")
            if not self._nav_btns:
                btn.get_style_context().add_class("active")
            btn.connect("clicked", lambda b, p=page_name: self._switch_page(p))
            nav_box.pack_start(btn, False, False, 0)
            self._nav_btns.append(btn)
            self._nav_pages.append(page_name)

        # Sidebar bottom actions
        side_bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        side_bottom.set_margin_top(0)
        side_bottom.set_margin_bottom(10)
        side_bottom.set_margin_start(10)
        side_bottom.set_margin_end(10)

        self._sb_btn_add = Gtk.Button(label=self._tr("add_wallpaper"))
        self._sb_btn_add.get_style_context().add_class("side-action")
        self._sb_btn_add.connect("clicked", lambda b: self._on_add_wallpaper())
        side_bottom.pack_start(self._sb_btn_add, False, False, 0)

        self._sb_btn_start = Gtk.Button(label=self._tr("start"))
        self._sb_btn_start.get_style_context().add_class("side-cmd")
        self._sb_btn_start.get_style_context().add_class("btn-primary")
        self._sb_btn_start.connect("clicked", lambda b: self._on_start())
        side_bottom.pack_start(self._sb_btn_start, False, False, 0)

        self._sb_btn_restart = Gtk.Button(label=self._tr("restart"))
        self._sb_btn_restart.get_style_context().add_class("side-cmd")
        self._sb_btn_restart.connect("clicked", lambda b: self._on_restart())
        side_bottom.pack_start(self._sb_btn_restart, False, False, 0)

        self._sb_btn_stop = Gtk.Button(label=self._tr("stop"))
        self._sb_btn_stop.get_style_context().add_class("side-cmd")
        self._sb_btn_stop.get_style_context().add_class("btn-danger")
        self._sb_btn_stop.connect("clicked", lambda b: self._on_stop())
        side_bottom.pack_start(self._sb_btn_stop, False, False, 0)

        side.pack_end(side_bottom, False, False, 0)

        # Status bar
        self._build_statusbar(vbox)

    # ── Library Page ─────────────────────────────────────
    def _build_library_page(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Toolbar
        tb = Gtk.Box(spacing=6)
        tb.set_margin_start(12)
        tb.set_margin_end(12)
        tb.set_margin_top(8)
        tb.set_margin_bottom(0)

        search_box = Gtk.Box(spacing=6)
        search_box.get_style_context().add_class("search-box")
        search_icon = Gtk.Image.new_from_icon_name("edit-find-symbolic", Gtk.IconSize.MENU)
        search_box.pack_start(search_icon, False, False, 0)
        self._search_entry = Gtk.Entry()
        self._search_entry.set_placeholder_text(self._tr("search_placeholder"))
        self._search_entry.connect("changed", lambda e: self._on_search())
        search_box.pack_start(self._search_entry, True, True, 0)
        tb.pack_start(search_box, True, True, 0)

        self._grid_btn = Gtk.Button()
        g = Gtk.Image.new_from_icon_name("view-grid-symbolic", Gtk.IconSize.MENU)
        self._grid_btn.add(g)
        self._grid_btn.get_style_context().add_class("toolbar-btn")
        self._grid_btn.set_tooltip_text(self._tr("grid_tooltip"))
        tb.pack_start(self._grid_btn, False, False, 0)

        vbox.pack_start(tb, False, False, 0)

        # Grid area
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox.pack_start(sw, True, True, 0)

        viewport = Gtk.Viewport()
        sw.add(viewport)

        self._flow = Gtk.FlowBox()
        self._flow.set_valign(Gtk.Align.START)
        self._flow.set_max_children_per_line(3)
        self._flow.set_min_children_per_line(3)
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_homogeneous(True)
        self._flow.set_column_spacing(8)
        self._flow.set_row_spacing(8)
        self._flow.set_margin_top(12)
        self._flow.set_margin_start(12)
        self._flow.set_margin_end(12)
        self._flow.set_margin_bottom(12)
        viewport.add(self._flow)

        self._rebuild_grid()
        return vbox

    def _rebuild_grid(self, filter_text=""):
        for ch in self._flow.get_children():
            self._flow.remove(ch)

        items = self._history.search(filter_text)
        for item in items:
            self._flow.add(self._make_card(item))

        # Add card
        self._flow.add(self._make_add_card())
        self._flow.show_all()

    def _make_card(self, item: HistoryItem):
        eb = Gtk.EventBox()
        eb.get_style_context().add_class("wp-card")
        if item.path == self._selected_path:
            eb.get_style_context().add_class("selected")
        eb.set_size_request(CARD_W, CARD_H)
        eb.connect("button-press-event", lambda w, e, p=item: self._on_card_click(p))

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Thumbnail image
        thumb_path = self._history.get_thumbnail_path(item)
        if thumb_path:
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(thumb_path, CARD_W, THUMB_H, True)
                img = Gtk.Image.new_from_pixbuf(pix)
            except Exception:
                img = Gtk.Image.new_from_icon_name("video-x-generic-symbolic", Gtk.IconSize.DIALOG)
                img.set_opacity(0.4)
        else:
            img = Gtk.Image.new_from_icon_name("video-x-generic-symbolic", Gtk.IconSize.DIALOG)
            img.set_opacity(0.4)
        vbox.pack_start(img, False, False, 0)

        # Video type badge
        badge = Gtk.Label(label=item.kind.upper())
        badge.get_style_context().add_class("badge")
        badge.set_margin_top(2)
        badge.set_margin_end(4)
        badge.set_halign(Gtk.Align.END)
        badge.set_valign(Gtk.Align.START)
        badge.set_no_show_all(False)

        # Info row
        info = Gtk.Box(spacing=6)
        info.set_margin_top(8)
        info.set_margin_start(10)
        info.set_margin_end(10)
        info.set_margin_bottom(8)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        name = Gtk.Label(label=item.name, xalign=0)
        name.get_style_context().add_class("wp-name")
        name.set_ellipsize(Pango.EllipsizeMode.END)
        left.pack_start(name, False, False, 0)
        desc = Gtk.Label(label=str(Path(item.path).parent.name), xalign=0)
        desc.get_style_context().add_class("wp-desc")
        desc.set_ellipsize(Pango.EllipsizeMode.END)
        left.pack_start(desc, False, False, 0)
        info.pack_start(left, True, True, 0)

        menu_btn = Gtk.Button()
        m = Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.MENU)
        menu_btn.add(m)
        menu_btn.get_style_context().add_class("wp-menu")
        menu_btn.set_size_request(24, 24)
        info.pack_end(menu_btn, False, False, 0)

        # Pack everything
        vbox.pack_start(info, True, True, 0)
        eb.add(vbox)

        # Badge overlay on top of EventBox
        ov = Gtk.Overlay()
        ov.add(eb)
        ov.add_overlay(badge)

        menu_btn.connect("clicked", lambda b, p=item: self._show_card_menu(b, p))
        return ov

    def _make_add_card(self):
        eb = Gtk.EventBox()
        eb.get_style_context().add_class("wp-card")
        eb.set_size_request(CARD_W, CARD_H)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        thumb = Gtk.Box()
        thumb.set_size_request(-1, THUMB_H)
        thumb.get_style_context().add_class("wp-thumb")
        thumb.set_name("add-thumb")
        css = Gtk.CssProvider()
        css.load_from_data(b"#add-thumb { border: 1.5px dashed #1e1e3a; }")
        thumb.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        plus = Gtk.Label(label="+")
        plus.get_style_context().add_class("add-plus")
        plus.set_opacity(0.3)
        v.pack_start(plus, False, False, 0)
        t = Gtk.Label(label=self._tr("add_new"))
        t.set_opacity(0.4)
        v.pack_start(t, False, False, 0)
        thumb.pack_start(v, True, True, 0)
        box.pack_start(thumb, False, False, 0)

        info = Gtk.Box()
        info.set_margin_top(10)
        info.set_margin_start(10)
        info.set_margin_end(10)
        info.set_margin_bottom(10)
        nm = Gtk.Label(label=self._tr("add_wallpaper"))
        nm.get_style_context().add_class("wp-name")
        nm.set_opacity(0.5)
        info.pack_start(nm, False, False, 0)
        box.pack_start(info, False, False, 0)

        eb.add(box)
        eb.connect("button-press-event", lambda w, e: self._on_add_wallpaper())
        return eb

    def _on_card_click(self, item: HistoryItem):
        if os.path.isfile(item.path):
            self._config.video_path = item.path
            self.set_title(f"Xwinwrap Manager — {item.name}")
            self._on_any_change()
        self._selected_path = item.path
        self._rebuild_grid(self._search_entry.get_text())

    def _show_card_menu(self, btn, item: HistoryItem):
        pop = Gtk.Popover.new(btn)
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        def mk_item(label, cb):
            b = Gtk.ModelButton(label=label)
            b.connect("clicked", cb)
            vb.pack_start(b, False, False, 0)

        mk_item(self._tr("apply_now"), lambda x: self._on_apply(item))
        mk_item(self._tr("remove_from_list"),
                lambda x: self._on_remove_from_history(item))
        vb.show_all()
        pop.add(vb)
        pop.popup()

    def _on_apply(self, item: HistoryItem):
        self._on_card_click(item)
        self._on_start()

    def _on_remove_from_history(self, item: HistoryItem):
        self._history.remove(item.path)
        self._rebuild_grid(self._search_entry.get_text())

    def _regenerate_thumbs(self):
        self._history.regenerate_thumbnails()
        self._rebuild_grid(self._search_entry.get_text())

    def _on_search(self):
        self._rebuild_grid(self._search_entry.get_text())

    # ── Settings Page ────────────────────────────────────
    def _build_settings_page(self):
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_margin_top(12)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_bottom(12)
        sw.add(vbox)

        # Video mode
        s = self._make_settings_section(vbox, "display_mode")
        self._mode_combo = Gtk.ComboBoxText()
        self._mode_combo.append("fs", "")
        self._mode_combo.append("window", "")
        self._mode_combo.set_active_id("fs")
        self._mode_combo.connect("changed", lambda w: self._on_any_change())
        s.attach(self._mode_combo, 0, 0, 1, 1)

        self._geo_entry = Gtk.Entry()
        self._geo_entry.set_placeholder_text(self._tr("geometry_ph"))
        self._lang_labels.append((self._geo_entry, "geometry_ph"))
        self._geo_entry.set_sensitive(False)
        self._geo_entry.connect("changed", lambda w: self._on_any_change())
        s.attach(self._geo_entry, 1, 0, 1, 1)

        # FPS
        s = self._make_settings_section(vbox, "fps")
        self._fps_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 165, 1)
        self._fps_scale.set_value(30)
        self._fps_scale.set_size_request(200, -1)
        self._fps_scale.connect("value-changed", lambda w: self._on_any_change())
        self._fps_val = Gtk.Label(label="30")
        self._fps_val.get_style_context().add_class("val")
        hb = Gtk.Box(spacing=6)
        hb.pack_start(self._fps_scale, True, True, 0)
        hb.pack_start(self._fps_val, False, False, 0)
        s.attach(self._make_label("fps"), 0, 0, 1, 1)
        s.attach(hb, 1, 0, 1, 1)

        # Brightness
        self._bright_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self._bright_scale.set_value(100)
        self._bright_scale.connect("value-changed", lambda w: self._on_any_change())
        self._bright_val = Gtk.Label(label="100%")
        self._bright_val.get_style_context().add_class("val")
        hb = Gtk.Box(spacing=6)
        hb.pack_start(self._bright_scale, True, True, 0)
        hb.pack_start(self._bright_val, False, False, 0)
        s.attach(self._make_label("brightness"), 0, 1, 1, 1)
        s.attach(hb, 1, 1, 1, 1)

        # Speed
        self._speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 25, 200, 5)
        self._speed_scale.set_value(100)
        self._speed_scale.connect("value-changed", lambda w: self._on_any_change())
        self._speed_val = Gtk.Label(label="100%")
        self._speed_val.get_style_context().add_class("val")
        hb = Gtk.Box(spacing=6)
        hb.pack_start(self._speed_scale, True, True, 0)
        hb.pack_start(self._speed_val, False, False, 0)
        s.attach(self._make_label("speed"), 0, 2, 1, 1)
        s.attach(hb, 1, 2, 1, 1)

        # Scale
        self._scale_combo = Gtk.ComboBoxText()
        self._scale_combo.append("", "")
        self._scale_combo.append("1920:1080", "")
        self._scale_combo.append("1280:720", "")
        self._scale_combo.append("960:540", "")
        self._scale_combo.set_active_id("")
        self._scale_combo.connect("changed", lambda w: self._on_any_change())
        s.attach(self._make_label("scale"), 0, 3, 1, 1)
        s.attach(self._scale_combo, 1, 3, 1, 1)

        # Behaviors
        s = self._make_settings_section(vbox, "behavior")
        self._tog_fs_pause = self._toggle_row(s, 0, "pause_fullscreen", True)
        self._tog_max_pause = self._toggle_row(s, 1, "pause_maximize", True)
        self._tog_audio = self._toggle_row(s, 2, "audio", False)
        self._tog_loop = self._toggle_row(s, 3, "loop", True)
        self._tog_hwdec = self._toggle_row(s, 4, "hwdec", True)
        self._tog_autostart = self._toggle_row(s, 5, "autostart", self._autostart.is_enabled())

        # Extra
        s = self._make_settings_section(vbox, "extra")
        self._tog_sticky = self._toggle_row(s, 0, "sticky", True)
        self._tog_argb = self._toggle_row(s, 1, "argb", False)
        self._tog_ovr = self._toggle_row(s, 2, "override", False)

        self._screen_entry = Gtk.Entry()
        self._screen_entry.set_placeholder_text(self._tr("screen_ph"))
        self._lang_labels.append((self._screen_entry, "screen_ph"))
        self._screen_entry.connect("changed", lambda w: self._on_any_change())
        s.attach(self._make_label("screen"), 0, 3, 1, 1)
        s.attach(self._screen_entry, 1, 3, 1, 1)

        self._fdt_combo = Gtk.ComboBoxText()
        self._fdt_combo.append("-1", "")
        self._fdt_combo.append("0", "")
        self._fdt_combo.append("1", "")
        self._fdt_combo.set_active_id("-1")
        self._fdt_combo.connect("changed", lambda w: self._on_any_change())
        s.attach(self._make_label("desktop_type"), 0, 4, 1, 1)
        s.attach(self._fdt_combo, 1, 4, 1, 1)

        # Command
        s = self._make_settings_section(vbox, "cmd")
        self._cmd_view = Gtk.Label(label="", xalign=0, wrap=True)
        self._cmd_view.get_style_context().add_class("label")
        self._cmd_view.set_selectable(True)
        s.attach(self._cmd_view, 0, 0, 2, 1)

        btn_h = Gtk.Box(spacing=6)
        self._cmd_btns = []
        for key, cb in [
            ("copy", lambda b: self._on_copy()),
            ("save_script", lambda b: self._on_save_script()),
            ("kill_all", lambda b: self._on_kill_all()),
        ]:
            b = Gtk.Button(label=self._tr(key))
            b.get_style_context().add_class("btn")
            b.get_style_context().add_class("btn-sm")
            b.connect("clicked", cb)
            self._cmd_btns.append((b, key))
            btn_h.pack_start(b, False, False, 0)
        s.attach(btn_h, 0, 1, 2, 1)

        self._rebuild_lang_combos()
        return sw

    def _make_settings_section(self, parent, title_key):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.get_style_context().add_class("section")
        t = Gtk.Label(label=self._tr(title_key), xalign=0)
        t.get_style_context().add_class("section-title")
        self._lang_labels.append((t, title_key))
        box.pack_start(t, False, False, 0)
        inner = Gtk.Grid(column_spacing=8, row_spacing=4)
        box.pack_start(inner, True, True, 0)
        parent.pack_start(box, False, False, 0)
        return inner

    def _make_label(self, key):
        lbl = Gtk.Label(label=self._tr(key), xalign=0)
        lbl.get_style_context().add_class("label")
        self._lang_labels.append((lbl, key))
        return lbl

    def _toggle_row(self, parent, row, key, default):
        hb = Gtk.Box(spacing=8)
        sw = Gtk.Switch()
        sw.set_active(default)
        sw.connect("notify::active", lambda w, p: self._on_any_change())
        hb.pack_start(sw, False, False, 0)
        lbl = Gtk.Label(label=self._tr(key), xalign=0)
        hb.pack_start(lbl, True, True, 0)
        self._lang_labels.append((lbl, key))
        parent.attach(hb, 0, row, 2, 1)
        return sw

    # ── Statusbar ────────────────────────────────────────
    def _build_statusbar(self, parent):
        box = Gtk.Box(spacing=0)
        box.set_size_request(-1, 26)
        box.get_style_context().add_class("statusbar-box")

        left = Gtk.Box(spacing=12)
        self._sb_dot = Gtk.Label(label="●")
        self._sb_dot.set_margin_end(2)
        left.pack_start(self._sb_dot, False, False, 0)
        self._sb_status = Gtk.Label(label=self._tr("stopped"))
        left.pack_start(self._sb_status, False, False, 0)
        self._sb_engine = Gtk.Label(label="xwinwrap + mpv")
        left.pack_start(self._sb_engine, False, False, 0)
        self._sb_stats = Gtk.Label(label="— MB RAM")
        left.pack_start(self._sb_stats, False, False, 0)
        box.pack_start(left, False, False, 0)

        ver = Gtk.Label(label="Xwinwrap Manager v1.0")
        box.pack_end(ver, False, False, 0)
        parent.pack_start(box, False, False, 0)

    # ── Navigation ───────────────────────────────────────
    def _switch_page(self, name):
        self._stack.set_visible_child_name(name)
        for btn, pname in zip(self._nav_btns, self._nav_pages):
            ctx = btn.get_style_context()
            if pname == name:
                ctx.add_class("active")
            else:
                ctx.remove_class("active")

    # ── Config ───────────────────────────────────────────
    def _read_config(self):
        c = XwinwrapConfig()
        c.video_path = self._config.video_path
        c.mode = self._mode_combo.get_active_id() or "fs"
        c.geometry = self._geo_entry.get_text() or "1920x1080+0+0"
        c.fps = int(self._fps_scale.get_value())
        c.brightness = int(self._bright_scale.get_value())
        c.speed = int(self._speed_scale.get_value())
        c.scale = self._scale_combo.get_active_id() or ""
        c.audio = self._tog_audio.get_active()
        c.loop = self._tog_loop.get_active()
        c.hwdec = self._tog_hwdec.get_active()
        c.fullscreen_pause = self._tog_fs_pause.get_active()
        c.maximize_pause = self._tog_max_pause.get_active()
        c.sticky = self._tog_sticky.get_active()
        c.argb = self._tog_argb.get_active()
        c.override_redirect = self._tog_ovr.get_active()
        c.screen = self._screen_entry.get_text().strip()
        fdt = self._fdt_combo.get_active_id()
        c.fdt_type = int(fdt) if fdt and fdt != "-1" else -1
        return c

    def _on_any_change(self):
        self._config = self._read_config()
        self._update_cmd_preview()
        mode = self._mode_combo.get_active_id()
        self._geo_entry.set_sensitive(mode == "window")
        self._fps_val.set_text(str(int(self._fps_scale.get_value())))
        self._bright_val.set_text(f"{int(self._bright_scale.get_value())}%")
        self._speed_val.set_text(f"{int(self._speed_scale.get_value())}%")

    def _update_cmd_preview(self):
        self._cmd_view.set_text(self._config.build_command_str())

    # ── Actions ──────────────────────────────────────────
    def _on_start(self):
        c = self._read_config()
        if not c.video_path or not os.path.isfile(c.video_path):
            self._show_error(self._tr("err_no_file"))
            return
        ok, err = self._manager.start(c)
        if not ok:
            self._show_error(self._lang.fmt("err_start", detail=err))
        else:
            self._config = c
            self._start_stats_timer()

    def _on_stop(self):
        self._manager.stop()
        self._stop_stats_timer()

    def _on_restart(self):
        self._on_stop()
        GLib.timeout_add(500, self._on_start)

    def _on_toggle_pause(self):
        if self._manager.is_running:
            self._on_stop()
        else:
            self._on_start()

    def _on_kill_all(self):
        kill_all()
        self._manager.stop()
        self._stop_stats_timer()
        self._on_status_changed(False)

    def _on_copy(self):
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(self._config.build_command_str(), -1)
        self._flash_message(self._tr("copy_done"))

    def _on_save_script(self):
        d = Gtk.FileChooserDialog(title=self._tr("save_title"), parent=self,
                                  action=Gtk.FileChooserAction.SAVE)
        d.add_button(self._tr("cancel"), Gtk.ResponseType.CANCEL)
        d.add_button(self._tr("save"), Gtk.ResponseType.ACCEPT)
        d.set_current_name("live-wallpaper.sh")
        if d.run() == Gtk.ResponseType.ACCEPT:
            generate_script(self._config.build_command_str(), d.get_filename())
            self._flash_message(self._tr("copy_done"))
        d.destroy()

    def _on_add_wallpaper(self):
        d = Gtk.FileChooserDialog(title=self._tr("add_wallpaper"), parent=self,
                                  action=Gtk.FileChooserAction.OPEN)
        d.add_button(self._tr("cancel"), Gtk.ResponseType.CANCEL)
        d.add_button(self._tr("save"), Gtk.ResponseType.ACCEPT)
        filt = Gtk.FileFilter()
        filt.set_name(self._tr("media_filter"))
        for p in ["*.mp4", "*.mkv", "*.webm", "*.avi", "*.mov",
                   "*.gif", "*.png", "*.jpg", "*.jpeg", "*.bmp"]:
            filt.add_pattern(p)
        d.add_filter(filt)
        if d.run() == Gtk.ResponseType.ACCEPT:
            p = d.get_filename()
            d.destroy()
            if p:
                self._history.add(p)
                self._rebuild_grid(self._search_entry.get_text())
                # auto-select
                items = self._history.get_all()
                if items:
                    self._on_card_click(items[0])
        else:
            d.destroy()

    def _toggle_theme(self):
        self._dark_theme = not self._dark_theme
        self._theme_btn.set_label("☀" if self._dark_theme else "☾")
        self._setup_css()

    def _on_switch_lang(self):
        self._lang.toggle()
        self._lang_btn.set_label(self._tr("switch_lang"))
        self.set_title(self._tr("app_title"))
        # Update all stored settings labels/placeholders
        for widget, key in self._lang_labels:
            txt = self._tr(key)
            if isinstance(widget, Gtk.Label):
                widget.set_text(txt)
            elif isinstance(widget, Gtk.Entry):
                widget.set_placeholder_text(txt)
        # Update command buttons
        for btn, key in self._cmd_btns:
            btn.set_label(self._tr(key))
        # Rebuild combos
        self._rebuild_lang_combos()
        # Update nav buttons
        for btn, key in zip(self._nav_btns, ["library_btn", "settings_btn"]):
            for ch in btn.get_child().get_children():
                if isinstance(ch, Gtk.Label):
                    ch.set_text(self._tr(key))
        # Update search placeholder
        self._search_entry.set_placeholder_text(self._tr("search_placeholder"))
        # Update sidebar buttons
        self._sb_btn_add.set_label(self._tr("add_wallpaper"))
        self._sb_btn_start.set_label(self._tr("start"))
        self._sb_btn_restart.set_label(self._tr("restart"))
        self._sb_btn_stop.set_label(self._tr("stop"))
        # Update grid + status
        self._rebuild_grid(self._search_entry.get_text())
        self._on_status_changed(self._manager.is_running)

    def _on_status_changed(self, running):
        txt = self._tr("running") if running else self._tr("stopped")
        self._sb_status.set_text(txt)
        if running:
            self._sb_dot.set_markup('<span foreground="#4ecdc4">●</span>')
        else:
            self._sb_dot.set_markup('<span foreground="#888">●</span>')
        self._sb_btn_start.set_sensitive(not running)
        self._sb_btn_restart.set_sensitive(running)
        self._sb_btn_stop.set_sensitive(running)
        if not running:
            self._sb_stats.set_text("— MB RAM")

    def _start_stats_timer(self):
        self._stop_stats_timer()
        self._stats_timer_id = GLib.timeout_add(2000, self._poll_stats)

    def _stop_stats_timer(self):
        if self._stats_timer_id:
            GLib.source_remove(self._stats_timer_id)
            self._stats_timer_id = None

    def _poll_stats(self):
        if not self._manager.is_running:
            self._stop_stats_timer()
            self._on_status_changed(False)
            return False
        s = self._manager.get_stats()
        self._sb_stats.set_text(f"{s['ram']} RAM")
        return True

    def _flash_message(self, msg):
        self._cmd_view.set_text(msg)
        GLib.timeout_add(2500, lambda: (self._update_cmd_preview(), False))


class XwinwrapApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.xwinwrap.wallpaper", flags=0)

    def do_activate(self):
        w = XwinwrapGUI(self)
        w.show_all()


def main():
    app = XwinwrapApp()
    app.run()


if __name__ == "__main__":
    main()
