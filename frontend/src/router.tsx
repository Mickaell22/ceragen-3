import { createBrowserRouter, Navigate, Outlet } from 'react-router';
import { redirectIfLoggedIn, requireUser } from './auth';
import FullLayout from './layouts/FullLayout';
import ErrorPage from './views/ErrorPage';
import Home from './views/Home';
import Login from './views/Login';
import NotFound from './views/NotFound';

const router = createBrowserRouter([
  {
    // Todo lo que cuelga de aquí exige sesión; los hijos leen el usuario con
    // useRouteLoaderData('app').
    id: 'app',
    path: '/',
    loader: requireUser,
    element: <FullLayout />,
    errorElement: <ErrorPage />,
    children: [{ index: true, element: <Home /> }],
  },
  {
    path: '/auth',
    element: <Outlet />,
    children: [
      { path: 'login', loader: redirectIfLoggedIn, element: <Login /> },
      { path: '404', element: <NotFound /> },
    ],
  },
  { path: '*', element: <Navigate to="/auth/404" replace /> },
]);

export default router;
