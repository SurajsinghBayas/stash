import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

export type MascotState = "idle" | "searching" | "found" | "checking" | "blocked" | "sleeping";

/**
 * Stash, the box that keeps an eye on things. Same drawing and states as style-guide.html.
 * `follow` makes the eyes track the pointer while idle.
 */
export function Mascot({ state = "idle", size = 40, follow = false, className, label }: {
  state?: MascotState; size?: number; follow?: boolean; className?: string; label?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!follow || state !== "idle") return;
    const el = ref.current;
    const pupils = el?.querySelector<SVGGElement>(".m-pupils");
    if (!el || !pupils) return;
    let frame = 0;
    const onMove = (e: PointerEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect();
        if (r.bottom < 0 || r.top > innerHeight) return;
        const dx = e.clientX - (r.left + r.width / 2);
        const dy = e.clientY - (r.top + r.height * 0.58);
        const d = Math.hypot(dx, dy) || 1;
        const k = Math.min(1, d / 220) * 3;
        pupils.style.transform = `translate(${((dx / d) * k).toFixed(2)}px, ${((dy / d) * k * 0.8).toFixed(2)}px)`;
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", onMove);
      pupils.style.transform = "";
    };
  }, [follow, state]);

  return (
    <span ref={ref} className={cn("mascot", className)} data-state={state} style={{ width: size, height: size }}
      role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <svg viewBox="0 0 64 64">
        <g className="m-lid">
          <rect x="6" y="13" width="52" height="10" rx="4" fill="var(--m-lid)" stroke="var(--m-ink)" strokeWidth="2.5" />
        </g>
        <rect x="9" y="21" width="46" height="36" rx="11" fill="var(--m-body)" stroke="var(--m-ink)" strokeWidth="2.5" />
        <path d="M22 50.5h20" stroke="var(--m-ink)" strokeWidth="2.5" strokeLinecap="round" opacity=".18" />
        <g className="m-open">
          <ellipse className="m-eyeball" cx="24" cy="37" rx="7" ry="7.5" fill="var(--m-eye)" stroke="var(--m-ink)" strokeWidth="2.5" />
          <ellipse className="m-eyeball" cx="40" cy="37" rx="7" ry="7.5" fill="var(--m-eye)" stroke="var(--m-ink)" strokeWidth="2.5" />
          <g className="m-pupils">
            <circle cx="24" cy="37" r="3.3" fill="var(--m-ink)" />
            <circle cx="40" cy="37" r="3.3" fill="var(--m-ink)" />
            <circle cx="25.3" cy="35.6" r="1" fill="var(--m-eye)" />
            <circle cx="41.3" cy="35.6" r="1" fill="var(--m-eye)" />
          </g>
        </g>
        <g className="m-happy" fill="none" stroke="var(--m-ink)" strokeWidth="2.75" strokeLinecap="round">
          <path d="M18 39.5q6-7 12 0" /><path d="M34 39.5q6-7 12 0" />
        </g>
        <g className="m-flat" fill="none" stroke="var(--m-ink)" strokeWidth="2.75" strokeLinecap="round">
          <path d="M18 37.5h12" /><path d="M34 37.5h12" />
        </g>
        <g className="m-closed" fill="none" stroke="var(--m-ink)" strokeWidth="2.75" strokeLinecap="round">
          <path d="M18 36q6 6 12 0" /><path d="M34 36q6 6 12 0" />
        </g>
      </svg>
    </span>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-[15px] font-semibold tracking-[-0.02em]", className)}>
      <Mascot size={26} />
      Stash
    </span>
  );
}
