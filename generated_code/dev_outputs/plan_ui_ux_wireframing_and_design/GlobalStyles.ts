import { createGlobalStyle } from 'styled-components';
import { ThemeType } from './theme';

// Defines global CSS styles for the application.
export const GlobalStyles = createGlobalStyle<{ theme: ThemeType }>`
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  body {
    background-color: ${({ theme }) => theme.colors.background};
    color: ${({ theme }) => theme.colors.textPrimary};
    font-family: ${({ theme }) => theme.fonts.secondary};
    overflow: hidden; /* Prevents scrollbars in the game UI */
  }

  h1, h2, h3, h4, h5, h6 {
    font-family: ${({ theme }) => theme.fonts.primary};
    font-weight: 700;
  }
`;