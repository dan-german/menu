# Merchant Catalogue Enrichment — API Model vs. Fine-Tuned Open-Weight Model

## Goal

Given a raw, messy menu, produce a structured menu: normalized dish names, category, cuisine tag(s), dietary tags, guessed ingredients, and a confidence score. Use the guessed ingredients to suggest new menu items the restaurant could plausibly add, ranked by overlap with ingredients it likely already stocks. Then show a small fine-tuned open-weight model can match this quality at a fraction of the cost and latency of a third-party API model.

**Example:**

Input: `"chikcen tikka masala (creamy, mild spice)"` — $14.00

Output:
```json
{
  "normalized_name": "Chicken Tikka Masala",
  "category": "Curry",
  "cuisine": "Indian",
  "dietary_tags": ["contains_dairy"],
  "ingredients": ["chicken", "yogurt", "tomato", "cream", "garam masala", "ginger", "garlic"],
  "confidence": 0.94
}
```

## Milestones

### 1. Dataset
Generate a small synthetic raw menu dataset (`scripts/generate_raw_dataset.py`). The current target is 20 restaurants — 2 per cuisine across Indian, Mexican, Thai, Japanese, Chinese, Italian, Mediterranean, American diner, Korean, and Middle Eastern — with roughly 20 items per menu. This milestone is purely about collecting raw, messy input data — no labels involved yet. The generator deliberately asks for realistic messiness: typos, inconsistent casing, missing descriptions, abbreviations, vague item names like "Chef's Special," occasional cross-cuisine items, and natural menu gaps for opportunity sizing.

Store the menu-level dataset at `data/raw/synthetic_menus.json`. Write `data/raw/summary.json` with basic quality counts, including restaurant count, total item count, and item-count range per menu. Downstream item-level code should flatten menus in memory when needed rather than maintaining a separate raw item file.

### 2. Eval set
Hand-label (or LLM-label + spot-check) ~100 items with correct category, cuisine, and dietary tags, sampled across restaurants. Also generate a reference ingredient list per dish the same way — LLM-drafted, then human-reviewed — but review every item fully rather than sampling, since ingredient lists are fuzzier and disagreements are more likely to be subtle than obviously wrong. Reference ingredient lists are organized per restaurant, matching how they'll be aggregated and scored in milestone 5. Used to score ingredient guessing via precision/recall/F1 against the core ingredients. Ingredient ground truth is inherently fuzzier than category/cuisine, so treat mismatches as a judgment call rather than a strict pass/fail. Suggestion quality (are the recommended new dishes actually good) isn't scorable this way — that stays a manual review step, not part of the eval set. All of this is held out from training entirely, used only for scoring — rigor here matters more than volume.

### 3. Baseline: API model pipeline
Use Claude or GPT with a structured-output prompt (JSON schema) to enrich all items — including the ingredient guess alongside category, cuisine, and dietary tags. Log latency and token cost per item, then score against the eval set: per-field accuracy, ingredient precision/recall/F1, plus confidence calibration.

### 4. Fine-tuned open-weight model
Use the API model to generate a larger labeled training set (distillation) from the non-eval items. Fine-tune a small open-weight model (Llama 3.1 8B, Qwen2.5-7B, or similar) with LoRA — full fine-tune isn't needed. Self-host it (vLLM, Ollama, or similar) and run the same eval set through it, logging latency and estimated serving cost.

### 5. Ingredient-based menu suggestions (opportunity sizing)
Directly mirrors the "opportunity sizing" theme in the JD. For each dish, prompt the model to guess a likely ingredient list, scored against the eval set's reference ingredient lists (milestone 2) via precision/recall/F1. Aggregate guessed ingredients per restaurant into an ingredient inventory. Suggest new dishes the restaurant doesn't currently offer, ranked primarily by **ease of use** — ingredient overlap with what the restaurant already stocks, e.g. "already uses chicken, coconut milk, curry spices for 3 dishes → a Thai coconut curry only needs 1 new ingredient." Treat popularity as an optional, clearly-labeled soft signal (LLM's general knowledge of common dishes) rather than a scored metric, since there's no real popularity data available. Suggestion quality itself (are the recommended dishes actually good) isn't scorable numerically — review that manually rather than folding it into the eval metrics.

### 6. Comparison write-up
A table of accuracy, p50/p95 latency, and cost per 1,000 items across both models, plus error analysis on where each one fails. Keep the tradeoffs honest — the goal isn't to claim a small model beats a frontier one, it's "good enough at a fraction of the cost and latency."

### 7. Stretch: agentic + scoring layer
A lightweight agent that takes a raw, unstructured menu and produces the structured catalogue, flagging uncertain fields instead of guessing. A simple "merchant opportunity score" from catalogue completeness, category coverage, and pricing consistency.

## Deliverables
- `pipeline/` — enrichment code for both API and fine-tuned paths
- `eval/` — labeled eval set + scoring script
- `results.md` — the comparison table and error analysis
- `README.md` — problem framing, how to run it, and what it demonstrates

## Out of scope
- Production infra (k8s, autoscaling, etc.) — mention as "next steps" in the write-up, don't build it
- Large-scale fine-tuning — LoRA on a small model is sufficient to prove the concept
