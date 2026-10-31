import {
  ArrowRight01Icon,
  Calendar03Icon,
  CheckmarkCircle02Icon,
  Clock01Icon,
  DashboardSquare01Icon,
  Edit02Icon,
  Message01Icon,
  Settings01Icon,
} from "@hugeicons/core-free-icons";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { KindIcon } from "@/canvas/kinds";
import { AppShell, Avatar } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Icon, Input } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api";
import { useMe, useProfile, useStorage, useUpdateMe, useUsage } from "@/lib/queries";
import type { Kind, User } from "@/lib/types";
import { cn, formatBytes } from "@/lib/utils";

const KINDS: Kind[] = ["link", "note", "text", "code", "image"];
const KIND_PLURAL: Record<Kind, string> = { link: "Links", note: "Notes", text: "Text", code: "Code", image: "Images" };

function Panel({ title, action, children, className }: { title: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-[16px] border border-border bg-surface p-5 sm:p-6", className)}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-[14px] font-semibold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Stat({ icon, label, value, to }: { icon: typeof Clock01Icon; label: string; value?: number; to?: string }) {
  const body = (
    <>
      <span className="grid size-8 place-items-center rounded-[9px] bg-accent-soft text-accent-text"><Icon icon={icon} size={16} /></span>
      <span className="mt-3 block text-[26px] font-semibold tabular tracking-[-0.02em]">
        {value === undefined ? <span className="shimmer inline-block h-7 w-10 rounded" /> : value.toLocaleString()}
      </span>
      <span className="mt-0.5 flex items-center gap-1 text-[13px] text-text-2">
        {label}{to && <Icon icon={ArrowRight01Icon} size={13} className="opacity-0 transition-opacity group-hover:opacity-100" />}
      </span>
    </>
  );
  const cls = "group rounded-[16px] border border-border bg-surface p-5 transition-colors";
  return to ? <Link to={to} className={cn(cls, "hover:bg-surface-2")}>{body}</Link> : <div className={cls}>{body}</div>;
}

function Meter({ label, used, total, format }: { label: string; used: number; total: number; format: (n: number) => string }) {
  const pct = total > 0 ? Math.min(100, (used / total) * 100) : 0;
  return (
    <div>
      <div className="flex justify-between text-[13.5px]">
        <span>{label}</span>
        <span className="text-text-3">{format(used)} of {format(total)}</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-3" role="progressbar" aria-label={label}
        aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
        <div className={cn("h-full rounded-full", pct > 90 ? "bg-danger" : "bg-accent")} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function NameEditor({ user }: { user: User }) {
  const update = useUpdateMe();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(user.display_name ?? "");
  useEffect(() => setName(user.display_name ?? ""), [user.display_name]);

  function submit(e: FormEvent) {
    e.preventDefault();
    update.mutate({ display_name: name.trim() || null }, {
      onSuccess: () => { setEditing(false); toast.success("Name updated"); },
      onError: (err) => toast.error(errorMessage(err)),
    });
  }

  if (!editing) {
    return (
      <div className="flex min-w-0 items-center gap-2">
        <h1 className="truncate text-[24px] font-semibold tracking-[-0.025em]">{user.display_name || "Add your name"}</h1>
        <Button variant="ghost" size="icon-sm" aria-label="Edit name" onClick={() => setEditing(true)}>
          <Icon icon={Edit02Icon} size={16} />
        </Button>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="flex max-w-[420px] gap-2">
      <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Your name" aria-label="Name"
        onKeyDown={(e) => e.key === "Escape" && (setEditing(false), setName(user.display_name ?? ""))} />
      <Button type="submit" variant="primary" loading={update.isPending}>Save</Button>
      <Button type="button" variant="ghost" onClick={() => { setEditing(false); setName(user.display_name ?? ""); }}>Cancel</Button>
    </form>
  );
}

function SignInMethod({ label, connected, detail }: { label: string; connected: boolean; detail?: string }) {
  return (
    <li className="flex items-center justify-between gap-3 rounded-md border border-border px-4 py-3">
      <div className="min-w-0">
        <p className="text-[14px] font-medium">{label}</p>
        {detail && <p className="truncate text-[12.5px] text-text-3">{detail}</p>}
      </div>
      {connected ? (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-success-soft px-2.5 py-1 text-[12px] font-medium text-success">
          <Icon icon={CheckmarkCircle02Icon} size={14} /> Connected
        </span>
      ) : (
        <span className="rounded-full bg-surface-3 px-2.5 py-1 text-[12px] text-text-3">Not connected</span>
      )}
    </li>
  );
}

export default function Profile() {
  const me = useMe();
  const user = me.data as User;
  const profile = useProfile();
  const storage = useStorage();
  const usage = useUsage();
  const p = profile.data;
  const name = user.display_name || user.email || "You";
  const since = new Date(p?.member_since ?? user.created_at).toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const maxKind = Math.max(1, ...KINDS.map((k) => p?.counts.by_kind[k] ?? 0));

  useEffect(() => { document.title = "Profile · Stash"; return () => { document.title = "Stash"; }; }, []);

  return (
    <AppShell title="Profile">
      <main className="mx-auto grid max-w-[960px] gap-5 px-4 pb-24 pt-8 sm:px-6">
        <section className="flex flex-col gap-5 rounded-[20px] border border-border bg-surface p-6 sm:flex-row sm:items-center sm:p-8">
          <Avatar name={name} src={user.avatar_url} size={80} />
          <div className="min-w-0 flex-1">
            <NameEditor user={user} />
            <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[14px] text-text-2">
              <span className="truncate">{user.email ?? "No email on this account"}</span>
              {user.email && (
                <span className={cn("rounded-full px-2 py-0.5 text-[11.5px] font-medium",
                  user.email_verified ? "bg-success-soft text-success" : "bg-warning-soft text-warning")}>
                  {user.email_verified ? "Verified" : "Not verified"}
                </span>
              )}
            </p>
            <p className="mt-2 flex items-center gap-1.5 text-[13px] text-text-3">
              <Icon icon={Calendar03Icon} size={14} /> Member since {since}
            </p>
          </div>
          <Button asChild variant="secondary" className="self-start sm:self-center">
            <Link to="/settings"><Icon icon={Settings01Icon} size={16} /> Settings</Link>
          </Button>
        </section>

        {profile.isError && <p className="text-[13px] text-danger">{errorMessage(profile.error)}</p>}

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat icon={DashboardSquare01Icon} label="Canvases" value={p?.counts.canvases} to="/app" />
          <Stat icon={Edit02Icon} label="Cards" value={p?.counts.cards} />
          <Stat icon={Clock01Icon} label="Upcoming reminders" value={p?.counts.upcoming_reminders} to="/reminders" />
          <Stat icon={Message01Icon} label="Questions asked" value={p?.counts.questions_asked} />
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <Panel title="Cards by type">
            {p && p.counts.cards === 0 ? (
              <p className="text-[13.5px] text-text-2">
                No cards yet. <Link to="/app" className="text-accent-text underline-offset-4 hover:underline">Open a canvas</Link> and
                paste a link to get started.
              </p>
            ) : (
              <ul className="grid gap-3">
                {KINDS.map((k) => {
                  const n = p?.counts.by_kind[k] ?? 0;
                  return (
                    <li key={k} className="grid grid-cols-[96px_1fr_40px] items-center gap-3 text-[13.5px]">
                      <span className="flex items-center gap-2 text-text-2"><KindIcon kind={k} size={15} /> {KIND_PLURAL[k]}</span>
                      <span className="h-2 overflow-hidden rounded-full bg-surface-3">
                        <span className="block h-full rounded-full bg-accent transition-[width] duration-500"
                          style={{ width: p ? `${(n / maxKind) * 100}%` : "0%" }} />
                      </span>
                      <span className="text-right tabular text-text-2">{p ? n : "–"}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>

          <Panel title="Sign-in methods">
            <ul className="grid gap-2">
              <SignInMethod label="Email and password" connected={!!p?.sign_in.password}
                detail={p?.sign_in.password ? user.email ?? undefined
                  : user.email ? "Use “Forgot password” on the sign-in page to add one" : undefined} />
              <SignInMethod label="Google" connected={!!p?.sign_in.providers.includes("google")} />
              <SignInMethod label="X" connected={!!p?.sign_in.providers.includes("x")} />
            </ul>
          </Panel>
        </div>

        <Panel title="Usage" action={<Link to="/settings" className="text-[13px] text-text-2 hover:text-text">Manage</Link>}>
          <div className="grid gap-5 md:grid-cols-2">
            <Meter label="Image storage" used={storage.data?.used_bytes ?? 0} total={storage.data?.quota_bytes ?? 0} format={formatBytes} />
            <Meter label="Assistant this month" used={usage.data?.used_tokens ?? 0} total={usage.data?.limit_tokens ?? 0}
              format={(n) => n.toLocaleString()} />
          </div>
          <p className="mt-4 text-[12.5px] text-text-3">The assistant allowance resets on the 1st of every month.</p>
        </Panel>
      </main>
    </AppShell>
  );
}
