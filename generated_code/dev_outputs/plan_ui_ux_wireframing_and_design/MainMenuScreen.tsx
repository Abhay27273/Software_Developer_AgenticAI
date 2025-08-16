import React from 'react';
import styled from 'styled-components';
import { Button } from '../components/common/Button';
import { Panel } from '../components/common/Panel';

const MenuContainer = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  width: 100vw;
`;

const Title = styled.h1`
  font-size: ${({ theme }) => theme.fontSizes.h1};
  color: ${({ theme }) => theme.colors.textPrimary};
  margin-bottom: 1rem;
  text-shadow: 0 0 10px ${({ theme }) => theme.colors.primary};
`;

interface MainMenuScreenProps {
  onStartRace: () => void;
}

export const MainMenuScreen: React.FC<MainMenuScreenProps> = ({ onStartRace }) => {
  return (
    <MenuContainer>
      <Panel>
        <Title>HYPERDRIVE</Title>
        <Button onClick={onStartRace}>Start Race</Button>
        <Button onClick={() => alert('Options clicked!')}>Options</Button>
        <Button onClick={() => alert('Exit clicked!')}>Exit</Button>
      </Panel>
    </MenuContainer>
  );
};