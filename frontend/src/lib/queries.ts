import { QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "./api";
import type {
  Canvas, DeletedCanvas, Hit, Inbound, Item, ItemVersion, MemoryFact, Page, Profile, Reminder, Template, Usage, User,
} from "./types";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (count, e) => !(e instanceof ApiError && e.status >= 400 && e.status < 500) && count < 2,
    },
  },
});

export const keys = {
  me: ["me"] as const,
  canvases: (q = "") => ["canvases", q] as const,
  canvas: (id: string) => ["canvas", id] as const,
  items: (id: string) => ["items", id] as const,
  reminders: (state: string) => ["reminders", state] as const,
  storage: ["storage"] as const,
  usage: ["usage"] as const,
  providers: ["providers"] as const,
  profile: ["profile"] as const,
  templates: ["templates"] as const,
  canvasTrash: ["canvas-trash"] as const,
  itemTrash: (id: string) => ["item-trash", id] as const,
  versions: (id: string) => ["versions", id] as const,
  inbound: ["inbound"] as const,
};

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        return (await api.get<{ data: User }>("/users/me")).data;
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: 5 * 60_000,
  });
}

export function useProviders() {
  return useQuery({
    queryKey: keys.providers,
    queryFn: async () => (await api.get<{ data: { google: boolean; x: boolean } }>("/auth/providers")).data,
    staleTime: Infinity,
  });
}

export function useCanvases(q: string) {
  return useQuery({
    queryKey: keys.canvases(q),
    queryFn: ({ signal }) =>
      api.get<Page<Canvas>>(`/canvases?limit=60${q ? `&q=${encodeURIComponent(q)}` : ""}`, signal),
    placeholderData: (prev) => prev,
  });
}

export function useCanvas(id: string) {
  return useQuery({
    queryKey: keys.canvas(id),
    queryFn: async () => (await api.get<{ data: Canvas }>(`/canvases/${id}`)).data,
  });
}

export async function fetchAllItems(canvasId: string, signal?: AbortSignal): Promise<Item[]> {
  const out: Item[] = [];
  let cursor: string | null = null;
  do {
    const qs: string = cursor ? `&cursor=${cursor}` : "";
    const page: Page<Item> = await api.get<Page<Item>>(`/canvases/${canvasId}/items?limit=2000${qs}`, signal);
    out.push(...page.data);
    cursor = page.page.next_cursor;
  } while (cursor);
  return out;
}

export function useCreateCanvas() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ title, template }: { title: string; template?: string }) =>
      (await api.post<{ data: Canvas }>("/canvases", template ? { title, template } : { title })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["canvases"] }),
  });
}

export function useRenameCanvas() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, title }: { id: string; title: string }) =>
      (await api.patch<{ data: Canvas }>(`/canvases/${id}`, { title })).data,
    onSuccess: (c) => {
      qc.setQueryData(keys.canvas(c.id), c);
      qc.invalidateQueries({ queryKey: ["canvases"] });
    },
  });
}

export function useDeleteCanvas() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/canvases/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["canvases"] });
      qc.invalidateQueries({ queryKey: keys.canvasTrash });
    },
  });
}

export function useTemplates() {
  return useQuery({
    queryKey: keys.templates,
    queryFn: async () => (await api.get<{ data: Template[] }>("/canvases/templates")).data,
    staleTime: Infinity,
  });
}

export function useCanvasTrash() {
  return useQuery({
    queryKey: keys.canvasTrash,
    queryFn: async () => (await api.get<{ data: DeletedCanvas[] }>("/canvases/trash")).data,
  });
}

export function useRestoreCanvas() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await api.post<{ data: Canvas }>(`/canvases/${id}/restore`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["canvases"] });
      qc.invalidateQueries({ queryKey: keys.canvasTrash });
    },
  });
}

export function useItemTrash(canvasId: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.itemTrash(canvasId),
    queryFn: async () => (await api.get<{ data: (Item & { deleted_at: string })[] }>(`/canvases/${canvasId}/trash`)).data,
    enabled,
    staleTime: 0,
  });
}

export function useVersions(itemId: string | null) {
  return useQuery({
    queryKey: keys.versions(itemId ?? ""),
    queryFn: async () => (await api.get<{ data: ItemVersion[] }>(`/items/${itemId}/versions`)).data,
    enabled: !!itemId,
    staleTime: 0,
  });
}

export function useInbound() {
  return useQuery({
    queryKey: keys.inbound,
    queryFn: async () => (await api.get<{ data: Inbound }>("/users/me/inbound")).data,
  });
}

export function useRotateInbound() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => (await api.post<{ data: Inbound }>("/users/me/inbound")).data,
    onSuccess: (d) => qc.setQueryData(keys.inbound, d),
  });
}

export async function quickFind(q: string, signal?: AbortSignal): Promise<Hit[]> {
  return (await api.get<{ data: Hit[] }>(`/search?q=${encodeURIComponent(q)}&limit=20`, signal)).data;
}

export function useReminders(state: "pending" | "sent" | "all") {
  return useQuery({
    queryKey: keys.reminders(state),
    queryFn: ({ signal }) => api.get<Page<Reminder>>(`/reminders?state=${state}&limit=100`, signal),
  });
}

export function useCreateReminder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { remind_at: string; item_id?: string | null; note?: string }) =>
      (await api.post<{ data: Reminder }>("/reminders", body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reminders"] }),
  });
}

export function useCancelReminder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/reminders/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reminders"] }),
  });
}

export function useUpdateMe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (patch: Partial<User>) => (await api.patch<{ data: User }>("/users/me", patch)).data,
    onSuccess: (u) => qc.setQueryData(keys.me, u),
  });
}

export function useMemories() {
  return useQuery({
    queryKey: ["memories"],
    queryFn: async () => (await api.get<{ data: MemoryFact[] }>("/users/me/memories")).data,
  });
}

export function useForgetMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/users/me/memories/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["memories"] }),
  });
}

export function useForgetAllMemories() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.del("/users/me/memories"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["memories"] }),
  });
}

export function useUsage() {
  return useQuery({
    queryKey: keys.usage,
    queryFn: async () => (await api.get<{ data: Usage }>("/users/me/usage")).data,
  });
}

export function useStorage() {
  return useQuery({
    queryKey: keys.storage,
    queryFn: async () =>
      (await api.get<{ data: { used_bytes: number; quota_bytes: number } }>("/users/me/storage")).data,
  });
}

export function useProfile() {
  return useQuery({
    queryKey: keys.profile,
    queryFn: async () => (await api.get<{ data: Profile }>("/users/me/profile")).data,
  });
}
