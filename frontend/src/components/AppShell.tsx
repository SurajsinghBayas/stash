import {
  Clock01Icon,
  Logout01Icon,
  Moon02Icon,
  Search01Icon,
  Settings01Icon,
  Sun03Icon,
} from "@hugeicons/core-free-icons";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "@/lib/api";
import { keys, useMe } from "@/lib/queries";
import { setMode, useMode } from "@/lib/theme";
import { modKey } from "@/lib/utils";
import { QuickFind } from "./QuickFind";
import { Mascot } from "./Mascot";
import { Button } from "./ui/button";
import { Icon, Kbd, Menu, MenuContent, MenuItem, MenuLabel, MenuSeparator, MenuTrigger } from "./ui/primitives";

export function Avatar({ name, src, size = 28 }: { name: string; src?: string | null; size?: number }) {
  const initials = name.split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((s) => s[0]!.toUpperCase()).join("");
  return src ? (
    <img src={src} alt="" width={size} height={size} referrerPolicy="no-referrer"
      className="rounded-full object-cover ring-1 ring-border" style={{ width: size, height: size }} />
  ) : (
    <span className="grid place-items-center rounded-full bg-surface-3 text-[11px] font-semibold text-text-2"
      style={{ width: size, height: size }}>{initials || "S"}</span>
  );
}

export function AccountMenu() {
  const me = useMe();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const mode = useMode();
  const user = me.data;
  if (!user) return null;
  const name = user.display_name || user.email || "You";

  async function signOut() {
    await api.post("/auth/logout").catch(() => {});
    qc.clear();
    qc.setQueryData(keys.me, null);
    navigate("/login", { replace: true });
  }

  return (
    <Menu>
      <MenuTrigger asChild>
        <button className="rounded-full outline-offset-2" aria-label="Account menu">
          <Avatar name={name} src={user.avatar_url} />
        </button>
      </MenuTrigger>
      <MenuContent className="w-[240px]">
        <MenuLabel>
          <span className="block truncate text-[13px] font-medium text-text">{user.display_name || "Signed in"}</span>
          <span className="block truncate">{user.email}</span>
        </MenuLabel>
        <MenuSeparator />
        <MenuItem icon={Clock01Icon} onSelect={() => navigate("/reminders")}>Reminders</MenuItem>
        <MenuItem icon={Settings01Icon} onSelect={() => navigate("/settings")}>Settings</MenuItem>
        <MenuItem icon={mode === "dark" ? Sun03Icon : Moon02Icon}
          onSelect={() => setMode(mode === "dark" ? "light" : "dark")}>
          {mode === "dark" ? "Light mode" : "Dark mode"}
        </MenuItem>
        <MenuSeparator />
        <MenuItem icon={Logout01Icon} onSelect={signOut}>Sign out</MenuItem>
      </MenuContent>
    </Menu>
  );
}

export function useQuickFindShortcut(open: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        open();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);
}

export function AppShell({ children, title }: { children: ReactNode; title?: ReactNode }) {
  const [findOpen, setFindOpen] = useState(false);
  useQuickFindShortcut(() => setFindOpen(true));
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-20 border-b border-border bg-bg/85 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center gap-3 px-4 sm:px-6">
          <Link to="/app" className="flex items-center gap-2 text-[15px] font-semibold tracking-[-0.02em]" aria-label="Your canvases">
            <Mascot size={26} />
            <span className="hidden sm:inline">Stash</span>
          </Link>
          {title && <span className="text-text-3">/</span>}
          <div className="min-w-0 flex-1 truncate text-[14px] font-medium">{title}</div>
          <Button variant="secondary" size="sm" onClick={() => setFindOpen(true)} className="gap-2 text-text-2"
            aria-label="Find a card">
            <Icon icon={Search01Icon} size={15} />
            <span className="hidden sm:inline">Find</span>
            <Kbd className="hidden sm:inline-flex">{modKey}K</Kbd>
          </Button>
          <AccountMenu />
        </div>
      </header>
      {children}
      <QuickFind open={findOpen} onOpenChange={setFindOpen} />
    </div>
  );
}
