import {
  AiChat02Icon,
  Clock01Icon,
  Link01Icon,
  Mail01Icon,
  Shield01Icon,
  SourceCodeIcon,
} from "@hugeicons/core-free-icons";
import { Link } from "react-router";
import { Mascot } from "@/components/Mascot";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/primitives";
import { useMe } from "@/lib/queries";

/** A still of the product, built from the same styles as the real cards. */
function ProductPreview() {
  return (
    <div className="relative overflow-hidden rounded-[18px] border border-border bg-canvas shadow-lg" aria-hidden="true"
      style={{ backgroundImage: "radial-gradient(var(--canvas-dot) 1.2px, transparent 1.2px)", backgroundSize: "22px 22px" }}>
      <div className="flex h-10 items-center gap-2 border-b border-border bg-bg/80 px-4 text-[12.5px] text-text-2">
        <span className="flex gap-1.5"><i className="size-2.5 rounded-full bg-surface-3" /><i className="size-2.5 rounded-full bg-surface-3" /><i className="size-2.5 rounded-full bg-surface-3" /></span>
        <span className="ml-2 font-medium text-text">Launch prep</span>
      </div>
      <div className="relative h-[420px] sm:h-[460px]">
        {/* link */}
        <div className="absolute left-[4%] top-[8%] w-[240px] rounded-[14px] border border-border bg-surface shadow-sm">
          <div className="aspect-[1.91] rounded-t-[13px] bg-[linear-gradient(135deg,#1d2b12,#0f1a24)]" />
          <div className="p-3">
            <p className="text-[11.5px] text-text-3">stripe.com</p>
            <p className="mt-0.5 text-[13px] font-medium leading-snug">Pricing page patterns that convert</p>
          </div>
        </div>
        {/* note, cited */}
        <div className="card is-hit absolute left-[38%] top-[14%] w-[210px] rounded-[14px] p-3.5 text-[13px] leading-snug"
          style={{ background: "var(--note-yellow)", color: "var(--note-yellow-ink)" }}>
          <span className="absolute -left-2.5 -top-2.5 grid size-6 place-items-center rounded-full bg-accent text-[12px] font-semibold text-accent-fg">1</span>
          <p className="font-semibold">Launch</p>
          <p className="mt-1">Friday 14 Nov, right after the pricing review. Pro at $8/mo.</p>
        </div>
        {/* code */}
        <div className="absolute left-[8%] top-[58%] hidden w-[300px] rounded-[14px] border border-border bg-surface shadow-sm sm:block">
          <div className="flex h-8 items-center gap-2 border-b border-border px-3 font-mono text-[11.5px] text-text-3">
            <Icon icon={SourceCodeIcon} size={13} /> flags.ts
          </div>
          <pre className="p-3 font-mono text-[11.5px] leading-relaxed text-text-2">
            <span className="text-[#ff9eb0]">export const</span> launch = {"{"}{"\n"}  pricingV2: <span className="text-accent-text">true</span>,{"\n"}  waitlist: <span className="text-accent-text">false</span>,{"\n"}{"}"}
          </pre>
        </div>
        {/* text */}
        <p className="absolute left-[42%] top-[60%] hidden text-[26px] font-medium tracking-[-0.015em] text-text sm:block">Ship it.</p>

        {/* chat */}
        <div className="absolute bottom-4 right-4 top-4 hidden w-[300px] flex-col rounded-[14px] border border-border bg-surface shadow-lg md:flex">
          <div className="flex items-center gap-2.5 border-b border-border px-3.5 py-3">
            <Mascot state="found" size={26} />
            <span className="text-[13px] font-semibold">Ask Stash</span>
          </div>
          <div className="flex flex-1 flex-col justify-end gap-3 p-3.5">
            <p className="ml-8 rounded-[12px] rounded-br-[4px] bg-surface-3 px-3 py-2 text-[13px]">When do we launch?</p>
            <p className="text-[13px] leading-relaxed">
              Friday 14 November, right after the pricing review
              <span className="mx-0.5 inline-grid size-[17px] place-items-center rounded-full bg-accent-soft align-middle text-[10.5px] font-semibold text-accent-text">1</span>.
            </p>
            <div className="flex items-center gap-2 rounded-md border border-border px-2.5 py-2 text-[12.5px]">
              <span className="grid size-5 place-items-center rounded-full bg-accent-soft text-[10.5px] font-semibold text-accent-text">1</span>
              Launch
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const FEATURES = [
  {
    icon: Link01Icon,
    title: "Save anything",
    body: "Paste a link and it becomes a card with its title and image. Notes, code and screenshots sit next to it, wherever you put them.",
  },
  {
    icon: AiChat02Icon,
    title: "Ask, and it points",
    body: "Ask a question in plain words. Stash answers only from your cards and shows you exactly which ones, right on the canvas.",
  },
  {
    icon: Clock01Icon,
    title: "Never lose the thread",
    body: "Set a reminder on any card and it lands in your inbox on time. A daily and weekly digest sums up what you noted.",
  },
];

export function Landing() {
  const me = useMe();
  const signedIn = !!me.data;

  return (
    <div className="min-h-dvh overflow-x-clip">
      <header className="mx-auto flex h-16 max-w-[1120px] items-center justify-between px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2 text-[16px] font-semibold tracking-[-0.02em]">
          <Mascot size={28} /> Stash
        </Link>
        <nav className="flex items-center gap-2">
          {signedIn ? (
            <Button asChild variant="primary" size="sm"><Link to="/app">Open Stash</Link></Button>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm"><Link to="/login">Sign in</Link></Button>
              <Button asChild variant="primary" size="sm"><Link to="/signup">Get started</Link></Button>
            </>
          )}
        </nav>
      </header>

      <main>
        <section className="mx-auto max-w-[1120px] px-4 pb-16 pt-14 sm:px-6 sm:pt-20">
          <div className="flex flex-col items-start gap-10 md:flex-row md:items-end md:justify-between">
            <div className="max-w-[640px] animate-[rise_420ms_var(--ease-out)]">
              <p className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-[12.5px] text-text-2">
                <span className="size-1.5 rounded-full bg-accent" /> A canvas that remembers for you
              </p>
              <h1 className="mt-5 text-[40px] font-semibold leading-[1.04] tracking-[-0.035em] sm:text-[60px]">
                Everything you save, on one canvas.
              </h1>
              <p className="mt-5 max-w-[52ch] text-[16px] leading-relaxed text-text-2 sm:text-[17px]">
                Drop in links, notes, code and images. Stash keeps an eye on all of it, finds the right card when you ask,
                and nudges you by email when it matters.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Button asChild variant="primary" size="lg">
                  <Link to={signedIn ? "/app" : "/signup"}>{signedIn ? "Open your canvases" : "Start for free"}</Link>
                </Button>
                {!signedIn && <Button asChild variant="secondary" size="lg"><Link to="/login">Sign in</Link></Button>}
              </div>
            </div>
            <div className="hidden md:block">
              <Mascot size={148} follow label="Stash, the mascot, watching your pointer" />
            </div>
          </div>
          <div className="mt-14 animate-[rise_620ms_var(--ease-out)]">
            <ProductPreview />
          </div>
        </section>

        <section className="mx-auto grid max-w-[1120px] gap-4 px-4 pb-20 sm:px-6 md:grid-cols-3">
          {FEATURES.map((f) => (
            <article key={f.title} className="rounded-[16px] border border-border bg-surface p-6">
              <span className="grid size-9 place-items-center rounded-[10px] bg-accent-soft text-accent-text">
                <Icon icon={f.icon} size={18} />
              </span>
              <h2 className="mt-4 text-[16px] font-semibold tracking-[-0.01em]">{f.title}</h2>
              <p className="mt-1.5 text-[14px] leading-relaxed text-text-2">{f.body}</p>
            </article>
          ))}
        </section>

        <section className="mx-auto max-w-[1120px] px-4 pb-24 sm:px-6">
          <div className="grid gap-8 rounded-[20px] border border-border bg-surface p-8 sm:p-10 md:grid-cols-[1fr_auto] md:items-center">
            <div className="flex gap-4">
              <span className="grid size-10 shrink-0 place-items-center rounded-[10px] bg-surface-3"><Icon icon={Shield01Icon} size={20} /></span>
              <div>
                <h2 className="text-[17px] font-semibold tracking-[-0.01em]">Safe by default</h2>
                <p className="mt-1.5 max-w-[60ch] text-[14px] leading-relaxed text-text-2">
                  Every card, question and answer passes a safety check. Adult or abusive content is never sent to the AI,
                  never shown in previews and never put in an email. Your cards are yours alone.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 text-[13px] text-text-2">
              <Icon icon={Mail01Icon} size={16} /> Digests you can turn off in one click
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-[1120px] flex-wrap items-center justify-between gap-4 px-4 py-8 text-[13px] text-text-3 sm:px-6">
          <span className="flex items-center gap-2"><Mascot size={20} state="sleeping" /> Stash</span>
          <span>Made for people who save too many tabs.</span>
        </div>
      </footer>
    </div>
  );
}
