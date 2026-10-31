import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, Input, Switch } from "@/components/ui/primitives";
import { api, errorMessage } from "@/lib/api";
import { useForgetAllMemories, useForgetMemory, useMe, useMemories, useStorage, useUpdateMe, useUsage } from "@/lib/queries";
import { setMode, useMode } from "@/lib/theme";
import type { User } from "@/lib/types";
import { cn, formatBytes } from "@/lib/utils";

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="grid gap-4 border-b border-border py-8 last:border-0 md:grid-cols-[240px_1fr] md:gap-10">
      <div>
        <h2 className="text-[14px] font-semibold">{title}</h2>
        {description && <p className="mt-1 text-[13px] text-text-2">{description}</p>}
      </div>
      <div className="grid gap-4">{children}</div>
    </section>
  );
}

function Row({ label, hint, htmlFor, children }: { label: string; hint?: string; htmlFor?: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border border-border bg-surface px-4 py-3">
      <div className="min-w-0">
        <label htmlFor={htmlFor} className="block text-[14px] font-medium">{label}</label>
        {hint && <p className="mt-0.5 text-[12.5px] text-text-2">{hint}</p>}
      </div>
      {children}
    </div>
  );
}

const select =
  "h-9 rounded-md border border-border bg-surface-2 px-2 text-[13.5px] outline-none hover:border-border-strong focus:border-accent";

function AssistantAllowance({ used, limit }: { used: number; limit: number }) {
  const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
  return (
    <div className="rounded-md border border-border bg-surface px-4 py-3">
      <div className="flex justify-between text-[13.5px]">
        <span>{used.toLocaleString()} tokens used</span>
        <span className="text-text-3">of {limit.toLocaleString()}</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-3" role="progressbar" aria-valuenow={Math.round(pct)}
        aria-valuemin={0} aria-valuemax={100} aria-label="Assistant allowance used">
        <div className={cn("h-full rounded-full", pct > 90 ? "bg-danger" : "bg-accent")} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function hourLabel(h: number) {
  return new Date(2000, 0, 1, h).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export default function Settings() {
  const me = useMe();
  const user = me.data as User;
  const update = useUpdateMe();
  const storage = useStorage();
  const usage = useUsage();
  const mode = useMode();
  const navigate = useNavigate();
  const [name, setName] = useState(user.display_name ?? "");
  const [confirmOut, setConfirmOut] = useState(false);
  const [confirmForget, setConfirmForget] = useState(false);
  const memories = useMemories();
  const forget = useForgetMemory();
  const forgetAll = useForgetAllMemories();
  useEffect(() => setName(user.display_name ?? ""), [user.display_name]);

  const zones = useMemo(() => {
    try {
      return Intl.supportedValuesOf("timeZone");
    } catch {
      return [user.timezone];
    }
  }, [user.timezone]);
  const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const save = (patch: Partial<User>, message = "Saved") =>
    update.mutate(patch, { onSuccess: () => toast.success(message), onError: (e) => toast.error(errorMessage(e)) });

  const used = storage.data?.used_bytes ?? 0;
  const quota = storage.data?.quota_bytes ?? 1;
  const pct = Math.min(100, (used / quota) * 100);

  return (
    <AppShell title="Settings">
      <main className="mx-auto max-w-[880px] px-4 pb-24 pt-4 sm:px-6">
        <Section title="Profile" description="How you appear in Stash and in emails.">
          <div className="flex gap-2">
            <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Your name" aria-label="Name" />
            <Button variant="secondary" disabled={name === (user.display_name ?? "")} loading={update.isPending}
              onClick={() => save({ display_name: name.trim() || null })}>Save</Button>
          </div>
          <Row label="Email" hint={user.email_verified ? "Verified" : "Not verified"}>
            <span className="truncate text-[13.5px] text-text-2">{user.email ?? "No email (signed in with X)"}</span>
          </Row>
        </Section>

        <Section title="Email digests" description="A short summary of what you saved, with key points and upcoming reminders. Nothing is sent for a day with no new cards.">
          {!user.email && (
            <p className="rounded-md bg-warning-soft px-3 py-2 text-[13px] text-warning">
              Add an email to your account to get digests and reminders.
            </p>
          )}
          <Row label="Daily digest" hint="Yesterday's cards, every morning." htmlFor="digest-daily">
            <Switch id="digest-daily" checked={user.digest_daily} disabled={!user.email}
              onCheckedChange={(v) => save({ digest_daily: v }, v ? "Daily digest on" : "Daily digest off")} />
          </Row>
          <Row label="Weekly digest" hint="Last week's cards, every Monday." htmlFor="digest-weekly">
            <Switch id="digest-weekly" checked={user.digest_weekly} disabled={!user.email}
              onCheckedChange={(v) => save({ digest_weekly: v }, v ? "Weekly digest on" : "Weekly digest off")} />
          </Row>
          <Row label="Send at" htmlFor="digest-hour">
            <select id="digest-hour" className={select} value={user.digest_hour}
              onChange={(e) => save({ digest_hour: Number(e.target.value) })}>
              {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{hourLabel(h)}</option>)}
            </select>
          </Row>
          <Row label="Time zone" hint={user.timezone !== browserZone ? `This device is on ${browserZone}.` : undefined} htmlFor="tz">
            <div className="flex items-center gap-2">
              {user.timezone !== browserZone && (
                <Button variant="ghost" size="sm" onClick={() => save({ timezone: browserZone })}>Use this</Button>
              )}
              <select id="tz" className={cn(select, "max-w-[200px]")} value={user.timezone}
                onChange={(e) => save({ timezone: e.target.value })}>
                {zones.map((z) => <option key={z} value={z}>{z.replace(/_/g, " ")}</option>)}
              </select>
            </div>
          </Row>
        </Section>

        <Section title="Assistant" description="Every account gets the same monthly allowance. Chat, reading cards, memory and digests share it, and it resets on the 1st.">
          <AssistantAllowance used={usage.data?.used_tokens ?? 0} limit={usage.data?.limit_tokens ?? 0} />
        </Section>

        <Section title="Memory" description="Facts Stash keeps from your chats so later answers fit you. Cards you saved are separate, and you can forget any fact.">
          <Row label="Remember from chat" hint="Off stops new facts and keeps existing ones out of answers." htmlFor="memory">
            <Switch id="memory" checked={user.memory_enabled}
              onCheckedChange={(v) => save({ memory_enabled: v }, v ? "Memory on" : "Memory off")} />
          </Row>
          {memories.isLoading ? (
            <p className="text-[13px] text-text-3">Loading…</p>
          ) : memories.isError ? (
            <p className="text-[13px] text-danger">{errorMessage(memories.error)}</p>
          ) : memories.data && memories.data.length > 0 ? (
            <div className="grid gap-2">
              <ul className="grid gap-2">
                {memories.data.map((m) => (
                  <li key={m.id} className="flex items-start justify-between gap-3 rounded-md border border-border bg-surface px-4 py-3">
                    <div className="min-w-0">
                      <p className="text-[14px]">{m.fact}</p>
                      <p className="mt-0.5 text-[12px] capitalize text-text-3">{m.kind}</p>
                    </div>
                    <Button variant="ghost" size="sm" disabled={forget.isPending}
                      onClick={() => forget.mutate(m.id, { onError: (e) => toast.error(errorMessage(e)) })}>Forget</Button>
                  </li>
                ))}
              </ul>
              <div className="flex justify-end">
                <Button variant="ghost" size="sm" onClick={() => setConfirmForget(true)}>Forget everything</Button>
              </div>
            </div>
          ) : (
            <p className="text-[13px] text-text-2">Nothing yet. Facts show up here after you chat, such as a project you are working on or how you like answers written.</p>
          )}
        </Section>

        <Section title="Appearance">
          <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Theme">
            {(["dark", "light"] as const).map((m) => (
              <button key={m} role="radio" aria-checked={mode === m} onClick={() => setMode(m)}
                className={cn("rounded-md border px-4 py-3 text-left text-[14px] font-medium capitalize transition-colors",
                  mode === m ? "border-accent bg-accent-soft" : "border-border hover:bg-surface-2")}>
                {m}
              </button>
            ))}
          </div>
        </Section>

        <Section title="Storage" description="Images count toward your storage. Links, notes and code don't.">
          <div className="rounded-md border border-border bg-surface px-4 py-3">
            <div className="flex justify-between text-[13.5px]">
              <span>{formatBytes(used)} used</span>
              <span className="text-text-3">of {formatBytes(quota)}</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-3" role="progressbar" aria-valuenow={Math.round(pct)}
              aria-valuemin={0} aria-valuemax={100} aria-label="Storage used">
              <div className={cn("h-full rounded-full", pct > 90 ? "bg-danger" : "bg-accent")} style={{ width: `${pct}%` }} />
            </div>
          </div>
        </Section>

        <Section title="Sessions">
          <Row label="Sign out everywhere" hint="Ends every session, including this one.">
            <Button variant="outline" size="sm" onClick={() => setConfirmOut(true)}>Sign out all</Button>
          </Row>
        </Section>
      </main>

      <Dialog open={confirmForget} onOpenChange={setConfirmForget}>
        <DialogContent title="Forget everything Stash remembers?" description="Answers go back to using only your cards. This does not delete any cards.">
          <div className="flex justify-end gap-2">
            <DialogClose asChild><Button variant="ghost">Cancel</Button></DialogClose>
            <Button variant="danger" loading={forgetAll.isPending} onClick={() => forgetAll.mutate(undefined, {
              onSuccess: () => { setConfirmForget(false); toast.success("Memory cleared"); },
              onError: (e) => toast.error(errorMessage(e)),
            })}>Forget everything</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmOut} onOpenChange={setConfirmOut}>
        <DialogContent title="Sign out everywhere?" description="You'll need to sign in again on every device.">
          <div className="flex justify-end gap-2">
            <DialogClose asChild><Button variant="ghost">Cancel</Button></DialogClose>
            <Button variant="danger" onClick={async () => {
              await api.post("/users/me/logout-all").catch(() => {});
              await api.post("/auth/logout").catch(() => {});
              navigate("/login", { replace: true });
              window.location.reload();
            }}>Sign out all</Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
