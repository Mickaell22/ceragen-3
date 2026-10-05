import type { FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { Box, Button, Card, Stack, TextField, Typography } from '@mui/material';
import PageContainer from '../components/PageContainer';
import Logo from '../components/Logo';

const Login = () => {
  const navigate = useNavigate();

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    // ponytail: solo maqueta; el login real contra la API llega el día 7 (feat/api-auth).
    navigate('/');
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
            <TextField id="username" label="Usuario" autoComplete="username" required fullWidth />
            <TextField id="password" label="Contraseña" type="password" autoComplete="current-password" required fullWidth />
            <Button type="submit" variant="contained" size="large" fullWidth>
              Ingresar
            </Button>
          </Stack>
        </Card>
      </Box>
    </PageContainer>
  );
};

export default Login;
