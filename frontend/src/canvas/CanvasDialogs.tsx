import { Copy01Icon, Globe02Icon, RefreshIcon } from "@hugeicons/core-free-icons";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, Icon, Input } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import { keys, useItemTrash, useVersions } from "@/lib/queries";
import type { Canvas, Item } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { KIND_LABEL, KindIcon } from "./kinds";

/** The text a person would recognise a card (or an earlier version of it) by. */
export function contentPreview(kind: Item["kind"], c: Record<string, unknown>): string {
  const s = (k: string) => (typeof c[k] === "string" ? (c[k] as string) : "");
  switch (kind) {
    case "note": return s("markdown");
    case "text": return s("text");
    case "code": return [s("filename"), s("source")].filter(Boolean).join("\n");
    case "link": return [s("title") || s("url"), s("comment")].filter(Boolean).join("\n");
    case "image": return s("caption") || s("filename");
  }
}

/** One line for a list: the first non-empty line, without Markdown symbols. */
function firstLine(text: string): string {
  const line = text.split("\n").map((l) => l.trim()).find(Boolean) ?? "";
  return line.replace(/^[#>\-*+\s]+/, "").replace(/[*_`~]/g, "").trim();
}

/* ---------- share ---------- */

export function ShareDialog({ canvas, open, onOpenChange }: { canvas: Canvas; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const url = canvas.share_token ? `${window.location.origin}/s/${canvas.share_token}` : null;

  async function run(on: boolean) {
    setBusy(true);
    try {
      let token: string | null = null;
      if (on) token = (await api.post<{ data: { token: string } }>(`/canvases/${canvas.id}/share`)).data.token;
      else await api.del(`/canvases/${canvas.id}/share`);
      qc.setQueryData<Canvas>(keys.canvas(canvas.id), (c) => (c ? { ...c, share_token: token } : c));
      if (on && token) {
        await navigator.clipboard?.writeText(`${window.location.origin}/s/${token}`).catch(() => {});
        toast.success("Link created and copied");
      } else toast.success("Link turned off. The old link no longer works.");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Share this canvas" description="Anyone with the link can view the canvas. They can't edit it or see your other canvases.">
        {url ? (
          <div className="grid gap-3">
            <div className="flex gap-2">
              <Input readOnly value={url} aria-label="Share link" onFocus={(e) => e.target.select()} className="h-9 text-[13px]" />
              <Button variant="secondary" onClick={() => navigator.clipboard.writeText(url).then(() => toast.success("Copied"))}>
                <Icon icon={Copy01Icon} size={15} /> Copy
              </Button>
            </div>
            <p className="text-[12.5px] text-text-3">
              Cards waiting for the safety check, and anything it hid, are not shown. Reminders, chat and your account stay private.
            </p>
            <div className="flex justify-end">
              <Button variant="ghost" className="text-danger" loading={busy} onClick={() => run(false)}>Stop sharing</Button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-3">
            <p className="flex items-center gap-2 text-[13.5px] text-text-2"><Icon icon={Globe02Icon} size={16} /> Only you can see this canvas.</p>
            <Button variant="primary" loading={busy} onClick={() => run(true)}>Create link</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

/* ---------- trash ---------- */

export function TrashDialog({ canvasId, open, onOpenChange, onRestored }: {
  canvasId: string; open: boolean; onOpenChange: (o: boolean) => void; onRestored: (item: Item) => void;
}) {
  const trash = useItemTrash(canvasId, open);
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);

  async function restore(id: string) {
    setBusy(id);
    try {
      const item = (await api.post<{ data: Item }>(`/items/${id}/restore`)).data;
      onRestored(item);
      qc.setQueryData<Item[]>(keys.itemTrash(canvasId), (rows) => rows?.filter((r) => r.id !== id));
      toast.success("Card restored");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  const rows = trash.data ?? [];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Recently deleted cards" description="Deleted cards are kept for 30 days, then removed for good." className="sm:max-w-[520px]">
        {trash.isPending ? (
          <div className="grid gap-2">{[0, 1].map((i) => <div key={i} className="shimmer h-14 rounded-md" />)}</div>
        ) : trash.isError ? (
          <p className="text-[13px] text-danger">{errorMessage(trash.error)}</p>
        ) : rows.length === 0 ? (
          <p className="text-[13.5px] text-text-2">Nothing here. Cards you delete from this canvas show up here.</p>
        ) : (
          <ul className="grid max-h-[55vh] gap-2 overflow-y-auto">
            {rows.map((it) => (
              <li key={it.id} className="flex items-center gap-3 rounded-md border border-border px-3 py-2.5">
                <KindIcon kind={it.kind} size={16} className="shrink-0 text-text-3" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px]">
                    {firstLine(contentPreview(it.kind, it.content as unknown as Record<string, unknown>)) || KIND_LABEL[it.kind]}
                  </p>
                  <p className="text-[12px] text-text-3">{KIND_LABEL[it.kind]} · deleted {timeAgo(it.deleted_at)}</p>
                </div>
                <Button variant="secondary" size="sm" loading={busy === it.id} disabled={!!busy} onClick={() => restore(it.id)}>
                  <Icon icon={RefreshIcon} size={14} /> Restore
                </Button>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}

/* ---------- history ---------- */

export function HistoryDialog({ item, onOpenChange, beforeRestore, onRestored }: {
  item: Item | null;
  onOpenChange: (o: boolean) => void;
  /** Saves pending edits first, and returns the card's current version. */
  beforeRestore: (id: string) => Promise<number | undefined>;
  onRestored: (item: Item) => void;
}) {
  const versions = useVersions(item?.id ?? null);
  const [busy, setBusy] = useState<number | null>(null);
  const rows = versions.data ?? [];

  async function restore(versionId: number) {
    if (!item) return;
    setBusy(versionId);
    try {
      const current = (await beforeRestore(item.id)) ?? item.version;
      const restored = (await api.post<{ data: Item }>(`/items/${item.id}/versions/${versionId}/restore`, { version: current })).data;
      onRestored(restored);
      onOpenChange(false);
      toast.success("Earlier version restored", { description: "What it replaced is in History too, so you can switch back." });
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Dialog open={!!item} onOpenChange={onOpenChange}>
      <DialogContent title="Card history" description="Earlier versions of this card's text. Moving or resizing isn't recorded." className="sm:max-w-[560px]">
        {versions.isPending ? (
          <div className="grid gap-2">{[0, 1].map((i) => <div key={i} className="shimmer h-20 rounded-md" />)}</div>
        ) : versions.isError ? (
          <p className="text-[13px] text-danger">{errorMessage(versions.error)}</p>
        ) : rows.length === 0 ? (
          <p className="text-[13.5px] text-text-2">No earlier versions yet. After you edit this card, its previous text shows up here.</p>
        ) : (
          <ol className="grid max-h-[60vh] gap-2 overflow-y-auto">
            {rows.map((v) => (
              <li key={v.id} className="rounded-md border border-border p-3">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span className="text-[12.5px] text-text-3">{timeAgo(v.created_at)} · {new Date(v.created_at).toLocaleString()}</span>
                  <Button variant="secondary" size="sm" loading={busy === v.id} disabled={busy !== null} onClick={() => restore(v.id)}>
                    Restore
                  </Button>
                </div>
                <p className="line-clamp-6 whitespace-pre-wrap break-words text-[13px] text-text-2">
                  {item ? contentPreview(item.kind, v.content) || "(empty)" : ""}
                </p>
              </li>
            ))}
          </ol>
        )}
      </DialogContent>
    </Dialog>
  );
}
