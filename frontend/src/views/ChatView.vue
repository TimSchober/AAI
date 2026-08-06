<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import { listAgents } from '@/api/client'
import type { AgentInfo, EmployerLead } from '@/api/types'
import ChatComposer from '@/components/ChatComposer.vue'
import EmployerPrompt from '@/components/EmployerPrompt.vue'
import MessageBubble from '@/components/MessageBubble.vue'
import { useChat } from '@/composables/useChat'

const RESEARCH_AGENT = 'company_research'

const agents = ref<AgentInfo[]>([])
const agentId = ref('')
const loadError = ref('')

const { messages, employers, busy, error, send, stop, startNewThread } = useChat(agentId)

const canResearch = computed(
  () => employers.value.length > 0 && agents.value.some((a) => a.id === RESEARCH_AGENT),
)

async function research(employer: EmployerLead): Promise<void> {
  agentId.value = RESEARCH_AGENT
  const where = employer.location ? ` in ${employer.location}` : ''
  await send(`Recherchiere bitte das Unternehmen "${employer.name}"${where}.`, [])
}

const scroller = ref<HTMLElement | null>(null)

onMounted(async () => {
  try {
    const { agents: available } = await listAgents()
    agents.value = available
    agentId.value = available[0]?.id ?? ''
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : String(err)
  }
})

watch(
  () => messages.value.length,
  async () => {
    await nextTick()
    scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: 'smooth' })
  },
)
</script>

<template>
  <section class="chat">
    <header class="bar">
      <select v-model="agentId" class="agents" :disabled="agents.length < 2">
        <option v-for="agent in agents" :key="agent.id" :value="agent.id">
          {{ agent.name }}
        </option>
      </select>
      <button type="button" class="new" @click="startNewThread">Neuer Chat</button>
    </header>

    <div ref="scroller" class="stream">
      <p v-if="loadError" class="notice error">Backend nicht erreichbar: {{ loadError }}</p>
      <p v-else-if="!messages.length" class="notice">
        Frag nach Stellenangeboten oder häng ein Bild deiner Unterlagen an.
      </p>

      <MessageBubble v-for="message in messages" :key="message.key" :message="message" />

      <EmployerPrompt
        v-if="canResearch"
        :employers="employers"
        :busy="busy"
        @research="research"
      />

      <p v-if="busy" class="notice">Der Agent arbeitet ...</p>
      <p v-if="error" class="notice error">{{ error }}</p>
    </div>

    <ChatComposer :busy="busy" @send="send" @stop="stop" />
  </section>
</template>

<style scoped>
.chat {
  display: grid;
  grid-template-rows: auto 1fr auto;
  height: 100%;
}

.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--border);
}

.agents,
.new {
  padding: 0.4rem 0.7rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}

.stream {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1.25rem;
  overflow-y: auto;
}

.notice {
  align-self: center;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.notice.error {
  color: var(--danger);
}
</style>
