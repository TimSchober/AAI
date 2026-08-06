<script setup lang="ts">
import type { EmployerLead } from '@/api/types'

defineProps<{ employers: EmployerLead[]; busy: boolean }>()
const emit = defineEmits<{ research: [employer: EmployerLead] }>()
</script>

<template>
  <aside class="prompt">
    <p class="lead">
      Stellen gefunden. Möchtest du wissen, wer dahintersteckt? Wähle ein Unternehmen aus,
      dann recherchiert der Unternehmens-Recherche-Agent es für dich.
    </p>

    <ul class="companies">
      <li v-for="employer in employers" :key="employer.name">
        <button
          type="button"
          class="company"
          :class="{ done: employer.researched }"
          :disabled="busy"
          :title="employer.jobTitle ? `Stelle: ${employer.jobTitle}` : employer.name"
          @click="emit('research', employer)"
        >
          <span class="name">{{ employer.name }}</span>
          <span v-if="employer.location" class="where">{{ employer.location }}</span>
          <span v-if="employer.researched" class="badge">recherchiert</span>
        </button>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.prompt {
  align-self: stretch;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.8rem 0.9rem;
  border: 1px dashed var(--border);
  border-radius: 0.75rem;
  background: var(--surface-strong);
}

.lead {
  font-size: 0.9rem;
  color: var(--text-muted);
  line-height: 1.45;
}

.companies {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  list-style: none;
}

.company {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  padding: 0.45rem 0.7rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 0.88rem;
  cursor: pointer;
  text-align: left;
}

.company:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.company:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.company.done {
  background: var(--accent-soft);
  border-color: transparent;
}

.where {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.badge {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--accent);
}
</style>
