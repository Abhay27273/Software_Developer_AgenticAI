import React from 'react';
import styled from 'styled-components';

const HUDContainer = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none; /* Allows clicks to pass through to the game canvas */
  font-family: ${({ theme }) => theme.fonts.primary};
  color: ${({ theme }) => theme.colors.textPrimary};
  text-shadow: 0 0 5px rgba(0, 0, 0, 0.8);
`;

const HUDElement = styled.div`
  position: absolute;
  padding: 1.5rem;
  font-size: ${({ theme }) => theme.fontSizes.hud};
`;

const Position = styled(HUDElement)`
  top: 0;
  left: 0;
`;

const LapTime = styled(HUDElement)`
  top: 0;
  right: 0;
  text-align: right;
`;

const Speedometer = styled(HUDElement)`
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  font-size: ${({ theme }) => theme.fontSizes.large};
`;

interface InGameHUDScreenProps {
  speed: number;
  lap: number;
  totalLaps: number;
  time: string;
  position: number;
  totalRacers: number;
}

export const InGameHUDScreen: React.FC<InGameHUDScreenProps> = ({
  speed,
  lap,
  totalLaps,
  time,
  position,
  totalRacers,
}) => {
  return (
    <HUDContainer>
      <Position>
        {position} / {totalRacers}
      </Position>
      <LapTime>
        <div>LAP: {lap}/{totalLaps}</div>
        <div>TIME: {time}</div>
      </LapTime>
      <Speedometer>
        {speed} <span style={{ fontSize: '1.5rem' }}>KM/H</span>
      </Speedometer>
    </HUDContainer>
  );
};