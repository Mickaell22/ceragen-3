import { useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { Alert, Box, Button, Card, Stack, TextField, Typography } from '@mui/material';
import PageContainer from '../components/PageContainer';
import Logo from '../components/Logo';
import { ApiError } from '../api';
import { login, safeNext } from '../auth';

const Login = () => {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setSubmitting(true);
    setError(null);
    try {
      await login(String(form.get('username')), String(form.get('password')));
      navigate(safeNext(params.get('next')), { replace: true });
    } catch (err) {
      // 401 y 423 traen un mensaje pensado para el usuario; el resto, genérico.
      setError(err instanceof ApiError ? err.message : 'Error inesperado, intenta de nuevo');
      setSubmitting(false);
    }
  };

  return (
    <PageContainer title="Iniciar sesión">
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: 2,
          background: 'radial-gradient(#d2f1df4d, #d3d7fa4d, #bad8f44d)',
        }}
      >
        <Card elevation={9} sx={{ p: 4, width: '100%', maxWidth: 450 }}>
          <Box sx={{ textAlign: 'center' }}>
            <Logo />
            <Typography variant="subtitle1" color="textSecondary" sx={{ mb: 2 }}>
              Centro de fisioterapia
            </Typography>
          </Box>
          <Stack component="form" spacing={3} onSubmit={onSubmit}>
            {error && (
              <Alert severity="error" role="alert">
                {error}
              </Alert>
            )}
            <TextField name="username" label="Usuario" autoComplete="username" autoFocus required fullWidth />
            <TextField
              name="password"
              label="Contraseña"
              type="password"
              autoComplete="current-password"
              required
              fullWidth
            />
            <Button type="submit" variant="contained" size="large" fullWidth loading={submitting}>
              Ingresar
            </Button>
          </Stack>
        </Card>
      </Box>
    </PageContainer>
  );
};

export default Login;
