import { useEffect, useMemo, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, Input, Label, Textarea } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api";
import { useCreateReminder } from "@/lib/queries";
import type { Item } from "@/lib/types";
import { cn, formatWhen, toOffsetISO } from "@/lib/utils";

function at(base: Date, days: number, hour: number, minute = 0) {
  const d = new Date(base);
  d.setDate(d.getDate() + days);
  d.setHours(hour, minute, 0, 0);
  return d;
}

function presets(now = new Date()) {
  const inHour = new Date(now.getTime() + 60 * 60 * 1000);
  inHour.setSeconds(0, 0);
  const evening = at(now, now.getHours() >= 17 ? 1 : 0, 18);
  const tomorrow = at(now, 1, 9);
  const monday = at(now, ((8 - now.getDay()) % 7) || 7, 9);
  return [
    { label: "In 1 hour", date: inHour },
    { label: now.getHours() >= 17 ? "Tomorrow evening" : "This evening", date: evening },
    { label: "Tomorrow morning", date: tomorrow },
    { label: "Next Monday", date: monday },
  ];
}

function localInputValue(d: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function ReminderDialog({ item, open, onOpenChange }: {
  item: Item | null; open: boolean; onOpenChange: (v: boolean) => void;
}) {
  const options = useMemo(() => presets(), [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const [choice, setChoice] = useState<number | "custom">(2);
  const [custom, setCustom] = useState("");
  const [note, setNote] = useState("");
  const create = useCreateReminder();

  useEffect(() => {
    if (open) {
      setChoice(2);
      setNote("");
      setCustom(localInputValue(options[2]!.date));
    }
  }, [open, options]);

  const when = choice === "custom" ? (custom ? new Date(custom) : null) : options[choice]!.date;
  const valid = !!when && !Number.isNaN(when.getTime()) && when.getTime() > Date.now() + 30_000 && (!!item || !!note.trim());

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!when || !valid) return;
    try {
      await create.mutateAsync({ remind_at: toOffsetISO(when), item_id: item?.id ?? null, note: note.trim() });
      toast.success(`We'll email you ${formatWhen(when.toISOString())}`);
      onOpenChange(false);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Remind me"
        description={item ? "Stash emails you about this card at the time you pick." : "Stash emails you at the time you pick."}>
        <form onSubmit={submit} className="grid gap-4">
          <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="When">
            {options.map((o, i) => (
              <button key={o.label} type="button" role="radio" aria-checked={choice === i} onClick={() => setChoice(i)}
                className={cn("rounded-md border px-3 py-2 text-left transition-colors",
                  choice === i ? "border-accent bg-accent-soft" : "border-border hover:border-border-strong hover:bg-surface-2")}>
                <span className="block text-[13.5px] font-medium">{o.label}</span>
                <span className="block text-[12px] text-text-3">{formatWhen(o.date.toISOString())}</span>
              </button>
            ))}
          </div>
          <div>
            <Label htmlFor="remind-custom">Or pick a time</Label>
            <Input id="remind-custom" type="datetime-local" value={custom} min={localInputValue(new Date())}
              onChange={(e) => { setCustom(e.target.value); setChoice("custom"); }}
              onFocus={() => setChoice("custom")} aria-invalid={choice === "custom" && !valid} />
          </div>
          <div>
            <Label htmlFor="remind-note" hint={item ? <span className="text-[12px] text-text-3">Optional</span> : undefined}>
              Note to self
            </Label>
            <Textarea id="remind-note" rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Reply before the call" />
          </div>
          <div className="flex items-center justify-end gap-2">
            <DialogClose asChild><Button variant="ghost">Cancel</Button></DialogClose>
            <Button type="submit" variant="primary" loading={create.isPending} disabled={!valid}>Set reminder</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
