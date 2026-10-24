import { redirect, type LoaderFunctionArgs } from 'react-router';
import { ApiError, request } from './api';

export type Role = { id: number; name: string; is_admin: boolean };
export type Me = { id: number; username: string; email: string; roles: Role[] };

// La API deja la sesión en una cookie httpOnly: el front nunca toca el token.
export const login = (username: string, password: string) =>
  request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });

export const logout = () => request('/auth/logout', { method: 'POST' });

/** Solo rutas internas: evita que ?next=https://otro-sitio sirva de redirección abierta. */
export function safeNext(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/';
}

/** Usuario de la sesión actual, o null si no hay sesión válida. */
async function currentUser(): Promise<Me | null> {
  try {
    return await request<Me>('/auth/me');
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

/** Loader de las rutas protegidas: sin sesión válida, al login recordando adónde iba. */
export async function requireUser({ request: req }: LoaderFunctionArgs): Promise<Me> {
  const me = await currentUser();
  if (!me) {
    const { pathname, search } = new URL(req.url);
    throw redirect(`/auth/login?next=${encodeURIComponent(pathname + search)}`);
  }
  return me;
}

/** Loader del login: si ya hay sesión, no tiene sentido mostrarlo. */
export async function redirectIfLoggedIn({ request: req }: LoaderFunctionArgs) {
  // ponytail: si la API está caída el login se muestra igual; el error aparece al enviar.
  const me = await currentUser().catch(() => null);
  return me ? redirect(safeNext(new URL(req.url).searchParams.get('next'))) : null;
}
