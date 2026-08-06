<script setup lang="ts">
import type { ChatMessage } from '@/composables/useChat'

const props = defineProps<{ message: ChatMessage }>()

const isUser = props.message.role === 'user'
const isTool = props.message.role === 'tool'

const label: Record<string, string> = {
  user: 'Du',
  assistant: 'Agent',
  tool: 'Tool-Ergebnis',
  system: 'System',
}
</script>

<template>
  <article class="bubble" :class="[message.role, { own: isUser }]">
    <header class="meta">{{ label[message.role] ?? message.role }}</header>

    <div v-if="message.images?.length" class="images">
      <img
        v-for="image in message.images"
        :key="image.url"
        :src="image.url"
        :alt="image.name"
        :title="image.name"
      />
    </div>

    <p v-if="message.content" class="text" :class="{ compact: isTool }">
      {{ message.content }}
    </p>

    <ul v-if="message.toolCalls?.length" class="tools">
      <li v-for="(call, index) in message.toolCalls" :key="call.id ?? index">
        <span class="tool-name">{{ call.name }}</span>
        <span class="tool-args">{{ JSON.stringify(call.args) }}</span>
      </li>
    </ul>
  </article>
</template>

<style scoped>
.bubble {
  max-width: min(48rem, 100%);
  padding: 0.75rem 0.9rem;
  border-radius: 0.75rem;
  background: var(--surface-strong);
  border: 1px solid var(--border);
}

.bubble.own {
  align-self: flex-end;
  background: var(--accent-soft);
  border-color: transparent;
}

.bubble.tool {
  background: transparent;
  border-style: dashed;
}

.meta {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
}

.text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.5;
}

.text.compact {
  font-family: var(--font-mono);
  font-size: 0.82rem;
  max-height: 12rem;
  overflow: auto;
  color: var(--text-muted);
}

.images {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.images img {
  max-height: 11rem;
  max-width: 100%;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
}

.tools {
  list-style: none;
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-family: var(--font-mono);
  font-size: 0.78rem;
}

.tools li {
  display: flex;
  gap: 0.5rem;
  padding: 0.3rem 0.5rem;
  border-radius: 0.4rem;
  background: var(--surface);
  color: var(--text-muted);
}

.tool-name {
  color: var(--accent);
  white-space: nowrap;
}

.tool-args {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
