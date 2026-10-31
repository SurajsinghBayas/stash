/** Small shadcn-style primitives on Radix, styled with Graphite tokens. */
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react";
import { Cancel01Icon } from "@hugeicons/core-free-icons";
import {
  Dialog as DialogPrimitive,
  DropdownMenu as MenuPrimitive,
  Popover as PopoverPrimitive,
  Switch as SwitchPrimitive,
  Tooltip as TooltipPrimitive,
} from "radix-ui";
import {
  forwardRef,
  type ComponentPropsWithoutRef,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";
import { cn } from "@/lib/utils";

/* ---------- Icon ---------- */
export function Icon({ icon, size = 18, className, strokeWidth = 1.75 }: {
  icon: IconSvgElement; size?: number; className?: string; strokeWidth?: number;
}) {
  return <HugeiconsIcon icon={icon} size={size} strokeWidth={strokeWidth} className={className} aria-hidden />;
}

/* ---------- Input / Textarea / Label ---------- */
const field =
  "w-full rounded-md bg-surface-2 border border-border px-3 text-[14px] text-text placeholder:text-text-3 " +
  "transition-[border-color,box-shadow] duration-150 outline-none hover:border-border-strong " +
  "focus:border-accent focus:ring-[3px] focus:ring-accent-soft aria-[invalid=true]:border-danger";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => <input ref={ref} className={cn(field, "h-10", className)} {...props} />,
);
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => <textarea ref={ref} className={cn(field, "py-2 resize-none", className)} {...props} />,
);
Textarea.displayName = "Textarea";

export function Label({ htmlFor, children, hint }: { htmlFor: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="mb-1.5 flex items-baseline justify-between">
      <label htmlFor={htmlFor} className="text-[13px] font-medium text-text-2">{children}</label>
      {hint}
    </div>
  );
}

export function FieldError({ id, children }: { id: string; children?: ReactNode }) {
  if (!children) return null;
  return <p id={id} role="alert" className="mt-1.5 text-[12.5px] text-danger">{children}</p>;
}

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd className={cn("inline-flex h-5 min-w-5 items-center justify-center rounded-[5px] border border-border-strong " +
      "bg-surface-2 px-1 font-mono text-[11px] text-text-3", className)}>{children}</kbd>
  );
}

/* ---------- Tooltip ---------- */
export const TooltipProvider = TooltipPrimitive.Provider;

export function Tip({ label, side = "top", children, kbd }: {
  label: ReactNode; side?: "top" | "bottom" | "left" | "right"; children: ReactNode; kbd?: string;
}) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content side={side} sideOffset={8}
          className="z-[70] flex items-center gap-2 rounded-[8px] bg-text px-2 py-1 text-[12px] font-medium text-bg shadow-md
            data-[state=delayed-open]:animate-[pop_160ms_var(--ease-out)]">
          {label}
          {kbd && <span className="font-mono text-[11px] opacity-60">{kbd}</span>}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

/* ---------- Dialog ---------- */
export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({ title, description, children, className, hideClose }: {
  title: ReactNode; description?: ReactNode; children: ReactNode; className?: string; hideClose?: boolean;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-[2px]
        data-[state=open]:animate-[fade-in_200ms_var(--ease-out)] data-[state=closed]:animate-[fade-out_150ms_ease-in]" />
      <DialogPrimitive.Content
        className={cn("fixed left-1/2 top-1/2 z-[60] w-[calc(100vw-32px)] max-w-[440px] -translate-x-1/2 -translate-y-1/2 " +
          "rounded-xl border border-border bg-surface p-5 shadow-lg outline-none " +
          "data-[state=open]:animate-[dialog-in_220ms_var(--ease-out)] data-[state=closed]:animate-[fade-out_150ms_ease-in]",
          className)}>
        <div className="mb-4 pr-8">
          <DialogPrimitive.Title className="text-[16px] font-semibold tracking-[-0.01em]">{title}</DialogPrimitive.Title>
          {description ? (
            <DialogPrimitive.Description className="mt-1 text-[13.5px] text-text-2">{description}</DialogPrimitive.Description>
          ) : (
            <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
          )}
        </div>
        {children}
        {!hideClose && (
          <DialogPrimitive.Close aria-label="Close"
            className="absolute right-3 top-3 grid size-8 place-items-center rounded-[8px] text-text-3 hover:bg-surface-2 hover:text-text">
            <Icon icon={Cancel01Icon} size={16} />
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

/* ---------- Dropdown menu ---------- */
export const Menu = MenuPrimitive.Root;
export const MenuTrigger = MenuPrimitive.Trigger;

export function MenuContent({ children, align = "end", className }: {
  children: ReactNode; align?: "start" | "end" | "center"; className?: string;
}) {
  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Content align={align} sideOffset={6}
        className={cn("z-[65] min-w-[200px] rounded-lg border border-border bg-surface p-1 shadow-lg " +
          "origin-[var(--radix-dropdown-menu-content-transform-origin)] data-[state=open]:animate-[pop_160ms_var(--ease-out)]",
          className)}>
        {children}
      </MenuPrimitive.Content>
    </MenuPrimitive.Portal>
  );
}

export const MenuItem = forwardRef<HTMLDivElement, ComponentPropsWithoutRef<typeof MenuPrimitive.Item> & {
  icon?: IconSvgElement; danger?: boolean; shortcut?: string;
}>(({ className, icon, danger, shortcut, children, ...props }, ref) => (
  <MenuPrimitive.Item ref={ref}
    className={cn("flex h-8 cursor-default select-none items-center gap-2.5 rounded-[7px] px-2 text-[13.5px] outline-none " +
      "data-[highlighted]:bg-surface-2 data-[disabled]:opacity-50", danger ? "text-danger" : "text-text", className)}
    {...props}>
    {icon && <Icon icon={icon} size={16} className={danger ? "" : "text-text-2"} />}
    <span className="flex-1">{children}</span>
    {shortcut && <span className="font-mono text-[11px] text-text-3">{shortcut}</span>}
  </MenuPrimitive.Item>
));
MenuItem.displayName = "MenuItem";

export function MenuSeparator() {
  return <MenuPrimitive.Separator className="my-1 h-px bg-border" />;
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <MenuPrimitive.Label className="px-2 pb-1 pt-1.5 text-[12px] text-text-3">{children}</MenuPrimitive.Label>;
}

/* ---------- Popover ---------- */
export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;
export const PopoverAnchor = PopoverPrimitive.Anchor;

export function PopoverContent({ children, className, side = "bottom", align = "center" }: {
  children: ReactNode; className?: string; side?: "top" | "bottom" | "left" | "right"; align?: "start" | "center" | "end";
}) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content side={side} align={align} sideOffset={8}
        className={cn("z-[65] rounded-lg border border-border bg-surface p-3 shadow-lg outline-none " +
          "origin-[var(--radix-popover-content-transform-origin)] data-[state=open]:animate-[pop_160ms_var(--ease-out)]",
          className)}>
        {children}
      </PopoverPrimitive.Content>
    </PopoverPrimitive.Portal>
  );
}

/* ---------- Switch ---------- */
export function Switch({ id, checked, onCheckedChange, disabled }: {
  id?: string; checked: boolean; onCheckedChange: (v: boolean) => void; disabled?: boolean;
}) {
  return (
    <SwitchPrimitive.Root id={id} checked={checked} onCheckedChange={onCheckedChange} disabled={disabled}
      className="relative h-[22px] w-[38px] shrink-0 rounded-full bg-surface-3 transition-colors duration-200
        data-[state=checked]:bg-accent disabled:opacity-50">
      <SwitchPrimitive.Thumb className="block size-[18px] translate-x-[2px] rounded-full bg-white shadow-sm
        transition-transform duration-200 ease-[var(--ease-out)] data-[state=checked]:translate-x-[18px]" />
    </SwitchPrimitive.Root>
  );
}
