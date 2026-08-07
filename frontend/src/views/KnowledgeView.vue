<script setup lang="ts">
/**
 * Drop zone for the knowledge base.
 *
 * Files and images dropped here go straight into the RAG store through the
 * backend, which forwards them to the MCP server's ingest tools. The document
 * type is derived from the file name unless one is picked explicitly.
 */
import { computed, onMounted, ref } from 'vue'

import { loadKnowledge, uploadDocuments } from '@/api/client'
import type { KnowledgeOverview, UploadResult } from '@/api/types'

const overview = ref<KnowledgeOverview | null>(null)
const queue = ref<File[]>([])
const results = ref<UploadResult[]>([])
const docType = ref('')
const caption = ref('')

const dragging = ref(false)
const busy = ref(false)
const error = ref('')

const fileInput = ref<HTMLInputElement | null>(null)

const accept = computed(() => {
  const data = overview.value?.accepts
  if (!data) return undefined
  return [...data.documents, ...data.images].join(',')
})

const counts = computed(() =>
  Object.entries(overview.value?.counts ?? {}).sort((a, b) => b[1] - a[1]),
)

function add(files: FileList | File[] | null): void {
  const incoming = Array.from(files ?? [])
  const known = new Set(queue.value.map((f) => `${f.name}:${f.size}`))
  queue.value = [
    ...queue.value,
    ...incoming.filter((f) => !known.has(`${f.name}:${f.size}`)),
  ]
}

function onDrop(event: DragEvent): void {
  dragging.value = false
  add(event.dataTransfer?.files ?? null)
}

function onPick(event: Event): void {
  const input = event.target as HTMLInputElement
  add(input.files)
  input.value = ''
}

function remove(index: number): void {
  queue.value.splice(index, 1)
}

function sizeLabel(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function refresh(): Promise<void> {
  try {
    overview.value = await loadKnowledge()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function upload(): Promise<void> {
  if (!queue.value.length || busy.value) return

  busy.value = true
  error.value = ''
  results.value = []
  try {
    const report = await uploadDocuments(queue.value, {
      docType: docType.value,
      caption: caption.value,
    })
    results.value = report.results
    queue.value = queue.value.filter(
      (file) => !report.results.some((r) => r.ok && r.filename === file.name),
    )
    caption.value = ''
    if (overview.value) overview.value = { ...overview.value, counts: report.counts }
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <section class="knowledge">
    <header class="head">
      <div>
        <h1>Wissensdatenbank</h1>
        <p class="muted">
          Lebenslauf, Zeugnisse, Notenübersicht oder Screenshots ablegen - der Agent
          durchsucht sie anschließend semantisch.
        </p>
      </div>
      <button type="button" class="ghost" @click="refresh">Aktualisieren</button>
    </header>

    <p v-if="error" class="banner error">{{ error }}</p>
    <p v-else-if="overview?.unavailable" class="banner error">
      MCP-Server nicht erreichbar - Hochladen schlägt fehl, bis er läuft.
      ({{ overview.unavailable }})
    </p>

    <div
      class="dropzone"
      :class="{ dragging }"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
      @click="fileInput?.click()"
    >
      <p class="drop-title">Dateien hierher ziehen</p>
      <p class="muted">
        {{ overview?.accepts.documents.join(' ') ?? '.md .txt .json .pdf .csv' }} sowie
        Bilder, bis {{ overview?.accepts.max_mb ?? 10 }} MB je Datei
      </p>
      <input
        ref="fileInput"
        class="file-input"
        type="file"
        multiple
        :accept="accept"
        @change="onPick"
        @click.stop
      />
    </div>

    <div class="options">
      <label>
        Dokumenttyp
        <select v-model="docType" class="control">
          <option value="">automatisch (aus dem Dateinamen)</option>
          <option v-for="type in overview?.doc_types ?? []" :key="type" :value="type">
            {{ type }}
          </option>
        </select>
      </label>
      <label class="grow">
        Kommentar (nur für Bilder)
        <input
          v-model="caption"
          class="control"
          type="text"
          placeholder="z.B. Screenshot der Notenübersicht"
        />
      </label>
    </div>

    <ul v-if="queue.length" class="queue">
      <li v-for="(file, index) in queue" :key="`${file.name}-${index}`">
        <span class="name">{{ file.name }}</span>
        <span class="muted">{{ sizeLabel(file.size) }}</span>
        <button type="button" class="remove" @click="remove(index)">x</button>
      </li>
    </ul>

    <button
      type="button"
      class="primary"
      :disabled="!queue.length || busy"
      @click="upload"
    >
      {{ busy ? 'Lädt hoch ...' : `In die Wissensdatenbank aufnehmen (${queue.length})` }}
    </button>

    <ul v-if="results.length" class="results">
      <li v-for="result in results" :key="result.filename" :class="result.ok ? 'ok' : 'bad'">
        <strong>{{ result.filename }}</strong>
        <span v-if="result.ok">
          als <code>{{ result.doc_type }}</code> gespeichert,
          {{ result.stored }} Abschnitt(e)
        </span>
        <span v-else>{{ result.error }}</span>
      </li>
    </ul>

    <section class="stock">
      <h2>Bestand</h2>
      <p v-if="!counts.length" class="muted">Noch nichts gespeichert.</p>
      <ul v-else class="counts">
        <li v-for="[type, count] in counts" :key="type">
          <span class="type">{{ type }}</span>
          <span class="count">{{ count }}</span>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.knowledge {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem;
  height: 100%;
  overflow-y: auto;
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

h1 {
  font-size: 1.25rem;
  font-weight: 600;
}

h2 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.muted {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.banner {
  padding: 0.6rem 0.8rem;
  border-radius: 0.6rem;
  border: 1px solid var(--danger);
  color: var(--danger);
  font-size: 0.9rem;
}

.dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  padding: 2.25rem 1rem;
  border: 2px dashed var(--border);
  border-radius: 0.9rem;
  background: var(--surface-strong);
  cursor: pointer;
  text-align: center;
}

.dropzone.dragging {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.drop-title {
  font-weight: 600;
}

.file-input {
  display: none;
}

.options {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.options label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.9rem;
}

.options .grow {
  flex: 1;
  min-width: 14rem;
}

.control {
  padding: 0.5rem 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
}

.queue,
.results,
.counts {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.queue li {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--surface);
}

.queue .name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remove {
  border: 1px solid var(--border);
  background: var(--surface-strong);
  color: var(--text);
  border-radius: 0.4rem;
  width: 1.6rem;
  height: 1.6rem;
  cursor: pointer;
  line-height: 1;
}

.primary,
.ghost {
  align-self: flex-start;
  padding: 0.55rem 0.9rem;
  border-radius: 0.6rem;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}

.primary {
  background: var(--accent);
  border-color: transparent;
  color: var(--accent-contrast);
}

.primary:disabled {
  opacity: 0.5;
  cursor: default;
}

.results li {
  font-size: 0.9rem;
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.results .ok {
  color: var(--text-muted);
}

.results .bad {
  color: var(--danger);
}

code {
  font-family: var(--font-mono);
  font-size: 0.85em;
}

.stock {
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--surface-strong);
}

.counts {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.counts li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--surface);
  font-size: 0.85rem;
}

.count {
  font-family: var(--font-mono);
  color: var(--accent);
}
</style>
