import { CheckmarkCircle02Icon } from "@hugeicons/core-free-icons";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { Mascot, Wordmark } from "@/components/Mascot";
import { Button } from "@/components/ui/button";
import { Icon, Input, Label, Textarea } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import { fetchAllItems, useCanvases, useCreateCanvas } from "@/lib/queries";
import type { Item } from "@/lib/types";
import { asUrl, hostOf } from "@/lib/utils";

const LAST_CANVAS = "stash-share-canvas";
const URL_IN_TEXT = /https?:\/\/[^\s<>"']+/i;

function remembered(): string | null {
  try {
    return localStorage.getItem(LAST_CANVAS);
  } catch {
    return null;
  }
}

/** What another app shared: Android puts the link in `url`, `text`, or both. */
function parseShare(params: URLSearchParams) {
  const title = (params.get("title") ?? "").trim();
  const text = (params.get("text") ?? "").trim();
  const url = asUrl(params.get("url") ?? "") ?? asUrl(text.match(URL_IN_TEXT)?.[0] ?? "");
  const rest = url ? text.replace(URL_IN_TEXT, "").trim() : text;
  return { title, text: rest, url };
}

/** Opened by the phone's share sheet (manifest share_target), or by hand at /share?url=… */
export default function ShareTarget() {
  const [params] = useSearchParams();
  const shared = useMemo(() => parseShare(params), [params]);
  const canvases = useCanvases("");
  const create = useCreateCanvas();
  const list = canvases.data?.data ?? [];
  const [canvasId, setCanvasId] = useState<string>("");
  const [note, setNote] = useState(shared.url ? shared.text : [shared.title, shared.text].filter(Boolean).join("\n\n"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<{ canvasId: string; itemId: string } | null>(null);

  useEffect(() => { document.title = "Save to Stash"; return () => { document.title = "Stash"; }; }, []);
  useEffect(() => {
    if (canvasId || !canvases.data) return;
    const last = remembered();
    setCanvasId(list.find((c) => c.id === last)?.id ?? list[0]?.id ?? "");
  }, [canvases.data, canvasId, list]);

  const nothing = !shared.url && !note.trim();

  async function save(e: FormEvent) {
    e.preventDefault();
    if (nothing) return;
    setBusy(true);
    setError(null);
    try {
      let target = canvasId;
      if (!target) target = (await create.mutateAsync({ title: "Inbox" })).id;
      // New cards go under what's already there, so nothing lands on top of an existing card.
      const items = await fetchAllItems(target);
      const y = items.length ? Math.max(...items.map((i) => i.y + (i.h ?? 240))) + 60 : 0;
      const x = items.length ? Math.min(...items.map((i) => i.x)) : 0;
      const body = shared.url
        ? { kind: "link", x, y, content: { url: shared.url, comment: note.trim().slice(0, 2000) } }
        : { kind: "note", x, y, w: 320, content: { markdown: note.trim().slice(0, 20000), color: "yellow" } };
      const item = (await api.post<{ data: Item }>(`/canvases/${target}/items`, body)).data;
      try { localStorage.setItem(LAST_CANVAS, target); } catch { /* private mode */ }
      setSaved({ canvasId: target, itemId: item.id });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-dvh bg-bg">
      <header className="flex h-14 items-center border-b border-border px-4">
        <Link to="/app" aria-label="Your canvases"><Wordmark /></Link>
      </header>
      <main className="mx-auto max-w-[480px] px-4 py-8">
        {saved ? (
          <div className="text-center">
            <Mascot state="found" size={64} />
            <h1 className="mt-4 flex items-center justify-center gap-2 text-[18px] font-semibold">
              <Icon icon={CheckmarkCircle02Icon} size={20} className="text-success" /> Saved to Stash
            </h1>
            <div className="mt-6 flex justify-center gap-2">
              <Button asChild variant="primary"><Link to={`/c/${saved.canvasId}?item=${saved.itemId}`}>Open canvas</Link></Button>
              <Button variant="secondary" onClick={() => window.history.length > 1 ? window.history.back() : window.close()}>Done</Button>
            </div>
          </div>
        ) : (
          <form onSubmit={save} className="grid gap-5">
            <h1 className="text-[20px] font-semibold tracking-[-0.02em]">Save to Stash</h1>
            {shared.url ? (
              <div className="rounded-md border border-border bg-surface px-4 py-3">
                <p className="text-[12px] text-text-3">{hostOf(shared.url)}</p>
                <p className="mt-0.5 line-clamp-2 break-all text-[14px] font-medium">{shared.title || shared.url}</p>
              </div>
            ) : null}
            <div className="grid gap-1.5">
              <Label htmlFor="share-note">{shared.url ? "Comment (optional)" : "Note"}</Label>
              <Textarea id="share-note" value={note} onChange={(e) => setNote(e.target.value)} rows={shared.url ? 2 : 6}
                maxLength={shared.url ? 2000 : 20000} placeholder={shared.url ? "Why you saved this…" : "Write or paste something"} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="share-canvas">Canvas</Label>
              {canvases.isPending ? <div className="shimmer h-10 rounded-md" /> : list.length ? (
                <select id="share-canvas" value={canvasId} onChange={(e) => setCanvasId(e.target.value)}
                  className="h-10 rounded-md border border-border bg-surface-2 px-3 text-[14px] outline-none focus:border-accent">
                  {list.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                </select>
              ) : (
                <Input id="share-canvas" readOnly value="A new canvas called Inbox" />
              )}
            </div>
            {error && <p role="alert" className="text-[13px] text-danger">{error}</p>}
            {nothing && <p className="text-[13px] text-text-2">Nothing was shared. Write a note, or share a link from another app.</p>}
            <Button type="submit" variant="primary" size="lg" loading={busy} disabled={nothing}>Save</Button>
          </form>
        )}
      </main>
    </div>
  );
}
