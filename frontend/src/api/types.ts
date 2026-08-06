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
