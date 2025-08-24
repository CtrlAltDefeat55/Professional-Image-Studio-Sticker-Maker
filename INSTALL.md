# Install & Run — Image Background Sticker Maker

**Cross‑platform** Tkinter GUI for making sticker‑style images with BiRefNet segmentation.

> **Compatibility:** Python **3.9+** and **Tk 8.6+**.  
> **Model:** First run will download **ZhengPeng7/BiRefNet** via 🤗 Transformers and cache it locally.  
> **GPU:** Uses CUDA automatically if PyTorch detects a supported GPU; otherwise runs on CPU.

## 1) Get the code

```bash
git clone https://github.com/<you>/image-background-sticker-maker.git
cd image-background-sticker-maker
```

## 2) Create a virtual environment (recommended)

```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# macOS/Linux
# source venv/bin/activate
```

## 3) Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux: install Tkinter (if missing)

Debian/Ubuntu:
```bash
sudo apt-get update
sudo apt-get install -y python3-tk
```

Fedora:
```bash
sudo dnf install -y python3-tkinter
```

### macOS notes

- If using Homebrew Python, you may need `brew install tcl-tk` and ensure your Python links against it.

### Windows notes

- No extra setup typically required.

### PyTorch notes

- The CPU wheels should install with `pip install torch torchvision` on most systems.
- For **GPU acceleration**, install the wheel matching your CUDA / platform per the official PyTorch instructions.

## 4) Run the app

```bash
python ImageBackgroundStickerMaker_v3.py
```

## 5) Uninstall / cleanup

Just remove the cloned folder. App settings live under `image_studio_v3_data/` next to the script and can be deleted if you want a fresh start.
