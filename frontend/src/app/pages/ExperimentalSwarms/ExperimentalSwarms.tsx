import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

const ExperimentalSwarms: React.FC = () => {
  const c = useClaudeTokens();

  return (
    <Box
      sx={{
        height: '100%',
        overflow: 'auto',
        bgcolor: c.bg.page,
        color: c.text.primary,
        px: 4,
        py: 3,
      }}
    >
      <Box
        sx={{
          maxWidth: 980,
          mx: 'auto',
          border: `1px solid ${c.border.subtle}`,
          bgcolor: c.bg.surface,
          borderRadius: 3,
          p: 3,
        }}
      >
        <Typography sx={{ fontSize: '1.25rem', fontWeight: 650, mb: 1 }}>
          Experimental Swarms
        </Typography>
        <Typography sx={{ color: c.text.muted, fontSize: '0.92rem' }}>
          Local-first experimental swarm runtime view.
        </Typography>
      </Box>
    </Box>
  );
};

export default ExperimentalSwarms;
