export interface FileNode {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
  children?: FileNode[];
}

export interface DiffSuggestion {
  path: string;
  original: string;
  modified: string;
  unified_diff?: string;
  status?: 'pending' | 'applied' | 'rejected';
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  reasoning?: string;
  isReasoningOpen?: boolean;
  isReasoningStreaming?: boolean;
  diff?: DiffSuggestion;
  timestamp: number;
}

export interface EditorTab {
  path: string;
  name: string;
  content: string;
  language: string;
  isDirty?: boolean;
}
