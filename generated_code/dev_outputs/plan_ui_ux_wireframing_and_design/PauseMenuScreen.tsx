import React from 'react';
import styled from 'styled-components';
import { Button } from '../components/common/Button';
import { Panel } from '../components/common/Panel';

const PauseOverlay = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
`;

const Title = styled.h2`
  font-size: ${({ theme }) => theme.fontSizes.h2};
  color: ${({ theme }) => theme.colors.textPrimary};
`;

interface PauseMenuScreenProps {
  onResume: () => void;
  onRestart: () => void;
  onExitToMenu: () => void;
}

export const PauseMenuScreen: React.FC<PauseMenuScreenProps> = ({
  onResume,
  onRestart,
  onExitToMenu,
}) => {
  return (
    <PauseOverlay>
      <Panel>
        <Title>PAUSED</Title>
        <Button onClick={onResume}>Resume</Button>
        <Button onClick={onRestart}>Restart Race</Button>
        <Button onClick={onExitToMenu}>Main Menu</Button>
      </Panel>
    </PauseOverlay>
  );
};