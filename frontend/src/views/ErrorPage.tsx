import { Box, Button, Typography } from '@mui/material';
import PageContainer from '../components/PageContainer';

// Errores de carga que no son de sesión (API caída, 500): mensaje genérico y reintento.
const ErrorPage = () => (
  <PageContainer title="Error">
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        textAlign: 'center',
        p: 2,
      }}
    >
      <Typography variant="h3" sx={{ mb: 2 }}>
        No se pudo cargar la aplicación
      </Typography>
      <Typography sx={{ mb: 4 }}>Revisa tu conexión o intenta de nuevo en unos minutos.</Typography>
      <Button variant="contained" onClick={() => window.location.reload()}>
        Reintentar
      </Button>
    </Box>
  </PageContainer>
);

export default ErrorPage;
