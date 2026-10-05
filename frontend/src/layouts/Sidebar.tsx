import { NavLink, useLocation } from 'react-router';
import { Box, Drawer, useMediaQuery, type Theme } from '@mui/material';
import { Menu, MenuItem, Sidebar as MuiSidebar } from 'react-mui-sidebar';
import { IconLayoutDashboard, type Icon } from '@tabler/icons-react';
import SimpleBar from 'simplebar-react';
import 'simplebar-react/dist/simplebar.min.css';
import Logo from '../components/Logo';

const WIDTH = '270px';

// Cada módulo nuevo (pacientes, agenda, facturas...) suma su entrada aquí.
const menu: { title: string; href: string; icon: Icon }[] = [
  { title: 'Inicio', href: '/', icon: IconLayoutDashboard },
];

const Items = () => {
  const { pathname } = useLocation();
  return (
    <Box sx={{ px: 3 }}>
      <Logo />
      <MuiSidebar width="100%" showProfile={false} themeColor="#5D87FF" themeSecondaryColor="#49BEFF1a">
        <Menu subHeading="GENERAL">
          {menu.map(({ title, href, icon: Icon }) => (
            <MenuItem
              key={href}
              link={href}
              component={NavLink}
              isSelected={pathname === href}
              borderRadius="7px"
              icon={<Icon stroke={1.5} size="1.3rem" />}
            >
              {title}
            </MenuItem>
          ))}
        </Menu>
      </MuiSidebar>
    </Box>
  );
};

type Props = { mobileOpen: boolean; onMobileClose: () => void };

const Sidebar = ({ mobileOpen, onMobileClose }: Props) => {
  const lgUp = useMediaQuery((theme: Theme) => theme.breakpoints.up('lg'));

  if (lgUp) {
    return (
      <Box sx={{ width: WIDTH, flexShrink: 0 }}>
        <Drawer anchor="left" open variant="permanent" slotProps={{ paper: { sx: { width: WIDTH } } }}>
          <SimpleBar style={{ height: '100%' }}>
            <Items />
          </SimpleBar>
        </Drawer>
      </Box>
    );
  }
  return (
    <Drawer
      anchor="left"
      open={mobileOpen}
      onClose={onMobileClose}
      variant="temporary"
      slotProps={{ paper: { sx: { width: WIDTH, boxShadow: (theme) => theme.shadows[8] } } }}
    >
      <Items />
    </Drawer>
  );
};

export default Sidebar;
