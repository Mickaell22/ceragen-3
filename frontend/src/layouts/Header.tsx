import { useState, type MouseEvent } from 'react';
import { useNavigate, useRouteLoaderData } from 'react-router';
import { AppBar, Avatar, Box, Button, IconButton, Menu, Toolbar, Typography } from '@mui/material';
import { IconMenu, IconUser } from '@tabler/icons-react';
import { logout, type Me } from '../auth';

const Header = ({ onMenuClick }: { onMenuClick: () => void }) => {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const me = useRouteLoaderData('app') as Me;
  const navigate = useNavigate();

  const onLogout = async () => {
    setAnchor(null);
    // Si la API no responde la cookie queda, pero el login la revalida y la sesión vence sola.
    await logout().catch(() => undefined);
    navigate('/auth/login', { replace: true });
  };

  return (
    <AppBar
      position="sticky"
      color="default"
      sx={{ boxShadow: 'none', bgcolor: 'background.paper', justifyContent: 'center', minHeight: { lg: 70 } }}
    >
      <Toolbar sx={{ color: 'text.secondary' }}>
        <IconButton
          color="inherit"
          aria-label="Abrir menú"
          onClick={onMenuClick}
          sx={{ display: { lg: 'none', xs: 'inline-flex' } }}
        >
          <IconMenu width="20" height="20" />
        </IconButton>
        <Box sx={{ flexGrow: 1 }} />
        <Typography sx={{ mr: 1, display: { xs: 'none', sm: 'block' } }}>{me.username}</Typography>
        <IconButton
          aria-label="Cuenta"
          aria-controls="account-menu"
          aria-haspopup="true"
          onClick={(e: MouseEvent<HTMLElement>) => setAnchor(e.currentTarget)}
        >
          <Avatar sx={{ width: 35, height: 35, bgcolor: 'primary.main' }}>
            <IconUser size={20} />
          </Avatar>
        </IconButton>
        <Menu
          id="account-menu"
          anchorEl={anchor}
          open={Boolean(anchor)}
          onClose={() => setAnchor(null)}
          anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          transformOrigin={{ horizontal: 'right', vertical: 'top' }}
          slotProps={{ paper: { sx: { width: 200 } } }}
        >
          <Box sx={{ py: 1, px: 2 }}>
            <Typography variant="subtitle2" color="textSecondary" sx={{ mb: 1 }}>
              {me.roles.map((r) => r.name).join(', ') || 'Sin rol asignado'}
            </Typography>
            <Button onClick={onLogout} variant="outlined" fullWidth>
              Cerrar sesión
            </Button>
          </Box>
        </Menu>
      </Toolbar>
    </AppBar>
  );
};

export default Header;
