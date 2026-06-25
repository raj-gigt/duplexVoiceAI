import { useCallback, useRef, useState } from "react";

export type AgentStatus =
  | "disconnected"
  | "connected"
  | "listening"
  | "processing";

const WS_URL = "ws://localhost:8000/voice";
const PLAYBACK_SAMPLE_RATE = 16000;

export function useVoiceAgent() {
  const [status, setStatus] = useState<AgentStatus>("disconnected");
  const [isMicOn, setIsMicOn] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  // Tracks the end time of the last scheduled playback buffer so we can
  // seamlessly queue consecutive chunks without gaps or overlaps.
  const nextPlayTimeRef = useRef(0);
  // Currently scheduled assistant-audio sources, so we can stop them all
  // immediately on a barge-in interrupt.
  const scheduledSourcesRef = useRef<AudioBufferSourceNode[]>([]);
  // Handler that resumes the AudioContext when the tab becomes visible again
  // (browsers auto-suspend the context when the page is backgrounded).
  const visibilityHandlerRef = useRef<(() => void) | null>(null);

  const flushScheduledAudio = useCallback(() => {
    for (const src of scheduledSourcesRef.current) {
      try {
        src.onended = null;
        src.stop();
      } catch {
        // already stopped
      }
    }
    scheduledSourcesRef.current = [];
    if (audioCtxRef.current) {
      nextPlayTimeRef.current = audioCtxRef.current.currentTime;
    }
    setStatus(isMicOn ? "listening" : "connected");
  }, [isMicOn]);

  const playPcmAudio = useCallback((pcmBytes: ArrayBuffer) => {
    const ctx = audioCtxRef.current;
    if (!ctx) return;

    // If the context was suspended (autoplay policy or backgrounded tab), its
    // clock is frozen and scheduled audio never plays. Resume before scheduling.
    if (ctx.state === "suspended") {
      void ctx.resume();
    }

    const int16 = new Int16Array(pcmBytes);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = (int16[i] ?? 0) / 32768;
    }

    const buffer = ctx.createBuffer(1, float32.length, PLAYBACK_SAMPLE_RATE);
    buffer.getChannelData(0).set(float32);

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);

    const now = ctx.currentTime;
    const startAt = Math.max(now, nextPlayTimeRef.current);
    source.start(startAt);
    nextPlayTimeRef.current = startAt + buffer.duration;

    scheduledSourcesRef.current.push(source);
    setStatus("processing");
    source.onended = () => {
      scheduledSourcesRef.current = scheduledSourcesRef.current.filter(
        (s) => s !== source,
      );
      if (audioCtxRef.current && nextPlayTimeRef.current <= audioCtxRef.current.currentTime + 0.05) {
        setStatus(isMicOn ? "listening" : "connected");
      }
    };
  }, [isMicOn]);

  const connect = useCallback(async () => {
    if (wsRef.current) return;

    const ctx = new AudioContext({ sampleRate: 48000 });
    audioCtxRef.current = ctx;
    await ctx.audioWorklet.addModule("/pcm-processor.js");
    // connect() runs from a user gesture, so this satisfies the autoplay policy.
    await ctx.resume();

    // Resume the context whenever the tab returns to the foreground.
    const onVisibility = () => {
      if (
        document.visibilityState === "visible" &&
        audioCtxRef.current &&
        audioCtxRef.current.state === "suspended"
      ) {
        void audioCtxRef.current.resume();
      }
    };
    visibilityHandlerRef.current = onVisibility;
    document.addEventListener("visibilitychange", onVisibility);

    const ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => setStatus("connected");

    ws.onmessage = (event: MessageEvent) => {
      if (typeof event.data === "string") {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "interrupt") {
            flushScheduledAudio();
          }
        } catch {
          // ignore non-JSON control frames
        }
        return;
      }
      if (event.data instanceof ArrayBuffer) {
        playPcmAudio(event.data);
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      setStatus("disconnected");
      setIsMicOn(false);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [playPcmAudio, flushScheduledAudio]);

  const disconnect = useCallback(() => {
    if (visibilityHandlerRef.current) {
      document.removeEventListener("visibilitychange", visibilityHandlerRef.current);
      visibilityHandlerRef.current = null;
    }
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    if (sourceNodeRef.current) {
      sourceNodeRef.current.disconnect();
      sourceNodeRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close();
      audioCtxRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    scheduledSourcesRef.current = [];
    nextPlayTimeRef.current = 0;
    setIsMicOn(false);
    setStatus("disconnected");
  }, []);

  const startMic = useCallback(async () => {
    const ws = wsRef.current;
    const ctx = audioCtxRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN || !ctx) return;

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: { ideal: 48000 },
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
    mediaStreamRef.current = stream;

    const source = ctx.createMediaStreamSource(stream);
    sourceNodeRef.current = source;

    const worklet = new AudioWorkletNode(ctx, "pcm-processor");
    workletNodeRef.current = worklet;

    worklet.port.onmessage = (e: MessageEvent) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(e.data as ArrayBuffer);
      }
    };

    source.connect(worklet);
    // AudioWorklet doesn't need to connect to destination for capture-only
    setIsMicOn(true);
    setStatus("listening");
  }, []);

  const stopMic = useCallback(() => {
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    if (sourceNodeRef.current) {
      sourceNodeRef.current.disconnect();
      sourceNodeRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    setIsMicOn(false);
    setStatus(wsRef.current ? "connected" : "disconnected");
  }, []);

  const toggleMic = useCallback(async () => {
    if (isMicOn) {
      stopMic();
    } else {
      await startMic();
    }
  }, [isMicOn, startMic, stopMic]);

  return { status, isMicOn, connect, disconnect, toggleMic };
}
