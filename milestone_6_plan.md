# Milestone 6: Live Model Comparison UI

## Summary

Add a locally served, live side-by-side model comparison UI. Start with Gemini and Ollama, while keeping the layout ready for up to four models. Build the frontend workflow first and add the local API bridge last.

## Planned Experience

- Load the restaurants found in `eval/messy_set.json` into a selector.
- When a restaurant is selected, load and display all of its messy menu items, grouped by their source category.
- Start no model work until the user presses a single `Cleanup` button.
- When `Cleanup` is pressed, send every item for the selected restaurant to each selected model.
- Run selected models concurrently, with each model processing its items sequentially.
- Show a shared input column and one live result lane per model.
- Update each item as it moves through queued, running, completed, or failed states.
- Display normalized name, normalized description, item latency, success count, error count, and average latency.
- Treat "real time" as item-level progress through server-sent events; token streaming is excluded from this milestone.

## Implementation Steps

1. Add a locally served Vue/Vite interface with restaurant selection, a complete menu preview, model selection, a `Cleanup` action, progress lanes, and aggregate summaries.
2. Develop the complete interaction and visual states against a small local fixture adapter shaped like the eventual backend responses.
3. Configure Gemini and `qwen3:4b` as the initial choices while representing models as data so two more can be added without redesigning the UI.
4. Add a small FastAPI service as the final implementation step, reusing the existing cleanup backends and replacing the frontend fixture adapter.
5. Expose only the local endpoints needed for available models, restaurants and their menu items, starting a restaurant cleanup run, and subscribing to run events.
6. Keep active run state in memory and handle unavailable models and item-level failures without stopping the other model lanes.
7. Document the local commands and environment variables needed to run both processes.

## Local Interfaces

- `GET /api/models`: return configured models and availability.
- `GET /api/restaurants`: return the unique restaurants in the evaluation set, identified by `restaurant_id` and labeled with `restaurant`.
- `GET /api/restaurants/{restaurant_id}/items`: return every evaluation item for the selected restaurant in dataset order.
- `POST /api/runs`: accept a `restaurant_id` and selected model IDs, resolve all matching items on the server, and return a run ID.
- `GET /api/runs/{run_id}/events`: stream run, model, and item progress using server-sent events.

The service binds to the loopback interface and is not deployed or exposed publicly. The frontend accesses it only from the local Vite development server.

## Verification

Because this MVP explicitly excludes automated tests, verify manually that:

- Gemini and Ollama begin together and update independently.
- Selecting a restaurant displays all and only that restaurant's menu items before cleanup starts.
- Pressing `Cleanup` submits the complete displayed menu to every selected model.
- Successful results appear as each item completes.
- One backend failure does not interrupt the other lane.
- Aggregate counts and latency values update correctly.
- The interface works with two lanes and remains usable when configured with four.
- Reloading or restarting the API clearly discards in-memory runs.
- The frontend can be exercised with fixture data before the API is added, then behaves the same after switching to live local data.

## Assumptions

- The first version compares one restaurant from the evaluation set at a time rather than accepting a custom menu or arbitrary item selection.
- `restaurant_id` is the stable selector value; the restaurant name is display text.
- Models run concurrently with each other but sequentially within each lane.
- Existing backend defaults and environment variables remain authoritative.
- The UI and API are served only on the developer's machine. Gemini requests still leave the machine because Gemini is a hosted model; Ollama inference remains local.
- A local backend bridge is still required to call the Python backends and keep the Gemini API key out of browser code.
- Milestone 5 remains unfinished; this UI becomes the inspection tool used to complete it later.
