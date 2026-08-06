<script setup lang="ts">
import { onUnmounted, ref } from 'vue'

const ACCEPTED = 'image/png,image/jpeg,image/webp,image/gif'

defineProps<{ busy: boolean }>()
const emit = defineEmits<{
  send: [text: string, files: File[]]
  stop: []
}>()

interface Pending {
  file: File
  url: string
}

const text = ref('')
const pending = ref<Pending[]>([])
const fileInput = ref<HTMLInputElement | null>(null)

function addFiles(files: FileList | File[] | null): void {
  for (const file of Array.from(files ?? [])) {
    if (file.type.startsWith('image/')) {
      pending.value.push({ file, url: URL.createObjectURL(file) })
    }
  }
}

function onPick(event: Event): void {
  const input = event.target as HTMLInputElement
  addFiles(input.files)
  input.value = ''
}

function onPaste(event: ClipboardEvent): void {
  const files = Array.from(event.clipboardData?.files ?? [])
  if (files.length) {
    event.preventDefault()
    addFiles(files)
  }
}

function remove(index: number): void {
  const [removed] = pending.value.splice(index, 1)
  if (removed) URL.revokeObjectURL(removed.url)
}

function submit(): void {
  const message = text.value.trim()
  if (!message && pending.value.length === 0) return

  emit(
    'send',
    message,
    pending.value.map((item) => item.file),
  )
  text.value = ''
  pending.value.forEach((item) => URL.revokeObjectURL(item.url))
  pending.value = []
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}

onUnmounted(() => pending.value.forEach((item) => URL.revokeObjectURL(item.url)))
</script>

<template>
  <form class="composer" @submit.prevent="submit">
    <ul v-if="pending.length" class="previews">
      <li v-for="(item, index) in pending" :key="item.url">
        <img :src="item.url" :alt="item.file.name" />
        <button type="button" class="remove" :title="`${item.file.name} entfernen`" @click="remove(index)">
          x
        </button>
      </li>
    </ul>

    <div class="row">
      <button type="button" class="attach" title="Bild anhängen" @click="fileInput?.click()">
        Bild
      </button>
      <input
        ref="fileInput"
        class="file-input"
        type="file"
        :accept="ACCEPTED"
        multiple
        @change="onPick"
      />

      <textarea
        v-model="text"
        class="input"
        rows="1"
        placeholder="Nachricht schreiben, Bild anhängen oder einfügen ..."
        @keydown="onKeydown"
        @paste="onPaste"
      ></textarea>

      <button v-if="busy" type="button" class="send stop" @click="emit('stop')">Stopp</button>
      <button v-else type="submit" class="send">Senden</button>
    </div>
  </form>
</template>

<style scoped>
.composer {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.9rem 1.25rem 1.1rem;
  border-top: 1px solid var(--border);
  background: var(--surface-strong);
}

.previews {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  list-style: none;
}

.previews li {
  position: relative;
}

.previews img {
  height: 4.5rem;
  width: 4.5rem;
  object-fit: cover;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
}

.remove {
  position: absolute;
  top: -0.4rem;
  right: -0.4rem;
  height: 1.3rem;
  width: 1.3rem;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  line-height: 1;
}

.row {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
}

.file-input {
  display: none;
}

.input {
  flex: 1;
  resize: none;
  max-height: 9rem;
  padding: 0.6rem 0.7rem;
  border-radius: 0.6rem;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  line-height: 1.45;
  field-sizing: content;
}

.input:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -1px;
}

.attach,
.send {
  padding: 0.6rem 0.9rem;
  border-radius: 0.6rem;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  cursor: pointer;
  white-space: nowrap;
}

.send {
  background: var(--accent);
  border-color: transparent;
  color: var(--accent-contrast);
}

.send.stop {
  background: var(--surface);
  color: var(--text);
  border-color: var(--border);
}

.attach:hover,
.send:hover {
  filter: brightness(1.1);
}
</style>
