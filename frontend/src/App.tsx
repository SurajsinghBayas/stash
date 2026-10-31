import { useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router";
import { Mascot } from "./components/Mascot";
import { setSessionLostHandler } from "./lib/api";
import { keys, useMe } from "./lib/queries";
import { Landing } from "./pages/Landing";
import { CheckEmail, ForgotPassword, Login, ResetPassword, Signup, VerifyEmail } from "./pages/Auth";

// The canvas pulls in React Flow and the markdown renderer; keep them out of the landing page bundle.
const Dashboard = lazy(() => import("./pages/Dashboard"));
const CanvasPage = lazy(() => import("./canvas/CanvasPage"));
const Settings = lazy(() => import("./pages/Settings"));
const Reminders = lazy(() => import("./pages/Reminders"));
const Profile = lazy(() => import("./pages/Profile"));
const About = lazy(() => import("./pages/Info").then((m) => ({ default: m.About })));
const Contact = lazy(() => import("./pages/Info").then((m) => ({ default: m.Contact })));
const Privacy = lazy(() => import("./pages/Info").then((m) => ({ default: m.Privacy })));
const Terms = lazy(() => import("./pages/Info").then((m) => ({ default: m.Terms })));
const SharedCanvas = lazy(() => import("./pages/SharedCanvas"));
const ShareTarget = lazy(() => import("./pages/ShareTarget"));

export function FullPageLoader({ label = "Loading" }: { label?: string }) {
  return (
    <div className="grid min-h-dvh place-items-center" role="status" aria-label={label}>
      <Mascot state="searching" size={48} />
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return <FullPageLoader />;
  if (!me.data) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <>{children}</>;
}

function GuestOnly({ children }: { children: ReactNode }) {
  const me = useMe();
  if (me.isPending) return <FullPageLoader />;
  if (me.data) return <Navigate to="/app" replace />;
  return <>{children}</>;
}

export function App() {
  const qc = useQueryClient();
  const navigate = useNavigate();

  useEffect(() => {
    setSessionLostHandler(() => {
      qc.setQueryData(keys.me, null);
    });
  }, [qc, navigate]);

  return (
    <Suspense fallback={<FullPageLoader />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<GuestOnly><Login /></GuestOnly>} />
        <Route path="/signup" element={<GuestOnly><Signup /></GuestOnly>} />
        <Route path="/check-email" element={<CheckEmail />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/app" element={<RequireAuth><Dashboard /></RequireAuth>} />
        <Route path="/c/:canvasId" element={<RequireAuth><CanvasPage /></RequireAuth>} />
        <Route path="/settings" element={<RequireAuth><Settings /></RequireAuth>} />
        <Route path="/reminders" element={<RequireAuth><Reminders /></RequireAuth>} />
        <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
        <Route path="/share" element={<RequireAuth><ShareTarget /></RequireAuth>} />
        <Route path="/s/:token" element={<SharedCanvas />} />
        <Route path="/about" element={<About />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}

function NotFound() {
  return (
    <div className="grid min-h-dvh place-items-center px-4 text-center">
      <div>
        <Mascot state="sleeping" size={64} />
        <h1 className="mt-4 text-[18px] font-semibold">Nothing here</h1>
        <p className="mt-1 text-text-2">This page doesn't exist, or it was moved.</p>
        <div className="mt-4 flex justify-center gap-4">
          <a href="/" className="text-accent-text underline-offset-4 hover:underline">Home</a>
          <a href="/app" className="text-accent-text underline-offset-4 hover:underline">Your canvases</a>
        </div>
      </div>
    </div>
  );
}
