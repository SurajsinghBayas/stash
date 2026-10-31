import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";
import { Spinner } from "./spinner";

const button = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium select-none " +
    "transition-[background-color,color,box-shadow,transform] duration-150 ease-[var(--ease-out)] " +
    "active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-accent text-accent-fg hover:bg-accent-hover",
        secondary: "bg-surface-2 text-text shadow-sm hover:bg-surface-3",
        ghost: "text-text-2 hover:bg-surface-2 hover:text-text",
        outline: "border border-border-strong text-text hover:bg-surface-2",
        danger: "bg-danger text-white hover:opacity-90",
        link: "text-accent-text underline-offset-4 hover:underline px-0 h-auto",
      },
      size: {
        sm: "h-8 rounded-[8px] px-3 text-[13px]",
        md: "h-9 rounded-md px-3.5 text-[13.5px]",
        lg: "h-11 rounded-md px-5 text-[15px]",
        icon: "size-9 rounded-md",
        "icon-sm": "size-8 rounded-[8px]",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {
  asChild?: boolean;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, loading, children, disabled, ...props }, ref) => {
    const Comp = asChild ? Slot.Root : "button";
    return (
      <Comp
        ref={ref}
        className={cn(button({ variant, size }), className)}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...props}
      >
        {loading ? (
          <>
            <Spinner className="size-4" />
            <span className="sr-only">Working…</span>
            {children}
          </>
        ) : (
          children
        )}
      </Comp>
    );
  },
);
Button.displayName = "Button";
