import styled from 'styled-components';

// A reusable panel component for menus and results screens.
export const Panel = styled.div`
  background-color: ${({ theme }) => theme.colors.panelBackground};
  border: 2px solid ${({ theme }) => theme.colors.border};
  border-radius: 8px;
  padding: 2rem 3rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
  box-shadow: 0 0 20px rgba(10, 116, 218, 0.3);
  backdrop-filter: blur(5px);
`;