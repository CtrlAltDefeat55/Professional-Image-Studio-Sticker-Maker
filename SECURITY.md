# Security Policy

## Reporting

If you discover a vulnerability or privacy issue, please open a **GitHub issue** with **SECURITY** in the title or email the maintainers if you prefer not to disclose publicly. Avoid publishing exploit details; a maintainer will coordinate next steps and timelines.

## Data & privacy

- The app stores **presets** and **last‑session settings** locally under `image_studio_v3_data/` next to the script. No telemetry is collected.
- **Model download:** On first run, the app uses 🤗 Transformers to download the **BiRefNet** model and cache it locally for offline reuse.
- Image edits happen in memory; output files are written only to the folder you choose.

## Permissions & risks

- Drag‑and‑drop uses OS file paths; only files you load or export are accessed.
- A **Delete Selected (Disk)** action exists in the UI; it permanently removes files you select after a confirmation dialog.
- Always keep backups of originals; batch operations can overwrite files if you choose an existing name.

## Supported versions

Target: **Python 3.9+** with **Tk 8.6+** on Windows/macOS/Linux. CPU is fine; CUDA is optional if you have a compatible GPU.
