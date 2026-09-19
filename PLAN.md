# Menu Cleanup Model Comparison App

## Goal

Build a small, interactive app that cleans messy restaurant menu item names and
descriptions, then compares Gemini with self-hosted open-weight models on output
quality, latency, reliability, and operating requirements.

The first implementation uses Gemini only. Local inference and the shared model
interface are introduced after the cleanup workflow works end to end. Milestone 6
may be implemented before Milestone 5 is complete so the comparison app can be used
to inspect results and finish the evaluation.

**Cleanup output:**

```json
{
  "normalized_name": "Chicken Tikka Masala",
  "normalized_description": "Chicken tikka in a mild creamy tomato curry sauce."
}
```

Recommendations are a future product capability. They are intentionally separate
from cleanup and are not represented in the current prompts, schemas, or interfaces.

## Milestones

### 1. Curate reference menus

Curate clean restaurant menus to serve as canonical reference material. Store item
names and descriptions in `data/raw/menus.json`, with quality counts in
`data/raw/summary.json`. Every ID is globally unique.

### 2. Messy menu generation (eval set)

Deliberately corrupt sourced menu items with realistic typos, casing, spacing,
abbreviations, punctuation, and damaged or missing descriptions. Keep the original
item beside each corrupted input so normalized names and descriptions are available
as evaluation references. Store the resulting set in `eval/messy_set.json`.

### 3. Gemini cleanup pipeline

Implement a minimal command-line workflow that cleans one menu item or runs Gemini
across the evaluation set. Gemini returns only `normalized_name` and
`normalized_description` through a strict JSON schema. Batch results retain source
metadata, expected text, latency, status, and per-item errors for later analysis.

### 4. Self-hosted open-weight models

Run existing instruction-tuned open-weight models locally without training them.
Introduce a shared backend interface when the first local model is added, and give
every backend the same cleanup input and two-field output contract.

### 5. Gemini-versus-local evaluation

Evaluate Gemini and local models on cleanup quality, latency, reliability, and local
hardware requirements. Keep runs reproducible and make failures inspectable without
discarding successful item results. Use the comparison app from Milestone 6 as the
interactive inspection surface when completing this evaluation.

### 6. Comparison app

Build a locally served Vue.js frontend for running cleanup and inspecting Gemini and
local-model outputs side by side. Let the user choose a restaurant from
`eval/messy_set.json`, load and preview all of its messy menu items, select the models
to compare, and start the complete restaurant cleanup with a single `Cleanup` action.
Process model lanes concurrently and stream item-level status and results as each
model works through the menu. Show per-model success, error, and latency summaries.
Start with Gemini and Ollama and keep the interface ready for up to four models. Keep
the app small: no token streaming, authentication, multi-user support, database
persistence, custom menu input, or arbitrary item selection. Develop the frontend
workflow first with local fixture data, then add the minimal loopback-only API as the
last implementation step. Do not deploy or expose the app or API publicly.

### 7. Recommendations

Explore recommendations as a separate capability after cleanup and model comparison
are established. Define its behavior and interfaces at that point; do not extend the
cleanup contract in anticipation of it.

## Deliverables

- `scripts/` - dataset utilities and the Gemini cleanup runner
- `eval/` - the evaluation set and reproducible model results
- `backends/` - added with the first self-hosted model
- `frontend/` - locally served comparison UI, implemented first
- `api/` - minimal local backend bridge, implemented after the UI workflow
- `milestone_6_plan.md` - detailed comparison app behavior and implementation plan
- `results.md` - comparison results and error analysis
- `README.md` - project framing and run instructions
