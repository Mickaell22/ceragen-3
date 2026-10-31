import { request } from './api';
import type { Role } from './auth';

export type User = {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  locked_until: string | null;
  last_login_at: string | null;
  roles: Role[];
};

export type RoleOption = Role & { description: string | null };

export const listUsers = () => request<User[]>('/users');
export const listRoles = () => request<RoleOption[]>('/roles');

export const createUser = (body: { username: string; email: string; password: string; role_ids: number[] }) =>
  request<{ id: number }>('/users', { method: 'POST', body: JSON.stringify(body) });

export const updateUser = (id: number, body: { email: string; is_active: boolean; role_ids: number[] }) =>
  request(`/users/${id}`, { method: 'PUT', body: JSON.stringify(body) });

export const resetPassword = (id: number, password: string) =>
  request(`/users/${id}/password`, { method: 'POST', body: JSON.stringify({ password }) });

export const unlockUser = (id: number) => request(`/users/${id}/unlock`, { method: 'POST' });

/** Loader de /users: usuarios y roles en paralelo. Un 403 lo muestra el errorElement de la ruta. */
export async function usersLoader() {
  const [users, roles] = await Promise.all([listUsers(), listRoles()]);
  return { users, roles };
}
