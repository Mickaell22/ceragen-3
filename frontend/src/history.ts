import type { LoaderFunctionArgs } from 'react-router';
import { request } from './api';
import { getPatient, type Patient, type PatientRow } from './patients';

export type Entry = {
  id: number;
  recorded_on: string;
  reason: string;
  diagnosis: string | null;
  treatment: string | null;
  notes: string | null;
  author: string | null;
  author_id: number | null;
  created_at: string;
  updated_at: string | null;
  is_active: boolean;
};

export type EntryInput = Pick<Entry, 'recorded_on' | 'reason' | 'diagnosis' | 'treatment' | 'notes'> & {
  is_active?: boolean;
};

export const searchPatients = (q: string) => request<PatientRow[]>(`/patients?q=${encodeURIComponent(q)}&limit=20`);

export const saveEntry = (patientId: number, entryId: number | null, body: EntryInput) =>
  entryId === null
    ? request(`/patients/${patientId}/history`, { method: 'POST', body: JSON.stringify(body) })
    : request(`/history/${entryId}`, { method: 'PUT', body: JSON.stringify(body) });

/** Loader de /medical-history: el paciente elegido vive en la URL (?patient=), así se puede enlazar. */
export async function historyLoader({ request: req }: LoaderFunctionArgs) {
  const id = Number(new URL(req.url).searchParams.get('patient'));
  if (!id) return { patient: null as Patient | null, entries: [] as Entry[] };
  const [patient, entries] = await Promise.all([getPatient(id), request<Entry[]>(`/patients/${id}/history`)]);
  return { patient, entries };
}
