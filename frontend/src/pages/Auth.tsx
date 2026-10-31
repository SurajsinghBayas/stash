import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { Mascot, type MascotState } from "@/components/Mascot";
import { Button } from "@/components/ui/button";
import { FieldError, Input, Label } from "@/components/ui/primitives";
import { api, ApiError, errorMessage } from "@/lib/api";
import { keys, useProviders } from "@/lib/queries";
import { useSeo } from "@/lib/seo";
import type { User } from "@/lib/types";

const OAUTH_ERRORS: Record<string, string> = {
  oauth_state: "That sign-in took too long or was opened in another browser. Try again.",
  oauth_failed: "We couldn't finish signing you in with that provider. Try again.",
  provider_not_configured: "That sign-in option isn't available right now.",
  account_suspended: "This account is suspended.",
};

function AuthLayout({ title, subtitle, mascot = "idle", children, footer }: {
  title: string; subtitle?: ReactNode; mascot?: MascotState; children: ReactNode; footer?: ReactNode;
}) {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-4 py-10">
      <div className="w-full max-w-[380px] animate-[rise_320ms_var(--ease-out)]">
        <Link to="/" className="mb-8 inline-flex" aria-label="Stash home">
          <Mascot state={mascot} size={44} follow />
        </Link>
        <h1 className="text-[22px] font-semibold tracking-[-0.02em]">{title}</h1>
        {subtitle && <p className="mt-1.5 text-[14px] text-text-2">{subtitle}</p>}
        <div className="mt-7">{children}</div>
        {footer && <div className="mt-6 text-[13.5px] text-text-2">{footer}</div>}
      </div>
    </main>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 24 24" className="size-[18px]" aria-hidden="true">
      <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5a5.6 5.6 0 0 1-2.4 3.6v3h3.9c2.2-2.1 3.5-5.1 3.5-8.8Z" />
      <path fill="#34A853" d="M12 24c3.2 0 6-1.1 8-2.9l-3.9-3c-1.1.7-2.5 1.2-4.1 1.2-3.1 0-5.8-2.1-6.7-5H1.3v3.1A12 12 0 0 0 12 24Z" />
      <path fill="#FBBC05" d="M5.3 14.3a7.2 7.2 0 0 1 0-4.6V6.6h-4a12 12 0 0 0 0 10.8l4-3.1Z" />
      <path fill="#EA4335" d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4A12 12 0 0 0 1.3 6.6l4 3.1c.9-2.9 3.6-4.9 6.7-4.9Z" />
    </svg>
  );
}

function XMark() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden="true">
      <path fill="currentColor" d="M18.2 2.25h3.3l-7.2 8.26 8.5 11.24h-6.7l-5.2-6.8-6 6.8H1.6l7.7-8.84L1.2 2.25H8l4.7 6.23 5.5-6.23Zm-1.2 17.52h1.8L7.1 4.13H5.1l11.9 15.64Z" />
    </svg>
  );
}

function OAuthButtons() {
  const providers = useProviders();
  if (!providers.data || (!providers.data.google && !providers.data.x)) return null;
  return (
    <>
      <div className="grid gap-2">
        {providers.data.google && (
          <Button asChild variant="outline" size="lg" className="w-full">
            <a href="/api/v1/auth/oauth/google/start"><GoogleMark /> Continue with Google</a>
          </Button>
        )}
        {providers.data.x && (
          <Button asChild variant="outline" size="lg" className="w-full">
            <a href="/api/v1/auth/oauth/x/start"><XMark /> Continue with X</a>
          </Button>
        )}
      </div>
      <div className="my-6 flex items-center gap-3 text-[12px] text-text-3">
        <span className="h-px flex-1 bg-border" />or<span className="h-px flex-1 bg-border" />
      </div>
    </>
  );
}

function useSignedIn() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  return (user: User) => {
    qc.setQueryData(keys.me, user);
    const next = params.get("next");
    navigate(next && next.startsWith("/") && !next.startsWith("//") ? next : "/app", { replace: true });
  };
}

export function Login() {
  useSeo({ title: "Sign in", path: "/login", description: "Sign in to Stash with Google, X or email." });
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(OAUTH_ERRORS[params.get("error") ?? ""] ?? null);
  const [unverified, setUnverified] = useState(false);
  const [busy, setBusy] = useState(false);
  const signedIn = useSignedIn();
  const navigate = useNavigate();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      signedIn((await api.post<{ data: User }>("/auth/login", { email, password })).data);
    } catch (err) {
      setUnverified(err instanceof ApiError && err.code === "email_not_verified");
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    await api.post("/auth/verify-email/resend", { email }).catch(() => {});
    navigate(`/check-email?email=${encodeURIComponent(email)}`);
  }

  return (
    <AuthLayout title="Sign in to Stash" mascot={error ? "blocked" : "idle"}
      footer={<>New here? <Link to="/signup" className="text-text underline-offset-4 hover:underline">Create an account</Link></>}>
      <OAuthButtons />
      <form onSubmit={submit} noValidate className="grid gap-4">
        <div>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" required value={email} autoFocus
            onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="password"
            hint={<Link to="/forgot-password" className="text-[12.5px] text-text-3 hover:text-text">Forgot password?</Link>}>
            Password
          </Label>
          <Input id="password" type="password" autoComplete="current-password" required value={password}
            onChange={(e) => setPassword(e.target.value)} aria-invalid={!!error} aria-describedby="login-error" />
          <FieldError id="login-error">{error}</FieldError>
          {unverified && (
            <Button type="button" variant="link" className="mt-1 text-[13px]" onClick={resend}>Send a new confirmation email</Button>
          )}
        </div>
        <Button type="submit" variant="primary" size="lg" loading={busy} className="mt-1 w-full">Sign in</Button>
      </form>
    </AuthLayout>
  );
}

export function Signup() {
  useSeo({ title: "Create your free account", path: "/signup",
    description: "Create a free Stash account. Save links, notes, code and images on one canvas and ask it anything." });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const tooShort = password.length > 0 && password.length < 10;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password.length < 10) return setError("Use at least 10 characters.");
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/signup", { email, password, display_name: name || null });
      navigate(`/check-email?email=${encodeURIComponent(email)}`);
    } catch (err) {
      setError(err instanceof ApiError && err.code === "email_taken"
        ? "There's already an account with this email. Sign in instead." : errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Create your Stash" subtitle="One place for every link, note and snippet you mean to come back to."
      footer={<>
        Have an account? <Link to="/login" className="text-text underline-offset-4 hover:underline">Sign in</Link>
        <p className="mt-4 text-[12.5px] text-text-3">
          By continuing you agree to the <Link to="/terms" className="underline underline-offset-2 hover:text-text">Terms</Link> and{" "}
          <Link to="/privacy" className="underline underline-offset-2 hover:text-text">Privacy policy</Link>.
        </p>
      </>}>
      <OAuthButtons />
      <form onSubmit={submit} noValidate className="grid gap-4">
        <div>
          <Label htmlFor="name" hint={<span className="text-[12px] text-text-3">Optional</span>}>Name</Label>
          <Input id="name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
        </div>
        <div>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" autoComplete="new-password" required value={password}
            onChange={(e) => setPassword(e.target.value)} aria-invalid={tooShort || !!error} aria-describedby="pw-help signup-error" />
          <p id="pw-help" className={`mt-1.5 text-[12.5px] ${tooShort ? "text-warning" : "text-text-3"}`}>At least 10 characters.</p>
          <FieldError id="signup-error">{error}</FieldError>
        </div>
        <Button type="submit" variant="primary" size="lg" loading={busy} className="mt-1 w-full">Create account</Button>
      </form>
    </AuthLayout>
  );
}

export function CheckEmail() {
  const [params] = useSearchParams();
  const email = params.get("email") ?? "";
  const [sent, setSent] = useState(false);
  return (
    <AuthLayout title="Check your email" mascot="checking"
      subtitle={<>We sent a confirmation link to <span className="text-text">{email || "your inbox"}</span>. It works for 24 hours.</>}
      footer={<Link to="/login" className="hover:text-text">Back to sign in</Link>}>
      {email && (
        <Button variant="secondary" disabled={sent} onClick={async () => {
          await api.post("/auth/verify-email/resend", { email }).catch(() => {});
          setSent(true);
        }}>
          {sent ? "Sent. Check spam too." : "Send it again"}
        </Button>
      )}
    </AuthLayout>
  );
}

export function VerifyEmail() {
  const [params] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const signedIn = useSignedIn();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // StrictMode runs effects twice; the token works once
    started.current = true;
    const token = params.get("token");
    if (!token) return setError("This link is missing its token.");
    api.post<{ data: User }>("/auth/verify-email", { token })
      .then((r) => signedIn(r.data))
      .catch((e) => setError(errorMessage(e)));
  }, [params, signedIn]);

  if (error)
    return (
      <AuthLayout title="That link didn't work" mascot="blocked" subtitle={error}
        footer={<Link to="/login" className="hover:text-text">Sign in to get a new link</Link>}>
        {null}
      </AuthLayout>
    );
  return <AuthLayout title="Confirming your email…" mascot="searching">{null}</AuthLayout>;
}

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/password/forgot", { email });
      setSent(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (sent)
    return (
      <AuthLayout title="Check your email" mascot="checking"
        subtitle="If there's an account for that address, a reset link is on its way. It works once, for 30 minutes."
        footer={<Link to="/login" className="hover:text-text">Back to sign in</Link>}>
        {null}
      </AuthLayout>
    );
  return (
    <AuthLayout title="Reset your password" subtitle="We'll email you a link to choose a new one."
      footer={<Link to="/login" className="hover:text-text">Back to sign in</Link>}>
      <form onSubmit={submit} noValidate className="grid gap-4">
        <div>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" required autoFocus value={email}
            onChange={(e) => setEmail(e.target.value)} aria-describedby="forgot-error" />
          <FieldError id="forgot-error">{error}</FieldError>
        </div>
        <Button type="submit" variant="primary" size="lg" loading={busy} className="w-full">Send reset link</Button>
      </form>
    </AuthLayout>
  );
}

export function ResetPassword() {
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const signedIn = useSignedIn();

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password.length < 10) return setError("Use at least 10 characters.");
    setBusy(true);
    try {
      signedIn((await api.post<{ data: User }>("/auth/password/reset", { token: params.get("token"), password })).data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Choose a new password" subtitle="You'll be signed out on your other devices.">
      <form onSubmit={submit} noValidate className="grid gap-4">
        <div>
          <Label htmlFor="password">New password</Label>
          <Input id="password" type="password" autoComplete="new-password" autoFocus value={password}
            onChange={(e) => setPassword(e.target.value)} aria-describedby="reset-error" />
          <FieldError id="reset-error">{error}</FieldError>
        </div>
        <Button type="submit" variant="primary" size="lg" loading={busy} className="w-full">Save password</Button>
      </form>
    </AuthLayout>
  );
}
