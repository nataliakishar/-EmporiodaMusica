export type Source = Record<string, unknown>;
export type Answer = { text: string; tools: string[]; sources: Source[] };
export type Session = { session_id: string; session_token: string; privacy_notice: string };
export type Contacts = { name: string; phone: string; email: string };
export type ApiResponse = {
  code: string;
  message?: string;
  answer?: Answer;
  registration?: { code: string; message: string; registration_id?: string };
  registration_confirmed?: boolean;
};

const configuredBase = process.env.NEXT_PUBLIC_API_URL?.trim();

export class ApiError extends Error {
  constructor(public code: string, message: string, public status = 0,
              public registered = false, public retryAfter?: number) { super(message); }
}

function apiBase() {
  const localPage = typeof window !== "undefined" && ["127.0.0.1", "localhost", "[::1]"].includes(window.location.hostname);
  if (!configuredBase && !localPage) {
    throw new ApiError("api_not_configured", "O atendimento online está em preparação. A conexão com a IA ainda não foi publicada.");
  }
  let url: URL;
  try { url = new URL(configuredBase || "http://127.0.0.1:8000"); }
  catch { throw new ApiError("api_not_configured", "A conexão do atendimento precisa ser configurada pela loja."); }
  const localApi = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (url.username || url.password || url.search || url.hash ||
      (url.protocol !== "https:" && !(localPage && localApi && url.protocol === "http:")) ||
      (!localPage && localApi)) {
    throw new ApiError("api_not_configured", "A conexão pública do atendimento precisa de um endereço HTTPS da loja.");
  }
  return url.toString().replace(/\/+$/, "");
}

async function request<T>(path: string, session?: Session, payload?: unknown, method = "POST"): Promise<T> {
  const base = apiBase();
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      method,
      headers: { "Content-Type": "application/json", ...(session ? { Authorization: `Bearer ${session.session_token}` } : {}) },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      cache: "no-store",
      signal: AbortSignal.timeout(240_000),
    });
  } catch {
    throw new ApiError("network_error", "Não recebemos a confirmação da API. Confira sua conexão e tente novamente. Nenhum reenvio foi feito automaticamente.");
  }
  let data;
  try { data = await response.json(); } catch { throw new ApiError("invalid_response", "O atendimento retornou uma resposta inesperada. Tente novamente."); }
  if (!response.ok) {
    const seconds = Number(response.headers.get("Retry-After"));
    throw new ApiError(typeof data.code === "string" ? data.code : "api_error",
      typeof data.message === "string" ? data.message : "Não foi possível concluir o atendimento.",
      response.status, data.registration_confirmed === true,
      Number.isFinite(seconds) && seconds > 0 ? seconds : undefined);
  }
  if (!data || typeof data.code !== "string") throw new ApiError("invalid_response", "O atendimento retornou uma resposta inesperada.");
  return data as T;
}

export async function openSession(): Promise<Session> {
  const session = await request<Session>("/sessions");
  if (!session.session_id || !session.session_token || !session.privacy_notice) throw new ApiError("invalid_response", "Não foi possível abrir a conversa.");
  return session;
}
export function sendMessage(session: Session, message: string) {
  return request<ApiResponse>(`/sessions/${session.session_id}/messages`, session, { message });
}
export function confirmContacts(session: Session, contacts: Contacts) {
  return request<ApiResponse>(`/sessions/${session.session_id}/registration`, session, { ...contacts, confirmed: true });
}
export function clearContext(session: Session) {
  return request<ApiResponse>(`/sessions/${session.session_id}/clear`, session);
}
export function closeSession(session: Session) {
  return request<ApiResponse>(`/sessions/${session.session_id}`, session, undefined, "DELETE");
}
