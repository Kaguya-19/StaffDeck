import { getEnterpriseAuthSession, setEnterpriseAuthSession, type EnterpriseAuthSession } from '../auth';
import { APP_BASE } from '../lib/app-path';
import { ReadBackoff } from './read-backoff';

const readBackoff = new ReadBackoff();

const resolveApiBase = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }

  return APP_BASE;
};

const API_BASE = resolveApiBase();

export const TENANT_ID = import.meta.env.VITE_TENANT_ID || 'tenant_demo';
export const SHOW_DEBUG = import.meta.env.VITE_SHOW_DEBUG === 'true';

export { ApiError } from '../../../packages/staffdeck-business-ui/src/FormalApiError';
import { ApiError } from '../../../packages/staffdeck-business-ui/src/FormalApiError';

export function isAuthError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

let authRefresh: Promise<boolean> | null = null;

export function refreshEnterpriseAuth(): Promise<boolean> {
  if (authRefresh) return authRefresh;
  const previous = getEnterpriseAuthSession();
  if (!previous) return Promise.resolve(false);
  authRefresh = (async () => {
    const response = await fetch(`${API_BASE}/api/auth/refresh`, { method: 'POST', credentials: 'same-origin' });
    if (!response.ok) return false;
    const next = await response.json() as EnterpriseAuthSession;
    if (!next.token || !next.user?.id) return false;
    setEnterpriseAuthSession(next);
    // Never replay one account's operation as another account.
    if (next.user.id !== previous.user.id || next.user.tenant_id !== previous.user.tenant_id) {
      window.location.reload();
      return false;
    }
    return true;
  })().catch(() => false).finally(() => { authRefresh = null; });
  return authRefresh;
}

async function request<T>(path: string, options: RequestInit = {}, retryAuth = true): Promise<T> {
  const reading = !options.method || options.method === 'GET';
  const pollingRead = reading && /^\/api\/chat\/(sessions|handoffs)(?:[/?]|$)/.test(path);
  const blocked = pollingRead ? readBackoff.blocked(path) : null;
  if (blocked) throw blocked;
  let response: Response;
  try { response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeader(),
      ...(options.headers || {}),
    },
    ...options,
  }); } catch (error) {
    if (pollingRead && error instanceof TypeError) readBackoff.failed(path, error);
    throw error;
  }
  if (response.status === 401 && retryAuth && !['/api/auth/login', '/api/auth/refresh', '/api/auth/logout'].includes(path)
    && await refreshEnterpriseAuth()) return request<T>(path, options, false);
  if (!response.ok) {
    const text = await response.text();
    const error = new ApiError(response.status, text, response.statusText);
    if (pollingRead && [502, 503, 504].includes(response.status)) readBackoff.failed(path, error);
    throw error;
  }
  if (pollingRead) readBackoff.succeeded(path);
  const text = await response.text();
  return (text ? JSON.parse(text) : {}) as T;
}

async function keepalivePost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    keepalive: true,
    headers: {
      'Content-Type': 'application/json',
      ...authHeader(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, text, response.statusText);
  }
  const text = await response.text();
  return (text ? JSON.parse(text) : {}) as T;
}

function authHeader(): Record<string, string> {
  const session = getEnterpriseAuthSession();
  return session?.token ? { Authorization: `Bearer ${session.token}` } : {};
}

export const api = {
  get: <T>(path: string, options?: { signal?: AbortSignal }) => request<T>(path, options),
  getWithSignal: <T>(path: string, signal: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  postWithSignal: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body), signal }),
  postKeepalive: <T>(path: string, body?: unknown) => keepalivePost<T>(path, body),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  blob: async (path: string) => {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: {
        ...authHeader(),
      },
    });
    if (!response.ok) {
      const text = await response.text();
      throw new ApiError(response.status, text, response.statusText);
    }
    return response.blob();
  },
  postBlob: async (path: string, body: unknown) => {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeader(),
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new ApiError(response.status, text, response.statusText);
    }
    return response.blob();
  },
  postForm: async <T>(path: string, form: FormData) => {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { ...authHeader() },
      body: form,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new ApiError(response.status, text, response.statusText);
    }
    return (await response.json()) as T;
  },
};

export async function uploadChatAttachments<T>(
  tenantId: string,
  files: File[],
  signal?: AbortSignal,
): Promise<T> {
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  const response = await fetch(`${API_BASE}/api/chat/attachments?tenant_id=${encodeURIComponent(tenantId)}`, {
    method: 'POST',
    headers: { ...authHeader() },
    body: form,
    signal,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, text, response.statusText);
  }
  return response.json() as Promise<T>;
}

export async function streamChatTurn(
  body: Record<string, unknown>,
  onEvent: (item: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamPost('/api/chat/stream', body, onEvent, signal);
}

export type StreamEvent = {
  event: string;
  data: Record<string, unknown>;
};

export async function streamPost(
  path: string,
  body: Record<string, unknown>,
  onEvent: (item: StreamEvent) => void,
  signal?: AbortSignal,
  retryAuth = true,
): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify(body),
    signal,
  });
  if (response.status === 401 && retryAuth && await refreshEnterpriseAuth()) {
    return streamPost(path, body, onEvent, signal, false);
  }
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, text, response.statusText);
  }
  if (!response.body) {
    throw new Error('当前浏览器不支持流式响应');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() || '';
    blocks.forEach((block) => {
      const parsed = parseSseBlock(block);
      if (parsed) onEvent(parsed);
    });
  }

  buffer += decoder.decode();
  const parsed = parseSseBlock(buffer);
  if (parsed) onEvent(parsed);
}

export async function streamGet(
  path: string,
  onEvent: (item: StreamEvent) => void,
  signal?: AbortSignal,
  retryAuth = true,
): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, { headers: { ...authHeader() }, signal });
  if (response.status === 401 && retryAuth && await refreshEnterpriseAuth()) {
    return streamGet(path, onEvent, signal, false);
  }
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, text, response.statusText);
  }
  if (!response.body) {
    throw new Error('当前浏览器不支持流式响应');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() || '';
    blocks.forEach((block) => {
      const parsed = parseSseBlock(block);
      if (parsed) onEvent(parsed);
    });
  }

  buffer += decoder.decode();
  const parsed = parseSseBlock(buffer);
  if (parsed) onEvent(parsed);
}

function parseSseBlock(block: string): StreamEvent | null {
  const lines = block.split('\n').map((line) => line.trimEnd());
  const eventLine = lines.find((line) => line.startsWith('event:'));
  const dataLines = lines.filter((line) => line.startsWith('data:'));
  if (!eventLine || dataLines.length === 0) return null;
  const event = eventLine.replace(/^event:\s*/, '');
  const rawData = dataLines.map((line) => line.replace(/^data:\s*/, '')).join('\n');
  try {
    return { event, data: JSON.parse(rawData) as Record<string, unknown> };
  } catch {
    return { event, data: { raw: rawData } };
  }
}
