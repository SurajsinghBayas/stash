import { Image01Icon, Link01Icon, Note01Icon, SourceCodeIcon, TextFontIcon } from "@hugeicons/core-free-icons";
import type { IconSvgElement } from "@hugeicons/react";
import { Icon } from "@/components/ui/primitives";
import type { Kind, NoteColor } from "@/lib/types";

export const KIND_ICON: Record<Kind, IconSvgElement> = {
  link: Link01Icon,
  note: Note01Icon,
  text: TextFontIcon,
  code: SourceCodeIcon,
  image: Image01Icon,
};

export const KIND_LABEL: Record<Kind, string> = { link: "Link", note: "Note", text: "Text", code: "Code", image: "Image" };

export function KindIcon({ kind, size = 16, className }: { kind: Kind; size?: number; className?: string }) {
  return <Icon icon={KIND_ICON[kind]} size={size} className={className} />;
}

export const NOTE_COLORS: NoteColor[] = ["yellow", "blue", "green", "pink", "plain"];

export function noteStyle(color: NoteColor | null | undefined): React.CSSProperties {
  if (!color || color === "plain") return { background: "var(--surface)", color: "var(--text)" };
  return { background: `var(--note-${color})`, color: `var(--note-${color}-ink)` };
}

/** Default sizes for new cards, in canvas units. */
export const DEFAULT_SIZE: Record<Kind, { w: number; h: number | null }> = {
  link: { w: 300, h: null },
  note: { w: 240, h: 200 },
  text: { w: 320, h: null },
  code: { w: 420, h: 240 },
  image: { w: 260, h: null },
};
