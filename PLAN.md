# Menu Enrichment Model Comparison App

## Goal

A simple, interactive app that enriches messy restaurant menu items — normalized name, normalized description, category, cuisine tag(s), and a confidence score — and lets you compare enrichment quality, cost, and latency across multiple models side by side: commercial API models (Claude/GPT/Gemini) alongside a self-hosted fine-tuned open-weight model. A Vue.js frontend drives the comparison interactively, backed by a real evaluation harness rather than eyeballed outputs.

**Example enrichment output (per item, per model):**

Input: `"chikcen tikka masala (creamy, mild spice)"` — $14.00

```json
{
  "normalized_name": "Chicken Tikka Masala",
  "normalized_description": "Chicken tikka in a mild creamy tomato curry sauce.",
  "category": "Curry",
  "cuisine": "Indian",
  "confidence": 0.94,
  "model": "claude-api",
  "latency_ms": 340,
  "cost_usd": 0.0021
}
```

The app's job is to produce this for the same item across every enabled model, then show accuracy, latency, and cost side by side.

## Milestones

### 1. Curate reference menus
Curate menus from a few specific cuisines in Tallinn to serve as the canonical reference material for our enricher (e.g Estonian, Italian, Asian, Middle Eastern). This milestone is purely about collecting clean, real input data (item name, description, price) — no labels involved yet. Store it at `data/raw/menus.json`, with `data/raw/summary.json` for basic quality counts. Every ID in `data/raw/menus.json` is globally unique across the entire file, including across cuisine buckets and entity types.

The curated JSON required limited manual cleanup for source-quality issues such as translation artifacts, duplicated descriptions, promotional copy, and descriptions that only repeated the item name.

### 2. Messy menu generation (eval set)
Deliberately corrupt our sourced menus via LLM — introduce typos, inconsistent casing, abbreviations, garbled or dropped descriptions — while keeping a mapping back to the original item. This gives three ground-truth fields for free, with no manual labeling needed: **normalized name** and **normalized description** (the original real values before corruption), and **cuisine** (already known from which cuisine bucket the restaurant was sourced under in milestone 1). Raw parent categories are available as evidence; map them into the controlled category taxonomy via an API model, using the item name and description when the source category is vague or promotional, then spot-check the results. This corrupted set, with its known-correct originals, becomes the eval set: run it through the enrichment pipeline and score how well each model restores the real name, description, and cuisine, plus accuracy on the normalized category and confidence calibration. Held out from "training" entirely.

### 3. Pluggable model backend interface
Define a common interface — e.g. `enrich(item, restaurant_context) -> EnrichmentResult` — that any model can implement, so the app can swap models without touching the rest of the pipeline. Each backend logs latency and cost alongside its structured output. Implement:
- **API backends** — Claude, GPT, and/or Gemini, called via their standard APIs
- **Local backend** — the self-hosted fine-tuned model (milestone 4), served via vLLM or Ollama
- **Zero-shot local backend** — the same open-weight base model *before* fine-tuning, as a third data point, so the comparison shows whether fine-tuning actually helped

This interface is the architectural core of the app — everything downstream (scoring, the dashboard) operates on `EnrichmentResult` objects regardless of which model produced them.

### 4. Fine-tuned open-weight model
Use an API model to generate a larger labeled training set (distillation) from the non-eval items. Fine-tune a small open-weight model (Llama 3.1 8B, Qwen2.5-7B, or similar) with LoRA — full fine-tune isn't needed. Self-host it and wire it into the backend interface from milestone 3 alongside its zero-shot counterpart.

### 5. Metrics and hardening
Score every backend against the eval set: per-field accuracy (category, cuisine) and confidence calibration (do stated confidence scores match actual accuracy — via `sklearn.calibration.calibration_curve` or manual Expected Calibration Error). Wrap these as repeatable, pytest-style tests with **DeepEval** rather than one-off scripts, so regressions are caught automatically. Use **Promptfoo** for quick side-by-side comparison runs across backends during development.

### 6. Comparison app (Vue.js)
The core deliverable. A small FastAPI (or similar) backend exposes: eval results per model, and a live "enrich this menu" endpoint that fans out to every enabled backend. A Vue.js frontend:
- Lets you pick a restaurant/menu from the dataset (or paste a custom item)
- Runs enrichment across all enabled models and shows outputs side by side, per item
- Shows an aggregate metrics table per model: accuracy, F1, latency, cost per 1,000 items, confidence calibration
- Toggle which models are included in the comparison

Keep this genuinely small — no auth, no multi-user support, no persistence beyond the eval/dataset files already on disk.

### 7. Stretch: real-world data validation
Stress-test the pipeline against **NYPL "What's on the Menu?"** — a public domain dataset of ~1.3M real transcribed dishes with names and prices from historical restaurant menus, available as a direct CSV download. Real, human-transcribed text is messier than synthetic generation tends to produce, so this checks whether the pipeline holds up beyond engineered test cases. Items would be auto-labeled by an API model, not hand-labeled.

### 8. Stretch: agentic + scoring layer
A lightweight agent that takes a raw, unstructured menu and produces the structured catalogue, flagging uncertain fields instead of guessing. A simple "merchant opportunity score" from catalogue completeness and category coverage.

## Deliverables
- `backends/` — the pluggable model interface and each backend implementation (API, local fine-tuned, local zero-shot)
- `eval/` — labeled eval set + DeepEval test suite
- `frontend/` — the Vue.js comparison app
- `api/` — the FastAPI service the frontend talks to
- `results.md` — the comparison numbers and error analysis
- `README.md` — problem framing, how to run it, and what it demonstrates

## Out of scope
- Ingredient guessing, ingredient-based menu suggestions, and popularity/opportunity-sizing features — deliberately dropped to keep the app simple and focused on the model-comparison core
- Production infra (k8s, autoscaling, etc.) — mention as "next steps" in the write-up, don't build it
- Large-scale fine-tuning — LoRA on a small model is sufficient to prove the concept
- Auth, multi-user support, or persistence beyond the dataset/eval files already on disk
