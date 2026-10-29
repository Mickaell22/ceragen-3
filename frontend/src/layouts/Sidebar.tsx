import { NavLink, useLocation, useRouteLoaderData } from 'react-router';
import { Box, Drawer, useMediaQuery, type Theme } from '@mui/material';
import { Menu, MenuItem, Sidebar as MuiSidebar } from 'react-mui-sidebar';
import {
  IconCalendar,
  IconCash,
  IconFileInvoice,
  IconLayoutDashboard,
  IconPoint,
  IconReportAnalytics,
  IconSettings,
  IconStethoscope,
  IconUsers,
  type Icon,
} from '@tabler/icons-react';
import SimpleBar from 'simplebar-react';
import 'simplebar-react/dist/simplebar.min.css';
import Logo from '../components/Logo';
import type { Me } from '../auth';

const WIDTH = '270px';

// Íconos que la base puede nombrar (security.menu.icon). Importarlos uno por uno
// deja fuera del bundle los miles de íconos de Tabler que no se usan.
// ponytail: un nombre que no esté aquí cae en IconPoint; al sumar un menú con
// ícono nuevo, agregarlo al mapa.
const ICONS: Record<string, Icon> = {
  'layout-dashboard': IconLayoutDashboard,
  users: IconUsers,
  calendar: IconCalendar,
  stethoscope: IconStethoscope,
  'file-invoice': IconFileInvoice,
  cash: IconCash,
  'report-analytics': IconReportAnalytics,
  settings: IconSettings,
};

// Los menús vienen de la API según los roles del usuario (security.fn_my_menus).
const Items = () => {
  const { pathname } = useLocation();
  const { menus } = useRouteLoaderData('app') as Me;
  return (
    <Box sx={{ px: 3 }}>
      <Logo />
      <MuiSidebar width="100%" showProfile={false} themeColor="#5D87FF" themeSecondaryColor="#49BEFF1a">
        {menus.map(({ module, menus: items }) => (
          <Menu key={module} subHeading={module.toUpperCase()}>
            {items.map(({ name, path, icon }) => {
              const ItemIcon = ICONS[icon] ?? IconPoint;
              return (
                <MenuItem
                  key={path}
                  link={path}
                  component={NavLink}
                  isSelected={pathname === path}
                  borderRadius="7px"
                  icon={<ItemIcon stroke={1.5} size="1.3rem" />}
                >
                  {name}
                </MenuItem>
              );
            })}
          </Menu>
        ))}
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
