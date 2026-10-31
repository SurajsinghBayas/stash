import {
  Add01Icon, Delete02Icon, Edit02Icon, MoreHorizontalIcon, RefreshIcon, Search01Icon,
} from "@hugeicons/core-free-icons";
import { useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Mascot } from "@/components/Mascot";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  Icon,
  Input,
  Menu,
  MenuContent,
  MenuItem,
  MenuTrigger,
} from "@/components/ui/primitives";
import { noteStyle } from "@/canvas/kinds";
import { errorMessage } from "@/lib/api";
import {
  useCanvases, useCanvasTrash, useCreateCanvas, useDeleteCanvas, useMe, useRenameCanvas, useRestoreCanvas, useTemplates,
} from "@/lib/queries";
import type { Canvas, PreviewShape } from "@/lib/types";
import { cn } from "@/lib/utils";
import { timeAgo } from "@/lib/utils";

/** A tiny map of the canvas: real card positions, scaled to fit. */
function Preview({ shapes }: { shapes: PreviewShape[] }) {
  const box = useMemo(() => {
    if (!shapes.length) return null;
    const xs = shapes.flatMap((s) => [s.x, s.x + (s.w ?? 260)]);
    const ys = shapes.flatMap((s) => [s.y, s.y + (s.h ?? 140)]);
    const minX = Math.min(...xs), minY = Math.min(...ys);
    const w = Math.max(...xs) - minX || 1, h = Math.max(...ys) - minY || 1;
    return { minX, minY, w, h };
  }, [shapes]);

  return (
    <div className="relative h-[140px] overflow-hidden rounded-t-[13px] bg-canvas"
      style={{ backgroundImage: "radial-gradient(var(--canvas-dot) 1px, transparent 1px)", backgroundSize: "14px 14px" }}>
      {box && (
        <svg className="absolute inset-0 h-full w-full p-5" viewBox={`0 0 ${box.w} ${box.h}`} preserveAspectRatio="xMidYMid meet"
          aria-hidden="true">
          {shapes.slice().reverse().map((s, i) => {
            const style = s.kind === "note" ? noteStyle(s.color) : null;
            return (
              <rect key={i} x={s.x - box.minX} y={s.y - box.minY} width={s.w ?? 260} height={s.h ?? 140}
                rx={Math.max(box.w, box.h) / 60}
                fill={style ? (style.background as string) : s.kind === "image" ? "var(--surface-3)" : "var(--surface)"}
                stroke="var(--border-strong)" strokeWidth={Math.max(box.w, box.h) / 220} />
            );
          })}
        </svg>
      )}
    </div>
  );
}

function CanvasCard({ canvas, onRename, onDelete }: { canvas: Canvas; onRename: () => void; onDelete: () => void }) {
  return (
    <li className="group relative">
      <Link to={`/c/${canvas.id}`}
        className="block rounded-[14px] border border-border bg-surface shadow-sm transition-[transform,box-shadow,border-color]
          duration-200 ease-[var(--ease-out)] hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md">
        <Preview shapes={canvas.preview} />
        <div className="border-t border-border px-4 py-3">
          <h3 className="truncate pr-8 text-[14px] font-medium">{canvas.title}</h3>
          <p className="mt-0.5 text-[12.5px] text-text-3 tabular">
            {canvas.item_count} {canvas.item_count === 1 ? "card" : "cards"} · {timeAgo(canvas.updated_at)}
          </p>
        </div>
      </Link>
      <div className="absolute bottom-3 right-2 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
        <Menu>
          <MenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label={`Options for ${canvas.title}`}>
              <Icon icon={MoreHorizontalIcon} size={16} />
            </Button>
          </MenuTrigger>
          <MenuContent>
            <MenuItem icon={Edit02Icon} onSelect={onRename}>Rename</MenuItem>
            <MenuItem icon={Delete02Icon} danger onSelect={onDelete}>Delete canvas</MenuItem>
          </MenuContent>
        </Menu>
      </div>
    </li>
  );
}

/** Blank canvas or a starter template. */
function NewCanvasDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const templates = useTemplates();
  const create = useCreateCanvas();
  const navigate = useNavigate();
  const [busy, setBusy] = useState<string | null>(null);

  async function make(key: string | null, title: string) {
    setBusy(key ?? "blank");
    try {
      const c = await create.mutateAsync({ title, template: key ?? undefined });
      onOpenChange(false);
      navigate(`/c/${c.id}`);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  const option = "flex flex-col items-start rounded-[12px] border border-border p-4 text-left transition-colors hover:border-border-strong hover:bg-surface-2 disabled:opacity-60";
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="New canvas" description="Start blank, or with a few cards already laid out." className="sm:max-w-[640px]">
        <div className="grid max-h-[60vh] gap-2.5 overflow-y-auto sm:grid-cols-2">
          <button className={cn(option, "border-dashed")} disabled={!!busy} onClick={() => make(null, "Untitled canvas")}>
            <span className="flex items-center gap-2 text-[14px] font-medium"><Icon icon={Add01Icon} size={16} /> Blank canvas</span>
            <span className="mt-1 text-[12.5px] text-text-2">An empty board. Paste, drop or write anything.</span>
            {busy === "blank" && <span className="mt-2 text-[12px] text-text-3">Creating…</span>}
          </button>
          {templates.isPending && Array.from({ length: 3 }, (_, i) => <div key={i} className="shimmer h-[88px] rounded-[12px]" />)}
          {templates.data?.map((t) => (
            <button key={t.key} className={option} disabled={!!busy} onClick={() => make(t.key, t.title)}>
              <span className="text-[14px] font-medium">{t.title}</span>
              <span className="mt-1 text-[12.5px] text-text-2">{t.description}</span>
              <span className="mt-2 text-[12px] text-text-3">{busy === t.key ? "Creating…" : `${t.cards} starter cards`}</span>
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function RecentlyDeleted() {
  const trash = useCanvasTrash();
  const restore = useRestoreCanvas();
  const [open, setOpen] = useState(false);
  const rows = trash.data ?? [];
  if (!rows.length) return null;
  return (
    <section className="mt-12">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="text-[13.5px] font-medium text-text-2 transition-colors hover:text-text">
        Recently deleted ({rows.length}) {open ? "▾" : "▸"}
      </button>
      {open && (
        <>
          <p className="mt-1 text-[12.5px] text-text-3">Deleted canvases are kept for 30 days, then removed for good.</p>
          <ul className="mt-3 grid gap-2 sm:max-w-[560px]">
            {rows.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface px-4 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-[14px]">{c.title}</p>
                  <p className="text-[12px] text-text-3 tabular">
                    {c.item_count} {c.item_count === 1 ? "card" : "cards"} · deleted {timeAgo(c.deleted_at)}
                  </p>
                </div>
                <Button variant="secondary" size="sm" loading={restore.isPending && restore.variables === c.id}
                  onClick={() => restore.mutate(c.id, {
                    onSuccess: () => toast.success(`“${c.title}” is back`),
                    onError: (e) => toast.error(errorMessage(e)),
                  })}>
                  <Icon icon={RefreshIcon} size={14} /> Restore
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export default function Dashboard() {
  const [q, setQ] = useState("");
  const canvases = useCanvases(q.trim());
  const [creating, setCreating] = useState(false);
  const rename = useRenameCanvas();
  const remove = useDeleteCanvas();
  const me = useMe();
  const [renaming, setRenaming] = useState<Canvas | null>(null);
  const [deleting, setDeleting] = useState<Canvas | null>(null);
  const [title, setTitle] = useState("");

  const newCanvas = () => setCreating(true);

  async function submitRename(e: FormEvent) {
    e.preventDefault();
    if (!renaming || !title.trim()) return;
    try {
      await rename.mutateAsync({ id: renaming.id, title: title.trim() });
      setRenaming(null);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const list = canvases.data?.data ?? [];
  const firstName = me.data?.display_name?.split(" ")[0];
  const isEmpty = !canvases.isPending && list.length === 0 && !q;

  return (
    <AppShell>
      <main className="mx-auto max-w-[1200px] px-4 pb-24 pt-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-[22px] font-semibold tracking-[-0.02em]">{firstName ? `${firstName}'s canvases` : "Your canvases"}</h1>
            <p className="mt-1 text-[13.5px] text-text-2">Each canvas is a board for one topic, project or trip.</p>
          </div>
          <div className="flex w-full items-center gap-2 sm:w-auto">
            {!isEmpty && (
              <div className="relative flex-1 sm:w-[240px] sm:flex-none">
                <Icon icon={Search01Icon} size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-3" />
                <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by name" className="h-9 pl-9"
                  aria-label="Filter canvases by name" />
              </div>
            )}
            <Button variant="primary" onClick={newCanvas}>
              <Icon icon={Add01Icon} size={16} /> New canvas
            </Button>
          </div>
        </div>

        {canvases.isPending ? (
          <ul className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" aria-busy="true">
            {Array.from({ length: 4 }, (_, i) => <li key={i} className="shimmer h-[200px] rounded-[14px]" />)}
          </ul>
        ) : isEmpty ? (
          <div className="mt-16 flex flex-col items-center text-center">
            <Mascot size={88} follow />
            <h2 className="mt-5 text-[17px] font-semibold">Start your first canvas</h2>
            <p className="mt-1.5 max-w-[42ch] text-[14px] text-text-2">
              Paste a link, drop an image or jot a note. Stash keeps an eye on all of it and finds it when you ask.
            </p>
            <Button variant="primary" size="lg" className="mt-6" onClick={newCanvas}>
              <Icon icon={Add01Icon} size={16} /> New canvas
            </Button>
          </div>
        ) : list.length === 0 ? (
          <p className="mt-12 text-center text-text-2">No canvas is called “{q}”.</p>
        ) : (
          <ul className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {list.map((c) => (
              <CanvasCard key={c.id} canvas={c} onRename={() => { setTitle(c.title); setRenaming(c); }}
                onDelete={() => setDeleting(c)} />
            ))}
          </ul>
        )}
        <RecentlyDeleted />
      </main>

      <NewCanvasDialog open={creating} onOpenChange={setCreating} />

      <Dialog open={!!renaming} onOpenChange={(o) => !o && setRenaming(null)}>
        <DialogContent title="Rename canvas">
          <form onSubmit={submitRename} className="grid gap-4">
            <Input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} aria-label="Canvas name" />
            <div className="flex justify-end gap-2">
              <DialogClose asChild><Button variant="ghost">Cancel</Button></DialogClose>
              <Button type="submit" variant="primary" loading={rename.isPending} disabled={!title.trim()}>Save</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <DialogContent title={`Delete “${deleting?.title}”?`}
          description={`Its ${deleting?.item_count ?? 0} cards go with it and its reminders are cancelled. You can restore it from “Recently deleted” for 30 days.`}>
          <div className="flex justify-end gap-2">
            <DialogClose asChild><Button variant="ghost">Cancel</Button></DialogClose>
            <Button variant="danger" loading={remove.isPending} onClick={async () => {
              if (!deleting) return;
              try {
                await remove.mutateAsync(deleting.id);
                setDeleting(null);
                toast.success("Canvas deleted", { description: "Restore it from “Recently deleted” below." });
              } catch (e) {
                toast.error(errorMessage(e));
              }
            }}>Delete canvas</Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
