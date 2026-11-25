import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useLoaderData, useNavigate, useRevalidator, useRouteLoaderData } from 'react-router';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
  debounce,
} from '@mui/material';
import { IconEdit, IconPlus } from '@tabler/icons-react';
import PageContainer from '../components/PageContainer';
import DashboardCard from '../components/DashboardCard';
import { ApiError } from '../api';
import type { Me } from '../auth';
import { saveEntry, searchPatients, type Entry, type historyLoader } from '../history';
import type { PatientRow } from '../patients';

type Data = Awaited<ReturnType<typeof historyLoader>>;

const today = () => new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD en hora local
const fmtDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('es-EC', { dateStyle: 'long' });

/** Buscador de pacientes que cambia ?patient= en la URL. */
const PatientSearch = () => {
  const navigate = useNavigate();
  const [results, setResults] = useState<PatientRow[]>([]);
  const search = useMemo(
    () => debounce((q: string) => searchPatients(q).then(setResults).catch(() => setResults([])), 300),
    [],
  );
  useEffect(() => () => search.clear(), [search]);
  return (
    <Autocomplete
      options={results}
      filterOptions={(x) => x}
      getOptionLabel={(p) => `${p.full_name} (${p.identification})`}
      onOpen={() => search('')}
      onInputChange={(_, q, reason) => reason === 'input' && search(q)}
      onChange={(_, p) => p && navigate(`/medical-history?patient=${p.id}`)}
      noOptionsText="Sin resultados"
      sx={{ maxWidth: 480 }}
      renderInput={(params) => <TextField {...params} label="Buscar paciente" />}
    />
  );
};

const EntryDialog = ({
  patientId,
  entry,
  onClose,
  onSaved,
}: {
  patientId: number;
  entry: Entry | null;
  onClose: () => void;
  onSaved: () => void;
}) => {
  const [active, setActive] = useState(entry?.is_active ?? true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const opt = (k: string) => String(form.get(k) ?? '').trim() || null;
    setSaving(true);
    setError(null);
    try {
      await saveEntry(patientId, entry?.id ?? null, {
        recorded_on: String(form.get('recorded_on')),
        reason: String(form.get('reason')).trim(),
        diagnosis: opt('diagnosis'),
        treatment: opt('treatment'),
        notes: opt('notes'),
        ...(entry ? { is_active: active } : {}),
      });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error inesperado, intenta de nuevo');
      setSaving(false);
    }
  };

  return (
    // Sin onClose: Escape o un clic afuera no cierran el texto clínico a medio escribir. Solo Cancelar.
    <Dialog open fullWidth maxWidth="md">
      <form onSubmit={onSubmit}>
        <DialogTitle>{entry ? 'Corregir entrada' : 'Nueva entrada'}</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ pt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                name="recorded_on"
                label="Fecha"
                type="date"
                required
                defaultValue={entry?.recorded_on ?? today()}
                slotProps={{ inputLabel: { shrink: true }, htmlInput: { max: today() } }}
              />
              <TextField
                name="reason"
                label="Motivo de la consulta"
                required
                fullWidth
                autoFocus
                defaultValue={entry?.reason}
                slotProps={{ htmlInput: { maxLength: 300 } }}
              />
            </Stack>
            <TextField name="diagnosis" label="Diagnóstico" multiline minRows={2} defaultValue={entry?.diagnosis ?? ''} />
            <TextField name="treatment" label="Tratamiento" multiline minRows={2} defaultValue={entry?.treatment ?? ''} />
            <TextField name="notes" label="Observaciones" multiline minRows={2} defaultValue={entry?.notes ?? ''} />
            {entry && (
              <FormControlLabel
                control={<Switch checked={active} onChange={(e) => setActive(e.target.checked)} />}
                label={active ? 'Vigente' : 'Anulada (queda en el historial, tachada)'}
              />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancelar</Button>
          <Button type="submit" variant="contained" loading={saving}>
            Guardar
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

const Field = ({ label, value }: { label: string; value: string | null }) =>
  value ? (
    <Box sx={{ mt: 1 }}>
      <Typography variant="subtitle2" color="textSecondary">
        {label}
      </Typography>
      <Typography sx={{ whiteSpace: 'pre-wrap' }}>{value}</Typography>
    </Box>
  ) : null;

const MedicalHistory = () => {
  const { patient, entries } = useLoaderData() as Data;
  const me = useRouteLoaderData('app') as Me;
  const isAdmin = me.roles.some((r) => r.is_admin);
  const { revalidate } = useRevalidator();
  const [editing, setEditing] = useState<Entry | 'new' | null>(null);

  return (
    <PageContainer title="Historial médico">
      <DashboardCard
        title={patient ? `Historial de ${patient.person.last_name} ${patient.person.first_name}` : 'Historial médico'}
        subtitle={patient ? `Identificación ${patient.person.identification}` : 'Elige un paciente para ver su historial'}
        action={
          patient && (
            <Button variant="contained" startIcon={<IconPlus size={18} />} onClick={() => setEditing('new')}>
              Nueva entrada
            </Button>
          )
        }
      >
        <PatientSearch />
        {patient && entries.length === 0 && (
          <Typography color="textSecondary" sx={{ mt: 3 }}>
            Este paciente todavía no tiene entradas.
          </Typography>
        )}
        <Stack spacing={2} sx={{ mt: 3 }}>
          {entries.map((e) => (
            <Card key={e.id} variant="outlined" sx={{ opacity: e.is_active ? 1 : 0.6 }}>
              <CardContent>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                  <Typography variant="h6" sx={{ textDecoration: e.is_active ? 'none' : 'line-through' }}>
                    {e.reason}
                  </Typography>
                  {!e.is_active && <Chip size="small" label="Anulada" />}
                  <Box sx={{ flexGrow: 1 }} />
                  {(isAdmin || e.author_id === me.id) && (
                    <Tooltip title="Corregir">
                      <IconButton aria-label={`Corregir ${e.reason}`} onClick={() => setEditing(e)}>
                        <IconEdit size={18} />
                      </IconButton>
                    </Tooltip>
                  )}
                </Stack>
                <Typography variant="subtitle2" color="textSecondary">
                  {fmtDate(e.recorded_on)} · {e.author ?? 'desconocido'}
                  {e.updated_at && ' · corregida'}
                </Typography>
                <Field label="Diagnóstico" value={e.diagnosis} />
                <Field label="Tratamiento" value={e.treatment} />
                <Field label="Observaciones" value={e.notes} />
              </CardContent>
            </Card>
          ))}
        </Stack>
      </DashboardCard>
      {editing && patient && (
        <EntryDialog
          patientId={patient.id}
          entry={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            revalidate();
          }}
        />
      )}
    </PageContainer>
  );
};

export default MedicalHistory;
