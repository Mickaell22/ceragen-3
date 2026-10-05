import { Link } from 'react-router';
import { Typography } from '@mui/material';

const Logo = () => (
  <Typography component={Link} to="/" variant="h3" color="primary" sx={{ display: 'block', py: 2.5 }}>
    Ceragen
  </Typography>
);

export default Logo;
