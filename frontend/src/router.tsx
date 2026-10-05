import { createBrowserRouter, Navigate, Outlet } from 'react-router';
import FullLayout from './layouts/FullLayout';
import Home from './views/Home';
import Login from './views/Login';
import NotFound from './views/NotFound';

const router = createBrowserRouter([
  {
    path: '/',
    element: <FullLayout />,
    children: [{ index: true, element: <Home /> }],
  },
  {
    path: '/auth',
    element: <Outlet />,
    children: [
      { path: 'login', element: <Login /> },
      { path: '404', element: <NotFound /> },
    ],
  },
  { path: '*', element: <Navigate to="/auth/404" replace /> },
]);

export default router;
