<script setup lang="ts">
/**
 * Upload one document and have the review agent comment on it.
 *
 * Deliberately one file at a time: the advice is about *this* CV, and a queue
 * would only blur whose feedback belongs to which file. Bulk filing is what the
 * Wissensdatenbank tab is for.
 */
import { computed, onMounted, ref } from 'vue'

import { loadKnowledge } from '@/api/client'
import type { KnowledgeOverview } from '@/api/types'
import MessageBubble from '@/components/MessageBubble.vue'
import { useReview } from '@/composables/useReview'

const REVIEWABLE = ['lebenslauf', 'motivation', 'zeugnis', 'arbeitszeugnis']

const { phase, messages, stored, error, run, stop, reset } = useReview()

const file = ref<File | null>(null)
const docType = ref('')
const target = ref('')
const dragging = ref(false)
const accepts = ref<KnowledgeOverview['accepts'] | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const busy = computed(() => phase.value === 'uploading' || phase.value === 'reviewing')
const advice = computed(() => messages.value.filter((m) => m.role === 'assistant'))
const steps = computed(() => messages.value.filter((m) => m.role !== 'assistant'))

const status = computed(() => {
  if (phase.value === 'uploading') return 'Dokument wird gespeichert ...'
  if (phase.value === 'reviewing') return 'Der Unterlagen-Coach liest und prüft ...'
  return ''
})

function pick(files: FileList | File[] | null): void {
  const [first] = Array.from(files ?? [])
  if (first) file.value = first
}

function onDrop(event: DragEvent): void {
  dragging.value = false
  pick(event.dataTransfer?.files ?? null)
}

function onPick(event: Event): void {
  const input = event.target as HTMLInputElement
  pick(input.files)
  input.value = ''
}

function start(): void {
  if (file.value) run(file.value, { docType: docType.value, target: target.value })
}

function clear(): void {
  reset()
  file.value = null
}

function sizeLabel(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

onMounted(async () => {
  try {
    accepts.value = (await loadKnowledge()).accepts
  } catch {
    // Only used for the hint text; the upload itself reports real problems.
  }
})
</script>

<template>
  <section class="review">
    <header class="head">
      <div>
        <h1>Unterlagen-Check</h1>
        <p class="muted">
          Lebenslauf, Anschreiben oder Zeugnis hochladen - der Unterlagen-Coach liest
          es und sagt konkret, was besser werden kann.
        </p>
      </div>
      <button v-if="messages.length || file" type="button" class="ghost" @click="clear">
        Neu anfangen
      </button>
    </header>

    <div
      class="dropzone"
      :class="{ dragging, filled: !!file }"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
      @click="fileInput?.click()"
    >
      <template v-if="file">
        <p class="drop-title">{{ file.name }}</p>
        <p class="muted">{{ sizeLabel(file.size) }} — zum Austauschen klicken</p>
      </template>
      <template v-else>
        <p class="drop-title">Dokument hierher ziehen</p>
        <p class="muted">
          {{ accepts?.documents.join(' ') ?? '.md .txt .json .pdf .csv' }} oder ein Bild,
          bis {{ accepts?.max_mb ?? 10 }} MB
        </p>
      </template>
      <input
        ref="fileInput"
        class="file-input"
        type="file"
        :accept="accepts ? [...accepts.documents, ...accepts.images].join(',') : undefined"
        @change="onPick"
        @click.stop
      />
    </div>

    <div class="options">
      <label>
        Art des Dokuments
        <select v-model="docType" class="control">
          <option value="">automatisch (aus dem Dateinamen)</option>
          <option v-for="type in REVIEWABLE" :key="type" :value="type">{{ type }}</option>
        </select>
      </label>
      <label class="grow">
        Zielstelle (optional)
        <input
          v-model="target"
          class="control"
          type="text"
          placeholder="z.B. Data Engineer bei einem Mittelständler in Köln"
        />
      </label>
    </div>

    <div class="actions">
      <button type="button" class="primary" :disabled="!file || busy" @click="start">
        Unterlagen prüfen lassen
      </button>
      <button v-if="busy" type="button" class="ghost" @click="stop">Abbrechen</button>
      <span v-if="status" class="muted">{{ status }}</span>
    </div>

    <p v-if="stored" class="banner ok">
      Gespeichert als <code>{{ stored.doc_type }}</code> ({{ stored.stored }} Abschnitte)
      - liegt jetzt auch in der Wissensdatenbank.
    </p>
    <p v-if="error" class="banner error">{{ error }}</p>

    <section v-if="advice.length" class="advice">
      <h2>Rückmeldung</h2>
      <MessageBubble v-for="message in advice" :key="message.key" :message="message" />
    </section>

    <details v-if="steps.length" class="steps">
      <summary>Was der Agent dafür getan hat ({{ steps.length }})</summary>
      <MessageBubble v-for="message in steps" :key="message.key" :message="message" />
    </details>

    <p v-if="phase === 'done' && !advice.length && !error" class="muted">
      Der Agent hat nichts zurückgegeben. Läuft das Modell? Siehe /ready.
    </p>
  </section>
</template>

<style scoped>
.review {
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

.dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  padding: 2rem 1rem;
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

.dropzone.filled {
  border-style: solid;
}

.drop-title {
  font-weight: 600;
  overflow-wrap: anywhere;
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
  min-width: 16rem;
}

.control {
  padding: 0.5rem 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
}

.actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.primary,
.ghost {
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

.banner {
  padding: 0.6rem 0.8rem;
  border-radius: 0.6rem;
  border: 1px solid var(--border);
  font-size: 0.9rem;
}

.banner.ok {
  border-color: var(--accent);
  color: var(--accent);
}

.banner.error {
  border-color: var(--danger);
  color: var(--danger);
}

code {
  font-family: var(--font-mono);
  font-size: 0.85em;
}

.advice {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.steps {
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.6rem 0.8rem;
  background: var(--surface-strong);
}

.steps summary {
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.steps > * + * {
  margin-top: 0.5rem;
}
</style>
