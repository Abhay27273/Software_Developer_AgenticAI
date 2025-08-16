import React from 'react';
import styled from 'styled-components';
import { Button } from '../components/common/Button';
import { Panel } from '../components/common/Panel';

const ResultsContainer = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  width: 100vw;
`;

const Title = styled.h1`
  font-size: ${({ theme }) => theme.fontSizes.h1};
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const Position = styled.div`
  font-size: ${({ theme }) => theme.fontSizes.large};
  font-family: ${({ theme }) => theme.fonts.primary};
  color: ${({ theme }) => theme.colors.accent};
  margin: 1rem 0;
`;

const StatsContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: ${({ theme }) => theme.fontSizes.body};
  color: ${({ theme }) => theme.colors.textSecondary};
  width: 100%;
`;

const Stat = styled.div`
  display: flex;
  justify-content: space-between;
  width: 100%;
  font-family: ${({ theme }) => theme.fonts.secondary};

  span:last-child {
    color: ${({ theme }) => theme.colors.textPrimary};
  }
`;

interface ResultsScreenProps {
  position: number;
  totalTime: string;
  bestLap: string;
  onNextRace: () => void;
  onExitToMenu: () => void;
}

export const ResultsScreen: React.FC<ResultsScreenProps> = ({
  position,
  totalTime,
  bestLap,
  onNextRace,
  onExitToMenu,
}) => {
  return (
    <ResultsContainer>
      <Panel style={{ minWidth: '450px' }}>
        <Title>RACE COMPLETE</Title>
        <Position>{position}st Place</Position>
        <StatsContainer>
          <Stat>
            <span>Total Time:</span>
            <span>{totalTime}</span>
          </Stat>
          <Stat>
            <span>Best Lap:</span>
            <span>{bestLap}</span>
          </Stat>
        </StatsContainer>
        <Button onClick={onNextRace}>Next Race</Button>
        <Button onClick={onExitToMenu}>Main Menu</Button>
      </Panel>
    </ResultsContainer>
  );
};