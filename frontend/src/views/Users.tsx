import { useState, type FormEvent } from 'react';
import { useLoaderData, useRevalidator } from 'react-router';
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
  FormGroup,
  FormLabel,
  IconButton,
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
import { IconEdit, IconKey, IconLockOpen, IconUserPlus } from '@tabler/icons-react';
import PageContainer from '../components/PageContainer';
import DashboardCard from '../components/DashboardCard';
import { ApiError } from '../api';
import {
  createUser,
  resetPassword,
  unlockUser,
  updateUser,
  type RoleOption,
  type User,
  type usersLoader,
} from '../users';

type Data = Awaited<ReturnType<typeof usersLoader>>;
type Editing = { kind: 'create' } | { kind: 'edit'; user: User } | { kind: 'password'; user: User } | null;

const errorText = (err: unknown) => (err instanceof ApiError ? err.message : 'Error inesperado, intenta de nuevo');

const Status = ({ user }: { user: User }) =>
  !user.is_active ? (
    <Chip size="small" label="Inactivo" />
  ) : user.locked_until ? (
    <Chip size="small" color="warning" label="Bloqueado" />
  ) : (
    <Chip size="small" color="success" label="Activo" />
  );

/** Alta y edición comparten formulario; la contraseña solo se pide al crear. */
const UserDialog = ({
  editing,
  roles,
  onClose,
  onSaved,
}: {
  editing: { kind: 'create' } | { kind: 'edit'; user: User };
  roles: RoleOption[];
  onClose: () => void;
  onSaved: () => void;
}) => {
  const user = editing.kind === 'edit' ? editing.user : null;
  const [roleIds, setRoleIds] = useState<number[]>(user?.roles.map((r) => r.id) ?? []);
  const [active, setActive] = useState(user?.is_active ?? true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const toggleRole = (id: number) =>
    setRoleIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (roleIds.length === 0) return setError('Asigna al menos un rol');
    const form = new FormData(e.currentTarget);
    const email = String(form.get('email'));
    setSaving(true);
    setError(null);
    try {
      if (user) await updateUser(user.id, { email, is_active: active, role_ids: roleIds });
      else
        await createUser({
          username: String(form.get('username')),
          email,
          password: String(form.get('password')),
          role_ids: roleIds,
        });
      onSaved();
    } catch (err) {
      setError(errorText(err));
      setSaving(false);
    }
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <form onSubmit={onSubmit}>
        <DialogTitle>{user ? `Editar ${user.username}` : 'Nuevo usuario'}</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ pt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            {!user && (
              <TextField
                name="username"
                label="Usuario"
                required
                autoFocus
                slotProps={{ htmlInput: { pattern: '[A-Za-z0-9._\\-]{3,50}' } }}
                helperText="3 a 50 caracteres: letras, números, punto, guion"
              />
            )}
            <TextField name="email" label="Correo" type="email" required defaultValue={user?.email} />
            {!user && (
              <TextField
                name="password"
                label="Contraseña inicial"
                type="password"
                autoComplete="new-password"
                required
                slotProps={{ htmlInput: { minLength: 8, maxLength: 72 } }}
                helperText="Entre 8 y 72 caracteres"
              />
            )}
            <FormGroup>
              <FormLabel>Roles</FormLabel>
              {roles.map((r) => (
                <FormControlLabel
                  key={r.id}
                  control={<Checkbox checked={roleIds.includes(r.id)} onChange={() => toggleRole(r.id)} />}
                  label={r.name}
                />
              ))}
            </FormGroup>
            {user && (
              <FormControlLabel
                control={<Switch checked={active} onChange={(e) => setActive(e.target.checked)} />}
                label={active ? 'Activo' : 'Inactivo (cierra sus sesiones)'}
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

const PasswordDialog = ({ user, onClose, onSaved }: { user: User; onClose: () => void; onSaved: () => void }) => {
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSaving(true);
    try {
      await resetPassword(user.id, String(new FormData(e.currentTarget).get('password')));
      onSaved();
    } catch (err) {
      setError(errorText(err));
      setSaving(false);
    }
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <form onSubmit={onSubmit}>
        <DialogTitle>Nueva contraseña para {user.username}</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ pt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              name="password"
              label="Contraseña"
              type="password"
              autoComplete="new-password"
              required
              autoFocus
              slotProps={{ htmlInput: { minLength: 8, maxLength: 72 } }}
              helperText="También desbloquea la cuenta y cierra sus sesiones abiertas"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancelar</Button>
          <Button type="submit" variant="contained" loading={saving}>
            Cambiar
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

const Users = () => {
  const { users, roles } = useLoaderData() as Data;
  const { revalidate } = useRevalidator();
  const [editing, setEditing] = useState<Editing>(null);
  const [error, setError] = useState<string | null>(null);

  const saved = () => {
    setEditing(null);
    revalidate(); // vuelve a correr el loader: la tabla queda igual a la base
  };

  const unlock = async (user: User) => {
    try {
      await unlockUser(user.id);
      revalidate();
    } catch (err) {
      setError(errorText(err));
    }
  };

  return (
    <PageContainer title="Usuarios">
      <DashboardCard
        title="Usuarios"
        subtitle="Cuentas del sistema y sus roles"
        action={
          <Button variant="contained" startIcon={<IconUserPlus size={18} />} onClick={() => setEditing({ kind: 'create' })}>
            Nuevo
          </Button>
        }
      >
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Usuario</TableCell>
              <TableCell>Correo</TableCell>
              <TableCell>Roles</TableCell>
              <TableCell>Estado</TableCell>
              <TableCell>Último ingreso</TableCell>
              <TableCell align="right">Acciones</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.id} hover>
                <TableCell>{u.username}</TableCell>
                <TableCell>{u.email}</TableCell>
                <TableCell>{u.roles.map((r) => r.name).join(', ') || 'Sin rol'}</TableCell>
                <TableCell>
                  <Status user={u} />
                </TableCell>
                <TableCell>{u.last_login_at ? new Date(u.last_login_at).toLocaleString('es-EC') : 'Nunca'}</TableCell>
                <TableCell align="right">
                  {u.locked_until && (
                    <Tooltip title="Desbloquear">
                      <IconButton aria-label={`Desbloquear ${u.username}`} onClick={() => unlock(u)}>
                        <IconLockOpen size={18} />
                      </IconButton>
                    </Tooltip>
                  )}
                  <Tooltip title="Cambiar contraseña">
                    <IconButton aria-label={`Cambiar contraseña de ${u.username}`} onClick={() => setEditing({ kind: 'password', user: u })}>
                      <IconKey size={18} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Editar">
                    <IconButton aria-label={`Editar ${u.username}`} onClick={() => setEditing({ kind: 'edit', user: u })}>
                      <IconEdit size={18} />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </DashboardCard>

      {(editing?.kind === 'create' || editing?.kind === 'edit') && (
        <UserDialog editing={editing} roles={roles} onClose={() => setEditing(null)} onSaved={saved} />
      )}
      {editing?.kind === 'password' && (
        <PasswordDialog user={editing.user} onClose={() => setEditing(null)} onSaved={saved} />
      )}
    </PageContainer>
  );
};

export default Users;
