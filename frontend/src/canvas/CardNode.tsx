import {
  Clock01Icon,
  Copy01Icon,
  Delete02Icon,
  Edit02Icon,
  LinkSquare02Icon,
  WorkHistoryIcon,
  TextFontIcon,
} from "@hugeicons/core-free-icons";
import { NodeResizeControl, NodeResizer, NodeToolbar, Position, type Node, type NodeProps } from "@xyflow/react";
import { createContext, memo, useContext, type ReactNode } from "react";
import { toast } from "sonner";
import { Icon, Tip } from "@/components/ui/primitives";
import type { Item, NoteColor, TextContent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { CodeCard, FlaggedBadge, ImageCard, LinkCard, NoteCard, TextCard } from "./cards";
import { NOTE_COLORS, noteStyle } from "./kinds";
import type { Patch } from "./useItemSync";

export type CardData = { item: Item; hit?: number };
export type CardNodeType = Node<CardData, "card">;

export interface CanvasActions {
  editingId: string | null;
  setEditing: (id: string | null) => void;
  update: (id: string, patch: Patch) => void;
  remove: (ids: string[]) => void;
  remind: (item: Item) => void;
  openImage: (item: Item) => void;
  history: (item: Item) => void;
  singleSelection: boolean;
}

const Ctx = createContext<CanvasActions | null>(null);
export const CanvasActionsProvider = Ctx.Provider;
function useActions() {
  const v = useContext(Ctx);
  if (!v) throw new Error("CanvasActionsProvider missing");
  return v;
}

/** Cards whose height follows their content; only their width is resizable. */
const AUTO_HEIGHT = new Set<Item["kind"]>(["link", "text", "image"]);
const MIN_W: Record<Item["kind"], number> = { link: 220, note: 160, text: 80, code: 260, image: 140 };

function ToolButton({ label, icon, onClick, danger, children }: {
  label: string; icon?: Parameters<typeof Icon>[0]["icon"]; onClick: () => void; danger?: boolean; children?: ReactNode;
}) {
  return (
    <Tip label={label}>
      <button aria-label={label} onClick={onClick}
        className={cn("grid size-8 place-items-center rounded-[8px] text-text-2 transition-colors hover:bg-surface-2 hover:text-text",
          danger && "hover:bg-danger-soft hover:text-danger")}>
        {icon ? <Icon icon={icon} size={16} /> : children}
      </button>
    </Tip>
  );
}

function plainText(item: Item): string {
  switch (item.kind) {
    case "link": return item.content.url;
    case "note": return item.content.markdown;
    case "text": return item.content.text;
    case "code": return item.content.source;
    case "image": return item.content.caption;
  }
}

const TEXT_SIZES: TextContent["size"][] = ["s", "m", "l", "xl"];

function CardNodeImpl({ id, data, selected }: NodeProps<CardNodeType>) {
  const a = useActions();
  const { item, hit } = data;
  const editing = a.editingId === id;
  const onChange = (content: Record<string, unknown>) => {
    const changed = Object.entries(content).some(([k, v]) => (item.content as unknown as Record<string, unknown>)[k] !== v);
    if (changed) a.update(id, { content });
  };
  const onDone = () => a.setEditing(null);
  const auto = AUTO_HEIGHT.has(item.kind);
  const isText = item.kind === "text";
  const flagged = item.safety_state === "flagged";

  const shell = cn(
    "card relative h-full rounded-[14px]",
    isText ? "rounded-[8px]" : "border border-border bg-surface shadow-sm",
    hit !== undefined && "is-hit",
  );

  let body: ReactNode;
  switch (item.kind) {
    case "link": body = <LinkCard item={item} editing={editing} onChange={onChange} onDone={onDone} />; break;
    case "note": body = <NoteCard item={item} editing={editing} onChange={onChange} onDone={onDone} />; break;
    case "text": body = <TextCard item={item} editing={editing} onChange={onChange} onDone={onDone} />; break;
    case "code": body = <CodeCard item={item} editing={editing} onChange={onChange} onDone={onDone} />; break;
    case "image":
      body = <ImageCard item={item} editing={editing} onChange={onChange} onDone={onDone} onOpen={() => a.openImage(item)} />;
      break;
  }

  return (
    <>
      {auto ? (
        selected && !editing && (
          <NodeResizeControl position="right" minWidth={MIN_W[item.kind]} maxWidth={1600}
            onResizeEnd={(_, p) => a.update(id, { w: Math.round(p.width) })}
            style={{ background: "transparent", border: "none", width: 12, height: "100%", cursor: "ew-resize" }}>
            <span className="absolute right-[-3px] top-1/2 h-8 w-[5px] -translate-y-1/2 rounded-full bg-accent" />
          </NodeResizeControl>
        )
      ) : (
        <NodeResizer isVisible={selected && !editing} minWidth={MIN_W[item.kind]} minHeight={100}
          onResizeEnd={(_, p) => a.update(id, { x: Math.round(p.x), y: Math.round(p.y), w: Math.round(p.width), h: Math.round(p.height) })} />
      )}

      <NodeToolbar isVisible={selected && a.singleSelection && !editing} position={Position.Top} offset={10}>
        <div className="flex items-center gap-0.5 rounded-[10px] border border-border bg-surface p-1 shadow-md">
          {item.kind !== "image" || item.content.upload_state === "ready" ? (
            <ToolButton label={item.kind === "link" ? "Add a comment" : item.kind === "image" ? "Edit caption" : "Edit"}
              icon={Edit02Icon} onClick={() => a.setEditing(id)} />
          ) : null}
          {item.kind === "note" && (
            <div className="mx-1 flex items-center gap-1" role="radiogroup" aria-label="Note colour">
              {NOTE_COLORS.map((c: NoteColor) => (
                <button key={c} role="radio" aria-checked={item.content.color === c} aria-label={c}
                  onClick={() => a.update(id, { content: { color: c } })}
                  className={cn("size-[18px] rounded-full border border-border-strong transition-transform hover:scale-110",
                    item.content.color === c && "ring-2 ring-accent ring-offset-1 ring-offset-surface")}
                  style={{ background: noteStyle(c).background as string }} />
              ))}
            </div>
          )}
          {isText && (
            <ToolButton label="Text size" onClick={() => {
              const s = item.content.size;
              a.update(id, { content: { size: TEXT_SIZES[(TEXT_SIZES.indexOf(s) + 1) % TEXT_SIZES.length] } });
            }}>
              <span className="flex items-center gap-0.5 text-[12px] font-semibold">
                <Icon icon={TextFontIcon} size={14} />{item.content.size.toUpperCase()}
              </span>
            </ToolButton>
          )}
          {item.kind === "link" && (
            <ToolButton label="Open link" icon={LinkSquare02Icon}
              onClick={() => {
                // The API only stores http(s) links; check again here so no other scheme can ever be opened.
                if (/^https?:\/\//i.test(item.content.url)) window.open(item.content.url, "_blank", "noopener,noreferrer");
              }} />
          )}
          <ToolButton label="Remind me" icon={Clock01Icon} onClick={() => a.remind(item)} />
          <ToolButton label="History" icon={WorkHistoryIcon} onClick={() => a.history(item)} />
          <ToolButton label="Copy" icon={Copy01Icon}
            onClick={() => navigator.clipboard.writeText(plainText(item)).then(() => toast.success("Copied"))} />
          <span className="mx-0.5 h-5 w-px bg-border" />
          <ToolButton label="Delete" icon={Delete02Icon} danger onClick={() => a.remove([id])} />
        </div>
      </NodeToolbar>

      <div className={shell} style={item.kind === "note" ? noteStyle(item.content.color) : undefined}
        data-kind={item.kind}>
        {hit !== undefined && (
          <span className="absolute -left-2.5 -top-2.5 z-[2] grid size-6 place-items-center rounded-full bg-accent
            text-[12px] font-semibold text-accent-fg shadow-md tabular">{hit}</span>
        )}
        {flagged && <FlaggedBadge />}
        {body}
      </div>
    </>
  );
}

export const CardNode = memo(CardNodeImpl);
export const nodeTypes = { card: CardNode };
