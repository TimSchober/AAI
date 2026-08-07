/**
 * One document review: upload the file, then let the review agent read it back
 * out of the knowledge base and comment on it.
 *
 * The file deliberately does not travel in the prompt. The upload stores it, and
 * the agent pulls it with the MCP tool `get_document` - which keeps a long CV out
 * of the conversation history and lets the agent reach for the user's other
 * documents when it needs context.
 */

import { onUnmounted, ref, type Ref } from 'vue'

import { streamChat, uploadDocuments } from '@/api/client'
import type { StreamEvent, UploadResult } from '@/api/types'
import type { ChatMessage } from '@/composables/useChat'

export const REVIEW_AGENT = 'document_review'

export type ReviewPhase = 'idle' | 'uploading' | 'reviewing' | 'done' | 'error'

export interface UseReview {
  phase: Ref<ReviewPhase>
  messages: Ref<ChatMessage[]>
  stored: Ref<UploadResult | null>
  error: Ref<string>
  threadId: Ref<string>
  run: (file: File, options?: { docType?: string; target?: string }) => Promise<void>
  stop: () => void
  reset: () => void
}

function newThreadId(): string {
  return crypto.randomUUID().replace(/-/g, '')
}

let counter = 0

/** The turn that starts the review. `source` is what the upload filed it under. */
export function reviewPrompt(source: string, filename: string, target = ''): string {
  const lines = [
    `Bitte prüfe das Dokument "${source}" (hochgeladen als "${filename}") und sag mir konkret, was ich daran verbessern kann.`,
  ]
  if (target.trim()) {
    lines.push(`Ich möchte mich damit hierauf bewerben: ${target.trim()}`)
  }
  return lines.join('\n')
}

export function useReview(): UseReview {
  const phase = ref<ReviewPhase>('idle')
  const messages = ref<ChatMessage[]>([])
  const stored = ref<UploadResult | null>(null)
  const error = ref('')
  const threadId = ref(newThreadId())

  let controller: AbortController | null = null

  function handle(event: StreamEvent): void {
    if (event.type === 'error') {
      error.value = event.error
      return
    }
    if (event.type !== 'message') return
    if (!event.content.trim() && !event.tool_calls?.length) return

    messages.value.push({
      key: `r${++counter}`,
      role: event.role,
      content: event.content,
      toolCalls: event.tool_calls,
    })
  }

  async function run(
    file: File,
    { docType = '', target = '' }: { docType?: string; target?: string } = {},
  ): Promise<void> {
    if (phase.value === 'uploading' || phase.value === 'reviewing') return

    reset()
    phase.value = 'uploading'
    try {
      const report = await uploadDocuments([file], { docType })
      const result = report.results[0]
      if (!result?.ok) {
        error.value = result?.error ?? 'Die Datei konnte nicht gespeichert werden.'
        phase.value = 'error'
        return
      }
      stored.value = result

      phase.value = 'reviewing'
      controller = new AbortController()
      await streamChat(
        REVIEW_AGENT,
        {
          message: reviewPrompt(result.source ?? file.name, file.name, target),
          threadId: threadId.value,
        },
        handle,
        controller.signal,
      )
      phase.value = error.value ? 'error' : 'done'
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        phase.value = 'idle'
        return
      }
      error.value = err instanceof Error ? err.message : String(err)
      phase.value = 'error'
    } finally {
      controller = null
    }
  }

  function stop(): void {
    controller?.abort()
  }

  function reset(): void {
    stop()
    messages.value = []
    stored.value = null
    error.value = ''
    phase.value = 'idle'
    threadId.value = newThreadId()
  }

  onUnmounted(stop)

  return { phase, messages, stored, error, threadId, run, stop, reset }
}
