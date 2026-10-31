import { Copy01Icon, Image01Icon, ViewOffIcon } from "@hugeicons/core-free-icons";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { highlight } from "sugar-high";
import { toast } from "sonner";
import { Mascot } from "@/components/Mascot";
import { Icon, Tip } from "@/components/ui/primitives";
import type { CodeContent, ImageContent, Item, LinkContent, NoteContent, TextContent } from "@/lib/types";
import { cn, hostOf } from "@/lib/utils";

export interface CardProps<C> {
  item: Item & { content: C };
  editing: boolean;
  onChange: (content: Partial<C>) => void;
  onDone: () => void;
}

/** Textareas inside cards must not start a canvas drag or zoom. */
const NO_CANVAS = "nodrag nowheel nopan";

/**
 * Focus the editor when editing starts. React Flow keeps a new node hidden until it has measured it, and a hidden
 * element can't take focus, so retry for a few frames until it does.
 */
function useAutoFocus(editing: boolean) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (!editing) return;
    let frame = 0;
    let tries = 0;
    const attempt = () => {
      const el = ref.current;
      if (!el) return;
      el.focus({ preventScroll: true });
      if (document.activeElement === el) {
        el.setSelectionRange(el.value.length, el.value.length);
      } else if (tries++ < 30) {
        frame = requestAnimationFrame(attempt);
      }
    };
    attempt();
    return () => cancelAnimationFrame(frame);
  }, [editing]);
  return ref;
}

function useAutoGrow(ref: React.RefObject<HTMLTextAreaElement | null>, value: string) {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${el.scrollHeight}px`;
  }, [ref, value]);
}

/** Escape or ⌘/Ctrl+Enter finishes editing. Blurring (not unmounting) runs each card's save-on-blur path. */
function onEditKeys(e: React.KeyboardEvent) {
  e.stopPropagation(); // canvas shortcuts (Delete, N, T…) must not fire while typing
  if (e.key === "Escape" || ((e.metaKey || e.ctrlKey) && e.key === "Enter")) {
    e.preventDefault();
    (e.target as HTMLElement).blur();
  }
}

export function FlaggedBadge() {
  return (
    <Tip label="Stash's safety check flagged this card. It's never sent to the AI or put in emails.">
      <span className="absolute right-2 top-2 z-[1] inline-flex items-center gap-1 rounded-full bg-warning-soft px-2 py-0.5
        text-[11px] font-medium text-warning">
        <Icon icon={ViewOffIcon} size={12} /> Hidden from AI
      </span>
    </Tip>
  );
}

/* ---------- Link ---------- */
export function LinkCard({ item, editing, onChange, onDone }: CardProps<LinkContent>) {
  const c = item.content;
  const [imgOk, setImgOk] = useState(true);
  const ref = useAutoFocus(editing);
  const host = hostOf(c.url);
  const hidden = c.blocked_domain || item.safety_state === "flagged";
  const pending = c.fetch_state === "pending";

  if (hidden && c.blocked_domain) {
    return (
      <div className="p-4">
        <p className="text-[12px] text-text-3">{host}</p>
        <p className="mt-1 text-[13.5px] text-text-2">Stash doesn't show previews for this site.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {pending ? (
        <div className="shimmer aspect-[1.91] w-full rounded-t-[13px]" />
      ) : c.image && imgOk && !hidden ? (
        <img src={c.image} alt="" loading="lazy" referrerPolicy="no-referrer" draggable={false}
          onError={() => setImgOk(false)} className="aspect-[1.91] w-full rounded-t-[13px] border-b border-border object-cover" />
      ) : null}
      <div className="p-3.5">
        <div className="flex items-center gap-1.5 text-[12px] text-text-3">
          {c.favicon && !hidden && (
            <img src={c.favicon} alt="" width={14} height={14} referrerPolicy="no-referrer" className="size-3.5 rounded-[3px]"
              onError={(e) => (e.currentTarget.style.display = "none")} />
          )}
          <span className="truncate">{c.site_name || host}</span>
        </div>
        {pending ? (
          <div className="mt-2 grid gap-1.5"><div className="shimmer h-4 w-4/5 rounded" /><div className="shimmer h-3 w-3/5 rounded" /></div>
        ) : (
          <>
            <h3 className="mt-1 line-clamp-2 text-[14px] font-medium leading-snug">{c.title || c.url}</h3>
            {!hidden && item.ai?.summary ? (
              <p className="mt-1 line-clamp-3 text-[12.5px] leading-snug text-text-2">{item.ai.summary}</p>
            ) : c.description && !hidden ? (
              <p className="mt-1 line-clamp-2 text-[12.5px] leading-snug text-text-2">{c.description}</p>
            ) : item.index_state === "pending" ? (
              <p className="mt-1 text-[12px] text-text-3">Reading this page…</p>
            ) : null}
            {!hidden && item.ai?.tags?.length > 0 && (
              <ul className="mt-2 flex flex-wrap gap-1">
                {item.ai.tags.map((tag) => (
                  <li key={tag} className="rounded-full bg-surface-3 px-2 py-0.5 text-[11px] text-text-2">#{tag}</li>
                ))}
              </ul>
            )}
          </>
        )}
        {editing ? (
          <textarea ref={ref} defaultValue={c.comment} placeholder="Why you saved this…" rows={2} maxLength={2000}
            onBlur={(e) => { onChange({ comment: e.target.value }); onDone(); }} onKeyDown={onEditKeys}
            className={cn(NO_CANVAS, "mt-2.5 w-full resize-none rounded-md border border-border bg-surface-2 p-2 text-[13px] outline-none focus:border-accent")} />
        ) : c.comment ? (
          <p className="mt-2.5 border-l-2 border-accent pl-2.5 text-[13px] text-text">{c.comment}</p>
        ) : null}
      </div>
    </div>
  );
}

/* ---------- Note ---------- */
export function NoteCard({ item, editing, onChange, onDone }: CardProps<NoteContent>) {
  const ref = useAutoFocus(editing);
  const md = item.content.markdown;
  if (editing) {
    return (
      <textarea ref={ref} defaultValue={md} maxLength={20000} placeholder="Write in Markdown…"
        onBlur={(e) => { onChange({ markdown: e.target.value }); onDone(); }} onKeyDown={onEditKeys}
        className={cn(NO_CANVAS, "h-full w-full resize-none bg-transparent p-4 font-mono text-[13px] leading-relaxed outline-none placeholder:opacity-50")} />
    );
  }
  return (
    <div className={cn("prose-note h-full overflow-hidden p-4", !md && "opacity-50")}>
      {md ? (
        <ReactMarkdown components={{ a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer nofollow">{children}</a> }}>
          {md}
        </ReactMarkdown>
      ) : "Double-click to write"}
    </div>
  );
}

/* ---------- Text ---------- */
const TEXT_SIZE: Record<TextContent["size"], string> = {
  s: "text-[14px] leading-normal",
  m: "text-[18px] leading-snug",
  l: "text-[26px] leading-tight font-medium tracking-[-0.015em]",
  xl: "text-[40px] leading-[1.05] font-semibold tracking-[-0.03em]",
};

export function TextCard({ item, editing, onChange, onDone }: CardProps<TextContent>) {
  const ref = useAutoFocus(editing);
  const [draft, setDraft] = useState(item.content.text);
  useEffect(() => setDraft(item.content.text), [item.content.text]);
  useAutoGrow(ref, draft);
  const size = TEXT_SIZE[item.content.size] ?? TEXT_SIZE.m;
  if (editing) {
    return (
      <textarea ref={ref} value={draft} rows={1} maxLength={2000} onChange={(e) => setDraft(e.target.value)}
        onBlur={() => { onChange({ text: draft }); onDone(); }} onKeyDown={onEditKeys}
        className={cn(NO_CANVAS, size, "block w-full resize-none overflow-hidden bg-transparent px-1 outline-none")} />
    );
  }
  return (
    <p className={cn(size, "whitespace-pre-wrap break-words px-1", !item.content.text && "text-text-3")}>
      {item.content.text || "Double-click to type"}
    </p>
  );
}

/* ---------- Code ---------- */
export const LANGUAGES = ["plaintext", "javascript", "typescript", "python", "go", "rust", "java", "sql", "bash", "json",
  "html", "css", "yaml", "markdown"];

export function CodeCard({ item, editing, onChange, onDone }: CardProps<CodeContent>) {
  const c = item.content;
  const ref = useAutoFocus(editing);
  const html = useMemo(() => (c.language === "plaintext" ? null : highlight(c.source)), [c.source, c.language]);
  const wrapRef = useRef<HTMLDivElement>(null);
  // Edits stay local until editing ends: every saved change re-runs the safety check and re-indexes the card.
  const draft = useRef<Partial<CodeContent>>({});
  const finish = () => {
    if (Object.keys(draft.current).length) onChange(draft.current);
    draft.current = {};
    onDone();
  };
  const set = (patch: Partial<CodeContent>) => Object.assign(draft.current, patch);

  // Leaving the whole editor (not moving between its fields) ends editing.
  const onBlurWithin = (e: React.FocusEvent) => {
    if (!wrapRef.current?.contains(e.relatedTarget as Node)) finish();
  };

  return (
    <div ref={wrapRef} className="code-card flex h-full flex-col" onBlur={editing ? onBlurWithin : undefined}>
      <div className="flex h-9 shrink-0 items-center gap-2 border-b border-border px-3 text-[12px] text-text-3">
        <span className="flex gap-1" aria-hidden="true">
          <span className="size-2 rounded-full bg-surface-3" /><span className="size-2 rounded-full bg-surface-3" />
        </span>
        {editing ? (
          <>
            <input defaultValue={c.filename} placeholder="filename" maxLength={120} onKeyDown={onEditKeys}
              onChange={(e) => set({ filename: e.target.value })}
              className={cn(NO_CANVAS, "min-w-0 flex-1 bg-transparent font-mono text-text outline-none")} aria-label="File name" />
            <select defaultValue={c.language} onChange={(e) => set({ language: e.target.value })} aria-label="Language"
              className={cn(NO_CANVAS, "rounded bg-surface-2 px-1 py-0.5 text-[12px] outline-none")}>
              {LANGUAGES.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </>
        ) : (
          <>
            <span className="min-w-0 flex-1 truncate font-mono text-text-2">{c.filename || c.language}</span>
            <button className={cn(NO_CANVAS, "rounded p-1 hover:bg-surface-2 hover:text-text")} aria-label="Copy code"
              onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(c.source).then(() => toast.success("Copied")); }}>
              <Icon icon={Copy01Icon} size={14} />
            </button>
          </>
        )}
      </div>
      {editing ? (
        <textarea ref={ref} defaultValue={c.source} maxLength={20000} spellCheck={false} onKeyDown={onEditKeys}
          onChange={(e) => set({ source: e.target.value })}
          className={cn(NO_CANVAS, "min-h-0 flex-1 resize-none bg-transparent p-3 font-mono text-[12.5px] leading-relaxed outline-none")} />
      ) : (
        <pre className={cn(NO_CANVAS, "min-h-0 flex-1 overflow-auto p-3 font-mono text-[12.5px] leading-relaxed", !c.source && "text-text-3")}>
          {html ? <code dangerouslySetInnerHTML={{ __html: html }} /> : <code>{c.source || "Double-click to paste code"}</code>}
        </pre>
      )}
    </div>
  );
}

/* ---------- Image ---------- */
const REJECT_REASON: Record<string, string> = {
  not_an_image: "That file isn't an image we can read.",
  type_mismatch: "The file type doesn't match its contents.",
  too_large: "That image is too large.",
};

export function ImageCard({ item, editing, onChange, onDone, onOpen }: CardProps<ImageContent> & { onOpen: () => void }) {
  const c = item.content;
  const ref = useAutoFocus(editing);
  const ratio = c.width && c.height ? `${c.width} / ${c.height}` : "4 / 3";

  let body: React.ReactNode;
  if (c.upload_state === "ready") {
    body = (
      <img src={`/api/v1/items/${item.id}/image?size=thumb&v=${item.version}`} alt={c.caption || c.filename} draggable={false}
        loading="lazy" onDoubleClick={(e) => { e.stopPropagation(); onOpen(); }}
        className="block w-full rounded-t-[13px] object-cover" style={{ aspectRatio: ratio }} />
    );
  } else if (c.upload_state === "blocked" || c.upload_state === "rejected") {
    body = (
      <div className="flex flex-col items-center gap-2 rounded-t-[13px] bg-surface-2 px-4 py-8 text-center" style={{ aspectRatio: ratio }}>
        <Mascot state="blocked" size={32} />
        <p className="text-[12.5px] text-text-2">
          {c.upload_state === "blocked" ? "This image didn't pass the safety check and was removed."
            : REJECT_REASON[c.reject_reason ?? ""] ?? "This image couldn't be used."}
        </p>
      </div>
    );
  } else {
    body = (
      <div className="flex flex-col items-center justify-center gap-2 rounded-t-[13px] bg-surface-2 text-[12.5px] text-text-2"
        style={{ aspectRatio: ratio }}>
        <Mascot state="checking" size={32} />
        {c.upload_state === "awaiting_upload" ? "Uploading…" : "Checking image…"}
      </div>
    );
  }

  return (
    <div>
      {body}
      <div className="flex items-center gap-1.5 px-3 py-2 text-[12.5px]">
        {editing ? (
          <textarea ref={ref} defaultValue={c.caption} rows={1} maxLength={300} placeholder="Add a caption"
            onBlur={(e) => { onChange({ caption: e.target.value }); onDone(); }} onKeyDown={onEditKeys}
            className={cn(NO_CANVAS, "w-full resize-none bg-transparent outline-none")} />
        ) : (
          <>
            <Icon icon={Image01Icon} size={13} className="shrink-0 text-text-3" />
            <span className={cn("truncate", c.caption ? "text-text" : "text-text-3")}>{c.caption || c.filename}</span>
          </>
        )}
      </div>
    </div>
  );
}
