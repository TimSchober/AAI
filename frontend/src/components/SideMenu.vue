<script setup lang="ts">
import { routes } from '@/router'

const entries = routes.filter((route) => route.meta?.label)
</script>

<template>
  <nav class="menu">
    <div class="brand">
      <span class="brand-title">Job Application Agent</span>
      <span class="brand-subtitle">Bewerbungsassistent</span>
    </div>

    <ul class="items">
      <li v-for="entry in entries" :key="entry.path">
        <RouterLink class="item" :to="entry.path">
          {{ entry.meta?.label }}
        </RouterLink>
      </li>
    </ul>
  </nav>
</template>

<style scoped>
.menu {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1.25rem 1rem;
  background: var(--surface-strong);
  border-right: 1px solid var(--border);
}

.brand {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.brand-title {
  font-weight: 600;
}

.brand-subtitle {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.items {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  list-style: none;
}

.item {
  display: block;
  padding: 0.55rem 0.75rem;
  border-radius: 0.5rem;
  color: var(--text-muted);
  text-decoration: none;
  font-size: 0.95rem;
}

.item:hover {
  background: var(--surface);
  color: var(--text);
}

.item.router-link-active {
  background: var(--accent-soft);
  color: var(--accent);
}

@media (max-width: 40rem) {
  .menu {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    border-right: none;
    border-bottom: 1px solid var(--border);
  }

  .brand-subtitle {
    display: none;
  }

  .items {
    flex-direction: row;
  }
}
</style>
