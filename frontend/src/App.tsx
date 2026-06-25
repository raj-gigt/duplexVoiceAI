import { useVoiceAgent } from "./hooks/useVoiceAgent";
import VoiceButton from "./components/VoiceButton";
import StatusIndicator from "./components/StatusIndicator";

export default function App() {
  const { status, isMicOn, connect, disconnect, toggleMic } = useVoiceAgent();

  return (
    <div className="app">
      <header className="app-header">
        <h1>Voice Agent</h1>
        <p className="app-subtitle">Duplex voice assistant powered by AI</p>
      </header>

      <main className="app-main">
        <StatusIndicator status={status} />
        <VoiceButton
          status={status}
          isMicOn={isMicOn}
          onConnect={connect}
          onDisconnect={disconnect}
          onToggleMic={toggleMic}
        />
        {status === "disconnected" && (
          <p className="app-hint">
            Click Connect to start a voice conversation
          </p>
        )}
        {status === "connected" && !isMicOn && (
          <p className="app-hint">
            Click the microphone to start speaking
          </p>
        )}
      </main>

      <footer className="app-footer">
        <span>ws://localhost:8000/voice</span>
      </footer>
    </div>
  );
}
