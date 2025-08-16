// This file defines the UI style guide as a reusable theme object.
export const theme = {
  colors: {
    primary: '#0A74DA',
    background: '#121212',
    panelBackground: 'rgba(25, 28, 32, 0.9)',
    textPrimary: '#FFFFFF',
    textSecondary: '#A0A0A0',
    accent: '#FFD700',
    border: '#0A74DA',
  },
  fonts: {
    primary: "'Orbitron', sans-serif",
    secondary: "'Roboto', sans-serif",
  },
  fontSizes: {
    h1: '3.5rem',
    h2: '2.5rem',
    body: '1.2rem',
    hud: '1.8rem',
    large: '5rem',
  },
};

export type ThemeType = typeof theme;