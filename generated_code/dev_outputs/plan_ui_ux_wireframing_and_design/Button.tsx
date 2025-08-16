import styled from 'styled-components';

// A reusable, styled button component following the UI style guide.
export const Button = styled.button`
  background-color: ${({ theme }) => theme.colors.primary};
  color: ${({ theme }) => theme.colors.textPrimary};
  border: none;
  padding: 1rem 2.5rem;
  font-family: ${({ theme }) => theme.fonts.primary};
  font-size: ${({ theme }) => theme.fontSizes.body};
  text-transform: uppercase;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  min-width: 250px;
  border-radius: 4px;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(10, 116, 218, 0.5);
  }

  &:active {
    transform: translateY(0);
    box-shadow: 0 2px 6px rgba(10, 116, 218, 0.5);
  }
`;