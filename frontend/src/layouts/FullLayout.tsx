import { useState } from 'react';
import { Outlet } from 'react-router';
import { Box, Container } from '@mui/material';
import Header from './Header';
import Sidebar from './Sidebar';

const FullLayout = () => {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <Box sx={{ display: 'flex', width: '100%' }}>
      <Sidebar mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />
      <Box sx={{ display: 'flex', flexGrow: 1, flexDirection: 'column', minWidth: 0 }}>
        <Header onMenuClick={() => setMobileOpen(true)} />
        <Container sx={{ pt: '20px', maxWidth: '1200px' }}>
          <Box sx={{ minHeight: 'calc(100vh - 170px)' }}>
            <Outlet />
          </Box>
        </Container>
      </Box>
    </Box>
  );
};

export default FullLayout;
