import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from 'styled-components';
import { theme } from '../styles/theme';
import { InGameHUDScreen } from './InGameHUDScreen';

describe('InGameHUDScreen', () => {
  it('renders all HUD elements with correct data', () => {
    render(
      <ThemeProvider theme={theme}>
        <InGameHUDScreen
          speed={250}
          lap={2}
          totalLaps={3}
          time="01:45"
          position={1}
          totalRacers={8}
        />
      </ThemeProvider>
    );

    expect(screen.getByText('1 / 8')).toBeInTheDocument();
    expect(screen.getByText('LAP: 2/3')).toBeInTheDocument();
    expect(screen.getByText('TIME: 01:45')).toBeInTheDocument();
    expect(screen.getByText('250')).toBeInTheDocument();
  });
});