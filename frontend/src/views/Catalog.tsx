import { useState, type FormEvent } from 'react';
import { useLoaderData, useRevalidator, useRouteLoaderData } from 'react-router';
import {
  Alert,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  InputAdornment,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
} from '@mui/material';
import { IconEdit, IconPlus } from '@tabler/icons-react';
import PageContainer from '../components/PageContainer';
import DashboardCard from '../components/DashboardCard';
import { ApiError } from '../api';
import type { Me } from '../auth';
import { saveItem, type CatalogField, type CatalogItem, type catalogLoader } from '../catalogs';

type Data = Awaited<ReturnType<typeof catalogLoader>>;

/** Cómo se muestra un valor en la tabla según el tipo de campo. */
const display = (field: CatalogField, value: CatalogItem[string]) => {
  if (field.type === 'bool') return value ? 'Sí' : 'No';
  if (field.type === 'percent') return `${Number(value)} %`;
  return value ?? '';
};

/** Campo del formulario según su tipo. Los bool van aparte (switch controlado). */
const Input = ({ field, value }: { field: CatalogField; value: CatalogItem[string] | undefined }) => {
  const common = { name: field.name, label: field.label, defaultValue: value ?? '', fullWidth: true };
  if (field.type === 'longtext') return <TextField {...common} multiline minRows={2} slotProps={{ htmlInput: { maxLength: 500 } }} />;
  if (field.type === 'percent')
    return (
      <TextField
        {...common}
        type="number"
        required
        slotProps={{
          htmlInput: { min: 0, max: 100, step: 0.01 },
          input: { endAdornment: <InputAdornment position="end">%</InputAdornment> },
        }}
      />
    );
  return <TextField {...common} required slotProps={{ htmlInput: { maxLength: 100 } }} />;
};

const ItemDialog = ({
  catalogKey,
  fields,
  item,
  onClose,
  onSaved,
}: {
  catalogKey: string;
  fields: CatalogField[];
  item: CatalogItem | null;
  onClose: () => void;
  onSaved: () => void;
}) => {
  const [flags, setFlags] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(fields.filter((f) => f.type === 'bool').map((f) => [f.name, Boolean(item?.[f.name])])),
  );
  const [active, setActive] = useState(item?.is_active ?? true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const body: Record<string, unknown> = { ...flags };
    for (const f of fields) {
      if (f.type === 'bool') continue;
      const raw = String(form.get(f.name) ?? '').trim();
      body[f.name] = f.type === 'longtext' && raw === '' ? null : raw;
    }
    if (item) body.is_active = active;
    setSaving(true);
    setError(null);
    try {
      await saveItem(catalogKey, item?.id ?? null, body);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error inesperado, intenta de nuevo');
      setSaving(false);
    }
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <form onSubmit={onSubmit}>
        <DialogTitle>{item ? 'Editar' : 'Nuevo registro'}</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ pt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            {fields.map((f) =>
              f.type === 'bool' ? (
                <FormControlLabel
                  key={f.name}
                  control={
                    <Checkbox
                      checked={flags[f.name]}
                      onChange={(e) => setFlags((s) => ({ ...s, [f.name]: e.target.checked }))}
                    />
                  }
                  label={f.label}
                />
              ) : (
                <Input key={f.name} field={f} value={item?.[f.name]} />
              ),
            )}
            {item && (
              <FormControlLabel
                control={<Switch checked={active} onChange={(e) => setActive(e.target.checked)} />}
                label={active ? 'Activo' : 'Inactivo (deja de aparecer en los formularios)'}
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

/** Pantalla genérica: la misma para todos los catálogos, armada con los metadatos de la API. */
const Catalog = () => {
  const { meta, items } = useLoaderData() as Data;
  const me = useRouteLoaderData('app') as Me;
  const canEdit = me.roles.some((r) => r.is_admin); // la API lo exige igual; esto solo oculta botones
  const { revalidate } = useRevalidator();
  const [editing, setEditing] = useState<CatalogItem | 'new' | null>(null);

  return (
    <PageContainer title={meta.title}>
      <DashboardCard
        title={meta.title}
        action={
          canEdit && (
            <Button variant="contained" startIcon={<IconPlus size={18} />} onClick={() => setEditing('new')}>
              Nuevo
            </Button>
          )
        }
      >
        <Table size="small">
          <TableHead>
            <TableRow>
              {meta.fields.map((f) => (
                <TableCell key={f.name}>{f.label}</TableCell>
              ))}
              <TableCell>Estado</TableCell>
              {canEdit && <TableCell align="right">Acciones</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id} hover sx={{ opacity: item.is_active ? 1 : 0.6 }}>
                {meta.fields.map((f) => (
                  <TableCell key={f.name}>{display(f, item[f.name])}</TableCell>
                ))}
                <TableCell>
                  <Chip size="small" color={item.is_active ? 'success' : 'default'} label={item.is_active ? 'Activo' : 'Inactivo'} />
                </TableCell>
                {canEdit && (
                  <TableCell align="right">
                    <Tooltip title="Editar">
                      <IconButton aria-label={`Editar ${item.name}`} onClick={() => setEditing(item)}>
                        <IconEdit size={18} />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </DashboardCard>
      {editing && (
        <ItemDialog
          key={meta.key}
          catalogKey={meta.key}
          fields={meta.fields}
          item={editing === 'new' ? null : editing}
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

export default Catalog;
