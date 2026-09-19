<script setup>
import { computed, reactive, ref } from 'vue'
import messySet from '../../eval/messy_set.json'

const models = [
  { id: 'gemini', name: 'Gemini', backend: 'gemini' },
  { id: 'qwen3:4b', name: 'Qwen 3 4B', backend: 'ollama', model: 'qwen3:4b' },
  { id: 'qwen3.5:9b', name: 'Qwen 3.5 9B', backend: 'ollama', model: 'qwen3.5:9b' },
  { id: 'ministral-3:8b', name: 'Ministral 3 8B', backend: 'ollama', model: 'ministral-3:8b' },
  { id: 'gemma3:12b', name: 'Gemma 3 12B', backend: 'ollama', model: 'gemma3:12b' },
]

const defaultPrompt = 
`
You are a careful restaurant menu copy editor, not a copywriter.

Rewrite the provided menu item as polished, natural English. Make only the minimum edits needed for correctness and readability. Never infer, embellish, advertise, or add information.

GENERAL RULES

- Use neutral, factual language only.
- Preserve the original meaning exactly.
- Do not add facts, qualities, descriptors, or context that are not explicitly present.
- Do not introduce subjective or promotional words such as “crisp,” “fresh,” “delicious,” “tender,” “rich,” “perfect,” or “offers.”
- Return only the corrected name and description in the required format.

NAME

- Correct only capitalization, punctuation, abbreviations, and obvious food-related typos.
- Preserve the dish identity, ingredients, quantities, sizes, and set composition.
- Do not rename, reinterpret, or improve the dish.
- Do not replace correctly spelled food terms.
- Convert quantities written with “pc,” “pcs,” or “tk” to “(X pieces).”

DESCRIPTION

- Write one concise, complete sentence.
- Preserve every useful fact explicitly stated in the original description.
- Turn terse lists into grammatical prose using only the supplied words and facts.
- Do not add a subject such as “this dish,” “this wine,” or the item name unless required to form a grammatical sentence.
- Do not add ingredients, accompaniments, tasting notes, textures, preparation methods, origins, serving suggestions, or marketing claims.
- Do not strengthen or interpret existing descriptions. For example, do not change “white wine” to “crisp white wine.”
- Ignore meaningless or corrupted fragments.
- If the description is already grammatical and natural, leave it unchanged.
- If the description is empty, state only facts established by the name, quantity, and category.

Example:
Input description: “White wine. Pear, citrus, floral notes.”
Output description: “White wine with pear, citrus, and floral notes.”
`

const restaurants = [...new Map(
  messySet.map((item) => [item.restaurant_id, {
    id: item.restaurant_id,
    name: item.restaurant,
    cuisine: item.source_cuisine,
  }]),
).values()].sort((a, b) => a.name.localeCompare(b.name))

const selectedRestaurantId = ref(restaurants[0]?.id)
const selectedModelIds = ref(['qwen3.5:9b', 'qwen3:4b', 'ministral-3:8b', 'gemma3:12b'])
const prompt = ref(defaultPrompt)
const running = ref(false)
const results = reactive({})

const items = computed(() =>
  messySet.filter((item) => item.restaurant_id === selectedRestaurantId.value),
)

const categories = computed(() => {
  const grouped = new Map()
  for (const item of items.value) {
    if (!grouped.has(item.category_source)) grouped.set(item.category_source, [])
    grouped.get(item.category_source).push(item)
  }
  return [...grouped.entries()].map(([name, categoryItems]) => ({
    name,
    items: categoryItems,
  }))
})

const selectedModels = computed(() =>
  models.filter((model) => selectedModelIds.value.includes(model.id)),
)

function resultFor(modelId, itemId) {
  return results[`${modelId}:${itemId}`]
}

function summaryFor(modelId) {
  const modelResults = items.value
    .map((item) => resultFor(modelId, item.item_id))
    .filter(Boolean)
  const completed = modelResults.filter((result) => result.status === 'done').length
  const errors = modelResults.filter((result) => result.status === 'error').length
  const latencies = modelResults
    .filter((result) => result.latency)
    .map((result) => result.latency)

  return {
    completed,
    errors,
    average: latencies.length
      ? Math.round(latencies.reduce((total, value) => total + value, 0) / latencies.length)
      : 0,
  }
}

async function runModel(model) {
  for (const item of items.value) {
    const key = `${model.id}:${item.item_id}`
    results[key].status = 'running'

    try {
      const response = await fetch('/api/cleanup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          backend: model.backend,
          model: model.model,
          prompt: prompt.value,
          item: {
            restaurant: item.restaurant,
            category: item.category_source,
            name: item.messy_item.name,
            description: item.messy_item.description,
          },
        }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'Cleanup failed')

      results[key] = {
        status: 'done',
        latency: payload.latency_ms,
        name: payload.output.normalized_name,
        description: payload.output.normalized_description,
      }
    } catch (error) {
      results[key] = {
        status: 'error',
        error: error instanceof Error ? error.message : String(error),
      }
    }
  }
}

async function cleanup() {
  if (!selectedModels.value.length || running.value) return

  for (const model of selectedModels.value) {
    for (const item of items.value) {
      results[`${model.id}:${item.item_id}`] = { status: 'queued' }
    }
  }

  running.value = true
  const remoteModels = selectedModels.value.filter((model) => model.backend !== 'ollama')
  const localModels = selectedModels.value.filter((model) => model.backend === 'ollama')
  const remoteRuns = remoteModels.map(runModel)

  for (const model of localModels) {
    await runModel(model)
  }

  await Promise.all(remoteRuns)
  running.value = false
}
</script>

<template>
  <main>
    <header class="toolbar">
      <div class="title">
        <span class="mark">MC</span>
        <div>
          <h1>Menu Cleanup</h1>
          <p>Compare normalized menus</p>
        </div>
      </div>

      <label class="restaurant-field">
        <span>Restaurant</span>
        <select v-model="selectedRestaurantId" :disabled="running">
          <option
            v-for="restaurant in restaurants"
            :key="restaurant.id"
            :value="restaurant.id"
          >
            {{ restaurant.name }}
          </option>
        </select>
      </label>

      <fieldset class="models" :disabled="running">
        <legend>Models</legend>
        <label v-for="model in models" :key="model.id">
          <input
            v-model="selectedModelIds"
            type="checkbox"
            :value="model.id"
            :disabled="!selectedModelIds.includes(model.id) && selectedModelIds.length >= 4"
          />
          {{ model.name }}
        </label>
      </fieldset>

      <button
        class="cleanup-button"
        :disabled="running || !selectedModels.length || !prompt.trim()"
        @click="cleanup"
      >
        {{ running ? 'Cleaning...' : 'Cleanup' }}
      </button>
    </header>

    <section class="context">
      <div>
        <span class="eyebrow">Selected menu</span>
        <h2>{{ restaurants.find((restaurant) => restaurant.id === selectedRestaurantId)?.name }}</h2>
      </div>
      <span>{{ items.length }} items</span>
    </section>

    <label class="prompt-field">
      <span>Cleanup prompt</span>
      <textarea v-model="prompt" :disabled="running" rows="8"></textarea>
    </label>

    <section class="comparison" :style="{ '--model-count': selectedModels.length }">
      <div class="table-head input-head">Messy input</div>
      <div class="table-head original-head">Original</div>
      <div v-for="model in selectedModels" :key="model.id" class="table-head model-head">
        <div>
          <strong>{{ model.name }}</strong>
          <span>
            {{ summaryFor(model.id).completed }}/{{ items.length }} done
            <template v-if="summaryFor(model.id).average"> · {{ summaryFor(model.id).average }} ms avg</template>
          </span>
        </div>
        <span class="status-dot" :class="{ active: running }"></span>
      </div>

      <template v-for="category in categories" :key="category.name">
        <div class="category-row">{{ category.name }}</div>

        <template v-for="item in category.items" :key="item.item_id">
          <article class="cell input-cell">
            <strong>{{ item.messy_item.name }}</strong>
            <p>{{ item.messy_item.description || 'No description' }}</p>
          </article>

          <article class="cell original-cell">
            <strong>{{ item.original_item.name }}</strong>
            <p>{{ item.original_item.description || 'No description' }}</p>
          </article>

          <article v-for="model in selectedModels" :key="model.id" class="cell result-cell">
            <template v-if="resultFor(model.id, item.item_id)?.status === 'done'">
              <strong>{{ resultFor(model.id, item.item_id).name }}</strong>
              <p>{{ resultFor(model.id, item.item_id).description || 'No description' }}</p>
              <span>{{ resultFor(model.id, item.item_id).latency }} ms</span>
            </template>
            <template v-else-if="resultFor(model.id, item.item_id)?.status === 'error'">
              <strong class="error-title">Cleanup failed</strong>
              <p>{{ resultFor(model.id, item.item_id).error }}</p>
            </template>
            <span
              v-else
              class="state"
              :class="resultFor(model.id, item.item_id)?.status"
            >
              {{ resultFor(model.id, item.item_id)?.status || 'Not started' }}
            </span>
          </article>
        </template>
      </template>
    </section>
  </main>
</template>
