/**
 * Local-first card state for one canvas.
 *
 * Edits apply to local state immediately and are sent as one batched PATCH every ~500 ms, with the version each
 * card had. If someone else (another tab, or the worker adding link metadata) changed a card first, the server
 * refuses that card and returns its current copy: geometry-only edits are re-applied on top of it automatically;
 * content edits yield to the server copy and the user is told.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { fetchAllItems } from "@/lib/queries";
import type { Item } from "@/lib/types";

export type Patch = Partial<Pick<Item, "x" | "y" | "w" | "h" | "z">> & { content?: Record<string, unknown> };
export type SaveStatus = "saved" | "saving" | "offline" | "error";

const GEOMETRY = new Set(["x", "y", "w", "h", "z"]);
const FLUSH_MS = 500;

function needsPolling(items: Iterable<Item>): boolean {
  for (const i of items) {
    if (i.kind === "link" && i.content.fetch_state === "pending") return true;
    if (i.kind === "image" && (i.content.upload_state === "processing" || i.content.upload_state === "awaiting_upload"))
      return true;
    if (i.safety_state === "unchecked" || i.index_state === "pending") return true;
  }
  return false;
}

export function useItemSync(canvasId: string) {
  const [items, setItems] = useState<Map<string, Item>>(new Map());
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [status, setStatus] = useState<SaveStatus>("saved");
  const itemsRef = useRef(items);
  itemsRef.current = items;
  const pending = useRef(new Map<string, Patch>());
  const creating = useRef(new Set<string>());
  /** Cards deleted here: a poll response that started before the delete must not bring them back. */
  const removed = useRef(new Set<string>());
  const inFlight = useRef(false);
  const timer = useRef<number | null>(null);

  const upsert = useCallback((list: Item[]) => {
    list.forEach((it) => removed.current.delete(it.id)); // restored cards are live again
    setItems((prev) => {
      const next = new Map(prev);
      for (const it of list) next.set(it.id, it);
      return next;
    });
  }, []);

  /* ---------- load ---------- */
  useEffect(() => {
    const ctrl = new AbortController();
    setLoaded(false);
    fetchAllItems(canvasId, ctrl.signal)
      .then((list) => {
        // Merge rather than replace: cards created before the load finished must survive it.
        setItems((prev) => new Map([...list.filter((i) => !removed.current.has(i.id)).map((i): [string, Item] => [i.id, i]), ...prev]));
        setLoaded(true);
      })
      .catch((e) => {
        if ((e as Error).name !== "AbortError") setLoadError(e instanceof ApiError ? e : null);
      });
    return () => ctrl.abort();
  }, [canvasId]);

  /* ---------- flush ---------- */
  const flush = useCallback(async () => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = null;
    if (inFlight.current || pending.current.size === 0) return;
    const batch = new Map(pending.current);
    pending.current.clear();
    inFlight.current = true;
    setStatus("saving");
    const body = {
      items: [...batch].flatMap(([id, patch]) => {
        const current = itemsRef.current.get(id);
        if (creating.current.has(id)) {
          pending.current.set(id, { ...patch, ...(pending.current.get(id) ?? {}) }); // not on the server yet
          return [];
        }
        return current ? [{ id, version: current.version, ...patch }] : [];
      }),
    };
    try {
      if (body.items.length) {
        const res = await api.patch<{ data: { updated: Item[]; conflicts: Item[] } }>(`/canvases/${canvasId}/items`, body);
        const { updated, conflicts } = res.data;
        setItems((prev) => {
          const next = new Map(prev);
          for (const server of updated) {
            const local = next.get(server.id);
            const again = pending.current.get(server.id);
            // Keep newer local edits made while this request was in flight.
            next.set(server.id, again && local ? { ...server, ...again, content: { ...server.content, ...(again.content ?? {}) } } as Item : server);
          }
          for (const server of conflicts) {
            const sent = batch.get(server.id) ?? {};
            const geometryOnly = Object.keys(sent).every((k) => GEOMETRY.has(k));
            if (geometryOnly) {
              next.set(server.id, { ...server, ...sent } as Item);
              pending.current.set(server.id, { ...sent, ...(pending.current.get(server.id) ?? {}) });
            } else {
              next.set(server.id, server);
              pending.current.delete(server.id);
              toast("This card changed somewhere else", { description: "We kept the newer version." });
            }
          }
          return next;
        });
      }
      setStatus("saved");
    } catch (e) {
      // Put the edits back; newer edits to the same card win.
      for (const [id, patch] of batch) pending.current.set(id, { ...patch, ...(pending.current.get(id) ?? {}) });
      setStatus(e instanceof ApiError && e.code === "offline" ? "offline" : "error");
      window.setTimeout(() => void flush(), 4000);
    } finally {
      inFlight.current = false;
      if (pending.current.size) schedule();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canvasId]);

  const schedule = useCallback(() => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void flush(), FLUSH_MS);
    setStatus((s) => (s === "saved" ? "saving" : s));
  }, [flush]);

  /** Apply a local edit and queue it for saving. */
  const update = useCallback(
    (id: string, patch: Patch) => {
      setItems((prev) => {
        const current = prev.get(id);
        if (!current) return prev;
        const next = new Map(prev);
        next.set(id, {
          ...current, ...patch, content: patch.content ? { ...current.content, ...patch.content } : current.content,
        } as Item);
        return next;
      });
      const queued = pending.current.get(id) ?? {};
      pending.current.set(id, {
        ...queued, ...patch, ...(patch.content ? { content: { ...(queued.content ?? {}), ...patch.content } } : {}),
      });
      schedule();
    },
    [schedule],
  );

  const create = useCallback(
    (body: { kind: Item["kind"]; x: number; y: number; w?: number | null; h?: number | null; z?: number; content: object }) => {
      // Optimistic: the card appears (and can be typed into) at once; edits wait for the create to land.
      const id = crypto.randomUUID();
      const now = new Date().toISOString();
      const draft = {
        id, canvas_id: canvasId, w: null, h: null, z: 0, ...body, version: 1, index_state: "pending",
        safety_state: "unchecked", safety_categories: [], ai: { summary: "", tags: [] }, created_at: now, updated_at: now,
        ...(body.kind === "link" ? { content: { ...body.content, fetch_state: "pending" } } : {}),
      } as unknown as Item;
      creating.current.add(id);
      upsert([draft]);
      const done = (async () => {
      try {
        const res = await api.post<{ data: Item; meta: { duplicate_of: { canvas_id: string; canvas_title: string } | null } }>(
          `/canvases/${canvasId}/items`, { id, ...body });
        // Keep anything typed while the create was in flight; it's still queued in `pending`.
        const typed = pending.current.get(id);
        upsert([typed ? ({ ...res.data, ...typed, content: { ...res.data.content, ...(typed.content ?? {}) } } as Item) : res.data]);
        return res;
      } catch (e) {
        pending.current.delete(id);
        setItems((prev) => {
          const next = new Map(prev);
          next.delete(id);
          return next;
        });
        throw e;
      } finally {
        creating.current.delete(id);
        if (pending.current.has(id)) schedule();
      }
      })();
      return { id, done };
    },
    [canvasId, upsert, schedule],
  );

  /** Deletes cards; resolves with the ids the server actually deleted. */
  const remove = useCallback(async (ids: string[]): Promise<string[]> => {
    const gone = ids.map((id) => itemsRef.current.get(id)).filter(Boolean) as Item[];
    ids.forEach((id) => removed.current.add(id));
    setItems((prev) => {
      const next = new Map(prev);
      ids.forEach((id) => next.delete(id));
      return next;
    });
    ids.forEach((id) => pending.current.delete(id));
    const results = await Promise.allSettled(gone.map((it) => api.del(`/items/${it.id}`)));
    const failed = gone.filter((_, i) => results[i]!.status === "rejected");
    if (failed.length) {
      upsert(failed);
      toast.error("Couldn't delete some cards. Try again.");
    }
    return gone.filter((_, i) => results[i]!.status === "fulfilled").map((it) => it.id);
  }, [upsert]);

  /* ---------- poll while the worker is busy with something on this canvas ---------- */
  const polling = loaded && needsPolling(items.values());
  useEffect(() => {
    if (!polling) return;
    // The worker normally finishes in seconds; stop after ~2 minutes so a stuck job can't poll forever.
    let ticks = 0;
    const t = window.setInterval(async () => {
      if (++ticks > 48) return window.clearInterval(t);
      if (document.hidden || inFlight.current) return;
      try {
        const server = await fetchAllItems(canvasId);
        setItems((prev) => {
          const next = new Map<string, Item>();
          for (const s of server) {
            if (removed.current.has(s.id)) continue;
            const local = prev.get(s.id);
            next.set(s.id, local && (pending.current.has(s.id) || local.version >= s.version) ? { ...local,
              // Server-owned fields always come from the server, including the summary written after indexing.
              safety_state: s.safety_state, safety_categories: s.safety_categories, index_state: s.index_state,
              ai: s.ai } as Item : s);
          }
          return next;
        });
      } catch {
        /* next tick */
      }
    }, 2500);
    return () => window.clearInterval(t);
  }, [polling, canvasId]);

  /* ---------- don't lose edits on close ---------- */
  useEffect(() => {
    const onHide = () => {
      if (!pending.current.size) return;
      const body = JSON.stringify({
        items: [...pending.current].map(([id, p]) => ({ id, version: itemsRef.current.get(id)?.version ?? 1, ...p })),
      });
      fetch(`/api/v1/canvases/${canvasId}/items`, {
        method: "PATCH", body, keepalive: true, credentials: "same-origin", headers: { "Content-Type": "application/json" },
      }).catch(() => {});
      pending.current.clear();
    };
    // Tab hidden: the page is still alive, so save normally and keep versions in step.
    const onVisibility = () => document.visibilityState === "hidden" && void flush();
    window.addEventListener("pagehide", onHide);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      onHide();
      window.removeEventListener("pagehide", onHide);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [canvasId, flush]);

  useEffect(() => {
    const onBefore = (e: BeforeUnloadEvent) => {
      if (inFlight.current) e.preventDefault();
    };
    window.addEventListener("beforeunload", onBefore);
    return () => window.removeEventListener("beforeunload", onBefore);
  }, []);

  /** The latest local copy of a card, without waiting for a render. */
  const current = useCallback((id: string) => itemsRef.current.get(id), []);

  return { items, loaded, loadError, status, update, create, remove, upsert, flush, current };
}
