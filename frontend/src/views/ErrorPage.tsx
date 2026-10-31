import { useRouteError } from 'react-router';
import { Box, Button, Typography } from '@mui/material';
import PageContainer from '../components/PageContainer';
import { ApiError } from '../api';

/** Errores de carga de una ruta. fullPage: cuando cae el layout entero (API caída al entrar). */
const ErrorPage = ({ fullPage = false }: { fullPage?: boolean }) => {
  const error = useRouteError();
  const forbidden = error instanceof ApiError && error.status === 403;
  return (
    <PageContainer title={forbidden ? 'Sin permiso' : 'Error'}>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: fullPage ? '100vh' : '50vh',
          textAlign: 'center',
          p: 2,
        }}
      >
        <Typography variant="h3" sx={{ mb: 2 }}>
          {forbidden ? 'No tienes permiso para ver esta página' : 'No se pudo cargar la página'}
        </Typography>
        {!forbidden && (
          <>
            <Typography sx={{ mb: 4 }}>Revisa tu conexión o intenta de nuevo en unos minutos.</Typography>
            <Button variant="contained" onClick={() => window.location.reload()}>
              Reintentar
            </Button>
          </>
        )}
      </Box>
    </PageContainer>
  );
};

export default ErrorPage;
