<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <section class="placeholder">
    <h1>{{ route.meta.label }}</h1>
    <p v-if="route.meta.hint">{{ route.meta.hint }}</p>
    <p class="muted">Dieser Bereich ist noch nicht umgesetzt.</p>
  </section>
</template>

<style scoped>
.placeholder {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 2rem;
}

h1 {
  font-size: 1.25rem;
  font-weight: 600;
}

.muted {
  color: var(--text-muted);
  font-size: 0.9rem;
}
</style>
