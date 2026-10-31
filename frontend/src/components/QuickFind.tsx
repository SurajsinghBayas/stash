import { Search01Icon } from "@hugeicons/core-free-icons";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { quickFind } from "@/lib/queries";
import type { Hit } from "@/lib/types";
import { cn } from "@/lib/utils";
import { KindIcon } from "@/canvas/kinds";
import { Mascot } from "./Mascot";
import { Icon, Kbd } from "./ui/primitives";

/** ⌘K: keyword search across every canvas. Runs in the database only; nothing is sent to AI. */
export function QuickFind({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!open) {
      setQ("");
      setHits([]);
    }
  }, [open]);

  useEffect(() => {
    const term = q.trim();
    if (!term) return setHits([]);
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        setHits(await quickFind(term, ctrl.signal));
        setActive(0);
      } catch {
        /* aborted or offline: keep the last results */
      } finally {
        setLoading(false);
      }
    }, 140);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [q]);

  function go(hit: Hit) {
    onOpenChange(false);
    navigate(`/c/${hit.canvas_id}?item=${hit.item_id}`);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, hits.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && hits[active]) {
      e.preventDefault();
      go(hits[active]);
    }
  }

  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[60] bg-black/40 data-[state=open]:animate-[fade-in_160ms_var(--ease-out)]" />
        <DialogPrimitive.Content aria-describedby={undefined}
          className="fixed left-1/2 top-[12vh] z-[60] w-[calc(100vw-32px)] max-w-[600px] -translate-x-1/2 overflow-hidden
            rounded-xl border border-border bg-surface shadow-lg outline-none data-[state=open]:animate-[pop_180ms_var(--ease-out)]">
          <DialogPrimitive.Title className="sr-only">Find a card</DialogPrimitive.Title>
          <div className="flex items-center gap-3 border-b border-border px-4">
            <Icon icon={Search01Icon} size={18} className="text-text-3" />
            <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKeyDown}
              placeholder="Find a card by any word in it…" aria-label="Search your cards"
              role="combobox" aria-expanded={hits.length > 0} aria-controls="quickfind-list"
              aria-activedescendant={hits[active] ? `qf-${hits[active].item_id}` : undefined}
              className="h-14 flex-1 bg-transparent text-[15px] outline-none placeholder:text-text-3" />
            <Kbd>Esc</Kbd>
          </div>
          <ul ref={listRef} id="quickfind-list" role="listbox" className="max-h-[50vh] overflow-y-auto p-1.5">
            {hits.map((h, i) => (
              <li key={h.item_id} id={`qf-${h.item_id}`} role="option" aria-selected={i === active} data-index={i}
                onMouseMove={() => setActive(i)} onClick={() => go(h)}
                className={cn("flex cursor-default items-start gap-3 rounded-lg px-3 py-2.5", i === active && "bg-surface-2")}>
                <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-md bg-surface-3 text-text-2">
                  <KindIcon kind={h.kind} size={15} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[14px] font-medium">{h.title}</span>
                  {h.snippet && <span className="block truncate text-[12.5px] text-text-2">{h.snippet}</span>}
                </span>
                <span className="mt-0.5 max-w-[30%] truncate text-[12px] text-text-3">{h.canvas_title}</span>
              </li>
            ))}
          </ul>
          {q.trim() && !loading && hits.length === 0 && (
            <div className="flex flex-col items-center gap-2 px-4 pb-8 pt-4 text-center text-[13.5px] text-text-2">
              <Mascot state="sleeping" size={36} />
              No card has “{q.trim()}”. Try another word.
            </div>
          )}
          {!q.trim() && (
            <p className="px-5 pb-4 pt-1 text-[12.5px] text-text-3">
              Searches titles, notes, code and link text on every canvas. ↑↓ to move, Enter to open.
            </p>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
