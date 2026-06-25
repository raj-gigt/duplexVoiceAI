const TARGET_SAMPLE_RATE = 16000;

class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channelData = input[0];
    const ratio = sampleRate / TARGET_SAMPLE_RATE;

    for (let i = 0; i < channelData.length; i++) {
      this._buffer.push(channelData[i]);
    }

    // When we have enough samples to produce a chunk at 16kHz, downsample and send
    const samplesNeeded = Math.floor(this._buffer.length / ratio);
    if (samplesNeeded === 0) return true;

    const pcm16 = new Int16Array(samplesNeeded);
    for (let i = 0; i < samplesNeeded; i++) {
      const srcIndex = Math.round(i * ratio);
      const sample = this._buffer[srcIndex] ?? 0;
      pcm16[i] = Math.max(-32768, Math.min(32767, Math.round(sample * 32767)));
    }

    // Drain consumed source samples
    const consumed = Math.round(samplesNeeded * ratio);
    this._buffer = this._buffer.slice(consumed);

    this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    return true;
  }
}

registerProcessor("pcm-processor", PCMProcessor);
