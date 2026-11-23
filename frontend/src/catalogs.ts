import type { LoaderFunctionArgs } from 'react-router';
import { request } from './api';

export type FieldType = 'text' | 'longtext' | 'percent' | 'bool' | 'ref';
/** ref: id de una fila de otro catálogo (`ref` = su key); se muestra como select. */
export type CatalogField = { name: string; label: string; type: FieldType; ref?: string | null };
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

const listItems = (key: string) => request<CatalogItem[]>(`/catalogs/${key}`);

/** Loader de /catalogs/:key: metadatos, filas y las filas de los catálogos referenciados. */
export async function catalogLoader({ params }: LoaderFunctionArgs) {
  const key = params.key ?? '';
  const [all, items] = await Promise.all([listCatalogs(), listItems(key)]);
  const meta = all.find((c) => c.key === key);
  if (!meta) throw new Response('Catálogo inexistente', { status: 404 });
  const refKeys = [...new Set(meta.fields.flatMap((f) => (f.type === 'ref' && f.ref ? [f.ref] : [])))];
  const refItems = await Promise.all(refKeys.map(listItems));
  const options: Record<string, CatalogItem[]> = Object.fromEntries(refKeys.map((k, i) => [k, refItems[i]]));
  return { meta, items, options };
}
