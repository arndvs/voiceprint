# Transcribe — Installation

`scripts/transcribe.py` turns audio/video into timestamped text transcripts. It uses OpenAI's Whisper for transcription and (optionally) pyannote for speaker diarization.

## Requirements

- **Python 3.9+**
- **ffmpeg + ffprobe** on PATH
  - Windows: place `ffmpeg.exe` and `ffprobe.exe` somewhere on PATH
  - macOS/Linux: `brew install ffmpeg` / `sudo apt install ffmpeg`
- **PyTorch** (see below)
- ~8 GB disk for Whisper model weights; a GPU with 8 GB+ VRAM recommended

## Install

1. Create a virtualenv and install PyTorch **first** (platform-specific):

   ```bash
   python -m venv .venv
   source .venv/bin/activate       # Windows: .venv\Scripts\activate
   # NVIDIA (Windows/Linux):
   pip install torch==2.2.1+cu121
   # Apple Silicon:
   pip install torch==2.2.1
   # Or follow https://pytorch.org for your platform
   ```

2. Install the transcriber deps:

   ```bash
   pip install -r scripts/requirements.txt
   ```

   Whisper downloads its model on first run (several GB for `turbo`), so expect a delay.

## Usage

```bash
python -m scripts.transcribe --dry-run                    # list media, don't transcribe
python -m scripts.transcribe                              # transcribe ./input → ./output
python -m scripts.transcribe source/jerry-seinfield/raw \
    --output-dir source/jerry-seinfield/transcripts
```

Flags: `--model`, `--no-timestamps`, `--no-recursive`, `--no-overwrite`, `--diarize`, `--dry-run`.

## Diarization (optional)

Speaker separation needs a free Hugging Face account + token. See `DIARIZATION.md`.

## Model choice

| Model | VRAM | Notes |
| ----- | ---- | ----- |
| `turbo` | ~6-7 GB | Fastest, up to ~20% fewer errors than `medium.en` on poor audio. Default. |
| `medium.en` | ~5-6 GB | Best accuracy on clean speech. |

CPU-only is possible but slow — a GPU is strongly recommended.
