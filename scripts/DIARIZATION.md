# Diarization Setup

Optional speaker labeling via pyannote. Only needed when the source has multiple speakers (podcasts, interviews). Stand-up specials are single-speaker — you can skip this.

## One-time setup

1. Create a free Hugging Face account: https://huggingface.co/join
2. Create a read-access token: https://huggingface.co/settings/tokens
3. Accept the terms for both model repos:
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
4. Set the token in your environment (never commit it):

   ```bash
   export HF_TOKEN=hf_xxxx            # macOS/Linux
   # Windows PowerShell: $env:HF_TOKEN="hf_xxxx"
   ```

   Or add `HF_TOKEN=hf_xxxx` to a local `.env` file (gitignored).

5. Install pyannote: `pip install pyannote.audio==3.1.0`

## Run

```bash
python -m pipeline.scripts.transcribe --diarize
```

The pipeline downloads the pyannote models on first use (~1.1 GB). If diarization fails at runtime, transcription continues without speaker labels (unless `--no-fallback`).

After the models are cached, the token is no longer needed for inference — you can unset `HF_TOKEN`.
