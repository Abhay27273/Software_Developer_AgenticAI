import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from 'styled-components';
import { theme } from '../styles/theme';
import { MainMenuScreen } from './MainMenuScreen';

describe('MainMenuScreen', () => {
  it('renders the main menu with title and buttons', () => {
    const handleStartRace = jest.fn();
    render(
      <ThemeProvider theme={theme}>
        <MainMenuScreen onStartRace={handleStartRace} />
      </ThemeProvider>
    );

    // Check for the title
    expect(screen.getByText('HYPERDRIVE')).toBeInTheDocument();

    // Check for buttons
    expect(screen.getByRole('button', { name: /start race/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /options/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /exit/i })).toBeInTheDocument();
  });
});