# Menu Cleanup Model Comparison

This project cleans messy restaurant menu item names and descriptions, then compares
Gemini with self-hosted open-weight models. Both backends return the same two-field
JSON cleanup contract.

## Local setup

Install Ollama, then fetch the default local model:

```sh
ollama pull qwen3:4b
```

Ollama normally starts with its desktop app. To start it from a terminal instead,
run `ollama serve`. Confirm the service and installed models with:

```sh
ollama list
```

Clean one item locally:

```sh
python3 scripts/cleanup.py --backend ollama item \
  --name "chkn tika masla" \
  --description "chicken curry"
```

Run a small local batch:

```sh
python3 scripts/cleanup.py --backend ollama batch --limit 2
```

This writes `eval/results/ollama_qwen3_4b_cleanup.json`. Use `--model` to select a
different installed model or `--output` to select another result path.

## Gemini

Set `GEMINI_API_KEY` (or `GOOGLE_API_KEY`), or place the key in
`.gemini_api_key`. Then run:

```sh
python3 scripts/cleanup.py --backend gemini item \
  --name "chkn tika masla" \
  --description "chicken curry"

python3 scripts/cleanup.py --backend gemini batch --limit 2
```

The legacy `scripts/cleanup_with_gemini.py` entry point remains available and uses
Gemini by default.
