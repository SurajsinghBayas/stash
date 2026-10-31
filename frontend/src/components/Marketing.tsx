import { Moon02Icon, Sun03Icon } from "@hugeicons/core-free-icons";
import { useEffect, type ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { useMe } from "@/lib/queries";
import { useSeo } from "@/lib/seo";
import { FOOTER_LINKS, SITE } from "@/lib/site";
import { setMode, useMode } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { Mascot } from "./Mascot";
import { Button } from "./ui/button";
import { Icon } from "./ui/primitives";

const NAV = [
  { label: "Features", to: "/#features" },
  { label: "How it works", to: "/#how-it-works" },
  { label: "FAQ", to: "/#faq" },
];

/** Scroll to `#section` after a route change (React Router doesn't do this for us). */
function useHashScroll() {
  const { hash, pathname } = useLocation();
  useEffect(() => {
    if (!hash) {
      window.scrollTo({ top: 0 });
      return;
    }
    const el = document.getElementById(decodeURIComponent(hash.slice(1)));
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [hash, pathname]);
}

export function MarketingHeader() {
  const me = useMe();
  const signedIn = !!me.data;
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1120px] items-center gap-6 px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2 text-[16px] font-semibold tracking-[-0.02em]" aria-label="Stash home">
          <Mascot size={28} /> Stash
        </Link>
        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          {NAV.map((n) => (
            <Link key={n.to} to={n.to} className="rounded-md px-2.5 py-1.5 text-[13.5px] text-text-2 transition-colors hover:bg-surface-2 hover:text-text">
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {signedIn ? (
            <Button asChild variant="primary" size="sm"><Link to="/app">Open Stash</Link></Button>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm"><Link to="/login">Sign in</Link></Button>
              <Button asChild variant="primary" size="sm"><Link to="/signup">Get started</Link></Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

function ThemeToggle() {
  const mode = useMode();
  const next = mode === "dark" ? "light" : "dark";
  return (
    <button onClick={() => setMode(next)} aria-label={`Switch to ${next} mode`}
      className="inline-flex items-center gap-2 rounded-md border border-border px-2.5 py-1.5 text-[12.5px] text-text-2 transition-colors hover:bg-surface-2 hover:text-text">
      <Icon icon={mode === "dark" ? Sun03Icon : Moon02Icon} size={14} />
      {mode === "dark" ? "Light" : "Dark"} mode
    </button>
  );
}

/** The full footer on public pages. `compact` is the one-line version for signed-in pages. */
export function SiteFooter({ compact = false }: { compact?: boolean }) {
  const year = new Date().getFullYear();
  if (compact) {
    return (
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 px-4 py-5 text-[12.5px] text-text-3 sm:px-6">
          <span>© {year} {SITE.name}</span>
          <nav className="flex flex-wrap gap-4" aria-label="Footer">
            <Link to="/" className="hover:text-text">Home</Link>
            <Link to="/about" className="hover:text-text">About</Link>
            <Link to="/contact" className="hover:text-text">Contact</Link>
            <Link to="/privacy" className="hover:text-text">Privacy</Link>
            <Link to="/terms" className="hover:text-text">Terms</Link>
          </nav>
        </div>
      </footer>
    );
  }
  return (
    <footer className="border-t border-border bg-surface/40">
      <div className="mx-auto grid max-w-[1120px] grid-cols-3 gap-x-6 gap-y-10 px-4 py-14 sm:px-6 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div className="col-span-3 md:col-span-1">
          <Link to="/" className="flex items-center gap-2 text-[15px] font-semibold tracking-[-0.02em]">
            <Mascot size={26} state="sleeping" /> Stash
          </Link>
          <p className="mt-3 max-w-[30ch] text-[13.5px] leading-relaxed text-text-2">
            One canvas for everything you save, and an assistant that finds it again.
          </p>
          <div className="mt-5"><ThemeToggle /></div>
        </div>
        {FOOTER_LINKS.map((group) => (
          <nav key={group.title} aria-label={group.title}>
            <h2 className="text-[12.5px] font-semibold uppercase tracking-[0.06em] text-text-3">{group.title}</h2>
            <ul className="mt-3 grid gap-2">
              {group.links.map((l) => (
                <li key={l.to}>
                  <Link to={l.to} className="text-[13.5px] text-text-2 transition-colors hover:text-text">{l.label}</Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="border-t border-border">
        <div className="mx-auto flex max-w-[1120px] flex-wrap items-center justify-between gap-3 px-4 py-5 text-[12.5px] text-text-3 sm:px-6">
          <span>© {year} {SITE.name}. All rights reserved.</span>
          <span>Made for people who save too many tabs.</span>
        </div>
      </div>
    </footer>
  );
}

export function MarketingLayout({ children }: { children: ReactNode }) {
  useHashScroll();
  return (
    <div className="flex min-h-dvh flex-col overflow-x-clip">
      <MarketingHeader />
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </div>
  );
}

/** Title block + readable column for About, Privacy, Terms and Contact. */
export function PageShell({ eyebrow, title, lead, children, className, seo }: {
  eyebrow?: string; title: string; lead?: ReactNode; children: ReactNode; className?: string;
  /** Search title, description and path for this page. */
  seo: { title: string; description: string; path: string };
}) {
  useSeo(seo);
  return (
    <MarketingLayout>
      <div className={cn("mx-auto max-w-[760px] px-4 pb-24 pt-14 sm:px-6 sm:pt-20", className)}>
        {eyebrow && <p className="text-[12.5px] font-semibold uppercase tracking-[0.08em] text-accent-text">{eyebrow}</p>}
        <h1 className="mt-3 text-[34px] font-semibold leading-[1.1] tracking-[-0.03em] sm:text-[44px]">{title}</h1>
        {lead && <div className="mt-4 text-[16px] leading-relaxed text-text-2">{lead}</div>}
        <div className="mt-10">{children}</div>
      </div>
    </MarketingLayout>
  );
}
