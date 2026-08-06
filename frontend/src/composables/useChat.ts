/**
 * Conversation state for one agent.
 */

import { onUnmounted, ref, type Ref } from 'vue'

import { resetThread, streamChat } from '@/api/client'
import type { ChatRole, EmployerLead, StreamEvent, ToolCall } from '@/api/types'

const JOB_RESULT_TOOLS = ['search_jobs', 'get_job_details']
const RESEARCH_TOOL = 'research_company'
const MAX_LEADS = 8

export interface ChatImage {
  url: string
  name: string
}

export interface ChatMessage {
  key: string
  role: ChatRole
  content: string
  toolCalls?: ToolCall[]
  images?: ChatImage[]
}

export interface UseChat {
  messages: Ref<ChatMessage[]>
  employers: Ref<EmployerLead[]>
  busy: Ref<boolean>
  error: Ref<string>
  threadId: Ref<string>
  send: (text: string, files: File[]) => Promise<void>
  stop: () => void
  startNewThread: () => Promise<void>
}

function jobsFromToolResult(content: string): Record<string, unknown>[] {
  let parsed: unknown
  try {
    parsed = JSON.parse(content)
  } catch {
    return []
  }
  if (Array.isArray(parsed)) return parsed as Record<string, unknown>[]
  if (!parsed || typeof parsed !== 'object') return []

  const record = parsed as Record<string, unknown>
  if (Array.isArray(record.jobs)) return record.jobs as Record<string, unknown>[]
  return record.arbeitgeber ? [record] : []
}

function newThreadId(): string {
  return crypto.randomUUID().replace(/-/g, '')
}

let counter = 0
function nextKey(): string {
  return `m${++counter}`
}

export function useChat(agentId: Ref<string>): UseChat {
  const messages = ref<ChatMessage[]>([])
  const employers = ref<EmployerLead[]>([])
  const busy = ref(false)
  const error = ref('')
  const threadId = ref(newThreadId())

  let controller: AbortController | null = null
  const previewUrls: string[] = []

  function push(message: Omit<ChatMessage, 'key'>): void {
    messages.value.push({ key: nextKey(), ...message })
  }

  function trackEmployers(event: Extract<StreamEvent, { type: 'message' }>): void {
    for (const call of event.tool_calls ?? []) {
      if (call.name !== RESEARCH_TOOL) continue
      const researched = String(call.args?.name ?? '').toLowerCase()
      employers.value = employers.value.map((lead) =>
        lead.name.toLowerCase() === researched ? { ...lead, researched: true } : lead,
      )
    }

    if (event.role !== 'tool' || !JOB_RESULT_TOOLS.includes(event.name ?? '')) return

    const known = new Set(employers.value.map((lead) => lead.name.toLowerCase()))
    const found: EmployerLead[] = []
    for (const job of jobsFromToolResult(event.content)) {
      const name = String(job.arbeitgeber ?? '').trim()
      if (!name || known.has(name.toLowerCase())) continue
      known.add(name.toLowerCase())
      found.push({
        name,
        location: String(job.ort ?? '').trim(),
        jobTitle: String(job.titel ?? '').trim(),
        researched: false,
      })
    }
    if (found.length) employers.value = [...found, ...employers.value].slice(0, MAX_LEADS)
  }

  function handle(event: StreamEvent): void {
    if (event.type === 'error') {
      error.value = event.error
      return
    }
    if (event.type !== 'message') return
    trackEmployers(event)
    if (!event.content.trim() && !event.tool_calls?.length) return
    push({
      role: event.role,
      content: event.content,
      toolCalls: event.tool_calls,
    })
  }

  async function send(text: string, files: File[]): Promise<void> {
    if (busy.value || (!text.trim() && files.length === 0)) return

    error.value = ''
    const images = files.map((file) => {
      const url = URL.createObjectURL(file)
      previewUrls.push(url)
      return { url, name: file.name }
    })
    push({ role: 'user', content: text, images })

    busy.value = true
    controller = new AbortController()
    try {
      await streamChat(
        agentId.value,
        { message: text, threadId: threadId.value, images: files },
        handle,
        controller.signal,
      )
    } catch (err) {
      if (!(err instanceof DOMException && err.name === 'AbortError')) {
        error.value = err instanceof Error ? err.message : String(err)
      }
    } finally {
      busy.value = false
      controller = null
    }
  }

  function stop(): void {
    controller?.abort()
  }

  async function startNewThread(): Promise<void> {
    stop()
    try {
      await resetThread(agentId.value, threadId.value)
    } catch {}
    messages.value = []
    employers.value = []
    error.value = ''
    threadId.value = newThreadId()
  }

  onUnmounted(() => {
    stop()
    previewUrls.forEach(URL.revokeObjectURL)
  })

  return { messages, employers, busy, error, threadId, send, stop, startNewThread }
}
