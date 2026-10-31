export type Kind = "link" | "note" | "text" | "code" | "image";
export type NoteColor = "yellow" | "blue" | "green" | "pink" | "plain";

export interface Usage {
  used_tokens: number;
  limit_tokens: number;
  resets_at: string;
}

export interface User {
  id: string;
  email: string | null;
  email_verified: boolean;
  display_name: string | null;
  avatar_url: string | null;
  timezone: string;
  digest_daily: boolean;
  digest_weekly: boolean;
  digest_hour: number;
  memory_enabled: boolean;
  has_password: boolean;
  is_admin?: boolean;
  created_at: string;
}

export interface Profile {
  sign_in: { password: boolean; providers: string[] };
  member_since: string;
  counts: {
    canvases: number;
    cards: number;
    by_kind: Partial<Record<Kind, number>>;
    upcoming_reminders: number;
    questions_asked: number;
  };
}

export interface PreviewShape {
  kind: Kind;
  x: number;
  y: number;
  w: number | null;
  h: number | null;
  color: NoteColor | null;
}

export interface Canvas {
  id: string;
  title: string;
  share_token?: string | null;
  viewport: { x: number; y: number; zoom: number };
  item_count: number;
  preview: PreviewShape[];
  created_at: string;
  updated_at: string;
}

export interface LinkContent {
  url: string;
  comment: string;
  url_norm?: string;
  title?: string;
  description?: string;
  image?: string;
  site_name?: string;
  favicon?: string;
  fetch_state?: "pending" | "ready" | "failed" | "blocked";
  blocked_domain?: boolean;
}
export interface NoteContent { markdown: string; color: NoteColor }
export interface TextContent { text: string; size: "s" | "m" | "l" | "xl" }
export interface CodeContent { language: string; source: string; filename: string }
export interface ImageContent {
  caption: string;
  filename: string;
  mime: string;
  upload_state: "awaiting_upload" | "processing" | "ready" | "rejected" | "blocked";
  reject_reason?: string;
  width?: number;
  height?: number;
}

interface ItemBase {
  id: string;
  canvas_id: string;
  x: number;
  y: number;
  w: number | null;
  h: number | null;
  z: number;
  version: number;
  index_state: "pending" | "ready" | "failed";
  safety_state: "unchecked" | "ok" | "flagged";
  safety_categories: string[];
  ai: { summary: string; tags: string[] };
  created_at: string;
  updated_at: string;
}
export type Item =
  | (ItemBase & { kind: "link"; content: LinkContent })
  | (ItemBase & { kind: "note"; content: NoteContent })
  | (ItemBase & { kind: "text"; content: TextContent })
  | (ItemBase & { kind: "code"; content: CodeContent })
  | (ItemBase & { kind: "image"; content: ImageContent });

export interface Hit {
  item_id: string;
  canvas_id: string;
  canvas_title: string;
  kind: Kind;
  kind_label: string;
  title: string;
  snippet: string;
}

export interface Reminder {
  id: string;
  item_id: string | null;
  canvas_id: string | null;
  note: string;
  remind_at: string;
  state: "pending" | "sent" | "cancelled" | "failed";
  sent_at: string | null;
  created_at: string;
}

export interface ChatStep {
  id: string;
  label: string;
  state: "active" | "done";
  detail?: string | null;
}

export interface ChatCheck {
  supported: boolean;
  note: string | null;
}

export interface ChatTurn {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  cited: string[];
  sources?: (Hit & { n: number })[];
  steps?: ChatStep[];
  check?: ChatCheck;
  status?: "streaming" | "blocked" | "error" | "done";
  created_at?: string;
  /** Server id of a saved answer, for actions like "save as note". */
  message_id?: number | null;
}

export interface MemoryFact {
  id: string;
  fact: string;
  kind: string;
  created_at: string;
}

export interface Page<T> {
  data: T[];
  page: { limit: number; next_cursor: string | null };
}

export interface Template {
  key: string;
  title: string;
  description: string;
  cards: number;
}

export interface DeletedCanvas extends Canvas {
  deleted_at: string;
}

export interface ItemVersion {
  id: number;
  version: number;
  content: Record<string, unknown>;
  created_at: string;
}

export interface Inbound {
  enabled: boolean;
  address: string | null;
}

export interface SharedCanvas {
  title: string;
  updated_at: string;
  items: { id: string; kind: Kind; x: number; y: number; w: number | null; h: number | null; z: number;
    content: Record<string, unknown> }[];
}
