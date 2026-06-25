import type { AgentStatus } from "../hooks/useVoiceAgent";

const labels: Record<AgentStatus, string> = {
  disconnected: "Disconnected",
  connected: "Connected",
  listening: "Listening...",
  processing: "Assistant speaking...",
};

export default function StatusIndicator({ status }: { status: AgentStatus }) {
  return (
    <div className={`status-indicator status-${status}`}>
      <span className="status-dot" />
      <span className="status-label">{labels[status]}</span>
    </div>
  );
}
