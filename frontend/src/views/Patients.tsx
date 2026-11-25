import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Form, Link, useLoaderData, useRevalidator, useRouteLoaderData, useSubmit } from 'react-router';
import {
  Alert,
  Autocomplete,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  Grid,
  IconButton,
  InputAdornment,
  MenuItem,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
  debounce,
} from '@mui/material';
import { IconEdit, IconNotes, IconSearch, IconUserPlus } from '@tabler/icons-react';
import PageContainer from '../components/PageContainer';
import DashboardCard from '../components/DashboardCard';
import { ApiError } from '../api';
import type { Me } from '../auth';
import type { CatalogItem } from '../catalogs';
import {
  BLOOD_TYPES,
  createClient,
  getPatient,
  savePatient,
  searchClients,
  type ClientRow,
  type Patient,
  type Person,
  type patientsLoader,
} from '../patients';

type Data = Awaited<ReturnType<typeof patientsLoader>>;
type Options = Data['options'];

const errorText = (err: unknown) => (err instanceof ApiError ? err.message : 'Error inesperado, intenta de nuevo');
const active = (items: CatalogItem[], keep: (number | null)[] = []) =>
  items.filter((i) => i.is_active || keep.includes(i.id));

/** Campo de texto opcional del formulario: vacío -> null (la API distingue "sin dato"). */
const opt = (form: FormData, name: string) => {
  const value = String(form.get(name) ?? '').trim();
  return value === '' ? null : value;
};
const optId = (form: FormData, name: string) => {
  const value = opt(form, name);
  return value === null ? null : Number(value);
};

/** Lee los campos de persona de un formulario (prefijo `p.`). */
const readPerson = (form: FormData): Person => ({
  identification_type: String(form.get('p.identification_type')) as Person['identification_type'],
  identification: String(form.get('p.identification')).trim(),
  first_name: String(form.get('p.first_name')).trim(),
  last_name: String(form.get('p.last_name')).trim(),
  birth_date: opt(form, 'p.birth_date'),
  gender_id: optId(form, 'p.gender_id'),
  marital_status_id: optId(form, 'p.marital_status_id'),
  email: opt(form, 'p.email'),
  phone: opt(form, 'p.phone'),
  address: opt(form, 'p.address'),
});

/** Datos de identidad, compartidos por el paciente y el cliente. La identificación no se edita. */
const PersonFields = ({ person, options, full }: { person?: Person; options: Options; full: boolean }) => {
  const editing = Boolean(person);
  return (
    <Grid container spacing={2}>
      <Grid size={{ xs: 12, sm: 4 }}>
        <TextField
          name="p.identification_type"
          label="Tipo"
          select
          fullWidth
          defaultValue={person?.identification_type ?? 'cedula'}
          disabled={editing}
        >
          <MenuItem value="cedula">Cédula</MenuItem>
          <MenuItem value="ruc">RUC</MenuItem>
          <MenuItem value="passport">Pasaporte</MenuItem>
        </TextField>
      </Grid>
      <Grid size={{ xs: 12, sm: 8 }}>
        <TextField
          name="p.identification"
          label="Identificación"
          required
          fullWidth
          defaultValue={person?.identification}
          disabled={editing}
          slotProps={{ htmlInput: { minLength: 5, maxLength: 20 } }}
          helperText={editing ? 'No se puede cambiar' : 'La cédula se valida con su dígito verificador'}
        />
        {/* Un campo disabled no viaja en el formulario: se reenvía oculto. */}
        {editing && (
          <>
            <input type="hidden" name="p.identification_type" value={person?.identification_type} />
            <input type="hidden" name="p.identification" value={person?.identification} />
          </>
        )}
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        <TextField name="p.first_name" label="Nombres" required fullWidth defaultValue={person?.first_name} />
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        <TextField name="p.last_name" label="Apellidos" required fullWidth defaultValue={person?.last_name} />
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        <TextField name="p.phone" label="Teléfono" fullWidth defaultValue={person?.phone ?? ''} />
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        <TextField name="p.email" label="Correo" type="email" fullWidth defaultValue={person?.email ?? ''} />
      </Grid>
      {full && (
        <>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              name="p.birth_date"
              label="Fecha de nacimiento"
              type="date"
              fullWidth
              defaultValue={person?.birth_date ?? ''}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField name="p.gender_id" label="Género" select fullWidth defaultValue={person?.gender_id ?? ''}>
              <MenuItem value="">Sin especificar</MenuItem>
              {active(options.genders, [person?.gender_id ?? null]).map((g) => (
                <MenuItem key={g.id} value={g.id}>
                  {g.name}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              name="p.marital_status_id"
              label="Estado civil"
              select
              fullWidth
              defaultValue={person?.marital_status_id ?? ''}
            >
              <MenuItem value="">Sin especificar</MenuItem>
              {active(options.maritalStatuses, [person?.marital_status_id ?? null]).map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.name}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid size={12}>
            <TextField name="p.address" label="Dirección" fullWidth defaultValue={person?.address ?? ''} />
          </Grid>
        </>
      )}
    </Grid>
  );
};

/** Alta rápida de un cliente (quien paga) desde el formulario del paciente. */
const ClientDialog = ({
  options,
  onClose,
  onCreated,
}: {
  options: Options;
  onClose: () => void;
  onCreated: (client: ClientRow) => void;
}) => {
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    e.stopPropagation(); // el diálogo vive dentro del formulario del paciente
    const person = readPerson(new FormData(e.currentTarget));
    setSaving(true);
    try {
      const { id } = await createClient(person);
      onCreated({ id, full_name: `${person.last_name} ${person.first_name}`, identification: person.identification, is_active: true });
    } catch (err) {
      setError(errorText(err));
      setSaving(false);
    }
  };

  return (
    // Sin onClose: Escape o un clic afuera no cierran el formulario (se perdería lo escrito). Solo Cancelar.
    <Dialog open fullWidth maxWidth="sm" aria-labelledby="client-dialog-title">
      <form onSubmit={onSubmit}>
        <DialogTitle id="client-dialog-title">Nuevo cliente</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <PersonFields options={options} full={false} />
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

/** Quien paga: buscador de clientes con alta rápida. Vacío = el paciente se paga solo. */
const ClientPicker = ({
  value,
  onChange,
  options,
}: {
  value: ClientRow | null;
  onChange: (client: ClientRow | null) => void;
  options: Options;
}) => {
  const [results, setResults] = useState<ClientRow[]>([]);
  const [creating, setCreating] = useState(false);
  // Una búsqueda por pausa al escribir, no una por tecla.
  const search = useMemo(() => debounce((q: string) => searchClients(q).then(setResults).catch(() => setResults([])), 300), []);
  useEffect(() => () => search.clear(), [search]);

  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
      <Autocomplete
        fullWidth
        value={value}
        options={value && !results.some((r) => r.id === value.id) ? [value, ...results] : results}
        filterOptions={(x) => x}
        getOptionLabel={(c) => `${c.full_name} (${c.identification})`}
        isOptionEqualToValue={(a, b) => a.id === b.id}
        onOpen={() => search('')}
        onInputChange={(_, q, reason) => reason === 'input' && search(q)}
        onChange={(_, c) => onChange(c)}
        noOptionsText="Sin resultados"
        renderInput={(params) => (
          <TextField {...params} label="Cliente que paga" helperText="Vacío si el paciente se paga solo" />
        )}
      />
      <Button sx={{ mt: 1, whiteSpace: 'nowrap' }} onClick={() => setCreating(true)}>
        Nuevo cliente
      </Button>
      {creating && (
        <ClientDialog
          options={options}
          onClose={() => setCreating(false)}
          onCreated={(c) => {
            setCreating(false);
            onChange(c);
          }}
        />
      )}
    </Stack>
  );
};

const PatientDialog = ({
  patient,
  options,
  onClose,
  onSaved,
}: {
  patient: Patient | null;
  options: Options;
  onClose: () => void;
  onSaved: () => void;
}) => {
  const [client, setClient] = useState<ClientRow | null>(patient?.client ?? null);
  const [allergies, setAllergies] = useState<CatalogItem[]>(
    options.allergies.filter((a) => patient?.allergy_ids.includes(a.id)),
  );
  const [diseases, setDiseases] = useState<CatalogItem[]>(
    options.diseases.filter((d) => patient?.disease_ids.includes(d.id)),
  );
  const [isActive, setIsActive] = useState(patient?.is_active ?? true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setSaving(true);
    setError(null);
    try {
      await savePatient(patient?.id ?? null, {
        person: readPerson(form),
        client_id: client?.id ?? null,
        blood_type: opt(form, 'blood_type'),
        emergency_contact_name: opt(form, 'emergency_contact_name'),
        emergency_contact_phone: opt(form, 'emergency_contact_phone'),
        notes: opt(form, 'notes'),
        allergy_ids: allergies.map((a) => a.id),
        disease_ids: diseases.map((d) => d.id),
        is_active: isActive,
      });
      onSaved();
    } catch (err) {
      setError(errorText(err));
      setSaving(false);
    }
  };

  const multi = (label: string, all: CatalogItem[], value: CatalogItem[], set: (v: CatalogItem[]) => void) => (
    <Autocomplete
      multiple
      disableCloseOnSelect
      options={active(all, value.map((v) => v.id))}
      value={value}
      onChange={(_, v) => set(v)}
      getOptionLabel={(o) => String(o.name)}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      renderInput={(params) => <TextField {...params} label={label} />}
    />
  );

  return (
    // Sin onClose a propósito: ver ClientDialog.
    <Dialog open fullWidth maxWidth="md">
      <form onSubmit={onSubmit}>
        <DialogTitle>
          {patient ? `Editar paciente: ${patient.person.last_name} ${patient.person.first_name}` : 'Nuevo paciente'}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ pt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <PersonFields person={patient?.person} options={options} full />
            <Divider />
            <ClientPicker value={client} onChange={setClient} options={options} />
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 4 }}>
                <TextField name="blood_type" label="Tipo de sangre" select fullWidth defaultValue={patient?.blood_type ?? ''}>
                  <MenuItem value="">Sin especificar</MenuItem>
                  {BLOOD_TYPES.map((b) => (
                    <MenuItem key={b} value={b}>
                      {b}
                    </MenuItem>
                  ))}
                </TextField>
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <TextField
                  name="emergency_contact_name"
                  label="Contacto de emergencia"
                  fullWidth
                  defaultValue={patient?.emergency_contact_name ?? ''}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <TextField
                  name="emergency_contact_phone"
                  label="Teléfono de emergencia"
                  fullWidth
                  defaultValue={patient?.emergency_contact_phone ?? ''}
                />
              </Grid>
            </Grid>
            {multi('Alergias', options.allergies, allergies, setAllergies)}
            {multi('Enfermedades', options.diseases, diseases, setDiseases)}
            <TextField
              name="notes"
              label="Observaciones"
              multiline
              minRows={2}
              defaultValue={patient?.notes ?? ''}
              slotProps={{ htmlInput: { maxLength: 2000 } }}
            />
            {patient && (
              <FormControlLabel
                control={<Switch checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />}
                label={isActive ? 'Activo' : 'Inactivo'}
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

const Patients = () => {
  const { q, patients, options } = useLoaderData() as Data;
  const me = useRouteLoaderData('app') as Me;
  // Tener la pantalla da permiso de escritura (la base lo exige igual): sin ella, solo lectura.
  const canEdit =
    me.roles.some((r) => r.is_admin) || me.menus.some((g) => g.menus.some((m) => m.path === '/patients'));
  const canSeeHistory =
    me.roles.some((r) => r.is_admin) || me.menus.some((g) => g.menus.some((m) => m.path === '/medical-history'));
  const { revalidate } = useRevalidator();
  const submit = useSubmit();
  // Una búsqueda por pausa al escribir: cada una recarga la lista entera.
  const search = useMemo(() => debounce((form: HTMLFormElement) => submit(form, { replace: true }), 300), [submit]);
  useEffect(() => () => search.clear(), [search]);
  const [editing, setEditing] = useState<{ patient: Patient | null } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openEdit = async (row: (typeof patients)[number]) => {
    try {
      setEditing({ patient: await getPatient(row.id) });
    } catch (err) {
      setError(errorText(err));
    }
  };

  return (
    <PageContainer title="Pacientes">
      <DashboardCard
        title="Pacientes"
        subtitle="Búsqueda por nombre, apellido o identificación"
        action={
          canEdit && (
            <Button
              variant="contained"
              startIcon={<IconUserPlus size={18} />}
              onClick={() => setEditing({ patient: null })}
            >
              Nuevo
            </Button>
          )
        }
      >
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        <Form role="search" onChange={(e) => search(e.currentTarget)}>
          <TextField
            name="q"
            defaultValue={q}
            placeholder="Buscar paciente"
            size="small"
            sx={{ mb: 2, width: { xs: '100%', sm: 360 } }}
            slotProps={{
              htmlInput: { 'aria-label': 'Buscar paciente' },
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <IconSearch size={18} />
                  </InputAdornment>
                ),
              },
            }}
          />
        </Form>
        {patients.length === 0 ? (
          <Typography color="textSecondary" sx={{ py: 3 }}>
            {q ? 'Ningún paciente coincide con la búsqueda.' : 'Todavía no hay pacientes registrados.'}
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Paciente</TableCell>
                <TableCell>Identificación</TableCell>
                <TableCell>Teléfono</TableCell>
                <TableCell>Paga</TableCell>
                <TableCell>Estado</TableCell>
                {(canEdit || canSeeHistory) && <TableCell align="right">Acciones</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {patients.map((p) => (
                <TableRow key={p.id} hover sx={{ opacity: p.is_active ? 1 : 0.6 }}>
                  <TableCell>{p.full_name}</TableCell>
                  <TableCell>{p.identification}</TableCell>
                  <TableCell>{p.phone ?? ''}</TableCell>
                  <TableCell>{p.client_name ?? 'El mismo paciente'}</TableCell>
                  <TableCell>
                    <Chip size="small" color={p.is_active ? 'success' : 'default'} label={p.is_active ? 'Activo' : 'Inactivo'} />
                  </TableCell>
                  {(canEdit || canSeeHistory) && (
                    <TableCell align="right">
                      {canSeeHistory && (
                        <Tooltip title="Historial médico">
                          <IconButton
                            component={Link}
                            to={`/medical-history?patient=${p.id}`}
                            aria-label={`Historial de ${p.full_name}`}
                          >
                            <IconNotes size={18} />
                          </IconButton>
                        </Tooltip>
                      )}
                      {canEdit && (
                      <Tooltip title="Editar">
                        <IconButton aria-label={`Editar ${p.full_name}`} onClick={() => openEdit(p)}>
                          <IconEdit size={18} />
                        </IconButton>
                      </Tooltip>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DashboardCard>
      {editing && (
        <PatientDialog
          patient={editing.patient}
          options={options}
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

export default Patients;
