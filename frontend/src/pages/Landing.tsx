import {
  AiChat02Icon,
  ArrowRight01Icon,
  Brain01Icon,
  Clock01Icon,
  CloudUploadIcon,
  CodeSquareIcon,
  Cursor01Icon,
  Image01Icon,
  Link01Icon,
  LockKeyIcon,
  Mail01Icon,
  Moon02Icon,
  Mortarboard02Icon,
  NoteIcon,
  Rocket01Icon,
  Search01Icon,
  Shield01Icon,
  SourceCodeIcon,
  SparklesIcon,
  TextFontIcon,
  Tick02Icon,
} from "@hugeicons/core-free-icons";
import { useEffect, type ReactNode } from "react";
import { Link } from "react-router";
import { MarketingLayout } from "@/components/Marketing";
import { Mascot } from "@/components/Mascot";
import { Button } from "@/components/ui/button";
import { Icon, Kbd } from "@/components/ui/primitives";
import { useMe } from "@/lib/queries";
import { modKey } from "@/lib/utils";

type IconType = typeof Link01Icon;

/** A still of the product, built from the same styles as the real cards. */
function ProductPreview() {
  return (
    <div className="relative overflow-hidden rounded-[18px] border border-border bg-canvas shadow-lg" aria-hidden="true"
      style={{ backgroundImage: "radial-gradient(var(--canvas-dot) 1.2px, transparent 1.2px)", backgroundSize: "22px 22px" }}>
      <div className="flex h-10 items-center gap-2 border-b border-border bg-bg/80 px-4 text-[12.5px] text-text-2">
        <span className="flex gap-1.5"><i className="size-2.5 rounded-full bg-surface-3" /><i className="size-2.5 rounded-full bg-surface-3" /><i className="size-2.5 rounded-full bg-surface-3" /></span>
        <span className="ml-2 font-medium text-text">Launch prep</span>
      </div>
      <div className="relative h-[300px] sm:h-[460px]">
        <div className="absolute left-[4%] top-[8%] w-[240px] rounded-[14px] border border-border bg-surface shadow-sm">
          <div className="aspect-[1.91] rounded-t-[13px] bg-[linear-gradient(135deg,#1d2b12,#0f1a24)]" />
          <div className="p-3">
            <p className="text-[11.5px] text-text-3">stripe.com</p>
            <p className="mt-0.5 text-[13px] font-medium leading-snug">Pricing page patterns that convert</p>
          </div>
        </div>
        <div className="card is-hit absolute left-[38%] top-[14%] w-[210px] rounded-[14px] p-3.5 text-[13px] leading-snug"
          style={{ background: "var(--note-yellow)", color: "var(--note-yellow-ink)" }}>
          <span className="absolute -left-2.5 -top-2.5 grid size-6 place-items-center rounded-full bg-accent text-[12px] font-semibold text-accent-fg">1</span>
          <p className="font-semibold">Launch</p>
          <p className="mt-1">Friday 14 Nov, right after the pricing review. Pro at $8/mo.</p>
        </div>
        <div className="absolute left-[8%] top-[58%] hidden w-[300px] rounded-[14px] border border-border bg-surface shadow-sm sm:block">
          <div className="flex h-8 items-center gap-2 border-b border-border px-3 font-mono text-[11.5px] text-text-3">
            <Icon icon={SourceCodeIcon} size={13} /> flags.ts
          </div>
          <pre className="p-3 font-mono text-[11.5px] leading-relaxed text-text-2">
            <span className="text-[#ff9eb0]">export const</span> launch = {"{"}{"\n"}  pricingV2: <span className="text-accent-text">true</span>,{"\n"}  waitlist: <span className="text-accent-text">false</span>,{"\n"}{"}"}
          </pre>
        </div>
        <p className="absolute left-[42%] top-[60%] hidden text-[26px] font-medium tracking-[-0.015em] text-text sm:block">Ship it.</p>

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

function SectionHead({ eyebrow, title, lead, center = false }: { eyebrow: string; title: string; lead?: string; center?: boolean }) {
  return (
    <div className={center ? "mx-auto max-w-[640px] text-center" : "max-w-[640px]"}>
      <p className="text-[12.5px] font-semibold uppercase tracking-[0.08em] text-accent-text">{eyebrow}</p>
      <h2 className="mt-3 text-[30px] font-semibold leading-[1.1] tracking-[-0.03em] sm:text-[38px]">{title}</h2>
      {lead && <p className="mt-4 text-[16px] leading-relaxed text-text-2">{lead}</p>}
    </div>
  );
}

function IconChip({ icon }: { icon: IconType }) {
  return (
    <span className="grid size-9 shrink-0 place-items-center rounded-[10px] bg-accent-soft text-accent-text">
      <Icon icon={icon} size={18} />
    </span>
  );
}

const CARD_TYPES: { icon: IconType; label: string }[] = [
  { icon: Link01Icon, label: "Links" },
  { icon: NoteIcon, label: "Notes" },
  { icon: TextFontIcon, label: "Text" },
  { icon: CodeSquareIcon, label: "Code" },
  { icon: Image01Icon, label: "Images" },
];

const STEPS = [
  { n: "1", title: "Drop it in", body: "Paste a link, type a note, drop in a screenshot or a code snippet. It lands on your canvas as a card in a second." },
  { n: "2", title: "Lay it out your way", body: "Drag cards around, group what belongs together and keep one canvas per project, trip, course or idea." },
  { n: "3", title: "Ask, and get reminded", body: "Ask a question and Stash answers from your cards, pointing at each one. Set a reminder and it reaches your inbox on time." },
];

/* ---------- small visuals for the feature rows ---------- */

function CardsVisual() {
  return (
    <div className="relative h-[360px]" aria-hidden="true">
      <div className="absolute left-0 top-[4%] w-[55%] rotate-[-2deg] rounded-[14px] border border-border bg-surface p-3 shadow-md">
        <div className="aspect-[2.6] rounded-[9px] bg-[linear-gradient(135deg,#22301a,#13202c)]" />
        <p className="mt-2 text-[11.5px] text-text-3">nngroup.com</p>
        <p className="text-[13px] font-medium leading-snug">10 usability heuristics for interface design</p>
      </div>
      <div className="absolute right-0 top-0 w-[40%] rotate-[3deg] rounded-[14px] p-3 text-[12.5px] leading-snug shadow-md"
        style={{ background: "var(--note-green)", color: "var(--note-green-ink)" }}>
        <p className="font-semibold">Interview notes</p>
        <p className="mt-1">Users want search that understands what they meant.</p>
      </div>
      <div className="absolute bottom-0 left-[6%] w-[52%] rotate-[1.5deg] rounded-[14px] border border-border bg-surface shadow-md">
        <p className="border-b border-border px-3 py-1.5 font-mono text-[11px] text-text-3">retry.py</p>
        <pre className="px-3 py-2 font-mono text-[11px] leading-relaxed text-text-2">
          <span className="text-[#ff9eb0]">for</span> attempt <span className="text-[#ff9eb0]">in</span> range(<span className="text-accent-text">3</span>):{"\n"}    <span className="text-[#ff9eb0]">try</span>: <span className="text-[#ff9eb0]">return</span> call()
        </pre>
      </div>
      <div className="absolute right-[2%] top-[44%] w-[34%] rotate-[-3deg] overflow-hidden rounded-[14px] border border-border bg-surface shadow-md">
        <div className="grid aspect-[1.15] place-items-center bg-[linear-gradient(160deg,#2a2614,#141d2b)] text-[11px] text-text-2">
          whiteboard.png
        </div>
      </div>
    </div>
  );
}

function ChatVisual() {
  return (
    <div className="rounded-[16px] border border-border bg-surface p-4 shadow-md" aria-hidden="true">
      <div className="flex items-center gap-2.5">
        <Mascot state="found" size={24} />
        <span className="text-[13px] font-semibold">Ask Stash</span>
        <span className="ml-auto rounded-full bg-surface-3 px-2 py-0.5 text-[11px] text-text-2">All canvases</span>
      </div>
      <p className="ml-10 mt-4 rounded-[12px] rounded-br-[4px] bg-surface-3 px-3 py-2 text-[13px]">What did users say about search?</p>
      <p className="mt-3 text-[13px] leading-relaxed">
        They want search that understands intent
        <Cite n={1} />, and they keep losing links they saved weeks ago
        <Cite n={2} />.
      </p>
      <div className="mt-3 grid gap-1.5">
        {["Interview notes", "Research board · Saved links"].map((t, i) => (
          <div key={t} className="flex items-center gap-2 rounded-md border border-border px-2.5 py-1.5 text-[12px]">
            <Cite n={i + 1} /> {t}
          </div>
        ))}
      </div>
    </div>
  );
}

function Cite({ n }: { n: number }) {
  return (
    <span className="mx-0.5 inline-grid size-[17px] place-items-center rounded-full bg-accent-soft align-middle text-[10.5px] font-semibold text-accent-text">
      {n}
    </span>
  );
}

function FindVisual() {
  return (
    <div className="rounded-[16px] border border-border bg-surface shadow-md" aria-hidden="true">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3 text-[13.5px]">
        <Icon icon={Search01Icon} size={16} className="text-text-3" />
        <span>pricing</span>
        <span className="ml-auto"><Kbd>{modKey}K</Kbd></span>
      </div>
      <ul className="p-2 text-[13px]">
        {[
          [NoteIcon, "Pricing review notes", "Launch prep"],
          [Link01Icon, "Pricing page patterns that convert", "Launch prep"],
          [CodeSquareIcon, "pricing_v2 feature flag", "Backend"],
        ].map(([icon, title, where], i) => (
          <li key={title as string} className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 ${i === 0 ? "bg-surface-2" : ""}`}>
            <Icon icon={icon as IconType} size={15} className="text-text-3" />
            <span className="truncate">{title as string}</span>
            <span className="ml-auto shrink-0 text-[11.5px] text-text-3">{where as string}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DigestVisual() {
  return (
    <div className="rounded-[16px] border border-border bg-surface p-5 shadow-md" aria-hidden="true">
      <div className="flex items-center gap-2 text-[12px] text-text-3">
        <Icon icon={Mail01Icon} size={14} /> Your Stash this week · Monday, 8:00
      </div>
      <p className="mt-3 text-[15px] font-semibold">12 new cards across 3 canvases</p>
      <ul className="mt-3 grid gap-1.5 text-[13px] text-text-2">
        <li className="flex gap-2"><Icon icon={Tick02Icon} size={15} className="mt-0.5 text-accent-text" /> Launch moved to Friday 14 November</li>
        <li className="flex gap-2"><Icon icon={Tick02Icon} size={15} className="mt-0.5 text-accent-text" /> Three articles saved on onboarding flows</li>
        <li className="flex gap-2"><Icon icon={Tick02Icon} size={15} className="mt-0.5 text-accent-text" /> New snippet: retry with backoff</li>
      </ul>
      <div className="mt-4 rounded-md border border-border px-3 py-2 text-[12.5px]">
        <span className="text-text-3">Coming up · </span>Send pricing deck to the team, Thursday 10:00
      </div>
    </div>
  );
}

function FeatureRow({ eyebrow, title, body, points, visual, flip = false }: {
  eyebrow: string; title: string; body: string; points: string[]; visual: ReactNode; flip?: boolean;
}) {
  return (
    <div className="grid items-center gap-10 md:grid-cols-2 md:gap-16">
      <div className={flip ? "md:order-2" : undefined}>
        <p className="text-[12.5px] font-semibold uppercase tracking-[0.08em] text-accent-text">{eyebrow}</p>
        <h3 className="mt-3 text-[26px] font-semibold leading-[1.15] tracking-[-0.025em] sm:text-[30px]">{title}</h3>
        <p className="mt-3 text-[15.5px] leading-relaxed text-text-2">{body}</p>
        <ul className="mt-5 grid gap-2.5">
          {points.map((p) => (
            <li key={p} className="flex gap-2.5 text-[14px]">
              <Icon icon={Tick02Icon} size={17} className="mt-0.5 shrink-0 text-accent-text" /> {p}
            </li>
          ))}
        </ul>
      </div>
      <div className={flip ? "md:order-1" : undefined}>{visual}</div>
    </div>
  );
}

const EXTRAS: { icon: IconType; title: string; body: string }[] = [
  { icon: CloudUploadIcon, title: "Saves as you go", body: "Every move and edit is kept automatically. No save button, nothing to lose." },
  { icon: Brain01Icon, title: "Learns how you like answers", body: "Stash remembers preferences from your chats. See every fact it keeps, and forget any of them." },
  { icon: Shield01Icon, title: "Safe by default", body: "Adult or abusive content is caught before it is shown, answered or emailed." },
  { icon: LockKeyIcon, title: "Private to you", body: "Your canvases are yours alone. Sign in with Google, X or email." },
  { icon: Moon02Icon, title: "Dark and light", body: "A calm interface that is easy on the eyes, day or night." },
  { icon: Cursor01Icon, title: "Drag, drop, paste", body: "Drop files onto the canvas or paste straight from your clipboard." },
];

const AUDIENCES: { icon: IconType; title: string; body: string }[] = [
  { icon: Mortarboard02Icon, title: "Students", body: "Lecture notes, papers and screenshots per course. Ask what you need before the exam." },
  { icon: SourceCodeIcon, title: "Developers", body: "Snippets, docs and bug notes in one place, found again by asking in plain words." },
  { icon: SparklesIcon, title: "Researchers and writers", body: "Sources and quotes on one board, with answers that point back to the exact card." },
  { icon: Rocket01Icon, title: "Founders and product teams", body: "Competitor links, interview notes and launch plans, with reminders that keep dates on track." },
];

const FAQ: { q: string; a: string }[] = [
  { q: "Is Stash free?", a: "Yes. Every account includes a monthly assistant allowance and 500 MB of image storage. Links, notes and code don't count toward storage." },
  { q: "Where do the answers come from?", a: "Only from your own cards. Stash does not search the web. Each answer shows which cards it used, and if your cards don't contain the answer, it tells you instead of guessing." },
  { q: "Can anyone else see my canvases?", a: "No. Canvases are private to your account. There is no public profile and nothing is shared unless you share it yourself." },
  { q: "What can I save?", a: "Links (with their title and preview image), notes, plain text, code snippets with syntax highlighting, and images such as screenshots or photos of a whiteboard." },
  { q: "How do reminders and digests work?", a: "Put a reminder on any card and it arrives by email at the time you pick. The daily and weekly digests summarise what you saved. Choose the hour and time zone, or turn them off in one click." },
  { q: "What does Stash remember about me?", a: "Only durable preferences from your chats, such as liking short answers. You can see every fact in Settings, forget any of them, or turn memory off." },
  { q: "Can I delete my data?", a: "Yes. Deleted cards and canvases can be restored for 30 days, then they are gone for good. You can download everything, or delete your whole account, from Settings." },
];

export function Landing() {
  const me = useMe();
  const signedIn = !!me.data;
  useEffect(() => { document.title = "Stash · Everything you save, on one canvas"; }, []);

  const primaryCta = (
    <Button asChild variant="primary" size="lg">
      <Link to={signedIn ? "/app" : "/signup"}>
        {signedIn ? "Open your canvases" : "Start for free"} <Icon icon={ArrowRight01Icon} size={17} />
      </Link>
    </Button>
  );

  return (
    <MarketingLayout>
      {/* hero */}
      <section className="mx-auto max-w-[1120px] px-4 pb-16 pt-14 sm:px-6 sm:pt-20">
        <div className="flex flex-col items-start gap-10 md:flex-row md:items-end md:justify-between">
          <div className="max-w-[660px] animate-[rise_420ms_var(--ease-out)]">
            <p className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-[12.5px] text-text-2">
              <span className="size-1.5 rounded-full bg-accent" /> A canvas that remembers for you
            </p>
            <h1 className="mt-5 text-[40px] font-semibold leading-[1.04] tracking-[-0.035em] sm:text-[60px]">
              Everything you save, on one canvas.
            </h1>
            <p className="mt-5 max-w-[54ch] text-[16px] leading-relaxed text-text-2 sm:text-[17px]">
              Drop in links, notes, code and images. Ask a question and Stash answers from your own cards, pointing at
              each one. Set a reminder and it reaches your inbox right on time.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              {primaryCta}
              {!signedIn && <Button asChild variant="secondary" size="lg"><Link to="/login">Sign in</Link></Button>}
            </div>
            <p className="mt-4 text-[13px] text-text-3">Free to use. Sign in with Google, X or email.</p>
          </div>
          <div className="hidden md:block">
            <Mascot size={148} follow label="Stash, the mascot, watching your pointer" />
          </div>
        </div>
        <div className="mt-14 animate-[rise_620ms_var(--ease-out)]">
          <ProductPreview />
        </div>
        <ul className="mt-8 flex flex-wrap items-center justify-center gap-2 text-[13px] text-text-2" aria-label="Card types">
          {CARD_TYPES.map((c) => (
            <li key={c.label} className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5">
              <Icon icon={c.icon} size={15} className="text-accent-text" /> {c.label}
            </li>
          ))}
        </ul>
      </section>

      {/* how it works */}
      <section id="how-it-works" className="scroll-mt-20 border-t border-border">
        <div className="mx-auto max-w-[1120px] px-4 py-20 sm:px-6 sm:py-24">
          <SectionHead eyebrow="How it works" title="From scattered tabs to a board you can ask." center />
          <ol className="mt-12 grid gap-4 md:grid-cols-3">
            {STEPS.map((s) => (
              <li key={s.n} className="rounded-[16px] border border-border bg-surface p-6">
                <span className="grid size-9 place-items-center rounded-full bg-accent text-[14px] font-semibold text-accent-fg">{s.n}</span>
                <h3 className="mt-4 text-[17px] font-semibold tracking-[-0.01em]">{s.title}</h3>
                <p className="mt-1.5 text-[14px] leading-relaxed text-text-2">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* features */}
      <section id="features" className="scroll-mt-20 border-t border-border">
        <div className="mx-auto grid max-w-[1120px] gap-24 px-4 py-20 sm:px-6 sm:py-24">
          <SectionHead eyebrow="Features" title="Built for the way you actually save things."
            lead="Not another folder of bookmarks. A visual board for everything, and an assistant that knows where it all is." />
          <FeatureRow eyebrow="Save anything" title="Links, notes, code and images, side by side."
            body="Paste a link and it becomes a card with its title and preview. Write notes in Markdown, keep code with syntax highlighting, and drop in screenshots."
            points={["Links are read for you, so answers can use what the page actually says",
              "Text inside images becomes searchable", "Color notes and place everything freely on an endless canvas"]}
            visual={<CardsVisual />} />
          <FeatureRow flip eyebrow="Ask Stash" title="Ask in plain words. Get answers that point."
            body="Ask about one canvas or all of them. Stash answers only from what you saved, numbers its sources and highlights each card on the canvas."
            points={["Every claim links back to the card it came from", "Says so when your cards don't have the answer",
              "Follows up naturally: ask, refine, compare"]}
            visual={<ChatVisual />} />
          <FeatureRow eyebrow="Find" title="Any card, in a keystroke."
            body={`Press ${modKey}K anywhere to search across every canvas and jump straight to the card you had in mind.`}
            points={["Searches titles, notes, code and link text", "Works from the dashboard and inside any canvas",
              "Keyboard first, mouse friendly"]}
            visual={<FindVisual />} />
          <FeatureRow flip eyebrow="Remember" title="Reminders and digests that keep you on track."
            body="Put a reminder on any card and it arrives by email at the exact time you choose. A daily or weekly digest sums up what you saved and what is coming up."
            points={["Pick the hour and your time zone", "Key points from the cards you saved, not just a list",
              "Turn any email off in one click"]}
            visual={<DigestVisual />} />
        </div>
      </section>

      {/* extras */}
      <section className="border-t border-border">
        <div className="mx-auto max-w-[1120px] px-4 py-20 sm:px-6 sm:py-24">
          <SectionHead eyebrow="And more" title="The details that make it feel effortless." center />
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {EXTRAS.map((f) => (
              <article key={f.title} className="flex gap-4 rounded-[16px] border border-border bg-surface p-5">
                <IconChip icon={f.icon} />
                <div>
                  <h3 className="text-[15px] font-semibold tracking-[-0.01em]">{f.title}</h3>
                  <p className="mt-1 text-[13.5px] leading-relaxed text-text-2">{f.body}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* audiences */}
      <section className="border-t border-border">
        <div className="mx-auto max-w-[1120px] px-4 py-20 sm:px-6 sm:py-24">
          <SectionHead eyebrow="Made for" title="One canvas, many kinds of work." />
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {AUDIENCES.map((a) => (
              <article key={a.title} className="rounded-[16px] border border-border bg-surface p-6">
                <IconChip icon={a.icon} />
                <h3 className="mt-4 text-[16px] font-semibold tracking-[-0.01em]">{a.title}</h3>
                <p className="mt-1.5 text-[13.5px] leading-relaxed text-text-2">{a.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* privacy band */}
      <section className="mx-auto max-w-[1120px] px-4 pb-20 sm:px-6">
        <div className="grid gap-8 rounded-[20px] border border-border bg-surface p-8 sm:p-10 md:grid-cols-[1fr_auto] md:items-center">
          <div className="flex gap-4">
            <span className="grid size-10 shrink-0 place-items-center rounded-[10px] bg-surface-3"><Icon icon={Shield01Icon} size={20} /></span>
            <div>
              <h2 className="text-[17px] font-semibold tracking-[-0.01em]">Your cards stay yours</h2>
              <p className="mt-1.5 max-w-[60ch] text-[14px] leading-relaxed text-text-2">
                Canvases are private to your account. Every card, question and answer passes a safety check, so adult or
                abusive content is never answered, previewed or emailed. We never sell your data.
              </p>
            </div>
          </div>
          <Button asChild variant="secondary"><Link to="/privacy">Read the privacy policy</Link></Button>
        </div>
      </section>

      {/* faq */}
      <section id="faq" className="scroll-mt-20 border-t border-border">
        <div className="mx-auto grid max-w-[1120px] gap-10 px-4 py-20 sm:px-6 sm:py-24 md:grid-cols-[1fr_1.4fr]">
          <SectionHead eyebrow="FAQ" title="Questions, answered." lead="Something else on your mind? We're happy to help." />
          <div className="grid gap-2">
            {FAQ.map((f) => (
              <details key={f.q} className="group rounded-[14px] border border-border bg-surface px-5 py-4 open:bg-surface-2">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[15px] font-medium [&::-webkit-details-marker]:hidden">
                  {f.q}
                  <span className="text-[20px] leading-none text-text-3 transition-transform group-open:rotate-45" aria-hidden="true">+</span>
                </summary>
                <p className="mt-2.5 text-[14px] leading-relaxed text-text-2">{f.a}</p>
              </details>
            ))}
            <p className="mt-2 text-[13.5px] text-text-2">
              Still curious? <Link to="/contact" className="text-accent-text underline-offset-4 hover:underline">Get in touch</Link>.
            </p>
          </div>
        </div>
      </section>

      {/* final cta */}
      <section className="mx-auto max-w-[1120px] px-4 pb-24 sm:px-6">
        <div className="flex flex-col items-center rounded-[24px] border border-border bg-surface px-6 py-14 text-center">
          <Mascot size={72} follow />
          <h2 className="mt-5 max-w-[20ch] text-[30px] font-semibold leading-[1.1] tracking-[-0.03em] sm:text-[40px]">
            Stop losing the things you saved.
          </h2>
          <p className="mt-3 max-w-[48ch] text-[15.5px] leading-relaxed text-text-2">
            Start a canvas in seconds. Your first question is one paste away.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            {primaryCta}
            {!signedIn && (
              <Button asChild variant="ghost" size="lg">
                <Link to="/login"><Icon icon={AiChat02Icon} size={17} /> I already have an account</Link>
              </Button>
            )}
          </div>
          <p className="mt-5 flex items-center gap-2 text-[12.5px] text-text-3">
            <Icon icon={Clock01Icon} size={14} /> Takes under a minute to set up
          </p>
        </div>
      </section>
    </MarketingLayout>
  );
}
