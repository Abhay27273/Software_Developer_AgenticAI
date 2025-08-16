import React, { useState, useEffect } from 'react';
import { ThemeProvider } from 'styled-components';
import { GlobalStyles } from './styles/GlobalStyles';
import { theme } from './styles/theme';
import { MainMenuScreen } from './screens/MainMenuScreen';
import { InGameHUDScreen } from './screens/InGameHUDScreen';
import { PauseMenuScreen } from './screens/PauseMenuScreen';
import { ResultsScreen } from './screens/ResultsScreen';

// Enum to manage the current game state, determining which screen to show.
type GameState = 'MainMenu' | 'InGame' | 'Paused' | 'Results';

function App() {
  const [gameState, setGameState] = useState<GameState>('MainMenu');

  // Mock game data
  const [speed, setSpeed] = useState(0);
  const [time, setTime] = useState(0);

  // This effect simulates the game loop for the HUD
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (gameState === 'InGame') {
      interval = setInterval(() => {
        setSpeed(prev => (prev < 290 ? prev + Math.floor(Math.random() * 5) : 290));
        setTime(prev => prev + 1);
      }, 100);
    }
    return () => clearInterval(interval);
  }, [gameState]);

  const formatTime = (totalSeconds: number) => {
    const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const seconds = (totalSeconds % 60).toString().padStart(2, '0');
    return `${minutes}:${seconds}`;
  };

  // State transition handlers
  const handleStartRace = () => setGameState('InGame');
  const handlePause = () => setGameState('Paused');
  const handleResume = () => setGameState('InGame');
  const handleFinishRace = () => setGameState('Results');
  const handleExitToMenu = () => setGameState('MainMenu');

  // This simulates pausing/unpausing via keyboard
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (gameState === 'InGame') handlePause();
        if (gameState === 'Paused') handleResume();
      }
      // Simulate finishing the race for demonstration
      if (e.key === 'f' && gameState === 'InGame') {
        handleFinishRace();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [gameState]);

  const renderScreen = () => {
    switch (gameState) {
      case 'MainMenu':
        return <MainMenuScreen onStartRace={handleStartRace} />;
      case 'InGame':
      case 'Paused':
        // Render HUD and Pause Menu overlay if paused
        return (
          <>
            {/* This div would be replaced by the actual game canvas */}
            <div style={{ background: '#333', width: '100vw', height: '100vh', textAlign: 'center', paddingTop: '40vh', fontSize: '2rem' }}>
              GAME RENDERING AREA <br/> (Press 'Esc' to Pause, 'f' to Finish)
            </div>
            <InGameHUDScreen
              speed={speed}
              lap={1}
              totalLaps={3}
              time={formatTime(time)}
              position={1}
              totalRacers={8}
            />
            {gameState === 'Paused' && (
              <PauseMenuScreen
                onResume={handleResume}
                onRestart={handleStartRace}
                onExitToMenu={handleExitToMenu}
              />
            )}
          </>
        );
      case 'Results':
        return (
          <ResultsScreen
            position={1}
            totalTime="02:34.567"
            bestLap="00:58.123"
            onNextRace={handleStartRace}
            onExitToMenu={handleExitToMenu}
          />
        );
      default:
        return <MainMenuScreen onStartRace={handleStartRace} />;
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <GlobalStyles />
      {renderScreen()}
    </ThemeProvider>
  );
}

export default App;