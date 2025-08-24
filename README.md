# Image Background Sticker Maker (v3.2) — Tkinter + BiRefNet

Create high‑quality **sticker‑style images** by isolating the subject, adding a **background‑reveal ring**, and optionally stacking **solid color outlines** — all in a fast, desktop GUI.

This app loads **BiRefNet** via 🤗 Transformers for robust subject masks and gives you precise control with **keep/remove brush editing**, **undo/redo**, **zoom/pan/fit**, and **batch saving**.

> Core script: `ImageBackgroundStickerMaker_v3.py` (GUI)  
> Model: `ZhengPeng7/BiRefNet` (downloaded automatically on first run)

---

## Table of Contents

- [Features](#features)
- [User Interface](#user-interface)
- [Installation](#installation)
- [Usage](#usage)
  - [Load images](#load-images)
  - [Background removal](#background-removal)
  - [Reveal & outlines](#reveal--outlines)
  - [Brush editing](#brush-editing)
  - [Navigation](#navigation)
  - [Saving](#saving)
- [Dependencies](#dependencies)
- [Contributing](#contributing)
- [Security & privacy](#security--privacy)
- [Acknowledgments](#acknowledgments)

---

## Features

- **Subject segmentation with BiRefNet** (CPU by default, uses **CUDA** when available).
- **Background Reveal** ring using pixels from the original photo (no edge stretching at the canvas border).
- **Solid Color Outline** layer for bold “sticker” looks.
- **Lock Reveal Outline** to freeze the subject for reveal while you brush‑edit.
- **Keep/Remove brush** with live circular cursor, **Undo/Redo** history.
- **Drag & drop** files into the app; **remove/clear list**, or **delete from disk (with confirmation)**.
- **Zoom/Pan/Fit** synchronized across Original and Processed views.
- **Session restore**: your last settings are saved and auto‑restored.
- **Batch save** or save **final of current** only.

> Settings & session data are stored under `image_studio_v3_data/` next to the script.

## User Interface

<img width="1995" height="1241" alt="UI_Showing_V3_2" src="https://github.com/user-attachments/assets/d4f3c951-ca96-4f56-ade8-aecc82d5b61f" />


## Installation

Quick start (see **[INSTALL.md](INSTALL.md)** for detailed, per‑OS steps and GPU notes):

```bash
git clone https://github.com/<you>/image-background-sticker-maker.git
cd image-background-sticker-maker
python -m venv venv
# Windows
.\venv\Scripts\activate
# macOS/Linux
# source venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Usage

Run the GUI:

```bash
python ImageBackgroundStickerMaker_v3.py
```

### Load images
- Click **LOAD IMAGES** or **drag & drop** files into the window.
- Use **Remove Selected**, **Clear All**, or **Delete Selected (Disk)** as needed.

### Background removal
- Toggle **Remove Background (Subject Isolation)**.
- Adjust **Threshold** to tighten/loosen the mask.
- Optionally toggle **Keep Original Background (blend subject alpha)** and set **Blend Alpha**.

### Reveal & outlines
- Check **Background Reveal (Contextual Outline)** to show a ring from the original photo around the subject.  
  - Set **Reveal width**.
  - Optionally enable **Background‑Reveal Outline (decorative)** and set color/width.
- Check **Solid Color Outline** to add a bold outer ring and set its color and width.
- Use **Lock Reveal Outline** to freeze the reveal subject while brush‑editing.

### Brush editing
- Choose **Off / Keep (+) / Remove (–)** and paint on **Original** or **Processed** view.
- Use **Brush** slider to change radius.
- **Undo/Redo** your edits anytime.

### Navigation
- **Zoom** with mouse wheel/trackpad, **Pan** by dragging, **Double‑click** to fit.
- **Previous/Next** buttons step through the file list; the active item stays highlighted.

### Saving
- Pick an **Output Folder** (or drop a folder onto the drop‑zone).
- Choose **Save Final (Current)** for the processed sticker of the active image.
- Or **Save ➜ Current / Selected / Batch** to export many at once.
- Enable **Save only final** to skip intermediates.

## Dependencies

Installed via `requirements.txt`:

- `transformers` — loads BiRefNet segmentation model
- `torch`, `torchvision` — inference backend (CUDA used if available)
- `Pillow` — image I/O and compositing
- `numpy`, `scipy` — mask operations & morphology
- `tkinterdnd2` — drag & drop support for Tkinter

## Contributing

Contributions are welcome! Please read **[CONTRIBUTING.md](CONTRIBUTING.md)** for setup, style, and a testing checklist.

## Security & privacy

- First run downloads the segmentation model from Hugging Face and caches it locally. No telemetry is collected.
- The app only reads images you load and writes to the folder you choose. A **Delete Selected (Disk)** action exists — use with care.

See **[SECURITY.md](SECURITY.md)** for details.

## Acknowledgments

- **BiRefNet** model by *ZhengPeng7* on Hugging Face.
