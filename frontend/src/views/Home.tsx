import { useEffect, useState } from 'react';
import { Chip, Stack, Typography } from '@mui/material';
import PageContainer from '../components/PageContainer';
import DashboardCard from '../components/DashboardCard';
import { getHealth, type Health } from '../api';

type State = Health | 'loading' | 'unreachable';

const Home = () => {
  const [health, setHealth] = useState<State>('loading');

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth('unreachable'));
  }, []);

  const ok = typeof health === 'object' && health.status === 'ok';
  const label =
    health === 'loading' ? 'Comprobando...' : health === 'unreachable' ? 'API sin respuesta' : `API ${health.status}, base ${health.db}`;

  return (
    <PageContainer title="Inicio">
      <DashboardCard title="Estado del sistema" subtitle="Conexión del frontend con la API y la base de datos">
        <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
          <Typography>Estado:</Typography>
          <Chip label={label} color={health === 'loading' ? 'default' : ok ? 'success' : 'error'} />
        </Stack>
      </DashboardCard>
    </PageContainer>
  );
};

export default Home;
