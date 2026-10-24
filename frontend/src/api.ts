// Cliente HTTP único: toda llamada a la API pasa por request().

// Se incrusta en el build: cambiarla exige recompilar el front.
export const API_URL = import.meta.env.VITE_API_URL;

if (!API_URL) {
  throw new Error('Falta VITE_API_URL: definirla en .env antes de compilar');
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set('Content-Type', 'application/json');

  let res: Response;
  try {
    // La sesión es una cookie httpOnly de la API: JS no la ve, el navegador la manda sola.
    res = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: 'include' });
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor');
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    // 422 trae una lista de errores de validación; el resto, un texto.
    const detail = typeof body?.detail === 'string' ? body.detail : 'No se pudo completar la operación';
    throw new ApiError(res.status, detail);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export type Health = { status: string; db: string };

// /health responde 503 con cuerpo JSON cuando la base cae: se muestra igual.
export const getHealth = (): Promise<Health> => fetch(`${API_URL}/health`).then((r) => r.json());
