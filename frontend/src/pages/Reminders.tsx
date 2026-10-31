import { Add01Icon, Cancel01Icon } from "@hugeicons/core-free-icons";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Mascot } from "@/components/Mascot";
import { Button } from "@/components/ui/button";
import { Icon, Tip } from "@/components/ui/primitives";
import { ReminderDialog } from "@/canvas/ReminderDialog";
import { errorMessage } from "@/lib/api";
import { useCancelReminder, useReminders } from "@/lib/queries";
import type { Reminder } from "@/lib/types";
import { cn, formatWhen, timeAgo } from "@/lib/utils";

function ReminderRow({ r, past }: { r: Reminder; past?: boolean }) {
  const cancel = useCancelReminder();
  const href = r.canvas_id ? `/c/${r.canvas_id}${r.item_id ? `?item=${r.item_id}` : ""}` : null;
  const title = r.note || (r.item_id ? "Card reminder" : "Reminder");
  return (
    <li className="flex items-center gap-4 rounded-md border border-border bg-surface px-4 py-3">
      <div className="w-[120px] shrink-0 text-[12.5px] tabular text-text-2 sm:w-[170px]">{formatWhen(r.remind_at)}</div>
      <div className="min-w-0 flex-1">
        {href ? (
          <Link to={href} className="block truncate text-[14px] font-medium hover:underline underline-offset-4">{title}</Link>
        ) : (
          <span className="block truncate text-[14px] font-medium">{title}</span>
        )}
        <span className="text-[12px] text-text-3">
          {past ? (r.state === "sent" ? `Emailed ${timeAgo(r.sent_at ?? r.remind_at)}` : r.state) : timeAgo(r.remind_at)}
        </span>
      </div>
      {!past && (
        <Tip label="Cancel reminder">
          <Button variant="ghost" size="icon-sm" aria-label={`Cancel reminder: ${title}`} loading={cancel.isPending}
            onClick={() => cancel.mutate(r.id, { onSuccess: () => toast("Reminder cancelled"), onError: (e) => toast.error(errorMessage(e)) })}>
            {!cancel.isPending && <Icon icon={Cancel01Icon} size={16} />}
          </Button>
        </Tip>
      )}
    </li>
  );
}

export default function Reminders() {
  const [tab, setTab] = useState<"pending" | "sent">("pending");
  const list = useReminders(tab);
  const [creating, setCreating] = useState(false);
  const rows = list.data?.data ?? [];

  return (
    <AppShell title="Reminders">
      <main className="mx-auto max-w-[760px] px-4 pb-24 pt-8 sm:px-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-[22px] font-semibold tracking-[-0.02em]">Reminders</h1>
            <p className="mt-1 text-[13.5px] text-text-2">Stash emails you at the time you set. Set one from any card, or a plain one here.</p>
          </div>
          <Button variant="primary" onClick={() => setCreating(true)}><Icon icon={Add01Icon} size={16} /> New</Button>
        </div>

        <div className="mt-6 inline-flex rounded-md bg-surface-2 p-1" role="tablist">
          {(["pending", "sent"] as const).map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
              className={cn("h-7 rounded-[7px] px-3 text-[13px] font-medium", tab === t ? "bg-surface-3 text-text shadow-sm" : "text-text-2")}>
              {t === "pending" ? "Upcoming" : "Sent"}
            </button>
          ))}
        </div>

        {list.isPending ? (
          <ul className="mt-4 grid gap-2">{[0, 1, 2].map((i) => <li key={i} className="shimmer h-[62px] rounded-md" />)}</ul>
        ) : rows.length === 0 ? (
          <div className="mt-14 flex flex-col items-center text-center">
            <Mascot state="sleeping" size={56} />
            <p className="mt-4 text-[14px] text-text-2">
              {tab === "pending" ? "Nothing coming up. Select a card and choose “Remind me”." : "No reminders sent yet."}
            </p>
          </div>
        ) : (
          <ul className="mt-4 grid gap-2">{rows.map((r) => <ReminderRow key={r.id} r={r} past={tab === "sent"} />)}</ul>
        )}
      </main>
      <ReminderDialog item={null} open={creating} onOpenChange={setCreating} />
    </AppShell>
  );
}
