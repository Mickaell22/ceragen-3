import type { LoaderFunctionArgs } from 'react-router';
import { request } from './api';
import type { CatalogItem } from './catalogs';

export type IdentificationType = 'cedula' | 'ruc' | 'passport';

export type Person = {
  identification_type: IdentificationType;
  identification: string;
  first_name: string;
  last_name: string;
  birth_date: string | null;
  gender_id: number | null;
  marital_status_id: number | null;
  email: string | null;
  phone: string | null;
  address: string | null;
};

export type PatientRow = {
  id: number;
  full_name: string;
  identification: string;
  phone: string | null;
  client_name: string | null;
  is_active: boolean;
};

export type Patient = {
  id: number;
  person: Person & { id: number };
  client_id: number | null;
  client: ClientRow | null;
  blood_type: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  notes: string | null;
  allergy_ids: number[];
  disease_ids: number[];
  is_active: boolean;
};

export type PatientInput = Omit<Patient, 'id' | 'person' | 'client'> & { person: Person };
export type ClientRow = { id: number; full_name: string; identification: string; is_active: boolean };

export const BLOOD_TYPES = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];

export const getPatient = (id: number) => request<Patient>(`/patients/${id}`);

export const savePatient = (id: number | null, body: PatientInput) =>
  id === null
    ? request<{ id: number }>('/patients', { method: 'POST', body: JSON.stringify(body) })
    : request(`/patients/${id}`, { method: 'PUT', body: JSON.stringify(body) });

export const searchClients = (q: string) => request<ClientRow[]>(`/clients?q=${encodeURIComponent(q)}`);

export const createClient = (person: Person) =>
  request<{ id: number }>('/clients', { method: 'POST', body: JSON.stringify({ person }) });

const catalog = (key: string) => request<CatalogItem[]>(`/catalogs/${key}`);

/** Loader de /patients: la búsqueda vive en la URL (?q=) para poder compartirla y volver atrás. */
export async function patientsLoader({ request: req }: LoaderFunctionArgs) {
  const q = new URL(req.url).searchParams.get('q') ?? '';
  const [patients, genders, maritalStatuses, allergies, diseases] = await Promise.all([
    request<PatientRow[]>(`/patients?q=${encodeURIComponent(q)}`),
    catalog('genders'),
    catalog('marital-statuses'),
    catalog('allergies'),
    catalog('diseases'),
  ]);
  return { q, patients, options: { genders, maritalStatuses, allergies, diseases } };
}
