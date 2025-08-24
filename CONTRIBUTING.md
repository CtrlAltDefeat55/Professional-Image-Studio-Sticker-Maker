# Contributing

Thanks for helping improve **Image Background Sticker Maker**! PRs and issues are welcome.

## Dev setup

```bash
git clone https://github.com/<you>/image-background-sticker-maker.git
cd image-background-sticker-maker
python -m venv venv
# Windows: .\venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
python -m pip install -r requirements.txt
```

## Project specifics

- **GUI:** Tkinter with `tkinterdnd2` drag‑and‑drop.
- **Segmentation:** 🤗 `transformers` + `torch` (BiRefNet). The first run will download model weights automatically.
- **State:** Presets & last session saved under `image_studio_v3_data/` next to the script.
- **Platforms:** Windows/macOS/Linux; uses CUDA if available, otherwise CPU.

## Style & quality

- Follow **PEP 8**; docstring new/changed functions.
- Keep PRs focused and bite‑sized.
- Recommended tooling:
  ```bash
  python -m pip install black ruff mypy
  black .
  ruff check .
  mypy .  # type hints encouraged but optional
  ```

## Testing checklist (please click through before submitting)

- ✅ App launches on your OS; file list & drag‑and‑drop work.
- ✅ Background removal toggles and **Threshold** behave as expected.
- ✅ **Background Reveal (Contextual Outline)** renders correctly; no fake/replicated pixels at edges.
- ✅ **Solid Color Outline** draws at the configured width/color.
- ✅ **Lock Reveal Outline** keeps the reveal stable while brush‑editing.
- ✅ Brush **Keep/Remove** works on both Original and Processed; **Undo/Redo** works.
- ✅ Zoom/Pan/Fit behave as expected across both canvases.
- ✅ **Save Final (Current)** and batch save options write files to the chosen output folder.
- ✅ “Delete Selected (Disk)” prompts and deletes only what you chose.

## Commit messages

Use clear, descriptive messages (e.g., `reveal: prevent edge stretch`, `brush: debounce preview updates`).

## Docs

If behavior changes (controls, shortcuts, outputs), update **README.md** and **INSTALL.md**.
