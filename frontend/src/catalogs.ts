import type { LoaderFunctionArgs } from 'react-router';
import { request } from './api';

export type FieldType = 'text' | 'longtext' | 'percent' | 'bool';
export type CatalogField = { name: string; label: string; type: FieldType };
export type CatalogMeta = { key: string; title: string; fields: CatalogField[] };
export type CatalogItem = { id: number; is_active: boolean } & Record<string, string | number | boolean | null>;

// Los metadatos no cambian mientras corre la app: se piden una vez.
let metaCache: Promise<CatalogMeta[]> | null = null;
const listCatalogs = () => (metaCache ??= request<CatalogMeta[]>('/catalogs').catch((err) => {
  metaCache = null; // un fallo no queda cacheado
  throw err;
}));

export const saveItem = (key: string, id: number | null, body: Record<string, unknown>) =>
  id === null
    ? request(`/catalogs/${key}`, { method: 'POST', body: JSON.stringify(body) })
    : request(`/catalogs/${key}/${id}`, { method: 'PUT', body: JSON.stringify(body) });

/** Loader de /catalogs/:key: metadatos del catálogo y sus filas. */
export async function catalogLoader({ params }: LoaderFunctionArgs) {
  const [all, items] = await Promise.all([listCatalogs(), request<CatalogItem[]>(`/catalogs/${params.key}`)]);
  const meta = all.find((c) => c.key === params.key);
  if (!meta) throw new Response('Catálogo inexistente', { status: 404 });
  return { meta, items };
}
