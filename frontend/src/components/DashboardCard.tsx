import type { ReactNode } from 'react';
import { Box, Card, CardContent, Stack, Typography } from '@mui/material';

type Props = { title?: string; subtitle?: string; action?: ReactNode; children: ReactNode };

const DashboardCard = ({ title, subtitle, action, children }: Props) => (
  <Card elevation={9}>
    <CardContent sx={{ p: '30px' }}>
      {title && (
        <Stack direction="row" spacing={2} sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box>
            <Typography variant="h5">{title}</Typography>
            {subtitle && (
              <Typography variant="subtitle2" color="textSecondary">
                {subtitle}
              </Typography>
            )}
          </Box>
          {action}
        </Stack>
      )}
      {children}
    </CardContent>
  </Card>
);

export default DashboardCard;
