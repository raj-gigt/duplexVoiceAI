import type { AgentStatus } from "../hooks/useVoiceAgent";

interface VoiceButtonProps {
  status: AgentStatus;
  isMicOn: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  onToggleMic: () => void;
}

export default function VoiceButton({
  status,
  isMicOn,
  onConnect,
  onDisconnect,
  onToggleMic,
}: VoiceButtonProps) {
  if (status === "disconnected") {
    return (
      <button className="voice-btn voice-btn--connect" onClick={onConnect}>
        <MicIcon />
        <span>Connect</span>
      </button>
    );
  }

  return (
    <div className="voice-controls">
      <button
        className={`voice-btn voice-btn--mic ${isMicOn ? "voice-btn--active" : ""} ${status === "processing" ? "voice-btn--speaking" : ""}`}
        onClick={onToggleMic}
      >
        <div className={`pulse-ring ${status === "listening" ? "pulse-ring--active" : ""}`} />
        <div className={`pulse-ring pulse-ring--delay ${status === "listening" ? "pulse-ring--active" : ""}`} />
        {isMicOn ? <MicIcon /> : <MicOffIcon />}
      </button>
      <button className="voice-btn voice-btn--disconnect" onClick={onDisconnect}>
        <HangUpIcon />
        <span>Disconnect</span>
      </button>
    </div>
  );
}

function MicIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="1" width="6" height="11" rx="3" />
      <path d="M19 10v1a7 7 0 0 1-14 0v-1" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

function MicOffIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="1" y1="1" x2="23" y2="23" />
      <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
      <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2c0 .76-.13 1.49-.35 2.17" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

function HangUpIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.68 13.31a16 16 0 0 0 3.41 2.6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7 2 2 0 0 1 1.72 2v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91" />
      <line x1="23" y1="1" x2="1" y2="23" />
    </svg>
  );
}
