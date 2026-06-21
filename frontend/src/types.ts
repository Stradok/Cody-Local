export interface OllamaModel {
  name: string
  size: number
}

export interface Message {
  role: "user" | "assistant" | "tool"
  content: string
  toolCalls?: ToolCall[]
  toolResult?: string
}

export interface ToolCall {
  name: string
  arguments: string
  result?: string
}

export interface FileEntry {
  name: string
  type: "file" | "directory"
  path: string
}

export interface OpenFile {
  path: string
  name: string
  content: string
}

export interface GitHubRepo {
  name: string
  full_name: string
  description: string
  private: boolean
  stars: number
  forks: number
  url: string
  clone_url: string
  language: string
  updated_at: string
}

export interface GitHubIssue {
  number: number
  title: string
  state: string
  user: string
  comments: number
  url: string
  body: string
  created_at: string
}

export interface GitHubPR {
  number: number
  title: string
  state: string
  user: string
  url: string
  body: string
  created_at: string
  head: string
  base: string
}
