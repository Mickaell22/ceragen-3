import { useState, type MouseEvent } from 'react';
import { Link } from 'react-router';
import { AppBar, Avatar, Box, Button, IconButton, Menu, Toolbar } from '@mui/material';
import { IconMenu, IconUser } from '@tabler/icons-react';

const Header = ({ onMenuClick }: { onMenuClick: () => void }) => {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);

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
            {/* ponytail: sin sesión real todavía; el logout de verdad llega con la auth (día 7). */}
            <Button component={Link} to="/auth/login" variant="outlined" fullWidth>
              Cerrar sesión
            </Button>
          </Box>
        </Menu>
      </Toolbar>
    </AppBar>
  );
};

export default Header;
