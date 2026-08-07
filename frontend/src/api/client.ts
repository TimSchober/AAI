/**
 * Thin client for the Flask backend.
 */

import type {
  AgentInfo,
  ChatRequest,
  KnowledgeOverview,
  SettingsResponse,
  SettingsSaved,
  StreamEvent,
  UploadResponse,
} from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init)
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status)
  }
  return (await response.json()) as T
}

export function listAgents(): Promise<{ count: number; agents: AgentInfo[] }> {
  return request('/api/agents')
}

export function resetThread(agentId: string, threadId: string): Promise<unknown> {
  return request(`/api/agents/${agentId}/threads/${threadId}`, { method: 'DELETE' })
}

export function loadSettings(): Promise<SettingsResponse> {
  return request('/api/settings')
}

/** Sends only the fields the user actually changed. */
export function saveSettings(values: Record<string, string>): Promise<SettingsSaved> {
  return request('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values }),
  })
}

export function loadKnowledge(): Promise<KnowledgeOverview> {
  return request('/api/knowledge')
}

export async function uploadDocuments(
  files: File[],
  options: { docType?: string; caption?: string } = {},
): Promise<UploadResponse> {
  const body = new FormData()
  files.forEach((file) => body.append('files', file, file.name))
  if (options.docType) body.append('doc_type', options.docType)
  if (options.caption) body.append('caption', options.caption)

  const response = await fetch(`${BASE}/api/knowledge/documents`, { method: 'POST', body })
  // 415 still carries a per-file report, so only fail on other errors.
  if (!response.ok && response.status !== 415) {
    throw new ApiError(await errorMessage(response), response.status)
  }
  return (await response.json()) as UploadResponse
}

export async function streamChat(
  agentId: string,
  { message, threadId, images = [] }: ChatRequest,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const body = new FormData()
  body.append('message', message)
  body.append('thread_id', threadId)
  images.forEach((image) => body.append('images', image, image.name))

  const response = await fetch(`${BASE}/api/agents/${agentId}/chat/stream`, {
    method: 'POST',
    body,
    signal,
  })
  if (!response.ok || !response.body) {
    throw new ApiError(await errorMessage(response), response.status)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const event = parseFrame(frame)
      if (event) onEvent(event)
    }
  }
}

function parseFrame(frame: string): StreamEvent | null {
  const payload = frame
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trim())
    .join('')
  if (!payload) return null
  try {
    return JSON.parse(payload) as StreamEvent
  } catch {
    return null
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    return body?.error ?? body?.detail ?? response.statusText
  } catch {
    return response.statusText || `HTTP ${response.status}`
  }
}
