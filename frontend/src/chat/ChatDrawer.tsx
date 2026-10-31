import { ArrowUp01Icon, Cancel01Icon, Delete02Icon, Shield01Icon } from "@hugeicons/core-free-icons";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import { Mascot, type MascotState } from "@/components/Mascot";
import { Button } from "@/components/ui/button";
import { Icon, Tip } from "@/components/ui/primitives";
import { KindIcon } from "@/canvas/kinds";
import { api, ApiError, errorMessage, request } from "@/lib/api";
import { readSSE } from "@/lib/sse";
import type { ChatCheck, ChatStep, ChatTurn, Hit } from "@/lib/types";
import { cn } from "@/lib/utils";

export type Source = Hit & { n: number };
type Scope = "canvas" | "all";

function upsertStep(steps: ChatStep[], step: ChatStep): ChatStep[] {
  const i = steps.findIndex((s) => s.id === step.id);
  if (i < 0) return [...steps, step];
  const next = steps.slice();
  next[i] = step;
  return next;
}

/** Live steps while an answer is still coming in; one quiet line once it has landed. */
function Steps({ steps, live }: { steps: ChatStep[]; live: boolean }) {
  if (!steps.length) return live ? <p className="text-[13px] text-text-3">Looking through your cards…</p> : null;
  if (live) {
    return (
      <ol className="grid gap-1" aria-label="Progress">
        {steps.map((s) => (
          <li key={s.id} className={cn("flex items-baseline gap-2 text-[12.5px]", s.state === "active" ? "text-text-2" : "text-text-3")}>
            <span className={cn("size-1.5 shrink-0 translate-y-[-1px] rounded-full",
              s.state === "active" ? "bg-accent animate-pulse" : "bg-text-3")} />
            <span className="min-w-0">
              {s.label}{s.state === "active" ? "…" : ""}
              {s.detail && s.state === "done" ? <span> · {s.detail}</span> : null}
            </span>
          </li>
        ))}
      </ol>
    );
  }
  const done = steps.filter((s) => s.state === "done");
  if (!done.length) return null;
  return <p className="text-[12px] text-text-3">{done.map((s) => s.label).join(" · ")}</p>;
}

const SUGGESTIONS = [
  "What did I save about pricing?",
  "Find the link about onboarding",
  "Which notes mention a deadline?",
];

function cleanAnswerText(text: string, sources: Source[]): string {
  let cleaned = text;

  // 1. Strip prompt metadata echoes like:
  // "• **1 Link on canvas "suraj's canvas"** - This is Resend, an..."
  // or "**1 Link on canvas ...** - ..."
  cleaned = cleaned.replace(
    /(?:^|\n)([ \t]*[•*-]?[ \t]*)\*\*(\d{1,2})\s+(?:Link|Note|Text|Code|Image)\s+on\s+canvas\s+"[^"]*"\*\*\s*[-–—:]*\s*(?:This is\s+)?(?:([A-Za-z0-9_.-]+),?\s+)?/gi,
    (_match, prefix, numStr, candidateName) => {
      const num = Number(numStr);
      const source = sources.find((s) => s.n === num);
      const bullet = prefix.trim() ? "- " : "";
      const name =
        source?.title && source.title !== "Link" && source.title !== "Card"
          ? source.title
          : candidateName || "Item";
      return `\n${bullet}**${name}**: `;
    }
  );

  // 2. Also strip "• **1 Link on canvas "..."**" without bold or with different casing
  cleaned = cleaned.replace(
    /(?:^|\n)([ \t]*[•*-]?[ \t]*)(?:\[?\d{1,2}\]?\s+)?(?:Link|Note|Text|Code|Image)\s+on\s+canvas\s+"[^"]*"\s*[-–—:]*\s*/gi,
    (_match, prefix) => {
      const bullet = prefix.trim() ? "\n- " : "\n";
      return bullet;
    }
  );

  // 3. Fix bare numbers at the end of sentences/bullets like "...programmatically 1." or "...programmatically 1"
  cleaned = cleaned.replace(
    /(?<=[a-zA-Z])\s+(\d{1,2})\s*([.!?]|\s*$)/gm,
    (match, numStr, punct) => {
      const num = Number(numStr);
      if (sources.some((s) => s.n === num)) {
        return ` [${num}]${punct}`;
      }
      return match;
    }
  );

  // 4. Normalize unicode bullets (•, –, —) to markdown "- "
  cleaned = cleaned.replace(/^[ \t]*[•–—][ \t]+/gm, "- ");

  // 5. Convert [n] to markdown links [n](#cite-n)
  cleaned = cleaned.replace(/\[(\d{1,2})\]/g, "[$1](#cite-$1)");

  return cleaned.trim();
}

/** Renders Markdown with interactive "[n]" citation chips. Markers that don't match a retrieved card are dropped. */
function Answer({ text, sources, onCite }: { text: string; sources: Source[]; onCite: (s: Source) => void }) {
  const formatted = useMemo(() => cleanAnswerText(text, sources), [text, sources]);

  return (
    <div className="prose-chat">
      <ReactMarkdown
        components={{
          a: ({ href, children }) => {
            if (href?.startsWith("#cite-")) {
              const num = Number(href.slice(6));
              const source = sources.find((s) => s.n === num);
              if (!source) return null;
              return (
                <button
                  key={num}
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    onCite(source);
                  }}
                  aria-label={`Show card ${source.n}: ${source.title}`}
                  className="mx-0.5 inline-grid size-[18px] translate-y-[-1px] place-items-center rounded-full bg-accent-soft
                    align-middle text-[11px] font-semibold text-accent-text transition-colors hover:bg-accent hover:text-accent-fg"
                >
                  {source.n}
                </button>
              );
            }
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer nofollow"
                className="underline underline-offset-2 hover:text-accent-text"
              >
                {children}
              </a>
            );
          },
        }}
      >
        {formatted}
      </ReactMarkdown>
    </div>
  );
}

export function ChatDrawer({ open, onClose, canvasId, onSources, onCite }: {
  open: boolean;
  onClose: () => void;
  canvasId: string;
  /** Cards to highlight on the canvas, keyed by citation number. */
  onSources: (sources: Source[]) => void;
  onCite: (source: Source) => void;
}) {
  const [scope, setScope] = useState<Scope>("canvas");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [mascot, setMascot] = useState<MascotState>("idle");
  const [notice, setNotice] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // History for this scope (sources aren't stored, so old answers show text only).
  useEffect(() => {
    if (!open) return;
    setTurns([]); // earlier turns are stored server-side; reload them for this scope
    const qs = scope === "canvas" ? `?canvas_id=${canvasId}` : "";
    api.get<{ data: ChatTurn[] }>(`/chat/history${qs}`)
      // Merge, don't replace: a question asked while history was loading must keep its turn.
      .then((r) => setTurns((cur) => [
        ...r.data.map((t): ChatTurn => ({ ...t, id: `h-${t.id}`, status: "done" })),
        ...cur.filter((t) => !String(t.id).startsWith("h-")),
      ]))
      .catch(() => {});
  }, [open, scope, canvasId]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 320);
    else {
      abort.current?.abort();
      onSources([]);
    }
  }, [open, onSources]);

  useLayoutEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight });
  }, [turns]);

  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  const patchLast = useCallback((fn: (t: ChatTurn) => ChatTurn) => {
    setTurns((ts) => {
      const last = ts[ts.length - 1];
      return last?.role === "assistant" ? [...ts.slice(0, -1), fn(last)] : ts;
    });
  }, []);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setInput("");
    setNotice(null);
    setBusy(true);
    setMascot("checking");
    onSources([]);
    const now = new Date().toISOString();
    setTurns((ts) => [
      ...ts,
      { id: `u-${now}`, role: "user", content: q, cited: [], status: "done" },
      { id: `a-${now}`, role: "assistant", content: "", cited: [], sources: [], status: "streaming" },
    ]);
    const ctrl = new AbortController();
    abort.current = ctrl;
    try {
      const res = await request<Response>("/chat", {
        method: "POST", raw: true, signal: ctrl.signal,
        body: scope === "canvas" ? { question: q, canvas_id: canvasId, scope } : { question: q, scope },
      });
      let sources: Source[] = [];
      for await (const { event, data } of readSSE(res)) {
        if (event === "status") {
          setMascot("searching");
        } else if (event === "step") {
          const step = data as ChatStep;
          patchLast((t) => ({ ...t, steps: upsertStep(t.steps ?? [], step) }));
          setMascot("searching");
        } else if (event === "check") {
          patchLast((t) => ({ ...t, check: data as ChatCheck }));
        } else if (event === "sources") {
          sources = data as Source[];
          patchLast((t) => ({ ...t, sources }));
          onSources(sources);
        } else if (event === "delta") {
          patchLast((t) => ({ ...t, content: t.content + (data as { text: string }).text }));
        } else if (event === "blocked") {
          patchLast((t) => ({ ...t, content: (data as { message: string }).message, status: "blocked", sources: [] }));
          onSources([]);
          setMascot("blocked");
        } else if (event === "error") {
          patchLast((t) => ({ ...t, content: (data as { message: string }).message, status: "error" }));
          setMascot("blocked");
        } else if (event === "done") {
          const cited = (data as { cited: string[] }).cited;
          patchLast((t) => ({ ...t, cited, status: t.status === "streaming" ? "done" : t.status }));
          setMascot((m) => (m === "blocked" ? m : cited.length ? "found" : "idle"));
          // Only the cards the answer actually used stay highlighted.
          if (cited.length) onSources(sources.filter((s) => cited.includes(s.item_id)));
        }
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        patchLast((t) => ({ ...t, status: "done", content: t.content || "Stopped." }));
        setMascot("idle");
      } else {
        setTurns((ts) => ts.slice(0, -2));
        setInput(q);
        setNotice(e instanceof ApiError && e.status === 429 && e.retryAfter && e.code === "rate_limited"
          ? `You're asking fast. Try again in ${e.retryAfter} seconds.` : errorMessage(e));
        setMascot("blocked");
      }
    } finally {
      setBusy(false);
      abort.current = null;
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    void ask(input);
  }

  async function clear() {
    const qs = scope === "canvas" ? `?canvas_id=${canvasId}` : "";
    await api.del(`/chat/history${qs}`).catch(() => {});
    setTurns([]);
    onSources([]);
    setMascot("idle");
  }

  return (
    <aside aria-label="Ask Stash" aria-hidden={!open} inert={!open}
      className={cn("fixed inset-y-0 right-0 z-30 flex w-full flex-col border-l border-border bg-surface shadow-lg sm:w-[400px]",
        "transition-transform duration-[320ms] ease-[var(--ease-drawer)]", open ? "translate-x-0" : "translate-x-full")}>
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border px-4">
        <Mascot state={mascot} size={30} />
        <div className="min-w-0 flex-1">
          <h2 className="text-[14px] font-semibold leading-tight">Ask Stash</h2>
          <p className="truncate text-[12px] text-text-3">Answers only from your cards</p>
        </div>
        {turns.length > 0 && (
          <Tip label="Clear this conversation">
            <Button variant="ghost" size="icon-sm" onClick={clear} aria-label="Clear conversation">
              <Icon icon={Delete02Icon} size={16} />
            </Button>
          </Tip>
        )}
        <Tip label="Close" kbd="Esc">
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close chat">
            <Icon icon={Cancel01Icon} size={16} />
          </Button>
        </Tip>
      </header>

      <div className="flex shrink-0 gap-1 border-b border-border p-2" role="tablist" aria-label="Search scope">
        {(["canvas", "all"] as const).map((s) => (
          <button key={s} role="tab" aria-selected={scope === s} onClick={() => setScope(s)} disabled={busy}
            className={cn("h-7 flex-1 rounded-[7px] text-[12.5px] font-medium transition-colors",
              scope === s ? "bg-surface-3 text-text" : "text-text-2 hover:text-text")}>
            {s === "canvas" ? "This canvas" : "All canvases"}
          </button>
        ))}
      </div>

      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-4 py-4" aria-live="polite">
        {turns.length === 0 ? (
          <div className="flex h-full flex-col justify-end gap-2 pb-2">
            <p className="mb-1 text-[13px] text-text-2">
              Ask about anything you saved. Stash finds the cards, answers from them, and points to each one.
            </p>
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => ask(s)}
                className="rounded-md border border-border px-3 py-2 text-left text-[13px] text-text-2 transition-colors
                  hover:border-border-strong hover:bg-surface-2 hover:text-text">{s}</button>
            ))}
          </div>
        ) : (
          <ol className="grid gap-5">
            {turns.map((t) => (
              <li key={t.id} className="animate-[rise_220ms_var(--ease-out)]">
                {t.role === "user" ? (
                  <div className="ml-10 rounded-[12px] rounded-br-[4px] bg-surface-3 px-3 py-2 text-[14px]">{t.content}</div>
                ) : (
                  <div>
                    {t.steps && t.steps.length > 0 && t.status !== "blocked" && (
                      <div className={t.content ? "mb-2" : ""}>
                        <Steps steps={t.steps} live={t.status === "streaming"} />
                      </div>
                    )}
                    {t.status === "streaming" && !t.content ? (
                      t.steps && t.steps.length > 0 ? null : <p className="text-[13px] text-text-3">Looking through your cards…</p>
                    ) : t.status === "blocked" ? (
                      <p className="flex items-center gap-2 text-[14px] text-text-2">
                        <Icon icon={Shield01Icon} size={16} className="text-warning" /> {t.content}
                      </p>
                    ) : t.status === "error" ? (
                      <p className="text-[14px] text-danger">{t.content}</p>
                    ) : (
                      <>
                        <Answer text={t.content} sources={t.sources ?? []} onCite={onCite} />
                        {t.check && !t.check.supported && t.check.note && (
                          <p className="mt-2 text-[12.5px] text-warning">{t.check.note}</p>
                        )}
                      </>
                    )}
                    {t.status !== "blocked" && t.sources && t.sources.length > 0 && (t.status !== "done" || t.cited.length > 0) && (
                      <ul className="mt-3 grid gap-1.5">
                        {t.sources.filter((s) => t.status !== "done" || t.cited.includes(s.item_id)).map((s) => (
                          <li key={s.item_id}>
                            <button onClick={() => onCite(s)}
                              className="flex w-full items-center gap-2.5 rounded-md border border-border px-2.5 py-2 text-left
                                transition-colors hover:border-border-strong hover:bg-surface-2">
                              <span className="grid size-5 shrink-0 place-items-center rounded-full bg-accent-soft text-[11px] font-semibold text-accent-text">{s.n}</span>
                              <KindIcon kind={s.kind} size={14} className="shrink-0 text-text-3" />
                              <span className="min-w-0 flex-1 truncate text-[13px]">{s.title}</span>
                              {s.canvas_id !== canvasId && <span className="max-w-[35%] truncate text-[11.5px] text-text-3">{s.canvas_title}</span>}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>

      <form onSubmit={submit} className="shrink-0 border-t border-border p-3">
        {notice && <p role="alert" className="mb-2 text-[12.5px] text-danger">{notice}</p>}
        <div className="flex items-end gap-2 rounded-[12px] border border-border bg-surface-2 p-1.5 pl-3 focus-within:border-accent
          focus-within:ring-[3px] focus-within:ring-accent-soft">
          <textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} rows={1} maxLength={2000}
            placeholder={scope === "canvas" ? "Ask about this canvas…" : "Ask about all your canvases…"} aria-label="Your question"
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void ask(input);
              } else if (e.key === "Escape") onClose();
            }}
            className="max-h-[160px] min-h-[24px] flex-1 resize-none bg-transparent py-1.5 text-[14px] outline-none placeholder:text-text-3" />
          {busy ? (
            <Button type="button" size="icon-sm" variant="secondary" onClick={() => abort.current?.abort()} aria-label="Stop">
              <span className="size-2.5 rounded-[2px] bg-text" />
            </Button>
          ) : (
            <Button type="submit" size="icon-sm" variant="primary" disabled={!input.trim()} aria-label="Send">
              <Icon icon={ArrowUp01Icon} size={16} strokeWidth={2.25} />
            </Button>
          )}
        </div>
        <p className="mt-2 px-1 text-[11.5px] text-text-3">Cards hidden by the safety check are never sent to the AI.</p>
      </form>
    </aside>
  );
}
