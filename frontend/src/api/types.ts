/** Shapes returned by the Flask backend. */

export interface AgentInfo {
  id: string
  name: string
  description: string
}

export interface ToolCall {
  id?: string
  name: string
  args: Record<string, unknown>
}

export type ChatRole = 'user' | 'assistant' | 'tool' | 'system'

export interface AttachmentInfo {
  filename: string
  mime_type: string
  size: number
}

export type StreamEvent =
  | { type: 'start'; agent: string; thread_id: string; attachments: AttachmentInfo[] }
  | {
      type: 'message'
      node: string
      role: ChatRole
      content: string
      id?: string
      name?: string
      tool_calls?: ToolCall[]
    }
  | { type: 'error'; error: string }
  | { type: 'end'; thread_id: string }

export interface EmployerLead {
  name: string
  location: string
  jobTitle: string
  researched: boolean
}

export interface ChatRequest {
  message: string
  threadId: string
  images?: File[]
}

/** One adjustable configuration variable, as described by /api/settings. */
export interface SettingField {
  key: string
  label: string
  kind: 'text' | 'url' | 'int' | 'float' | 'secret' | 'choice' | 'csv'
  help: string
  service: string
  service_label: string
  /** True when the backend applies it without being restarted. */
  live: boolean
  /** True when the value currently comes from the settings file. */
  overridden: boolean
  value: string
  is_set: boolean
  choices?: string[]
}

export interface SettingGroup {
  name: string
  settings: SettingField[]
}

export interface SettingsResponse {
  file: string
  /** False when the backend cannot write the settings file (permissions). */
  writable: boolean
  groups: SettingGroup[]
}

export interface RestartNotice {
  service: string
  label: string
  settings: string[]
}

export interface SettingsSaved {
  saved: string[]
  applied: string[]
  restart_required: RestartNotice[]
  /** Endpoints that were saved but could not be reached from the backend. */
  warnings: string[]
  file: string
}

export interface KnowledgeOverview {
  counts: Record<string, number>
  total: number
  doc_types: string[]
  /** Set when the MCP server could not be reached; the counts are empty then. */
  unavailable: string
  accepts: {
    documents: string[]
    images: string[]
    max_mb: number
  }
}

export interface UploadResult {
  ok: boolean
  filename: string
  kind?: 'image' | 'document'
  doc_type?: string
  stored?: number
  source?: string
  error?: string
}

export interface UploadResponse {
  results: UploadResult[]
  stored: number
  counts: Record<string, number>
}
