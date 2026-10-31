import { RefreshIcon } from "@hugeicons/core-free-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Mascot } from "@/components/Mascot";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { FieldError, Icon, Input, Label } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import { keys, useMe } from "@/lib/queries";
import type { User } from "@/lib/types";
import { cn, formatBytes, timeAgo } from "@/lib/utils";
import { FullPageLoader, NotFound } from "../App";

type Row = Record<string, string | number | boolean | null>;
interface Metrics {
  generated_at: string;
  totals: Record<string, number>;
  active: { dau: number; wau: number; mau: number };
  daily: { day: string; signups: number; cards: number; questions: number; active_users: number }[];
  cards_by_kind: { kind: string; count: number }[];
  sign_in: { method: string; count: number }[];
  ai: { requests: number; tokens: number; p95_ms: number; errors: number; budget_per_user: number;
    tasks: { task: string; requests: number; input_tokens: number; output_tokens: number; avg_ms: number; errors: number }[] };
  moderation: { source: string; action: string; count: number }[];
  jobs: { states: { state: string; count: number }[]; due: number; oldest_due_s: number;
    failed: { id: number; kind: string; attempts: number; error: string; updated_at: string }[] };
  emails: { reminders: number; reminders_failed: number; daily_digests: number; weekly_digests: number };
  top_users: Row[];
  recent_users: Row[];
  system: Row & { db_bytes: number; pool_in_use: number; pool_size: number };
}

const num = new Intl.NumberFormat("en");
const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
const n = (v: number) => (Math.abs(v) >= 10_000 ? compact.format(v) : num.format(v));

/** Keep the admin page out of search results without listing its path in robots.txt. */
function useNoIndex() {
  useEffect(() => {
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex, nofollow";
    document.head.appendChild(meta);
    document.title = "Admin · Stash";
    return () => meta.remove();
  }, []);
}

export default function Admin() {
  useNoIndex();
  const me = useMe();
  if (me.isPending) return <FullPageLoader />;
  if (!me.data) return <AdminSignIn />;
  if (!me.data.is_admin) return <NotFound />;
  return <AdminDashboard />;
}

function AdminSignIn() {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      qc.setQueryData(keys.me, (await api.post<{ data: User }>("/auth/login", { email, password })).data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-[360px]">
        <Mascot state={error ? "blocked" : "idle"} size={44} />
        <h1 className="mt-6 text-[22px] font-semibold tracking-[-0.02em]">Stash admin</h1>
        <p className="mt-1.5 text-[14px] text-text-2">Sign in with the admin account.</p>
        <form onSubmit={submit} noValidate className="mt-7 grid gap-4">
          <div>
            <Label htmlFor="admin-email">Email</Label>
            <Input id="admin-email" type="email" autoComplete="username" required autoFocus value={email}
              onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="admin-password">Password</Label>
            <Input id="admin-password" type="password" autoComplete="current-password" required value={password}
              onChange={(e) => setPassword(e.target.value)} aria-invalid={!!error} aria-describedby="admin-error" />
            <FieldError id="admin-error">{error}</FieldError>
          </div>
          <Button type="submit" variant="primary" size="lg" loading={busy} className="mt-1 w-full">Sign in</Button>
        </form>
      </div>
    </main>
  );
}

function AdminDashboard() {
  const q = useQuery({
    queryKey: ["admin-metrics"],
    queryFn: async () => (await api.get<{ data: Metrics }>("/admin/metrics")).data,
    refetchInterval: 60_000,
  });
  const m = q.data;

  return (
    <AppShell title="Admin">
      <main className="mx-auto max-w-[1200px] px-4 pb-24 pt-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-[22px] font-semibold tracking-[-0.02em]">Admin</h1>
            <p className="mt-1 text-[14px] text-text-2">
              {m ? <>Updated {timeAgo(m.generated_at)} · refreshes every minute · {String(m.system.environment)}</>
                : "Loading metrics…"}
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => q.refetch()} loading={q.isFetching} className="gap-1.5">
            <Icon icon={RefreshIcon} size={15} /> Refresh
          </Button>
        </div>

        {q.isError && <p className="mt-6 text-danger" role="alert">{errorMessage(q.error)}</p>}
        {m && <Body m={m} />}
      </main>
    </AppShell>
  );
}

function Body({ m }: { m: Metrics }) {
  const t = m.totals;
  const failedJobs = m.jobs.states.find((s) => s.state === "dead")?.count ?? 0;
  return (
    <>
      <section aria-label="Totals" className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Users" value={n(t.users)} note={`+${n(t.new_users_7d)} this week · ${n(t.verified_users)} verified`} />
        <Stat label="Active users" value={n(m.active.dau)} note={`today · ${n(m.active.wau)} this week · ${n(m.active.mau)} in 30 days`} />
        <Stat label="Cards" value={n(t.cards)} note={`${n(t.canvases)} canvases · ${n(t.shared_canvases)} shared`} />
        <Stat label="Questions asked" value={n(t.questions)} note={`${n(t.memories)} memories saved`} />
        <Stat label="AI tokens, 30 days" value={n(m.ai.tokens)} note={`${n(m.ai.requests)} requests · p95 ${n(m.ai.p95_ms)} ms`} />
        <Stat label="Storage" value={formatBytes(t.storage_bytes)} note={`database ${formatBytes(m.system.db_bytes)}`} />
        <Stat label="Reminders" value={n(t.reminders_pending)} note={`pending · ${n(t.reminders_sent)} sent`} />
        <Stat label="Needs attention" value={n(t.flagged_cards + failedJobs + m.ai.errors)}
          note={`${n(t.flagged_cards)} flagged cards · ${n(failedJobs)} failed jobs · ${n(m.ai.errors)} AI errors`}
          tone={t.flagged_cards + failedJobs + m.ai.errors > 0 ? "warn" : undefined} />
      </section>

      <section aria-label="Last 30 days" className="mt-8">
        <SectionTitle>Last 30 days</SectionTitle>
        <div className="grid gap-3 md:grid-cols-2">
          <DailyChart title="Sign-ups" data={m.daily} field="signups" />
          <DailyChart title="Active users" data={m.daily} field="active_users" average />
          <DailyChart title="Cards created" data={m.daily} field="cards" />
          <DailyChart title="Questions asked" data={m.daily} field="questions" />
        </div>
      </section>

      <section aria-label="Breakdowns" className="mt-8 grid gap-3 md:grid-cols-3">
        <Panel title="Cards by kind">
          <Bars rows={m.cards_by_kind.map((r) => ({ label: r.kind, value: r.count }))} />
        </Panel>
        <Panel title="Sign-in methods">
          <Bars rows={m.sign_in.map((r) => ({ label: r.method === "x" ? "X" : r.method, value: r.count }))} />
        </Panel>
        <Panel title="Emails sent, 30 days">
          <Bars rows={[
            { label: "Reminders", value: m.emails.reminders },
            { label: "Daily digests", value: m.emails.daily_digests },
            { label: "Weekly digests", value: m.emails.weekly_digests },
          ]} />
          {m.emails.reminders_failed > 0 && (
            <p className="mt-3 text-[12.5px] text-warning">{n(m.emails.reminders_failed)} reminders failed to send</p>
          )}
        </Panel>
      </section>

      <section aria-label="AI" className="mt-8">
        <SectionTitle>AI usage, 30 days <span className="font-normal text-text-3">· budget {n(m.ai.budget_per_user)} tokens per user per month</span></SectionTitle>
        <Table empty="No AI requests yet" cols={["Task", "Requests", "Input tokens", "Output tokens", "Avg latency", "Errors"]}
          rows={m.ai.tasks.map((r) => [r.task, n(r.requests), n(r.input_tokens), n(r.output_tokens), `${n(r.avg_ms)} ms`,
            <span key="e" className={r.errors ? "text-danger" : undefined}>{n(r.errors)}</span>])}
          numeric />
      </section>

      <section aria-label="Safety and jobs" className="mt-8 grid gap-3 md:grid-cols-2">
        <Panel title="Content safety, 30 days">
          {m.moderation.length ? (
            <Bars rows={m.moderation.map((r) => ({ label: `${r.action} · ${r.source.replace("_", " ")}`, value: r.count }))} />
          ) : <p className="text-[13.5px] text-text-2">Nothing blocked or flagged.</p>}
        </Panel>
        <Panel title="Background jobs">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-[13.5px] sm:grid-cols-4">
            {["queued", "running", "done", "dead"].map((state) => (
              <div key={state}>
                <div className="text-text-3">{state === "dead" ? "failed" : state}</div>
                <div className={cn("tabular text-[18px] font-semibold", state === "dead" && failedJobs > 0 && "text-danger")}>
                  {n(m.jobs.states.find((s) => s.state === state)?.count ?? 0)}
                </div>
              </div>
            ))}
          </div>
          <p className={cn("mt-3 text-[12.5px]", m.jobs.oldest_due_s > 300 ? "text-warning" : "text-text-2")}>
            {m.jobs.due ? `${n(m.jobs.due)} due now, oldest waiting ${duration(m.jobs.oldest_due_s)}` : "Queue is clear"}
          </p>
          {m.jobs.failed.length > 0 && (
            <ul className="mt-3 grid gap-2 border-t border-border pt-3">
              {m.jobs.failed.map((j) => (
                <li key={j.id} className="text-[12.5px]">
                  <span className="font-medium">{j.kind}</span>
                  <span className="text-text-3"> · {j.attempts} attempts · {timeAgo(j.updated_at)}</span>
                  <div className="truncate font-mono text-[11.5px] text-text-2" title={j.error}>{j.error || "no error recorded"}</div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </section>

      <section aria-label="Users" className="mt-8 grid gap-6 lg:grid-cols-2">
        <div className="min-w-0">
          <SectionTitle>Most active users</SectionTitle>
          <Table empty="No users yet" cols={["User", "Cards", "Canvases", "AI tokens", "Last active"]} numeric
            rows={m.top_users.map((u) => [<UserCell key="u" u={u} />, n(Number(u.cards)), n(Number(u.canvases)),
              n(Number(u.ai_tokens_30d)), u.last_active ? timeAgo(String(u.last_active)) : "never"])} />
        </div>
        <div className="min-w-0">
          <SectionTitle>Newest sign-ups</SectionTitle>
          <Table empty="No users yet" cols={["User", "Method", "Status", "Joined"]}
            rows={m.recent_users.map((u) => [<UserCell key="u" u={u} />, String(u.method),
              u.suspended ? <span key="s" className="text-danger">suspended</span>
                : u.email_verified ? "verified" : <span key="s" className="text-warning">unverified</span>,
              timeAgo(String(u.created_at))])} />
        </div>
      </section>

      <section aria-label="System" className="mt-8">
        <SectionTitle>System</SectionTitle>
        <div className="flex flex-wrap gap-2 text-[12.5px]">
          <Chip ok>DB pool {m.system.pool_in_use}/{m.system.pool_size} in use</Chip>
          {(["chat", "embeddings", "vector_search", "mail"] as const).map((k) => (
            <Chip key={k} ok={!!m.system[k]}>{k.replace("_", " ")} {m.system[k] ? "on" : "off"}</Chip>
          ))}
        </div>
      </section>
    </>
  );
}

function duration(s: number) {
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.round(s / 60)} min`;
  return `${Math.round(s / 3600)} h`;
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="mb-3 text-[14px] font-semibold">{children}</h2>;
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-[14px] border border-border bg-surface p-4">
      <h3 className="mb-3 text-[13.5px] font-semibold">{title}</h3>
      {children}
    </div>
  );
}

function Stat({ label, value, note, tone }: { label: string; value: string; note: string; tone?: "warn" }) {
  return (
    <div className="rounded-[14px] border border-border bg-surface p-4">
      <div className="text-[12.5px] text-text-2">{label}</div>
      <div className={cn("tabular mt-1 text-[26px] font-semibold tracking-[-0.02em]", tone === "warn" && "text-warning")}>{value}</div>
      <div className="mt-1 text-[12px] leading-snug text-text-3">{note}</div>
    </div>
  );
}

function Chip({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1",
      ok ? "text-text" : "text-text-3")}>
      <span aria-hidden="true" className={cn("size-1.5 rounded-full", ok ? "bg-success" : "bg-text-3")} />
      {children}
    </span>
  );
}

function UserCell({ u }: { u: Row }) {
  return (
    <div className="min-w-0">
      <div className="truncate font-medium">{String(u.display_name || u.email || "No email")}</div>
      {u.display_name && <div className="truncate text-[12px] text-text-3">{String(u.email ?? "")}</div>}
    </div>
  );
}

function Table({ cols, rows, empty, numeric }: { cols: string[]; rows: ReactNode[][]; empty: string; numeric?: boolean }) {
  if (!rows.length) return <p className="rounded-[14px] border border-border bg-surface p-4 text-[13.5px] text-text-2">{empty}</p>;
  return (
    <div className="overflow-x-auto rounded-[14px] border border-border bg-surface">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-border text-left text-[12px] text-text-3">
            {cols.map((c, i) => (
              <th key={c} scope="col" className={cn("px-4 py-2.5 font-medium", numeric && i > 0 && "text-right")}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-border last:border-0">
              {r.map((cell, j) => (
                <td key={j} className={cn("max-w-[260px] px-4 py-2.5", numeric && j > 0 && "tabular text-right",
                  j > 0 && "whitespace-nowrap")}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Horizontal bars for a short breakdown: one hue, label and value in text ink. */
function Bars({ rows }: { rows: { label: string; value: number }[] }) {
  if (!rows.length) return <p className="text-[13.5px] text-text-2">No data yet.</p>;
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="grid gap-2.5">
      {rows.map((r) => (
        <li key={r.label} className="text-[13px]">
          <div className="flex justify-between gap-3">
            <span className="truncate capitalize">{r.label}</span>
            <span className="tabular text-text-2">{n(r.value)}</span>
          </div>
          <div className="mt-1 h-1.5 rounded-full bg-surface-2">
            <div className="h-full rounded-full bg-[var(--chart)]" style={{ width: `${(r.value / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

type Day = Metrics["daily"][number];
type DayField = "signups" | "cards" | "questions" | "active_users";

/** 30 daily bars with a hover tooltip; a hidden table carries the same numbers for screen readers. */
/** `average` for counts that can't be added up across days (the same person is active on many days). */
function DailyChart({ title, data, field, average }: { title: string; data: Day[]; field: DayField; average?: boolean }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 600, H = 140, top = 8, bottom = 20;
  const values = data.map((d) => d[field]);
  const max = Math.max(1, ...values);
  const total = values.reduce((a, b) => a + b, 0);
  const slot = W / data.length;
  const barW = Math.max(2, slot - 2);
  const plotH = H - top - bottom;
  const label = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString("en", { month: "short", day: "numeric", timeZone: "UTC" });
  const h = hover !== null ? data[hover] : null;

  return (
    <div className="rounded-[14px] border border-border bg-surface p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[13.5px] font-semibold">{title}</h3>
        <span className="tabular text-[12.5px] text-text-2">
          {h ? <>{label(h.day)}: <span className="font-semibold text-text">{n(h[field])}</span></> : average ? <>{n(Math.round(total / data.length))} a day on average</> : <>{n(total)} total</>}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 block h-[140px] w-full" role="img" preserveAspectRatio="none"
        aria-label={`${title}, last 30 days: ${average ? `${n(Math.round(total / data.length))} a day on average` : `${n(total)} in total`}, peak ${n(max)} in a day`} onMouseLeave={() => setHover(null)}>
        <line x1={0} x2={W} y1={top} y2={top} className="stroke-[var(--border)]" strokeDasharray="3 4" />
        <line x1={0} x2={W} y1={H - bottom} y2={H - bottom} className="stroke-[var(--border-strong)]" />
        {data.map((d, i) => {
          const v = d[field];
          const bh = (v / max) * plotH;
          const x = i * slot + 1;
          const y = H - bottom - bh;
          const r = Math.min(4, barW / 2, bh);
          return (
            <g key={d.day} onMouseEnter={() => setHover(i)}>
              <rect x={i * slot} y={0} width={slot} height={H - bottom} fill="transparent" />
              {v > 0 && (
                <path d={`M${x},${H - bottom} V${y + r} Q${x},${y} ${x + r},${y} H${x + barW - r} Q${x + barW},${y} ${x + barW},${y + r} V${H - bottom} Z`}
                  className={cn("fill-[var(--chart)] transition-opacity", hover !== null && hover !== i && "opacity-40")} />
              )}
            </g>
          );
        })}
      </svg>
      <div className="mt-1 flex justify-between text-[11.5px] text-text-3">
        <span>{label(data[0].day)}</span>
        <span>peak {n(max)}/day</span>
        <span>{label(data[data.length - 1].day)}</span>
      </div>
      <table className="sr-only">
        <caption>{title} per day</caption>
        <tbody>{data.map((d) => <tr key={d.day}><th scope="row">{d.day}</th><td>{d[field]}</td></tr>)}</tbody>
      </table>
    </div>
  );
}
