import { Link } from 'react-router';
import { Box, Button, Typography } from '@mui/material';
import PageContainer from '../components/PageContainer';

const NotFound = () => (
  <PageContainer title="Página no encontrada">
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
      <Typography variant="h1" color="primary" sx={{ mb: 2 }}>
        404
      </Typography>
      <Typography variant="h4" sx={{ mb: 4 }}>
        La página que buscas no existe.
      </Typography>
      <Button variant="contained" component={Link} to="/">
        Volver al inicio
      </Button>
    </Box>
  </PageContainer>
);

export default NotFound;
