# gen-autodj-agent

Macro-First Ableton automation skeleton for the Invisible DJ hackathon track.

## Docs
* Architecture principles: `AGENTS.md`
* Project brief: `docs/project-brief.md`
* Working notes: `docs/working-notes.md`
* Super Rack setup: `docs/ableton-super-rack-setup.md`

## Install
```bash
brew install portaudio
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

## Environment
```bash
export GEMINI_API_KEY="YOUR_API_KEY"
```

## Dev Test Setup
```bash
PYTHONPATH=. pytest -q
```

## Quick Runtime Validation
```bash
python scripts/list_live_structure.py --max-params 24
python scripts/smoke_pylive.py --targets config/ableton_targets.json --all-targets --value 0.8
python main.py --targets config/ableton_targets.json --auto-play --auto-play-mode clip --auto-play-track 0 --auto-play-slot 0
```

## Gemini Live Dry Run (No Ableton Write)
```bash
python main.py \
  --gemini-live \
  --gemini-model gemini-2.5-flash-native-audio-preview-12-2025 \
  --gemini-video-fps 1.0 \
  --gemini-hold-sec 2.0 \
  --gemini-neutral-ramp-sec 1.0 \
  --prompt "차분하게 시작해서 드랍 전에 빌드업해줘" \
  --dry-run-controls
```
