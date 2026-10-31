import {
  AiChat02Icon,
  ArrowLeft01Icon,
  CheckmarkCircle02Icon,
  FullScreenIcon,
  Image01Icon,
  Link01Icon,
  Note01Icon,
  Search01Icon,
  SourceCodeIcon,
  TextFontIcon,
} from "@hugeicons/core-free-icons";
import {
  applyNodeChanges,
  Background,
  BackgroundVariant,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type NodeChange,
  type Viewport,
} from "@xyflow/react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "sonner";
import { AccountMenu, useQuickFindShortcut } from "@/components/AppShell";
import { Mascot } from "@/components/Mascot";
import { QuickFind } from "@/components/QuickFind";
import { Button } from "@/components/ui/button";
import { Icon, Input, Kbd, Popover, PopoverAnchor, PopoverContent, Tip } from "@/components/ui/primitives";
import { Spinner } from "@/components/ui/spinner";
import { ChatDrawer, type Source } from "@/chat/ChatDrawer";
import { api, errorMessage } from "@/lib/api";
import { useCanvas, useRenameCanvas } from "@/lib/queries";
import type { Item, Kind } from "@/lib/types";
import { asUrl, cn, modKey } from "@/lib/utils";
import { CanvasActionsProvider, nodeTypes, type CanvasActions, type CardNodeType } from "./CardNode";
import { DEFAULT_SIZE } from "./kinds";
import { ReminderDialog } from "./ReminderDialog";
import { useItemSync, type SaveStatus } from "./useItemSync";

const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

const EMPTY_CONTENT: Record<Exclude<Kind, "image" | "link">, object> = {
  note: { markdown: "", color: "yellow" },
  text: { text: "", size: "m" },
  code: { language: "javascript", source: "", filename: "" },
};

function SaveIndicator({ status }: { status: SaveStatus }) {
  const label = { saved: "Saved", saving: "Saving…", offline: "Offline. Will save when you're back.", error: "Couldn't save. Retrying…" }[status];
  return (
    <span className={cn("hidden items-center gap-1.5 text-[12.5px] sm:flex",
      status === "saved" ? "text-text-3" : status === "saving" ? "text-text-2" : "text-warning")} role="status">
      {status === "saving" ? <Spinner className="size-3.5" /> : status === "saved" ? <Icon icon={CheckmarkCircle02Icon} size={14} /> : null}
      {label}
    </span>
  );
}

function TitleEditor({ id, title }: { id: string; title: string }) {
  const [value, setValue] = useState(title);
  const rename = useRenameCanvas();
  useEffect(() => setValue(title), [title]);
  const save = () => {
    const t = value.trim();
    if (!t) return setValue(title);
    if (t !== title) rename.mutate({ id, title: t }, { onError: (e) => { toast.error(errorMessage(e)); setValue(title); } });
  };
  return (
    <input value={value} onChange={(e) => setValue(e.target.value)} onBlur={save} maxLength={120} aria-label="Canvas name"
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === "Escape") (e.target as HTMLInputElement).blur(); }}
      className="h-8 min-w-0 max-w-[340px] flex-1 truncate rounded-md bg-transparent px-2 text-[14px] font-medium outline-none
        hover:bg-surface-2 focus:bg-surface-2 focus:ring-[3px] focus:ring-accent-soft" />
  );
}

function Board() {
  const { canvasId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const flow = useReactFlow<CardNodeType>();
  const canvas = useCanvas(canvasId);
  const sync = useItemSync(canvasId);
  const wrapper = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const [nodes, setNodes] = useState<CardNodeType[]>([]);
  const [editingId, setEditing] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [findOpen, setFindOpen] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState("");
  const [remindFor, setRemindFor] = useState<Item | null>(null);
  const [lightbox, setLightbox] = useState<Item | null>(null);
  const [hits, setHits] = useState<Map<string, number>>(new Map());
  const [dragOver, setDragOver] = useState(false);

  useQuickFindShortcut(useCallback(() => setFindOpen(true), []));

  /* ---------- items → nodes, keeping React Flow's own state (selection, measurements, drag) ---------- */
  useEffect(() => {
    setNodes((prev) => {
      const prevById = new Map(prev.map((n) => [n.id, n]));
      return [...sync.items.values()].map((it) => {
        const p = prevById.get(it.id);
        return {
          ...(p ?? {}),
          id: it.id,
          type: "card" as const,
          position: p?.dragging ? p.position : { x: it.x, y: it.y },
          width: it.w ?? DEFAULT_SIZE[it.kind].w,
          height: it.h ?? undefined,
          zIndex: it.z,
          data: { item: it, hit: hits.get(it.id) },
        };
      });
    });
  }, [sync.items, hits]);

  const onNodesChange = useCallback((changes: NodeChange<CardNodeType>[]) => {
    // Deletion goes through onNodesDelete so it's saved; everything else is view state.
    setNodes((nds) => applyNodeChanges(changes.filter((c) => c.type !== "remove"), nds));
  }, []);

  const selected = nodes.filter((n) => n.selected);
  const maxZ = useMemo(() => Math.max(0, ...[...sync.items.values()].map((i) => i.z)), [sync.items]);

  /* ---------- placing new cards ---------- */
  const viewCenter = useCallback(() => {
    const r = wrapper.current?.getBoundingClientRect();
    if (!r) return { x: 0, y: 0 };
    const chatW = chatOpen && window.innerWidth >= 640 ? 400 : 0;
    return flow.screenToFlowPosition({ x: r.left + (r.width - chatW) / 2, y: r.top + r.height / 2 });
  }, [flow, chatOpen]);

  /** Where a new card goes: the given point, or the free spot nearest the middle of the view. */
  const placeAt = useCallback((kind: Kind, at?: { x: number; y: number }) => {
    const size = DEFAULT_SIZE[kind];
    const h = size.h ?? 160;
    const z = maxZ + 1; // new cards land on top
    if (at) return { x: Math.round(at.x), y: Math.round(at.y), w: size.w, h: size.h, z };
    const c = viewCenter();
    const taken = flow.getNodes().map((n) => ({
      x: n.position.x, y: n.position.y,
      w: n.measured?.width ?? n.width ?? 260, h: n.measured?.height ?? n.height ?? 160,
    }));
    const GAP = 24;
    const free = (x: number, y: number) =>
      taken.every((r) => x + size.w + GAP <= r.x || r.x + r.w + GAP <= x || y + h + GAP <= r.y || r.y + r.h + GAP <= y);
    let x = c.x - size.w / 2, y = c.y - h / 2;
    // Walk a square spiral outward from the centre until the card fits.
    for (let ring = 0, found = free(x, y); !found && ring < 30; ring++) {
      const step = 60 * (ring + 1);
      for (const [dx, dy] of [[step, 0], [-step, 0], [0, step], [0, -step], [step, step], [-step, -step], [step, -step], [-step, step]]) {
        if (free(c.x - size.w / 2 + dx!, c.y - h / 2 + dy!)) {
          x = c.x - size.w / 2 + dx!;
          y = c.y - h / 2 + dy!;
          found = true;
          break;
        }
      }
    }
    return { x: Math.round(x), y: Math.round(y), w: size.w, h: size.h, z };
  }, [viewCenter, maxZ, flow]);

  const addCard = useCallback(async (kind: "note" | "text" | "code", at?: { x: number; y: number }, content?: object) => {
    const { id, done } = sync.create({ kind, ...placeAt(kind, at), content: content ?? EMPTY_CONTENT[kind] });
    setNodes((nds) => nds.map((n) => ({ ...n, selected: n.id === id })));
    if (!content) setEditing(id);
    try {
      await done;
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }, [sync, placeAt]);

  const addLink = useCallback(async (url: string, at?: { x: number; y: number }) => {
    try {
      const res = await sync.create({ kind: "link", ...placeAt("link", at), content: { url, comment: "" } }).done;
      const dup = res.meta.duplicate_of;
      if (dup) {
        toast("You saved this link before", {
          description: dup.canvas_id === canvasId ? "It's already on this canvas." : `It's also on “${dup.canvas_title}”.`,
          action: dup.canvas_id === canvasId ? undefined : { label: "Open", onClick: () => navigate(`/c/${dup.canvas_id}`) },
        });
      }
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }, [sync, placeAt, canvasId, navigate]);

  const uploadImage = useCallback(async (file: File, at?: { x: number; y: number }) => {
    if (!IMAGE_TYPES.includes(file.type)) return toast.error("Use a JPEG, PNG, WebP or GIF image.");
    if (file.size > MAX_IMAGE_BYTES) return toast.error("Images can be up to 10 MB.");
    const pos = placeAt("image", at);
    let itemId: string | null = null;
    try {
      const start = await api.post<{ data: { item: Item; upload: { url: string; method: string; headers: Record<string, string> } } }>(
        `/canvases/${canvasId}/uploads`, { filename: file.name.slice(0, 200) || "image", mime: file.type, bytes: file.size, x: pos.x, y: pos.y });
      itemId = start.data.item.id;
      sync.upsert([start.data.item]);
      const put = await fetch(start.data.upload.url, { method: "PUT", headers: start.data.upload.headers, body: file });
      if (!put.ok) throw new Error("upload failed");
      const done = await api.post<{ data: Item }>(`/items/${itemId}/uploaded`);
      sync.upsert([done.data]);
    } catch (e) {
      toast.error(e instanceof Error && e.message === "upload failed" ? "The upload didn't go through. Try again." : errorMessage(e));
      if (itemId) void sync.remove([itemId]);
    }
  }, [canvasId, placeAt, sync]);

  /* ---------- paste & drop ---------- */
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input, textarea, [contenteditable=true]")) return;
      const files = [...(e.clipboardData?.files ?? [])].filter((f) => f.type.startsWith("image/"));
      if (files.length) {
        e.preventDefault();
        files.slice(0, 10).forEach((f) => void uploadImage(f));
        return;
      }
      const text = e.clipboardData?.getData("text/plain") ?? "";
      if (!text.trim()) return;
      e.preventDefault();
      const url = asUrl(text);
      if (url) void addLink(url);
      else if (/[{};]\s*$|^\s*(import|def|function|const|class|SELECT)\b/m.test(text) && text.includes("\n"))
        void addCard("code", undefined, { language: "plaintext", source: text.slice(0, 20000), filename: "" });
      else void addCard(text.length > 140 || text.includes("\n") ? "note" : "text", undefined,
        text.length > 140 || text.includes("\n") ? { markdown: text.slice(0, 20000), color: "yellow" } : { text, size: "m" });
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [uploadImage, addLink, addCard]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const at = flow.screenToFlowPosition({ x: e.clientX, y: e.clientY });
    const files = [...e.dataTransfer.files].filter((f) => f.type.startsWith("image/"));
    if (files.length) return files.slice(0, 10).forEach((f, i) => void uploadImage(f, { x: at.x + i * 24, y: at.y + i * 24 }));
    const url = asUrl(e.dataTransfer.getData("text/uri-list") || e.dataTransfer.getData("text/plain"));
    if (url) void addLink(url, at);
  };

  /* ---------- keyboard ---------- */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input, textarea, select, [contenteditable=true], [role=dialog]") || e.altKey) return;
      if (editingId) return; // a card is being edited: its keys are text, never shortcuts
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === "j") { e.preventDefault(); setEditing(null); setChatOpen((o) => !o); return; }
      if (mod) return;
      const k = e.key.toLowerCase();
      if (k === "n") { e.preventDefault(); void addCard("note"); }
      else if (k === "t") { e.preventDefault(); void addCard("text"); }
      else if (k === "c") { e.preventDefault(); void addCard("code"); }
      else if (k === "l") { e.preventDefault(); setLinkOpen(true); }
      else if (k === "i") { e.preventDefault(); fileInput.current?.click(); }
      else if (k === "/") { e.preventDefault(); setChatOpen(true); }
      else if (k === "1" && e.shiftKey) { e.preventDefault(); flow.fitView({ duration: 400, padding: 0.2, maxZoom: 1 }); }
      else if (k === "enter" && selected.length === 1) { e.preventDefault(); setEditing(selected[0]!.id); }
      else if (k === "escape") { setNodes((nds) => nds.map((n) => (n.selected ? { ...n, selected: false } : n))); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [addCard, flow, selected, editingId]);

  /* ---------- viewport: restore, save, and jump to ?item= ---------- */
  const restored = useRef(false);
  useEffect(() => {
    if (restored.current || !canvas.data || !sync.loaded) return;
    restored.current = true;
    const target = params.get("item");
    const it = target ? sync.items.get(target) : undefined;
    if (it) {
      requestAnimationFrame(() => focusItem(it.id));
      params.delete("item");
      setParams(params, { replace: true });
    } else if (canvas.data.viewport && (canvas.data.viewport.x || canvas.data.viewport.y || canvas.data.viewport.zoom !== 1)) {
      flow.setViewport(canvas.data.viewport);
    } else if (sync.items.size) {
      requestAnimationFrame(() => flow.fitView({ padding: 0.2, maxZoom: 1 }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canvas.data, sync.loaded]);

  const viewportTimer = useRef<number | null>(null);
  const onMoveEnd = useCallback((_: unknown, vp: Viewport) => {
    if (!restored.current) return;
    if (viewportTimer.current) clearTimeout(viewportTimer.current);
    viewportTimer.current = window.setTimeout(() => {
      api.patch(`/canvases/${canvasId}`, { viewport: { x: Math.round(vp.x), y: Math.round(vp.y), zoom: +vp.zoom.toFixed(3) } })
        .catch(() => {});
    }, 800);
  }, [canvasId]);

  const focusItem = useCallback((id: string, n?: number) => {
    const node = flow.getNode(id);
    if (!node) return;
    const w = node.measured?.width ?? node.width ?? 260;
    const h = node.measured?.height ?? node.height ?? 160;
    const chatShift = chatOpen && window.innerWidth >= 640 ? 200 / Math.max(flow.getZoom(), 0.6) : 0;
    flow.setCenter(node.position.x + w / 2 + chatShift, node.position.y + h / 2, { zoom: Math.max(flow.getZoom(), 0.9), duration: 600 });
    setNodes((nds) => nds.map((x) => ({ ...x, selected: x.id === id })));
    setHits((prev) => (prev.has(id) ? prev : new Map([...prev, [id, n ?? prev.size + 1]])));
  }, [flow, chatOpen]);

  const onSources = useCallback((sources: Source[]) => {
    setHits(new Map(sources.filter((s) => s.canvas_id === canvasId).map((s) => [s.item_id, s.n])));
  }, [canvasId]);

  const onCite = useCallback((s: Source) => {
    if (s.canvas_id === canvasId) focusItem(s.item_id, s.n);
    else navigate(`/c/${s.canvas_id}?item=${s.item_id}`);
  }, [canvasId, focusItem, navigate]);

  /* ---------- actions for cards ---------- */
  const actions: CanvasActions = useMemo(() => ({
    editingId,
    setEditing,
    update: (id, patch) => sync.update(id, patch),
    remove: (ids) => { void sync.remove(ids); setEditing(null); },
    remind: (item) => setRemindFor(item),
    openImage: (item) => setLightbox(item),
    singleSelection: selected.length === 1,
  }), [editingId, sync, selected.length]);

  if (canvas.error || sync.loadError) {
    return (
      <div className="grid min-h-dvh place-items-center px-4 text-center">
        <div>
          <Mascot state="sleeping" size={64} />
          <h1 className="mt-4 text-[18px] font-semibold">This canvas isn't here</h1>
          <p className="mt-1 text-text-2">It may have been deleted.</p>
          <Button asChild variant="secondary" className="mt-4"><Link to="/app">Back to your canvases</Link></Button>
        </div>
      </div>
    );
  }

  const tools: { kind: string; label: string; icon: typeof Note01Icon; key: string; run: () => void }[] = [
    { kind: "note", label: "Note", icon: Note01Icon, key: "N", run: () => void addCard("note") },
    { kind: "text", label: "Text", icon: TextFontIcon, key: "T", run: () => void addCard("text") },
    { kind: "code", label: "Code", icon: SourceCodeIcon, key: "C", run: () => void addCard("code") },
    { kind: "image", label: "Image", icon: Image01Icon, key: "I", run: () => fileInput.current?.click() },
  ];

  const empty = sync.loaded && sync.items.size === 0;

  return (
    <CanvasActionsProvider value={actions}>
      <div className="flex h-dvh flex-col bg-canvas">
        <header className="z-20 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-bg/85 px-3 backdrop-blur-md">
          <Tip label="All canvases">
            <Button asChild variant="ghost" size="icon-sm" aria-label="All canvases">
              <Link to="/app"><Icon icon={ArrowLeft01Icon} size={18} /></Link>
            </Button>
          </Tip>
          {canvas.data ? <TitleEditor id={canvasId} title={canvas.data.title} /> : <div className="shimmer h-5 w-40 rounded" />}
          <div className="flex-1" />
          <SaveIndicator status={sync.status} />
          <Button variant="ghost" size="sm" onClick={() => setFindOpen(true)} aria-label="Find a card" className="text-text-2">
            <Icon icon={Search01Icon} size={15} /><Kbd className="hidden sm:inline-flex">{modKey}K</Kbd>
          </Button>
          <AccountMenu />
        </header>

        <div ref={wrapper} className={cn("relative min-h-0 flex-1", dragOver && "ring-2 ring-inset ring-accent")}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)} onDrop={onDrop}
          onDoubleClick={(e) => {
            if (!(e.target as HTMLElement).classList.contains("react-flow__pane")) return;
            void addCard("note", flow.screenToFlowPosition({ x: e.clientX, y: e.clientY }));
          }}>
          <ReactFlow<CardNodeType>
            nodes={nodes}
            onNodesChange={onNodesChange}
            nodeTypes={nodeTypes}
            onNodeDragStop={(_, __, dragged) => dragged.forEach((n) => sync.update(n.id, { x: Math.round(n.position.x), y: Math.round(n.position.y) }))}
            onNodeDoubleClick={(_, n) => setEditing(n.id)}
            onNodesDelete={(deleted) => actions.remove(deleted.map((n) => n.id))}
            onPaneClick={() => setEditing(null)}
            onMoveEnd={onMoveEnd}
            deleteKeyCode={["Backspace", "Delete"]}
            multiSelectionKeyCode={["Meta", "Shift"]}
            selectionOnDrag
            panOnDrag={[1, 2]}
            panOnScroll
            zoomOnDoubleClick={false}
            minZoom={0.1}
            maxZoom={3}
            proOptions={{ hideAttribution: true }}
            onlyRenderVisibleElements={nodes.length > 150}
            elevateNodesOnSelect
            aria-label="Canvas"
          >
            <Background variant={BackgroundVariant.Dots} gap={22} size={1.4} color="var(--canvas-dot)" />
          </ReactFlow>

          {!sync.loaded && (
            <div className="pointer-events-none absolute inset-0 grid place-items-center"><Mascot state="searching" size={44} /></div>
          )}
          {empty && (
            <div className="pointer-events-none absolute inset-0 grid place-items-center px-4 text-center">
              <div className="animate-[rise_320ms_var(--ease-out)]">
                <Mascot size={64} follow />
                <p className="mt-4 text-[15px] font-medium">An empty canvas</p>
                <p className="mt-1 max-w-[36ch] text-[13.5px] text-text-2">
                  Paste a link or image, drop files here, or double-click anywhere to write a note.
                </p>
              </div>
            </div>
          )}

          {/* Toolbar */}
          <div className={cn("absolute bottom-5 left-1/2 z-10 flex -translate-x-1/2 items-center gap-1 rounded-[14px] border border-border",
            "bg-surface/95 p-1.5 shadow-lg backdrop-blur-md transition-transform duration-[320ms] ease-[var(--ease-drawer)]",
            chatOpen && "sm:-translate-x-[calc(50%+200px)]")} role="toolbar" aria-label="Add to canvas">
            {tools.map((t) => (
              <Tip key={t.kind} label={`Add ${t.label.toLowerCase()}`} kbd={t.key}>
                <Button variant="ghost" size="icon" onClick={t.run} aria-label={`Add ${t.label.toLowerCase()}`}>
                  <Icon icon={t.icon} size={19} />
                </Button>
              </Tip>
            ))}
            <Popover open={linkOpen} onOpenChange={setLinkOpen}>
              <PopoverAnchor asChild>
                <span>
                  <Tip label="Add link" kbd="L">
                    <Button variant="ghost" size="icon" onClick={() => setLinkOpen(true)} aria-label="Add link">
                      <Icon icon={Link01Icon} size={19} />
                    </Button>
                  </Tip>
                </span>
              </PopoverAnchor>
              <PopoverContent side="top" className="w-[340px]">
                <form onSubmit={(e: FormEvent) => {
                  e.preventDefault();
                  const url = asUrl(linkUrl);
                  if (!url) return toast.error("That doesn't look like a link.");
                  void addLink(url);
                  setLinkUrl("");
                  setLinkOpen(false);
                }} className="flex gap-2">
                  <Input autoFocus value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)} placeholder="Paste a link"
                    className="h-9" aria-label="Link address" />
                  <Button type="submit" variant="primary" disabled={!linkUrl.trim()}>Add</Button>
                </form>
              </PopoverContent>
            </Popover>
            <span className="mx-1 h-6 w-px bg-border" />
            <Tip label="Fit everything" kbd="⇧1">
              <Button variant="ghost" size="icon" onClick={() => flow.fitView({ duration: 400, padding: 0.2, maxZoom: 1 })} aria-label="Fit everything in view">
                <Icon icon={FullScreenIcon} size={18} />
              </Button>
            </Tip>
            <Tip label="Ask Stash" kbd={`${modKey}J`}>
              <Button variant="primary" onClick={() => { setEditing(null); setChatOpen((o) => !o); }} aria-pressed={chatOpen} className="ml-0.5 gap-1.5">
                <Icon icon={AiChat02Icon} size={17} /> <span className="hidden sm:inline">Ask</span>
              </Button>
            </Tip>
          </div>

          <input ref={fileInput} type="file" accept={IMAGE_TYPES.join(",")} multiple hidden
            onChange={(e) => { [...(e.target.files ?? [])].slice(0, 10).forEach((f) => void uploadImage(f)); e.target.value = ""; }} />
        </div>
      </div>

      <ChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} canvasId={canvasId} onSources={onSources} onCite={onCite} />
      <QuickFind open={findOpen} onOpenChange={setFindOpen} />
      <ReminderDialog item={remindFor} open={!!remindFor} onOpenChange={(o) => !o && setRemindFor(null)} />

      <DialogPrimitive.Root open={!!lightbox} onOpenChange={(o) => !o && setLightbox(null)}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-[60] bg-black/80 data-[state=open]:animate-[fade-in_200ms_var(--ease-out)]" />
          <DialogPrimitive.Content aria-describedby={undefined} onClick={() => setLightbox(null)}
            className="fixed inset-0 z-[60] grid place-items-center p-6 outline-none data-[state=open]:animate-[pop_220ms_var(--ease-out)]">
            <DialogPrimitive.Title className="sr-only">Image</DialogPrimitive.Title>
            {lightbox?.kind === "image" && (
              <figure className="max-h-full max-w-full">
                <img src={`/api/v1/items/${lightbox.id}/image?size=display&v=${lightbox.version}`} alt={lightbox.content.caption}
                  className="max-h-[85vh] max-w-full rounded-lg object-contain shadow-lg" />
                {lightbox.content.caption && <figcaption className="mt-3 text-center text-[13.5px] text-white/80">{lightbox.content.caption}</figcaption>}
              </figure>
            )}
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
    </CanvasActionsProvider>
  );
}

export default function CanvasPage() {
  const { canvasId } = useParams();
  return (
    <ReactFlowProvider key={canvasId}>
      <Board />
    </ReactFlowProvider>
  );
}
