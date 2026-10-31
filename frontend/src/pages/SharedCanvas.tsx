import { FullScreenIcon } from "@hugeicons/core-free-icons";
import { useQuery } from "@tanstack/react-query";
import {
  Background, BackgroundVariant, ReactFlow, ReactFlowProvider, useReactFlow, type Node, type NodeProps,
} from "@xyflow/react";
import { useEffect, useMemo } from "react";
import { Link, useParams } from "react-router";
import { CodeCard, LinkCard, NoteCard, TextCard } from "@/canvas/cards";
import { DEFAULT_SIZE, noteStyle } from "@/canvas/kinds";
import { Mascot, Wordmark } from "@/components/Mascot";
import { Button } from "@/components/ui/button";
import { Icon, Tip } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useMe } from "@/lib/queries";
import type { Item, NoteColor, SharedCanvas as Shared } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";

type SharedCard = Shared["items"][number];
type SharedNode = Node<{ card: SharedCard; token: string }, "shared">;

const noop = () => {};

/** The shared view only has what the owner chose to show; fill in the rest so the normal cards can render it. */
function asItem(card: SharedCard): Item {
  return {
    ...card, canvas_id: "", version: 1, index_state: "ready", safety_state: "ok", safety_categories: [],
    ai: { summary: "", tags: [] }, created_at: "", updated_at: "",
  } as unknown as Item;
}

function SharedCardNode({ data }: NodeProps<SharedNode>) {
  const { card, token } = data;
  const item = asItem(card);
  const isText = card.kind === "text";
  let body;
  switch (item.kind) {
    case "link": body = <LinkCard item={item} editing={false} onChange={noop} onDone={noop} />; break;
    case "note": body = <NoteCard item={item} editing={false} onChange={noop} onDone={noop} />; break;
    case "text": body = <TextCard item={item} editing={false} onChange={noop} onDone={noop} />; break;
    case "code": body = <CodeCard item={item} editing={false} onChange={noop} onDone={noop} />; break;
    case "image":
      body = (
        <figure>
          <img src={`/api/v1/public/canvases/${token}/items/${card.id}/image?size=thumb`} alt={item.content.caption || "Image"}
            loading="lazy" draggable={false} className="block w-full rounded-[13px]"
            style={item.content.width && item.content.height ? { aspectRatio: `${item.content.width} / ${item.content.height}` } : undefined} />
          {item.content.caption && <figcaption className="px-3 py-2 text-[12.5px] text-text-2">{item.content.caption}</figcaption>}
        </figure>
      );
  }
  return (
    <div className={cn("card relative h-full rounded-[14px]", isText ? "rounded-[8px]" : "overflow-hidden border border-border bg-surface shadow-sm")}
      style={card.kind === "note" ? noteStyle(card.content.color as NoteColor) : undefined} data-kind={card.kind}>
      {body}
    </div>
  );
}

const nodeTypes = { shared: SharedCardNode };

function Board({ token, data }: { token: string; data: Shared }) {
  const flow = useReactFlow();
  const nodes = useMemo<SharedNode[]>(() => data.items.map((c) => ({
    id: c.id, type: "shared", position: { x: c.x, y: c.y }, zIndex: c.z,
    width: c.w ?? DEFAULT_SIZE[c.kind].w, height: c.h ?? undefined,
    data: { card: c, token }, draggable: false, selectable: false, connectable: false,
  })), [data, token]);

  return (
    <div className="relative min-h-0 flex-1">
      <ReactFlow<SharedNode> nodes={nodes} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.15, maxZoom: 1 }}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable={false} panOnScroll panOnDrag zoomOnDoubleClick={false}
        minZoom={0.1} maxZoom={3} proOptions={{ hideAttribution: true }} onlyRenderVisibleElements={nodes.length > 150}
        aria-label="Shared canvas">
        <Background variant={BackgroundVariant.Dots} gap={22} size={1.4} color="var(--canvas-dot)" />
      </ReactFlow>
      {nodes.length === 0 && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div><Mascot size={56} /><p className="mt-3 text-[14px] text-text-2">Nothing to show on this canvas yet.</p></div>
        </div>
      )}
      <div className="absolute bottom-5 left-1/2 z-10 -translate-x-1/2 rounded-[12px] border border-border bg-surface/95 p-1 shadow-lg backdrop-blur-md">
        <Tip label="Fit everything">
          <Button variant="ghost" size="icon" aria-label="Fit everything in view"
            onClick={() => flow.fitView({ duration: 400, padding: 0.15, maxZoom: 1 })}>
            <Icon icon={FullScreenIcon} size={18} />
          </Button>
        </Tip>
      </div>
    </div>
  );
}

export default function SharedCanvas() {
  const { token = "" } = useParams();
  const me = useMe();
  const shared = useQuery({
    queryKey: ["shared", token],
    queryFn: async () => (await api.get<{ data: Shared }>(`/public/canvases/${encodeURIComponent(token)}`)).data,
    staleTime: 60_000,
  });

  useEffect(() => {
    // Shared canvases are private content made viewable, not pages for search engines.
    let robots = document.head.querySelector<HTMLMetaElement>('meta[name="robots"]');
    const before = robots?.content ?? null;
    if (!robots) robots = Object.assign(document.createElement("meta"), { name: "robots" });
    robots.content = "noindex, nofollow";
    document.head.appendChild(robots);
    return () => {
      if (before === null) robots.remove();
      else robots.content = before;
      document.title = "Stash";
    };
  }, []);
  useEffect(() => {
    if (shared.data) document.title = `${shared.data.title} · Shared on Stash`;
  }, [shared.data]);

  const notFound = shared.error instanceof ApiError && shared.error.status === 404;

  return (
    <div className="flex h-dvh flex-col bg-canvas">
      <header className="z-20 flex h-14 shrink-0 items-center gap-3 border-b border-border bg-bg/85 px-3 backdrop-blur-md sm:px-4">
        <Link to="/" aria-label="Stash home"><Wordmark /></Link>
        <span className="h-5 w-px bg-border" />
        <div className="min-w-0 flex-1">
          {shared.data ? (
            <>
              <h1 className="truncate text-[14px] font-medium leading-tight">{shared.data.title}</h1>
              <p className="text-[11.5px] text-text-3">View only · updated {timeAgo(shared.data.updated_at)}</p>
            </>
          ) : shared.isPending ? <div className="shimmer h-4 w-40 rounded" /> : null}
        </div>
        <Button asChild variant="primary" size="sm">
          {me.data ? <Link to="/app">Open Stash</Link> : <Link to="/signup">Make your own</Link>}
        </Button>
      </header>
      {shared.isPending ? (
        <div className="grid flex-1 place-items-center"><Mascot state="searching" size={44} /></div>
      ) : shared.data ? (
        <ReactFlowProvider><Board token={token} data={shared.data} /></ReactFlowProvider>
      ) : (
        <div className="grid flex-1 place-items-center px-4 text-center">
          <div>
            <Mascot state="sleeping" size={64} />
            <h2 className="mt-4 text-[18px] font-semibold">{notFound ? "This link doesn't work" : "Couldn't load this canvas"}</h2>
            <p className="mt-1 max-w-[40ch] text-text-2">
              {notFound ? "The owner may have stopped sharing it, or deleted the canvas." : "Check your connection and try again."}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
