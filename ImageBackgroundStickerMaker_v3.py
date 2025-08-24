#!/usr/bin/env python3
"""
🚀 PROFESSIONAL IMAGE STUDIO V3.2 — Aligned Background-Reveal + Solid Outline (No-stretch + Session restore)

New in 3.2:
- 🛑 No edge stretching: when outlines extend past the original image, only the lines show.
  The reveal ring never uses fake/replicated pixels beyond the photo.
- 💾 Full Last-Session restore: ALL user-pickable settings (colors, widths, toggles, preview mode,
  brush size, "save only final", lock) are saved to JSON and restored on startup.
- 🔄 Auto-save session on changes and on exit.

UI upgrades in this build:
- 🗂️ Remove/clear selected files from the list (non-destructive) + Delete-from-disk (with confirmation)
- ▶️ Always-highlight the active image in the list (and auto-select it on Next/Previous)
- ⌫ Delete key removes selected items from the list
- Selection stays in view and synced with navigation

Carry-overs from 3.1:
- Solid Outline controls enable/disable properly + typeable width entries
- Presets save/restore ALL user-pickable settings too
- Outline never clipped: canvas auto-expands based on total outline width
- Brush performance: processed image updates only when the stroke ends
- "Lock Reveal Outline": freezes the reveal subject so brushing won’t move the reveal ring
- True "Background Reveal" ring from original photo around subject
- Optional decorative & solid-color rings for 3-layer effect
- Pixel-perfect masks (letterbox ➜ unpad), cached for speed
- Debounced UI updates + clear status + hover tooltips
- Thickness sync between Outline width and Reveal width
- Startup window +200px width & height
- Save-only-final option + "Save Final (Current)" button
- Single completion popup
- Brush editing on ORIGINAL & PROCESSED (Keep/Remove) + Undo/Redo (Ctrl+Z/Ctrl+Y)
- Live brush preview circle (no image residue)
- Quadrupled ranges for thickness sliders
- App-specific data dir with JSONs inside it
- Help window with plain-English guide + tips
"""

import tkinter as tk
from tkinter import filedialog, colorchooser, ttk, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import os, json, datetime
from PIL import Image, ImageTk, ImageColor
import numpy as np
from scipy.ndimage import binary_dilation
import torch
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

# ───────────────── Setup model ─────────────────
print("🔄 Loading BiRefNet model...")
model = AutoModelForImageSegmentation.from_pretrained("ZhengPeng7/BiRefNet", trust_remote_code=True)
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device).eval()
print(f"✅ Model loaded on device: {device}")

# ──────────────── Paths / files (app-specific) ───────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DATA_DIR = os.path.join(SCRIPT_DIR, "image_studio_v3_data")
CACHE_DIR = os.path.join(APP_DATA_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(APP_DATA_DIR, exist_ok=True)

PRESET_FILE = os.path.join(APP_DATA_DIR, "image_studio_v3_presets.json")
LAST_SESSION_FILE = os.path.join(APP_DATA_DIR, "image_studio_v3_last_session.json")
TEMP_DIR = CACHE_DIR  # alias

# ──────────────── Small utils ────────────────
def create_disk_structure(radius: int):
    L = np.arange(-radius, radius + 1)
    X, Y = np.meshgrid(L, L)
    return (X**2 + Y**2 <= radius**2).astype(bool)

def hex_to_rgba_tuple(hex_color: str, alpha=255):
    r, g, b = ImageColor.getrgb(hex_color)
    return (r, g, b, alpha)

def pad_with_transparent(img_rgba: Image.Image, pad: int) -> Image.Image:
    """Pad an image with TRANSPARENT pixels (no edge replication)."""
    if pad <= 0: return img_rgba
    w, h = img_rgba.size
    canvas = Image.new("RGBA", (w + 2*pad, h + 2*pad), (0, 0, 0, 0))
    canvas.paste(img_rgba, (pad, pad))
    return canvas

# ─────────────── Tooltips (hover help) ───────────────
class ToolTip:
    def __init__(self, widget, text, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._id = None
        self._tip = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, _):
        self._cancel()
        self._id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self._tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#111", foreground="#fff",
                         relief=tk.SOLID, borderwidth=1,
                         font=("Arial", 9), padx=6, pady=4)
        label.pack()

    def _hide(self, _=None):
        self._cancel()
        if self._tip:
            self._tip.destroy()
            self._tip = None

    def _cancel(self):
        if self._id:
            try: self.widget.after_cancel(self._id)
            except Exception: pass
            self._id = None

# ─────────────── Presets IO ───────────────
def load_presets():
    try:
        with open(PRESET_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "Default": {
                "outline_thickness": 10,
                "outline_color": "#ff0000",
                "bg_remove": False,
                "bg_threshold": 0.5,
                "keep_original_bg": True,
                "bg_blend_alpha": 0.3,
                "contextual_outline": False,
                "contextual_thickness": 15,
                "solid_outline": False,
                "solid_outline_color": "#000000",
                "solid_outline_thickness": 5,
                "bg_reveal_outline": False,
                "bg_reveal_outline_color": "#000000",
                "bg_reveal_outline_thickness": 4,
                "overlay_flossiness": 0.5,
                "save_only_final": False,
                "preview_mode": "outlined",
                "brush_size": 30,
                "lock_reveal_outline": False
            }
        }

def save_presets(presets):
    try:
        with open(PRESET_FILE, 'w') as f:
            json.dump(presets, f, indent=2)
    except Exception as e:
        print(f"Error saving presets: {e}")

# ─────────────── Main App ───────────────
class ImageProcessor(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("🚀 PROFESSIONAL IMAGE STUDIO V3.2 - COMPLETE")
        self.geometry("2000x1200")
        self.minsize(1200, 900)
        self.configure(bg="#2c3e50")

        # Menu with Help
        m = tk.Menu(self); self.config(menu=m)
        m.add_command(label="Help", command=self.open_help)

        self.init_state()
        self.create_layout()
        self.setup_bindings()
        self.load_session()   # ⬅ restore last session (after UI exists)
        self.cleanup_temp_files()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ── State ──
    def init_state(self):
        self.files = []
        self.current_index = 0
        self.original_images = {}
        self.processed_images = {}

        self.mask_cache = {}
        self._preview_job = None

        self._suspend_sync = False

        self.outline_thickness = tk.IntVar(value=10)
        self.outline_color = "#ff0000"
        self.solid_outline_color = "#000000"
        self.bg_reveal_outline_color = "#000000"
        self.bg_remove = tk.BooleanVar(value=False)
        self.bg_threshold = tk.DoubleVar(value=0.5)
        self.keep_original_bg = tk.BooleanVar(value=True)
        self.bg_blend_alpha = tk.DoubleVar(value=0.3)
        self.contextual_outline = tk.BooleanVar(value=False)
        self.contextual_thickness = tk.IntVar(value=15)
        self.solid_outline = tk.BooleanVar(value=False)
        self.solid_outline_thickness = tk.IntVar(value=5)
        self.bg_reveal_outline = tk.BooleanVar(value=False)
        self.bg_reveal_outline_thickness = tk.IntVar(value=4)
        self.overlay_flossiness = tk.DoubleVar(value=0.5)
        self.preview_mode = tk.StringVar(value="outlined")

        self.save_only_final = tk.BooleanVar(value=False)

        # Brush edit state
        self.edit_mode = tk.StringVar(value="off")   # off / keep / remove
        self.brush_size = tk.IntVar(value=30)
        self._painting = False

        # Lock reveal option + cache per image
        self.lock_reveal_outline = tk.BooleanVar(value=False)
        self.frozen_subj_masks = {}  # path -> bool ndarray (subject mask used for reveal when locked)

        # per-image manual masks + history
        self.user_keep_masks = {}    # path -> bool ndarray
        self.user_remove_masks = {}  # path -> bool ndarray
        self.history = {}            # path -> list[(keep, remove)]
        self.future = {}             # path -> list[(keep, remove)]

        # Brush preview overlays
        self._brush_preview_tag = {'orig': 'brush_preview_orig', 'proc': 'brush_preview_proc'}

        self.zoom_levels = {'orig': 1.0, 'proc': 1.0}
        self.pan_offsets = {'orig': [0, 0], 'proc': [0, 0]}
        self.last_mouse_pos = {'orig': None, 'proc': None}
        self.is_panning = {'orig': False, 'proc': False}

        self.output_dir = ""
        self.presets = load_presets()
        self.current_preset = "Default"

        # Sync + persist on changes
        self.outline_thickness.trace_add("write", self._sync_thickness_pair)
        self.contextual_thickness.trace_add("write", self._sync_reveal_pair)
        self.contextual_outline.trace_add("write", lambda *_: (self.update_reveal_controls(), self._sync_thickness_pair(), self.save_session()))
        self.edit_mode.trace_add("write", lambda *_: (self._on_edit_mode_changed(), self.save_session()))
        self.solid_outline.trace_add("write", lambda *_: (self.update_solid_controls(), self.save_session()))
        self.lock_reveal_outline.trace_add("write", lambda *_: (self._on_lock_reveal_toggle(), self.save_session()))
        self.bg_remove.trace_add("write", lambda *_: self.save_session())
        self.bg_threshold.trace_add("write", lambda *_: self.save_session())
        self.keep_original_bg.trace_add("write", lambda *_: self.save_session())
        self.bg_blend_alpha.trace_add("write", lambda *_: self.save_session())
        self.solid_outline_thickness.trace_add("write", lambda *_: self.save_session())
        self.bg_reveal_outline.trace_add("write", lambda *_: (self.update_reveal_controls(), self.save_session()))
        self.bg_reveal_outline_thickness.trace_add("write", lambda *_: self.save_session())
        self.overlay_flossiness.trace_add("write", lambda *_: self.save_session())
        self.preview_mode.trace_add("write", lambda *_: self.save_session())
        self.save_only_final.trace_add("write", lambda *_: self.save_session())
        self.brush_size.trace_add("write", lambda *_: self.save_session())

    # ── UI ──
    def create_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        left_frame = ttk.Frame(self)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        left_frame.configure(width=420)

        right_frame = ttk.Frame(self)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=0)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_columnconfigure(1, weight=1)

        self.build_left(left_frame)
        self.build_right(right_frame)

    def build_left(self, parent):
        parent.grid_rowconfigure(0, weight=0)
        parent.grid_rowconfigure(1, weight=0)
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_rowconfigure(3, weight=0)
        parent.grid_rowconfigure(4, weight=0)
        parent.grid_rowconfigure(5, weight=0)
        parent.grid_rowconfigure(6, weight=0)
        parent.grid_columnconfigure(0, weight=1)

        # Presets
        preset_frame = tk.LabelFrame(parent, text="Presets", padx=5, pady=5)
        preset_frame.grid(row=0, column=0, sticky="ew", pady=2)
        top = tk.Frame(preset_frame); top.pack(fill=tk.X)
        tk.Label(top, text="Preset:").pack(side=tk.LEFT)
        self.preset_var = tk.StringVar(value=self.current_preset)
        self.preset_combo = ttk.Combobox(top, textvariable=self.preset_var, values=list(self.presets.keys()))
        self.preset_combo.pack(side=tk.LEFT, padx=5)
        self.preset_combo.bind("<<ComboboxSelected>>", self.load_preset)
        tk.Button(top, text="Save", command=self.save_preset).pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="Delete", command=self.delete_preset).pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="New", command=self.new_preset).pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="Help", command=self.open_help).pack(side=tk.RIGHT, padx=2)

        # Files
        file_frame = tk.Frame(parent, bg="#3498db", bd=2, relief="raised")
        file_frame.grid(row=1, column=0, sticky="ew", pady=2)
        btn = tk.Button(file_frame, text="📁 LOAD IMAGES", command=self.load_files,
                        bg="#2980b9", fg="white", font=("Arial", 10, "bold"),
                        relief="flat", height=2)
        btn.pack(fill=tk.X, padx=5, pady=5)
        ToolTip(btn, "Add images to the list. Drag & drop works, too.")

        # List
        list_frame = tk.Frame(parent, bg="#2c3e50", bd=2, relief="sunken")
        list_frame.grid(row=2, column=0, sticky="nsew", pady=2)
        tk.Label(list_frame, text="📋 IMAGES:", bg="#2c3e50", fg="white", font=("Arial", 9, "bold")).pack(pady=2)
        self.file_list = tk.Listbox(list_frame, height=5, selectmode=tk.EXTENDED, bg="#34495e", fg="white", relief="flat", font=("Arial", 8))
        self.file_list.pack(fill=tk.BOTH, expand=True, padx=3, pady=2)
        self.file_list.bind("<<ListboxSelect>>", self.on_select)

        # File controls (remove/delete)
        controls = tk.Frame(list_frame, bg="#2c3e50")
        controls.pack(fill=tk.X, padx=3, pady=3)

        rem_btn = tk.Button(controls, text="Remove Selected",
                            command=self.remove_selected_from_list)
        rem_btn.pack(side=tk.LEFT, padx=2)

        rem_all_btn = tk.Button(controls, text="Clear All",
                                command=self.remove_all_from_list)
        rem_all_btn.pack(side=tk.LEFT, padx=2)

        del_btn = tk.Button(controls, text="Delete Selected (Disk)…",
                            command=self.delete_selected_from_disk,
                            bg="#c0392b", fg="white")
        del_btn.pack(side=tk.RIGHT, padx=2)

        ToolTip(rem_btn, "Remove from list (does not touch your files).")
        ToolTip(rem_all_btn, "Remove all from list (does not touch your files).")
        ToolTip(del_btn, "PERMANENTLY delete selected files from disk.")

        # Remove from list with Delete key
        self.file_list.bind("<Delete>", lambda e: self.remove_selected_from_list())

        # Settings
        settings = tk.LabelFrame(parent, text="Settings", padx=5, pady=5)
        settings.grid(row=3, column=0, sticky="ew", pady=2)

        # Background
        bg = tk.Frame(settings, bg="#c0392b", bd=1, relief="sunken")
        bg.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(bg, text="🖼️ BACKGROUND", font=("Arial", 9, "bold"), bg="#c0392b", fg="white").pack(pady=3)

        self.bg_remove_check = tk.Checkbutton(bg, text="Remove Background (Subject Isolation)",
                                              variable=self.bg_remove, bg="#c0392b", fg="white",
                                              font=("Arial", 8), command=self.schedule_preview)
        self.bg_remove_check.pack(anchor=tk.W, padx=5)
        ToolTip(self.bg_remove_check, "Cut the subject onto transparency. Used by Reveal/Outlines.")

        self.keep_bg_check = tk.Checkbutton(bg, text="Keep Original Background (blend subject alpha)",
                                            variable=self.keep_original_bg, bg="#c0392b", fg="white",
                                            font=("Arial", 8), command=self.schedule_preview)
        self.keep_bg_check.pack(anchor=tk.W, padx=5)
        ToolTip(self.keep_bg_check, "Preview the subject translucently over the original scene (no hard cut).")

        tf = tk.Frame(bg, bg="#c0392b"); tf.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(tf, text="Threshold:", bg="#c0392b", fg="white", font=("Arial", 8)).pack(side=tk.LEFT)
        self.threshold_slider = tk.Scale(tf, from_=0.1, to=0.9, resolution=0.01, orient=tk.HORIZONTAL,
                                         variable=self.bg_threshold, bg="#c0392b", fg="white", length=120,
                                         troughcolor="#e74c3c", command=lambda _=None: self.schedule_preview())
        self.threshold_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.threshold_entry = tk.Entry(tf, width=8); self.threshold_entry.pack(side=tk.LEFT)
        self.threshold_entry.bind("<Return>", lambda e: self.update_from_entry(self.bg_threshold, self.threshold_entry))
        ToolTip(self.threshold_slider, "Higher = tighter subject. No model rerun; reuses cached mask.")

        bf = tk.Frame(bg, bg="#c0392b"); bf.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(bf, text="Blend Alpha:", bg="#c0392b", fg="white", font=("Arial", 8)).pack(side=tk.LEFT)
        self.blend_slider = tk.Scale(bf, from_=0.0, to=1.0, resolution=0.01, orient=tk.HORIZONTAL,
                                     variable=self.bg_blend_alpha, bg="#c0392b", fg="white", length=120,
                                     troughcolor="#e74c3c", command=lambda _=None: self.schedule_preview())
        self.blend_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.blend_entry = tk.Entry(bf, width=8); self.blend_entry.pack(side=tk.LEFT)
        self.blend_entry.bind("<Return>", lambda e: self.update_from_entry(self.bg_blend_alpha, self.blend_entry))
        ToolTip(self.blend_slider, "When 'Keep Background' is on, controls translucency of the subject.")

        # Outline
        ol = tk.Frame(settings, bg="#27ae60", bd=1, relief="sunken")
        ol.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(ol, text="🎨 OUTLINE", font=("Arial", 9, "bold"), bg="#27ae60", fg="white").pack(pady=3)

        cf = tk.Frame(ol, bg="#27ae60"); cf.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(cf, text="Outline Color:", bg="#27ae60", fg="white", font=("Arial", 8)).pack(side=tk.LEFT)
        self.color_btn = tk.Button(cf, text="Pick", bg=self.outline_color, fg="white",
                                   font=("Arial", 8, "bold"), command=self.choose_color, relief="flat", width=6)
        self.color_btn.pack(side=tk.LEFT, padx=6)
        ToolTip(self.color_btn, "Color for the main outline when 'Background Reveal' is OFF.")

        tf2 = tk.Frame(ol, bg="#27ae60"); tf2.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(tf2, text="Thickness:", bg="#27ae60", fg="white", font=("Arial", 8)).pack(side=tk.LEFT)
        self.thickness_slider = tk.Scale(tf2, from_=0, to=200, orient=tk.HORIZONTAL,
                                         variable=self.outline_thickness, bg="#27ae60", fg="white", length=120,
                                         troughcolor="#2ecc71", command=lambda _=None: self.schedule_preview())
        self.thickness_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.thickness_entry = tk.Entry(tf2, width=8); self.thickness_entry.pack(side=tk.LEFT)
        self.thickness_entry.bind("<Return>", lambda e: self.update_from_entry(self.outline_thickness, self.thickness_entry))
        ToolTip(self.thickness_slider, "Outline width (also drives Reveal width when enabled).")

        self.contextual_check = tk.Checkbutton(ol, text="Background Reveal (Contextual Outline)",
                                               variable=self.contextual_outline, bg="#27ae60", fg="white",
                                               font=("Arial", 8), command=self.schedule_preview)
        self.contextual_check.pack(anchor=tk.W, padx=5)
        ToolTip(self.contextual_check, "Shows a ring from the original background around the subject.")

        rv_line = tk.Frame(ol, bg="#27ae60"); rv_line.pack(fill=tk.X, padx=20, pady=2)
        tk.Label(rv_line, text="Reveal width:", bg="#27ae60", fg="white", font=("Arial", 8)).pack(side=tk.LEFT)
        self.contextual_slider = tk.Scale(rv_line, from_=5, to=200, orient=tk.HORIZONTAL,
                                          variable=self.contextual_thickness,
                                          command=lambda _=None: self.schedule_preview(), length=160)
        self.contextual_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.contextual_entry = tk.Entry(rv_line, width=8); self.contextual_entry.pack(side=tk.LEFT)
        self.contextual_entry.bind("<Return>", lambda e: self.update_from_entry(self.contextual_thickness, self.contextual_entry))
        ToolTip(self.contextual_slider, "Width of that background ring (pixels).")

        soli_line = tk.Frame(ol, bg="#27ae60"); soli_line.pack(fill=tk.X, padx=5, pady=2)
        self.solid_check = tk.Checkbutton(soli_line, text="Solid Color Outline", variable=self.solid_outline,
                                          bg="#27ae60", fg="white", font=("Arial", 8),
                                          command=self.schedule_preview)
        self.solid_check.pack(side=tk.LEFT)
        self.solid_color_btn = tk.Button(soli_line, text="Color", command=self.choose_solid_color,
                                         bg=self.solid_outline_color, fg="white", width=6)
        self.solid_color_btn.pack(side=tk.LEFT, padx=8)
        tk.Label(soli_line, text="Width:", bg="#27ae60", fg="white", font=("Arial", 8)).pack(side=tk.LEFT)
        self.solid_thickness_slider = tk.Scale(soli_line, from_=1, to=160, orient=tk.HORIZONTAL,
                                               variable=self.solid_outline_thickness,
                                               command=lambda _=None: self.schedule_preview(), length=140)
        self.solid_thickness_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.solid_thickness_entry = tk.Entry(soli_line, width=6); self.solid_thickness_entry.pack(side=tk.LEFT)
        self.solid_thickness_entry.bind("<Return>", lambda e: self.update_from_entry(self.solid_outline_thickness, self.solid_thickness_entry))
        ToolTip(self.solid_check, "Adds a colored ring outside the reveal for a bold sticker look.")

        adv = tk.LabelFrame(settings, text="Advanced Outlining", padx=5, pady=5)
        adv.pack(fill=tk.X, pady=5)
        rf = tk.Frame(adv); rf.pack(fill=tk.X, pady=2)
        self.reveal_check = tk.Checkbutton(rf, text="Background-Reveal Outline (decorative)",
                                           variable=self.bg_reveal_outline, command=self.schedule_preview)
        self.reveal_check.pack(side=tk.LEFT)
        self.reveal_color_btn = tk.Button(rf, text="Color", command=self.choose_reveal_color,
                                          bg=self.bg_reveal_outline_color, width=8)
        self.reveal_color_btn.pack(side=tk.LEFT, padx=5)
        tk.Label(rf, text="Thickness:").pack(side=tk.LEFT)
        self.reveal_thickness_slider = tk.Scale(rf, from_=1, to=80, orient=tk.HORIZONTAL,
                                                variable=self.bg_reveal_outline_thickness,
                                                command=lambda _=None: self.schedule_preview(), length=140)
        self.reveal_thickness_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.reveal_thickness_entry = tk.Entry(rf, width=8); self.reveal_thickness_entry.pack(side=tk.LEFT)
        self.reveal_thickness_entry.bind("<Return>", lambda e: self.update_from_entry(self.bg_reveal_outline_thickness, self.reveal_thickness_entry))

        # Lock reveal outline so brushing won't shift the reveal ring
        lock_line = tk.Frame(adv); lock_line.pack(fill=tk.X, pady=2)
        self.lock_reveal_check = tk.Checkbutton(lock_line, text="Lock Reveal Outline (freeze current subject for reveal)",
                                                variable=self.lock_reveal_outline, command=self.schedule_preview)
        self.lock_reveal_check.pack(side=tk.LEFT)
        ToolTip(self.lock_reveal_check, "When ON, the background-reveal ring uses a frozen subject mask so brushing won’t move it. Uncheck to update again.")

        self.contextual_outline.trace_add("write", lambda *_: self.update_reveal_controls())
        self.bg_reveal_outline.trace_add("write", lambda *_: self.update_reveal_controls())
        self.update_reveal_controls()
        self.update_solid_controls()

        # Preview mode
        mf = tk.Frame(settings); mf.pack(fill=tk.X, pady=2)
        tk.Label(mf, text="Preview:").pack(side=tk.LEFT)
        for mode in ["original", "bg_removed", "outlined"]:
            tk.Radiobutton(mf, text=mode.title(), variable=self.preview_mode, value=mode,
                           command=self.schedule_preview).pack(side=tk.LEFT, padx=10)

        # Brush-based Mask Editing
        edit = tk.LabelFrame(parent, text="Mask Editing (hover shows brush size)", padx=5, pady=5)
        edit.grid(row=4, column=0, sticky="ew", pady=4)
        tk.Radiobutton(edit, text="Off", variable=self.edit_mode, value="off").pack(side=tk.LEFT, padx=4)
        tk.Radiobutton(edit, text="Keep (+)", variable=self.edit_mode, value="keep").pack(side=tk.LEFT, padx=4)
        tk.Radiobutton(edit, text="Remove (–)", variable=self.edit_mode, value="remove").pack(side=tk.LEFT, padx=4)
        ToolTip(edit, "Paint on ORIGINAL or PROCESSED: 'Keep' adds to subject, 'Remove' subtracts. Overlay only — never draws on your image.")
        tk.Label(edit, text="Brush:").pack(side=tk.LEFT, padx=6)
        self.brush_slider = tk.Scale(edit, from_=3, to=300, orient=tk.HORIZONTAL,
                                     variable=self.brush_size, length=160, command=lambda _=None: self._refresh_brush_preview())
        self.brush_slider.pack(side=tk.LEFT)
        self.undo_btn = tk.Button(edit, text="⟲ Undo", command=self.undo_edit)
        self.undo_btn.pack(side=tk.LEFT, padx=6)
        self.redo_btn = tk.Button(edit, text="⟳ Redo", command=self.redo_edit)
        self.redo_btn.pack(side=tk.LEFT)
        ToolTip(self.undo_btn, "Ctrl+Z")
        ToolTip(self.redo_btn, "Ctrl+Y")

        # Output
        out = tk.LabelFrame(parent, text="Output", padx=5, pady=5)
        out.grid(row=5, column=0, sticky="ew", pady=2)
        top = tk.Frame(out); top.pack(fill=tk.X)
        tk.Label(top, text="Output Folder:").pack(side=tk.LEFT)
        self.output_entry = tk.Entry(top, width=40); self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.output_entry.insert(0, self.output_dir)
        tk.Button(top, text="Browse...", command=self.browse_output_dir).pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="Clear", command=self.clear_output_dir).pack(side=tk.LEFT, padx=2)

        drop = tk.Frame(out, bg="lightblue", relief="groove", bd=2); drop.pack(fill=tk.X, pady=5)
        tk.Label(drop, text="Drop a folder here for output", bg="lightblue", font=("Arial", 9)).pack(pady=10)
        drop.drop_target_register(DND_FILES); drop.dnd_bind("<<Drop>>", self.on_output_drop)

        # Actions
        act = tk.Frame(parent); act.grid(row=6, column=0, sticky="ew", pady=2)
        tk.Button(act, text="Previous", command=self.prev_image).pack(side=tk.LEFT, padx=2)
        tk.Button(act, text="Next", command=self.next_image).pack(side=tk.LEFT, padx=2)

        # Save controls
        tk.Label(act, text=" | Save:").pack(side=tk.LEFT, padx=10)
        self.save_current_btn = tk.Button(act, text="Current", command=self.save_current, bg="#4CAF50", fg="white")
        self.save_current_btn.pack(side=tk.LEFT, padx=2)
        self.save_selected_btn = tk.Button(act, text="Selected", command=self.save_selected, bg="#2196F3", fg="white")
        self.save_selected_btn.pack(side=tk.LEFT, padx=2)
        self.save_batch_btn = tk.Button(act, text="Batch", command=self.save_batch, bg="#FF9800", fg="white")
        self.save_batch_btn.pack(side=tk.LEFT, padx=2)

        self.final_only_check = tk.Checkbutton(act, text="Save only final", variable=self.save_only_final)
        self.final_only_check.pack(side=tk.LEFT, padx=12)
        self.save_final_now_btn = tk.Button(act, text="Save Final (Current)", command=self.save_final_current, bg="#673AB7", fg="white")
        self.save_final_now_btn.pack(side=tk.LEFT, padx=2)

        self.file_count_label = tk.Label(parent, text="Selected: 0 / Total: 0", font=("Arial", 8))
        self.file_count_label.grid(row=7, column=0, sticky="ew", pady=2)

    def build_right(self, parent):
        left = tk.Frame(parent, bg="#34495e", bd=2, relief="groove")
        left.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        left.grid_rowconfigure(1, weight=1); left.grid_columnconfigure(0, weight=1)
        lh = tk.Frame(left, bg="#34495e"); lh.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        tk.Label(lh, text="📷 ORIGINAL", font=("Arial", 12, "bold"), bg="#34495e", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(lh, text="FIT", command=lambda: self.fit_view('orig'), bg="#27ae60", fg="white",
                  font=("Arial", 9, "bold"), relief="flat").pack(side=tk.RIGHT, padx=2)
        self.original_canvas = tk.Canvas(left, bg="#2c3e50", relief="sunken", bd=2)
        self.original_canvas.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        right = tk.Frame(parent, bg="#e74c3c", bd=2, relief="groove")
        right.grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
        right.grid_rowconfigure(1, weight=1); right.grid_columnconfigure(0, weight=1)
        rh = tk.Frame(right, bg="#e74c3c"); rh.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        tk.Label(rh, text="✨ PROCESSED", font=("Arial", 12, "bold"), bg="#e74c3c", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(rh, text="FIT", command=lambda: self.fit_view('proc'), bg="#27ae60", fg="white",
                  font=("Arial", 9, "bold"), relief="flat").pack(side=tk.RIGHT, padx=2)
        self.processed_canvas = tk.Canvas(right, bg="#2c3e50", relief="sunken", bd=2)
        self.processed_canvas.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self.status_label = tk.Label(parent, text="🎯 STATUS: Ready | Wheel: ZOOM | Drag: PAN | Double-click: FIT | Edit: Keep/Remove on ORIGINAL & PROCESSED",
                                     font=("Arial", 9), bg="#2c3e50", fg="#ecf0f1")
        self.status_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)

        self.file_info_label = tk.Label(parent, text="No image loaded", font=("Arial", 10))
        self.file_info_label.grid(row=2, column=0, columnspan=2, pady=5)

    # ── Bindings / helpers ──
    def setup_bindings(self):
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self.drop)

        # ORIGINAL canvas
        self.original_canvas.bind("<MouseWheel>", lambda e: self.on_mouse_wheel(e, 'orig'))
        self.original_canvas.bind("<ButtonPress-1>", lambda e: self._press(e, 'orig'))
        self.original_canvas.bind("<B1-Motion>",  lambda e: self._drag(e, 'orig'))
        self.original_canvas.bind("<ButtonRelease-1>", lambda e: self._release(e, 'orig'))
        self.original_canvas.bind("<Double-Button-1>", lambda e: self.fit_view('orig'))
        self.original_canvas.bind("<Motion>", lambda e: self._on_motion(e, 'orig'))
        self.original_canvas.bind("<Leave>",  lambda e: self.hide_brush_preview('orig'))

        # PROCESSED canvas
        self.processed_canvas.bind("<MouseWheel>", lambda e: self.on_mouse_wheel(e, 'proc'))
        self.processed_canvas.bind("<ButtonPress-1>", lambda e: self._press(e, 'proc'))
        self.processed_canvas.bind("<B1-Motion>",  lambda e: self._drag(e, 'proc'))
        self.processed_canvas.bind("<ButtonRelease-1>", lambda e: self._release(e, 'proc'))
        self.processed_canvas.bind("<Double-Button-1>", lambda e: self.fit_view('proc'))
        self.processed_canvas.bind("<Motion>", lambda e: self._on_motion(e, 'proc'))
        self.processed_canvas.bind("<Leave>",  lambda e: self.hide_brush_preview('proc'))

        self.bind("<Configure>", self.on_window_resize)
        self.bind("<Control-s>", lambda e: self.save_current())
        self.bind("<Control-Shift-s>", lambda e: self.save_selected())
        self.bind("<Control-b>", lambda e: self.save_batch())
        self.bind("<Control-z>", lambda e: self.undo_edit())
        self.bind("<Control-y>", lambda e: self.redo_edit())

    def status(self, text):
        self.status_label.config(text=f"🎯 STATUS: {text}")
        self.update_idletasks()

    def busy(self, on=True):
        try:
            self.config(cursor="watch" if on else "")
            self.update_idletasks()
        except Exception:
            pass

    def schedule_preview(self, delay_ms=120):
        if self._preview_job:
            try: self.after_cancel(self._preview_job)
            except Exception: pass
        # Persist settings whenever a change schedules a preview
        self.save_session()
        self._preview_job = self.after(delay_ms, self.show_preview)

    def update_from_entry(self, var, entry):
        try:
            raw = entry.get().strip()
            val = float(raw) if isinstance(var, tk.DoubleVar) else int(raw)
            var.set(val)
            self.schedule_preview()
        except Exception:
            entry.bell()

    def update_reveal_controls(self, *_):
        contextual_on = self.contextual_outline.get()
        reveal_on = self.bg_reveal_outline.get()
        self.reveal_check.config(state=tk.NORMAL if contextual_on else tk.DISABLED)
        dep_state = tk.NORMAL if (contextual_on and reveal_on) else tk.DISABLED
        for w in (self.reveal_color_btn, self.reveal_thickness_slider, self.reveal_thickness_entry):
            w.config(state=dep_state)
        self.lock_reveal_check.config(state=(tk.NORMAL if contextual_on else tk.DISABLED))

    def update_solid_controls(self):
        st = tk.NORMAL if self.solid_outline.get() else tk.DISABLED
        for w in (self.solid_color_btn, self.solid_thickness_slider, self.solid_thickness_entry):
            w.config(state=st)

    def _sync_thickness_pair(self, *_):
        if not self.contextual_outline.get(): return
        if self._suspend_sync: return
        try:
            self._suspend_sync = True
            self.contextual_thickness.set(self.outline_thickness.get())
        finally:
            self._suspend_sync = False
        self.schedule_preview()

    def _sync_reveal_pair(self, *_):
        if not self.contextual_outline.get(): return
        if self._suspend_sync: return
        try:
            self._suspend_sync = True
            self.outline_thickness.set(self.contextual_thickness.get())
        finally:
            self._suspend_sync = False
        self.schedule_preview()

    # ── Canvas nav + paint/preview ──
    def on_mouse_wheel(self, event, key):
        canvas = self.original_canvas if key == 'orig' else self.processed_canvas
        x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
        zoom_factor = 1.1 if event.delta > 0 else 0.9
        new_zoom = max(0.1, min(5.0, self.zoom_levels[key] * zoom_factor))
        if new_zoom != self.zoom_levels[key]:
            self.set_zoom(key, new_zoom, center=(x, y))
        other = 'proc' if key == 'orig' else 'orig'
        self.zoom_levels[other] = new_zoom
        self.pan_offsets[other] = self.pan_offsets[key].copy()
        self.redraw_canvas(other)
        self._refresh_brush_preview()

    def set_zoom(self, key, zoom, center=None):
        old = self.zoom_levels[key]
        self.zoom_levels[key] = zoom
        if center and old != 0:
            zr = zoom / old
            dx = center[0] * (1 - zr)
            dy = center[1] * (1 - zr)
            self.pan_offsets[key][0] = self.pan_offsets[key][0] * zr + dx
            self.pan_offsets[key][1] = self.pan_offsets[key][1] * zr + dy
        self.redraw_canvas(key)

    def _press(self, event, key):
        if self.edit_mode.get() == "off":
            self.on_pan_start(event, key)
        else:
            self._painting = True
            self.push_history()
            self.paint_at_event(event, key)
            # Do NOT schedule preview while painting (lag fix)
            self.update_brush_preview(key, event.x, event.y)

    def _drag(self, event, key):
        if self.edit_mode.get() == "off":
            self.on_pan_drag(event, key)
        else:
            if self._painting:
                self.paint_at_event(event, key)
                # no preview updates mid-stroke
                self.update_brush_preview(key, event.x, event.y)

    def _release(self, event, key):
        if self.edit_mode.get() == "off":
            self.on_pan_end(event, key)
        else:
            self._painting = False
            # update once the stroke finishes
            self.schedule_preview()

    def _on_motion(self, event, key):
        if self.edit_mode.get() != "off":
            self.update_brush_preview(key, event.x, event.y)

    def _on_edit_mode_changed(self):
        cur = "tcross" if self.edit_mode.get() != "off" else ""
        for c in (self.original_canvas, self.processed_canvas):
            try: c.config(cursor=cur)
            except Exception: pass
        if self.edit_mode.get() == "off":
            self.hide_brush_preview('orig'); self.hide_brush_preview('proc')

    def _refresh_brush_preview(self):
        self.hide_brush_preview('orig')
        self.hide_brush_preview('proc')

    def canvas_to_image_xy(self, key, cx, cy):
        z = self.zoom_levels[key]
        px, py = self.pan_offsets[key]
        ix = int((cx - px) / z)
        iy = int((cy - py) / z)
        return ix, iy

    def update_brush_preview(self, key, cx, cy):
        if self.edit_mode.get() == "off":
            self.hide_brush_preview(key)
            return
        canvas = self.original_canvas if key == 'orig' else self.processed_canvas
        tag = self._brush_preview_tag[key]
        try: canvas.delete(tag)
        except Exception: pass
        r = max(1, int(self.brush_size.get() * self.zoom_levels[key]))
        x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r
        canvas.create_oval(x0-1, y0-1, x1+1, y1+1, outline="black", width=2, tags=(tag,))
        canvas.create_oval(x0, y0, x1, y1, outline="white", width=1, tags=(tag,))

    def hide_brush_preview(self, key):
        canvas = self.original_canvas if key == 'orig' else self.processed_canvas
        tag = self._brush_preview_tag[key]
        try: canvas.delete(tag)
        except Exception: pass

    # Paint into user masks
    def paint_at_event(self, event, key):
        if not self.files: return
        path = self.files[self.current_index]
        if path not in self.original_images: return
        img = self.original_images[path]
        w, h = img.size
        ix, iy = self.canvas_to_image_xy(key, event.x, event.y)
        if ix < 0 or iy < 0 or ix >= w or iy >= h:
            return

        keep = self.user_keep_masks.get(path)
        remove = self.user_remove_masks.get(path)
        if keep is None or keep.shape[:2] != (h, w):
            keep = np.zeros((h, w), dtype=bool); self.user_keep_masks[path] = keep
        if remove is None or remove.shape[:2] != (h, w):
            remove = np.zeros((h, w), dtype=bool); self.user_remove_masks[path] = remove

        r = max(1, int(self.brush_size.get()))
        yy, xx = np.ogrid[-iy:h-iy, -ix:w-ix]
        disk = xx*xx + yy*yy <= r*r

        mode = self.edit_mode.get()
        if mode == "keep":
            keep[disk] = True
            remove[disk] = False
        elif mode == "remove":
            remove[disk] = True
            keep[disk] = False
        else:
            return

        self.status(f"Painting {mode} at {ix},{iy} (r={r}) on {'ORIGINAL' if key=='orig' else 'PROCESSED'}")
        # NO schedule_preview while dragging

    # history helpers for undo/redo brush edits
    def push_history(self):
        if not self.files: return
        path = self.files[self.current_index]
        img = self.original_images.get(path)
        if img is None: return
        w, h = img.size
        k = self.user_keep_masks.get(path)
        r = self.user_remove_masks.get(path)
        if k is None or k.shape[:2] != (h, w):
            k = np.zeros((h, w), dtype=bool)
        if r is None or r.shape[:2] != (h, w):
            r = np.zeros((h, w), dtype=bool)
        self.user_keep_masks[path] = k
        self.user_remove_masks[path] = r
        self.history.setdefault(path, []).append((k.copy(), r.copy()))
        self.future[path] = []  # clear redo on new edit

    def undo_edit(self):
        if not self.files: return
        path = self.files[self.current_index]
        if not self.history.get(path): return
        cur_k = self.user_keep_masks.get(path)
        cur_r = self.user_remove_masks.get(path)
        self.future.setdefault(path, []).append((cur_k.copy(), cur_r.copy()))
        prev_k, prev_r = self.history[path].pop()
        self.user_keep_masks[path] = prev_k
        self.user_remove_masks[path] = prev_r
        self.schedule_preview()

    def redo_edit(self):
        if not self.files: return
        path = self.files[self.current_index]
        if not self.future.get(path): return
        cur_k = self.user_keep_masks.get(path)
        cur_r = self.user_remove_masks.get(path)
        self.history.setdefault(path, []).append((cur_k.copy(), cur_r.copy()))
        next_k, next_r = self.future[path].pop()
        self.user_keep_masks[path] = next_k
        self.user_remove_masks[path] = next_r
        self.schedule_preview()

    # Pan helpers
    def on_pan_start(self, event, key):
        self.is_panning[key] = True
        self.last_mouse_pos[key] = (event.x, event.y)

    def on_pan_drag(self, event, key):
        if self.is_panning[key] and self.last_mouse_pos[key]:
            dx = event.x - self.last_mouse_pos[key][0]
            dy = event.y - self.last_mouse_pos[key][1]
            self.pan_offsets[key][0] += dx
            self.pan_offsets[key][1] += dy
            self.last_mouse_pos[key] = (event.x, event.y)
            self.redraw_canvas(key)
            other = 'proc' if key == 'orig' else 'orig'
            self.pan_offsets[other][0] += dx
            self.pan_offsets[other][1] += dy
            self.redraw_canvas(other)

    def on_pan_end(self, event, key):
        self.is_panning[key] = False
        self.last_mouse_pos[key] = None

    def fit_view(self, key):
        canvas = self.original_canvas if key == 'orig' else self.processed_canvas
        cw, ch = canvas.winfo_width(), canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            canvas.after(100, lambda: self.fit_view(key)); return
        if not self.files: return
        path = self.files[self.current_index]
        if path not in self.original_images: return
        img = self.original_images[path]
        iw, ih = img.size
        padding = 20
        scale = min((cw - padding) / iw, (ch - padding) / ih, 1.0)
        self.zoom_levels[key] = scale
        self.pan_offsets[key] = [0, 0]
        self.redraw_canvas(key)
        other = 'proc' if key == 'orig' else 'orig'
        self.zoom_levels[other] = scale
        self.pan_offsets[other] = [0, 0]
        self.redraw_canvas(other)
        self._refresh_brush_preview()

    def redraw_canvas(self, key):
        canvas = self.original_canvas if key == 'orig' else self.processed_canvas
        if not self.files or self.current_index >= len(self.files): return
        path = self.files[self.current_index]
        if path not in self.original_images: return
        img = self.original_images[path] if key == 'orig' else self.processed_images.get(path, self.original_images[path])
        zoom = self.zoom_levels[key]
        pan_x, pan_y = self.pan_offsets[key]
        nw, nh = int(img.width * zoom), int(img.height * zoom)
        if nw > 0 and nh > 0:
            resized = img.resize((nw, nh), Image.LANCZOS)
            photo = ImageTk.PhotoImage(resized)
            canvas.delete("all")
            canvas.create_image(pan_x + nw//2, pan_y + nh//2, image=photo, anchor=tk.CENTER)
            setattr(self, f"{key}_photo", photo)  # keep ref

    def on_window_resize(self, _):
        if self.files:
            self.after(100, lambda: self.fit_view('orig'))

    # ── File list sync & controls ──
    def sync_list_selection_to_current(self, preserve_other_selection=False):
        """Refresh the list so the active item is obvious and selected.
        - Adds a '▶ ' marker to the active row.
        - Optionally preserves multi-selection when user clicked in the list.
        """
        if not hasattr(self, "file_list"):
            return
        if not self.files:
            self.file_list.delete(0, tk.END)
            self.update_file_count()
            return

        previous_selection = set(self.file_list.curselection()) if preserve_other_selection else set()

        # Rebuild list with a marker on the active row
        self.file_list.delete(0, tk.END)
        for i, f in enumerate(self.files):
            name = os.path.basename(f)
            prefix = "▶ " if i == self.current_index else "  "
            self.file_list.insert(tk.END, f"{prefix}{name}")

        if preserve_other_selection:
            for i in previous_selection:
                if 0 <= i < len(self.files):
                    self.file_list.selection_set(i)
        else:
            self.file_list.selection_clear(0, tk.END)
            if 0 <= self.current_index < len(self.files):
                self.file_list.selection_set(self.current_index)

        self.file_list.activate(self.current_index)
        self.file_list.see(self.current_index)
        self.update_file_count()

    # ── File ops ──
    def load_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp *.tiff")])
        if files:
            self.files.extend(files)
            self.current_index = len(self.files) - 1
            self.sync_list_selection_to_current(preserve_other_selection=False)
            self.update_file_count()
            self.mask_cache.clear()
            self.schedule_preview()

    def drop(self, event):
        files = self.tk.splitlist(event.data)
        valid = [f for f in files if os.path.isfile(f) and f.lower().endswith(('.jpg','.jpeg','.png','.gif','.bmp','.tiff'))]
        if valid:
            self.files.extend(valid)
            self.current_index = len(self.files) - 1
            self.sync_list_selection_to_current(preserve_other_selection=False)
            self.update_file_count()
            self.mask_cache.clear()
            self.schedule_preview()

    def update_file_list(self):
        self.sync_list_selection_to_current(preserve_other_selection=True)

    def update_file_count(self):
        total = len(self.files); selected = len(self.file_list.curselection())
        self.file_count_label.config(text=f"Selected: {selected} / Total: {total}")

    def on_select(self, event):
        self.update_file_count()
        sel = event.widget.curselection()
        if sel:
            self.current_index = sel[0]
            # preserve multi-selection the user made, but update the ▶ marker
            self.sync_list_selection_to_current(preserve_other_selection=True)
            self.schedule_preview()

    def prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            # when navigating, make the current one *the* selection
            self.sync_list_selection_to_current(preserve_other_selection=False)
            self.schedule_preview()

    def next_image(self):
        if self.current_index < len(self.files) - 1:
            self.current_index += 1
            self.sync_list_selection_to_current(preserve_other_selection=False)
            self.schedule_preview()

    # Remove/Clear/Delete helpers
    def _remove_paths(self, indices, delete_from_disk=False):
        """Remove items by indices from the list (optionally delete from disk),
        clean up caches, and keep current_index valid.
        """
        if not indices:
            return

        indices = sorted(set(int(i) for i in indices))
        paths = [self.files[i] for i in indices]

        if delete_from_disk:
            if not messagebox.askyesno(
                "Delete from disk",
                f"PERMANENTLY delete {len(paths)} file(s) from disk?\nThis cannot be undone."
            ):
                return

        for i in reversed(indices):
            if not (0 <= i < len(self.files)):
                continue
            path = self.files[i]

            if delete_from_disk:
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"Delete failed for {path}: {e}")

            # Remove from list and purge all caches for this path
            self.files.pop(i)
            self.original_images.pop(path, None)
            self.processed_images.pop(path, None)
            self.user_keep_masks.pop(path, None)
            self.user_remove_masks.pop(path, None)
            self.history.pop(path, None)
            self.future.pop(path, None)
            self.mask_cache.pop(path, None)
            self.frozen_subj_masks.pop(path, None)

            if i < self.current_index:
                self.current_index -= 1

        if self.current_index >= len(self.files):
            self.current_index = max(0, len(self.files) - 1)

        self.sync_list_selection_to_current(preserve_other_selection=False)
        if self.files:
            self.schedule_preview()
        else:
            self.original_canvas.delete("all")
            self.processed_canvas.delete("all")
            self.file_info_label.config(text="No image loaded")
            self.status("Ready")
        self.update_file_count()

    def remove_selected_from_list(self):
        sel = self.file_list.curselection()
        if not sel:
            messagebox.showinfo("Nothing selected", "Select one or more files to remove from the list.")
            return
        self._remove_paths(sel, delete_from_disk=False)

    def remove_all_from_list(self):
        if not self.files:
            return
        if not messagebox.askyesno("Clear all?", "Remove ALL files from the list? (Does NOT delete from disk)"):
            return
        self._remove_paths(range(len(self.files)), delete_from_disk=False)

    def delete_selected_from_disk(self):
        sel = self.file_list.curselection()
        if not sel:
            messagebox.showinfo("Nothing selected", "Select one or more files to delete from disk.")
            return
        self._remove_paths(sel, delete_from_disk=True)

    # ── Color pickers ──
    def choose_color(self):
        color = colorchooser.askcolor(color=self.outline_color, title="Choose Outline Color")
        if color[1]:
            self.outline_color = color[1]
            self.color_btn.config(bg=self.outline_color)
            self.schedule_preview()

    def choose_solid_color(self):
        color = colorchooser.askcolor(color=self.solid_outline_color, title="Choose Solid Outline Color")
        if color[1]:
            self.solid_outline_color = color[1]
            self.solid_color_btn.config(bg=self.solid_outline_color)
            self.schedule_preview()

    def choose_reveal_color(self):
        color = colorchooser.askcolor(color=self.bg_reveal_outline_color, title="Choose Background-Reveal Outline Color")
        if color[1]:
            self.bg_reveal_outline_color = color[1]
            self.reveal_color_btn.config(bg=self.bg_reveal_outline_color)
            self.schedule_preview()

    # ── Mask helpers ──
    def _compute_float_mask(self, img):
        size = 1024
        w, h = img.size
        scale = min(size / w, size / h)
        nw, nh = int(round(w * scale)), int(round(h * scale))
        dx, dy = (size - nw) // 2, (size - nh) // 2

        resized = img.resize((nw, nh), Image.BILINEAR)
        canvas = Image.new("RGB", (size, size), (0, 0, 0))
        canvas.paste(resized, (dx, dy))

        to_tensor = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225]),
        ])
        t = to_tensor(canvas).unsqueeze(0).to(device)

        with torch.no_grad():
            preds = model(t)[0]
            pred = torch.sigmoid(preds)[0, 0].cpu().numpy()

        crop = pred[dy:dy+nh, dx:dx+nw]
        crop_img = Image.fromarray((crop * 255).astype(np.uint8))
        mask_full = crop_img.resize((w, h), Image.BILINEAR)
        return np.asarray(mask_full, dtype=np.float32) / 255.0

    def get_float_mask(self, img, path):
        if path in self.mask_cache:
            return self.mask_cache[path]
        try:
            self.busy(True); self.status("Computing mask…")
            m = self._compute_float_mask(img)
            self.mask_cache[path] = m
            return m
        finally:
            self.busy(False); self.status("Ready")

    def _ensure_user_masks(self, path, size):
        w, h = size
        k = self.user_keep_masks.get(path)
        r = self.user_remove_masks.get(path)
        if k is None or k.shape[:2] != (h, w):
            k = np.zeros((h, w), dtype=bool); self.user_keep_masks[path] = k
        if r is None or r.shape[:2] != (h, w):
            r = np.zeros((h, w), dtype=bool); self.user_remove_masks[path] = r
        return k, r

    def build_boolean_mask(self, original_img: Image.Image, path: str) -> np.ndarray:
        """Returns boolean subject mask (with threshold + user edits)."""
        m = self.get_float_mask(original_img, path)
        thr = float(self.bg_threshold.get())
        base = m > thr
        keep, remove = self._ensure_user_masks(path, original_img.size)
        base = (base | keep) & (~remove)
        return base

    # ── Render steps ──
    def remove_background(self, img, path):
        base = self.build_boolean_mask(img, path)
        alpha_mask = (base.astype(np.uint8)) * 255
        mask_pil = Image.fromarray(alpha_mask, mode="L")

        rgba = img.convert("RGBA")
        rgba.putalpha(mask_pil)

        if self.keep_original_bg.get():
            alpha = max(0.0, min(1.0, float(self.bg_blend_alpha.get())))
            soft = Image.fromarray((alpha_mask * (alpha)).astype(np.uint8), mode="L")
            result = img.copy()
            result.putalpha(soft)
            return result

        return rgba

    def _on_lock_reveal_toggle(self):
        """Capture or ignore the frozen reveal subject mask based on the toggle."""
        if not self.files:
            return
        path = self.files[self.current_index]
        if not self.lock_reveal_outline.get():
            return
        # Capture current subject mask for reveal
        orig = self.original_images.get(path)
        if orig is None:
            try:
                orig = Image.open(path).convert("RGB")
                self.original_images[path] = orig
            except Exception:
                return
        self.frozen_subj_masks[path] = self.build_boolean_mask(orig, path).copy()

    def _get_subject_mask_for_reveal(self, subject_img_rgba: Image.Image, original_img_rgb: Image.Image, path: str) -> np.ndarray:
        """Return subject mask to drive reveal/outline."""
        if self.lock_reveal_outline.get() and path in self.frozen_subj_masks:
            return self.frozen_subj_masks[path]
        arr = np.array(subject_img_rgba)
        return (arr[:, :, 3] > 10)

    def _compute_required_padding(self) -> int:
        """Compute how many pixels to pad so the outline never clips."""
        if self.contextual_outline.get():
            pad = int(self.contextual_thickness.get())
            if self.bg_reveal_outline.get():
                pad += int(self.bg_reveal_outline_thickness.get())
            if self.solid_outline.get():
                pad += int(self.solid_outline_thickness.get())
            return max(0, pad)
        else:
            return max(0, int(self.outline_thickness.get()))

    def add_outline(self, subject_img, original_img, path):
        # Determine padding to avoid clipped outlines
        pad = self._compute_required_padding()

        # Prepare images with padding
        subject = subject_img.convert("RGBA")
        sw, sh = subject.size
        subject_padded = Image.new("RGBA", (sw + 2*pad, sh + 2*pad), (0,0,0,0))
        subject_padded.paste(subject, (pad, pad))

        # Keep transparent padding (no edge stretching)
        original_rgba = original_img.convert("RGBA")
        original_padded = pad_with_transparent(original_rgba, pad)

        # Subject mask (optionally frozen) and padded
        subj_mask = self._get_subject_mask_for_reveal(subject, original_img, path)
        subj_mask_padded = np.pad(subj_mask, pad_width=pad, mode='constant', constant_values=False)

        # Mask for the exact original-image area inside the padded canvas
        img_extent = np.zeros_like(subj_mask_padded, dtype=bool)
        img_extent[pad:pad+sh, pad:pad+sw] = True

        base = Image.new("RGBA", subject_padded.size, (0,0,0,0))
        base = Image.alpha_composite(base, subject_padded)

        if self.contextual_outline.get():
            # ---- Contextual (background reveal) ring ----
            reveal_px = int(self.contextual_thickness.get())
            struct = create_disk_structure(max(0, reveal_px))

            expanded = binary_dilation(subj_mask_padded, structure=struct)
            # never let contextual ring go past the image bounds
            expanded_clipped = expanded & img_extent
            reveal_ring = expanded_clipped & (~subj_mask_padded)

            # Paste original background where the clipped reveal ring is
            reveal_mask = Image.fromarray((reveal_ring * 255).astype(np.uint8), mode="L")
            base.paste(original_padded, (0,0), reveal_mask)

            # Optional decorative color ring just outside the reveal
            if self.bg_reveal_outline.get():
                deco_th = int(self.bg_reveal_outline_thickness.get())
                deco_struct = create_disk_structure(max(0, deco_th))
                # Build off the CLIPPED reveal so it hugs the border with no gap
                deco_outer = binary_dilation(reveal_ring, structure=deco_struct)
                deco_only = deco_outer & (~reveal_ring)
                deco_mask = Image.fromarray((deco_only * 255).astype(np.uint8), mode="L")
                color_img = Image.new("RGBA", base.size, hex_to_rgba_tuple(self.bg_reveal_outline_color))
                base.paste(color_img, (0,0), deco_mask)

            # Optional solid outline outside everything
            if self.solid_outline.get():
                so_th = int(self.solid_outline_thickness.get())
                so_struct = create_disk_structure(max(0, so_th))
                # base the solid outline on the CLIPPED expansion
                outer = binary_dilation(expanded_clipped, structure=so_struct)
                solid_only = outer & (~expanded_clipped)
                solid_mask = Image.fromarray((solid_only * 255).astype(np.uint8), mode="L")
                color_img = Image.new("RGBA", base.size, hex_to_rgba_tuple(self.solid_outline_color))
                base.paste(color_img, (0,0), solid_mask)

        else:
            # ---- Simple solid outline (non-contextual) ----
            th = int(self.outline_thickness.get())
            struct2 = create_disk_structure(max(0, th))
            dil = binary_dilation(subj_mask_padded, structure=struct2)
            outline_mask = Image.fromarray(((dil & (~subj_mask_padded)) * 255).astype(np.uint8), mode="L")
            color_img = Image.new("RGBA", base.size, hex_to_rgba_tuple(self.outline_color))
            base.paste(color_img, (0,0), outline_mask)

        return base

    def build_final_image(self, original_img, path):
        mode = self.preview_mode.get()
        img = original_img.copy()
        if mode in ("bg_removed", "outlined") and self.bg_remove.get():
            img = self.remove_background(original_img, path)
        if mode == "outlined":
            img = self.add_outline(img, original_img, path)
        return img

    def show_preview(self):
        if not self.files or self.current_index >= len(self.files): return
        path = self.files[self.current_index]
        try:
            if path not in self.original_images:
                self.original_images[path] = Image.open(path).convert("RGB")

            original_img = self.original_images[path]
            processed = self.build_final_image(original_img, path)

            self.processed_images[path] = processed
            self.redraw_canvas('orig'); self.redraw_canvas('proc')
            self.file_info_label.config(text=f"{os.path.basename(path)} - {original_img.size[0]}x{original_img.size[1]} - Mode: {self.preview_mode.get()}")
            self.status("Ready")
        except Exception as e:
            print(f"Error in show_preview: {e}")
            self.status("Error (see console)")
            self.file_info_label.config(text=f"Error loading {os.path.basename(path)}")

    # ── Saving ──
    def save_current(self):
        if not self.files or self.current_index >= len(self.files):
            messagebox.showerror("Error", "No current image to save"); return
        output_dir = self.get_output_dir_or_prompt()
        if not output_dir: return
        current_file = self.files[self.current_index]
        self.process_and_save([current_file], output_dir, final_only=self.save_only_final.get())

    def save_final_current(self):
        if not self.files or self.current_index >= len(self.files):
            messagebox.showerror("Error", "No current image to save"); return
        output_dir = self.get_output_dir_or_prompt()
        if not output_dir: return
        current_file = self.files[self.current_index]
        self.process_and_save([current_file], output_dir, final_only=True)

    def save_selected(self):
        sel = self.file_list.curselection()
        if not sel:
            messagebox.showerror("Error", "No images selected"); return
        output_dir = self.get_output_dir_or_prompt()
        if not output_dir: return
        selected_files = [self.files[i] for i in sel]
        self.process_and_save(selected_files, output_dir, final_only=self.save_only_final.get())

    def save_batch(self):
        if not self.files:
            messagebox.showerror("Error", "No images to save"); return
        output_dir = self.get_output_dir_or_prompt()
        if not output_dir: return
        self.process_and_save(self.files, output_dir, final_only=self.save_only_final.get())

    def get_output_dir_or_prompt(self):
        out = self.output_entry.get().strip()
        if not out:
            out = filedialog.askdirectory(title="Select Output Folder")
            if out: self.set_output_dir(out)
            else: return None
        if not os.path.exists(out): os.makedirs(out)
        return out

    def set_output_dir(self, path):
        self.output_dir = path
        self.output_entry.delete(0, tk.END); self.output_entry.insert(0, path)
        self.save_session()

    def browse_output_dir(self):
        d = filedialog.askdirectory(title="Select Output Folder")
        if d: self.set_output_dir(d)

    def clear_output_dir(self):
        self.output_dir = ""
        self.output_entry.delete(0, tk.END)
        self.save_session()

    def on_output_drop(self, event):
        files = self.tk.splitlist(event.data)
        if files:
            p = files[0]
            if os.path.isdir(p): self.set_output_dir(p)
            elif os.path.isfile(p): self.set_output_dir(os.path.dirname(p))

    def set_saving_ui(self, enabled: bool):
        for btn in (self.save_current_btn, self.save_selected_btn, self.save_batch_btn, self.save_final_now_btn):
            try: btn.config(state=tk.NORMAL if enabled else tk.DISABLED)
            except Exception: pass

    def process_and_save(self, file_paths, output_dir, final_only=False):
        total, ok, errs = len(file_paths), 0, 0
        self.set_saving_ui(False)
        self.status("Saving…")
        try:
            for path in file_paths:
                try:
                    base = os.path.splitext(os.path.basename(path))[0]
                    original = self.original_images.get(path, Image.open(path).convert("RGB"))

                    if final_only:
                        final_img = self.build_final_image(original, path)
                        final_img.save(os.path.join(output_dir, f"{base}_final.png"), "PNG")
                    else:
                        img = original.copy()
                        if self.bg_remove.get():
                            bg_removed = self.remove_background(original, path)
                            bg_removed.save(os.path.join(output_dir, f"{base}_bg_removed.png"), "PNG")
                            img = bg_removed

                        outlined = self.add_outline(img, original, path)
                        outlined.save(os.path.join(output_dir, f"{base}_outlined.png"), "PNG")

                        temp = self.outline_color
                        self.outline_color = "#ffffff"
                        white_outlined = self.add_outline(img, original, path)
                        self.outline_color = temp
                        white_outlined.save(os.path.join(output_dir, f"{base}_white_outlined.png"), "PNG")

                        if self.bg_remove.get():
                            bg_only = self.remove_background(original, path)
                            bg_only.save(os.path.join(output_dir, f"{base}_background_only.png"), "PNG")

                    ok += 1
                except Exception as e:
                    print(f"Error processing {path}: {e}")
                    errs += 1
        finally:
            self.set_saving_ui(True)
            self.status("Ready")

        messagebox.showinfo("Save Complete", f"Saved: {ok}/{total}" + (f" | Errors: {errs}" if errs else ""))

    # ── Presets / session ──
    def save_preset(self):
        name = self.preset_var.get().strip() or f"Preset_{datetime.datetime.now().strftime('%H%M%S')}"
        p = self._snapshot_settings(include_output=False)
        self.presets[name] = p
        save_presets(self.presets)
        self.preset_combo['values'] = list(self.presets.keys())
        self.preset_var.set(name)
        self.current_preset = name
        messagebox.showinfo("Success", f"Preset '{name}' saved successfully!")
        self.save_session()

    def load_preset(self, _=None):
        name = self.preset_var.get()
        if name not in self.presets: return
        self.current_preset = name
        self._apply_settings(self.presets[name], from_preset=True)
        self.schedule_preview()
        self.save_session()

    def delete_preset(self):
        name = self.preset_var.get()
        if name == "Default":
            messagebox.showerror("Error", "Cannot delete Default preset"); return
        if name in self.presets:
            del self.presets[name]
            save_presets(self.presets)
            self.preset_combo['values'] = list(self.presets.keys())
            self.preset_var.set("Default")
            self.load_preset()
            messagebox.showinfo("Success", f"Preset '{name}' deleted!")
            self.save_session()

    def new_preset(self):
        self.preset_var.set("New Preset"); self.preset_combo.focus()

    # ---------- Session persistence ----------
    def _snapshot_settings(self, include_output=True):
        snap = {
            "outline_thickness": self.outline_thickness.get(),
            "outline_color": self.outline_color,
            "bg_remove": self.bg_remove.get(),
            "bg_threshold": self.bg_threshold.get(),
            "keep_original_bg": self.keep_original_bg.get(),
            "bg_blend_alpha": self.bg_blend_alpha.get(),
            "contextual_outline": self.contextual_outline.get(),
            "contextual_thickness": self.contextual_thickness.get(),
            "solid_outline": self.solid_outline.get(),
            "solid_outline_color": self.solid_outline_color,
            "solid_outline_thickness": self.solid_outline_thickness.get(),
            "bg_reveal_outline": self.bg_reveal_outline.get(),
            "bg_reveal_outline_color": self.bg_reveal_outline_color,
            "bg_reveal_outline_thickness": self.bg_reveal_outline_thickness.get(),
            "overlay_flossiness": self.overlay_flossiness.get(),
            "save_only_final": self.save_only_final.get(),
            "preview_mode": self.preview_mode.get(),
            "brush_size": self.brush_size.get(),
            "lock_reveal_outline": self.lock_reveal_outline.get(),
            "current_preset": self.current_preset,
        }
        if include_output:
            snap["output_dir"] = self.output_dir
        return snap

    def _apply_settings(self, p, from_preset=False):
        # Set tk vars and UI (with fallbacks)
        self.outline_thickness.set(p.get("outline_thickness", 10))
        self.outline_color = p.get("outline_color", "#ff0000"); self.color_btn.config(bg=self.outline_color)
        self.bg_remove.set(p.get("bg_remove", False))
        self.bg_threshold.set(p.get("bg_threshold", 0.5))
        self.keep_original_bg.set(p.get("keep_original_bg", True))
        self.bg_blend_alpha.set(p.get("bg_blend_alpha", 0.3))
        self.contextual_outline.set(p.get("contextual_outline", False))
        self.contextual_thickness.set(p.get("contextual_thickness", 15))
        self.solid_outline.set(p.get("solid_outline", False))
        self.solid_outline_color = p.get("solid_outline_color", "#000000"); self.solid_color_btn.config(bg=self.solid_outline_color)
        self.solid_outline_thickness.set(p.get("solid_outline_thickness", 5))
        self.bg_reveal_outline.set(p.get("bg_reveal_outline", False))
        self.bg_reveal_outline_color = p.get("bg_reveal_outline_color", "#000000"); self.reveal_color_btn.config(bg=self.bg_reveal_outline_color)
        self.bg_reveal_outline_thickness.set(p.get("bg_reveal_outline_thickness", 4))
        self.overlay_flossiness.set(p.get("overlay_flossiness", 0.5))
        self.save_only_final.set(p.get("save_only_final", False))
        self.preview_mode.set(p.get("preview_mode", "outlined"))
        self.brush_size.set(p.get("brush_size", 30))
        self.lock_reveal_outline.set(p.get("lock_reveal_outline", False))

        # Preset/session label behavior
        if from_preset:
            self.current_preset = self.preset_var.get()
            try: self.preset_var.set(self.current_preset)
            except Exception: pass
        else:
            self.current_preset = "Last Session"
            try: self.preset_var.set(self.current_preset)
            except Exception: pass

        self.update_reveal_controls()
        self.update_solid_controls()

        # Output dir (if provided)
        if "output_dir" in p:
            self.set_output_dir(p.get("output_dir", ""))

    def load_session(self):
        try:
            if os.path.exists(LAST_SESSION_FILE):
                with open(LAST_SESSION_FILE, 'r') as f:
                    session = json.load(f)
                    # Backward compatible: if it was only {"output_dir": "..."}
                    if isinstance(session, dict) and ("outline_thickness" in session or "output_dir" in session):
                        self._apply_settings(session)
                        self.schedule_preview()
        except Exception as e:
            print("load_session error:", e)

    def save_session(self):
        try:
            with open(LAST_SESSION_FILE, 'w') as f:
                json.dump(self._snapshot_settings(include_output=True), f, indent=2)
        except Exception as e:
            print("save_session error:", e)

    def cleanup_temp_files(self):
        try:
            for file in os.listdir(CACHE_DIR):
                fp = os.path.join(CACHE_DIR, file)
                if os.path.isfile(fp):
                    os.remove(fp)
        except Exception:
            pass

    def open_help(self):
        win = tk.Toplevel(self)
        win.title("Help & Tips — Professional Image Studio V3.2")
        win.geometry("720x640")
        frame = tk.Frame(win); frame.pack(fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(frame); sb.pack(side=tk.RIGHT, fill=tk.Y)
        txt = tk.Text(frame, wrap=tk.WORD, yscrollcommand=sb.set)
        sb.config(command=txt.yview)
        txt.pack(fill=tk.BOTH, expand=True)
        guide = """
QUICK START
- Load an image ➜ choose Preview (Original / BG Removed / Outlined).
- Toggle "Remove Background" to isolate the subject.
- Optional: turn on "Background Reveal" to show a ring from the original scene.
- Paint with Keep(+) / Remove(–) on ORIGINAL or PROCESSED to fix small areas.
- Hover shows the brush circle; nothing is drawn onto your image—only the mask is edited.
- Save: use "Save only final" if you only want exactly what you see on PROCESSED.

WHAT'S NEW (3.2)
• No edge-stretch: when outlines go outside the original bounds, only the lines appear; the ring uses transparency beyond the photo.
• Full Last-Session restore: every setting you can pick is saved automatically and restored next launch.

LOCK REVEAL OUTLINE TIPS
• Turn ON to freeze the current reveal subject (per image). Adjust sliders freely; brushing will not shift the ring.
• To re-freeze after big edits: uncheck, then re-check to capture the new subject.
"""
        txt.insert("1.0", guide.strip())
        txt.config(state=tk.DISABLED)
        tk.Button(win, text="Close", command=win.destroy).pack(pady=6)

    def on_close(self):
        self.save_session()
        self.cleanup_temp_files()
        self.destroy()

# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = ImageProcessor()
    app.mainloop()
