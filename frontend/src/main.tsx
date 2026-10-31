import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { Toaster } from "sonner";
import { App } from "./App";
import { TooltipProvider } from "./components/ui/primitives";
import { queryClient } from "./lib/queries";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <TooltipProvider delayDuration={400} skipDelayDuration={200}>
          <App />
          <Toaster
            position="bottom-right"
            toastOptions={{
              className: "!bg-surface !text-text !border-border !shadow-lg !rounded-lg !font-sans !text-[13.5px]",
            }}
          />
        </TooltipProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
