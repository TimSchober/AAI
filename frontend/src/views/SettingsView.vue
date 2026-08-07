<script setup lang="ts">
/**
 * Edits the variables that otherwise live in .env.
 *
 * Only changed fields are submitted, so a masked secret stays untouched unless
 * the user types a new one. The backend applies what it reads itself and tells
 * us which other services still need a restart.
 */
import { computed, onMounted, reactive, ref } from 'vue'

import { loadSettings, saveSettings } from '@/api/client'
import type { RestartNotice, SettingField, SettingGroup } from '@/api/types'

const groups = ref<SettingGroup[]>([])
const file = ref('')
const writable = ref(true)
const draft = reactive<Record<string, string>>({})
const original = reactive<Record<string, string>>({})

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const savedKeys = ref<string[]>([])
const restart = ref<RestartNotice[]>([])
const warnings = ref<string[]>([])

const changed = computed(() =>
  Object.keys(draft).filter((key) => draft[key] !== original[key]),
)

function inputType(field: SettingField): string {
  if (field.kind === 'secret') return 'password'
  if (field.kind === 'int' || field.kind === 'float') return 'number'
  if (field.kind === 'url') return 'url'
  return 'text'
}

function placeholder(field: SettingField): string {
  if (field.kind === 'secret') return field.is_set ? 'gesetzt - zum Ändern eingeben' : 'nicht gesetzt'
  return 'nicht gesetzt'
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const data = await loadSettings()
    groups.value = data.groups
    file.value = data.file
    writable.value = data.writable
    for (const group of data.groups) {
      for (const field of group.settings) {
        draft[field.key] = field.value
        original[field.key] = field.value
      }
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

async function submit(): Promise<void> {
  if (!changed.value.length || saving.value) return

  saving.value = true
  error.value = ''
  savedKeys.value = []
  restart.value = []
  warnings.value = []
  try {
    const values = Object.fromEntries(changed.value.map((key) => [key, draft[key]]))
    const report = await saveSettings(values)
    savedKeys.value = report.saved
    restart.value = report.restart_required
    warnings.value = report.warnings
    // Re-read: secrets come back masked and derived values may have moved.
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

function revert(): void {
  for (const key of Object.keys(draft)) draft[key] = original[key]
  savedKeys.value = []
  restart.value = []
  warnings.value = []
}

onMounted(load)
</script>

<template>
  <section class="settings">
    <header class="head">
      <div>
        <h1>Einstellungen</h1>
        <p class="muted">
          Diese Werte überschreiben die <code>.env</code>. Gespeichert wird in
          <code>{{ file || '…' }}</code>.
        </p>
      </div>
      <div class="actions">
        <button type="button" class="ghost" :disabled="!changed.length || saving" @click="revert">
          Verwerfen
        </button>
        <button type="button" class="primary" :disabled="!changed.length || saving" @click="submit">
          {{ saving ? 'Speichert ...' : `Speichern (${changed.length})` }}
        </button>
      </div>
    </header>

    <p v-if="!writable && !loading" class="banner error">
      Die Einstellungsdatei ist nicht beschreibbar - Speichern schlägt fehl.
      In Docker muss <code>{{ file }}</code> dem Benutzer <code>app</code> (uid 1000)
      gehören.
    </p>
    <p v-if="error" class="banner error">{{ error }}</p>
    <p v-if="savedKeys.length && !error" class="banner ok">
      Gespeichert: {{ savedKeys.join(', ') }}.
    </p>
    <p v-for="notice in restart" :key="notice.service" class="banner warn">
      {{ notice.label }} muss neu gestartet werden, damit
      {{ notice.settings.join(', ') }} wirkt.
    </p>
    <p v-for="warning in warnings" :key="warning" class="banner error">
      Gespeichert, aber: {{ warning }}
    </p>

    <p v-if="loading" class="muted">Lädt ...</p>

    <form v-else class="groups" @submit.prevent="submit">
      <fieldset v-for="group in groups" :key="group.name" class="group">
        <legend>{{ group.name }}</legend>

        <div v-for="field in group.settings" :key="field.key" class="field">
          <label :for="field.key">
            {{ field.label }}
            <span class="key">{{ field.key }}</span>
          </label>

          <select
            v-if="field.choices"
            :id="field.key"
            v-model="draft[field.key]"
            class="control"
          >
            <option v-for="choice in field.choices" :key="choice" :value="choice">
              {{ choice }}
            </option>
          </select>
          <input
            v-else
            :id="field.key"
            v-model="draft[field.key]"
            class="control"
            :type="inputType(field)"
            :placeholder="placeholder(field)"
            autocomplete="off"
            spellcheck="false"
          />

          <p class="hint">
            <span class="badge" :class="field.live ? 'live' : 'restart'">
              {{ field.live ? 'wirkt sofort' : `Neustart: ${field.service_label}` }}
            </span>
            <span v-if="field.overridden" class="badge override">überschrieben</span>
            {{ field.help }}
          </p>
        </div>
      </fieldset>
    </form>
  </section>
</template>

<style scoped>
.settings {
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

.muted {
  color: var(--text-muted);
  font-size: 0.9rem;
}

code {
  font-family: var(--font-mono);
  font-size: 0.85em;
}

.actions {
  display: flex;
  gap: 0.5rem;
}

.primary,
.ghost {
  padding: 0.5rem 0.9rem;
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

.primary:disabled,
.ghost:disabled {
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

.banner.warn {
  background: var(--surface);
}

.groups {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.group {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: 1rem;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--surface-strong);
}

legend {
  grid-column: 1 / -1;
  padding: 0 0.4rem;
  font-weight: 600;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

label {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  font-size: 0.9rem;
  flex-wrap: wrap;
}

.key {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
}

.control {
  padding: 0.5rem 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  min-width: 0;
}

.control:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -1px;
}

.hint {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.badge {
  padding: 0.1rem 0.4rem;
  border-radius: 0.3rem;
  border: 1px solid var(--border);
  font-size: 0.7rem;
  white-space: nowrap;
}

.badge.live {
  color: var(--accent);
  border-color: var(--accent);
}

.badge.override {
  color: var(--text);
}
</style>
