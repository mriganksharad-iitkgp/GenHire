/* Real microphone PCM, mono/16 kHz. No analyser or recorder is owned here. */
class InterviewPCM extends AudioWorkletProcessor {
  constructor() {
    super(); this.samples = []; this.position = 0; this.previous = 0;
    this.packet = new Int16Array(3200); this.used = 0;
    this.port.onmessage = (event) => {
      if (event.data?.type === "flush") { this.flush(); this.port.postMessage({ type: "flushed" }); }
    };
  }
  flush() {
    if (!this.used) return;
    const buffer = this.packet.slice(0, this.used).buffer;
    this.port.postMessage({ type: "audio", buffer }, [buffer]); this.used = 0;
  }
  process(inputs) {
    const channels = inputs[0]; if (!channels?.length) return true;
    let mono = channels[0]; const ratio = sampleRate / 16000;
    if (channels.length > 1) {
      mono = new Float32Array(mono.length);
      for (let i = 0; i < mono.length; i++) for (const channel of channels) mono[i] += channel[i] / channels.length;
    }
    // A carried sample and fractional index preserve continuity across blocks.
    const samples = [this.previous, ...mono];
    while (this.position < mono.length) {
      const index = Math.floor(this.position), fraction = this.position - index;
      const value = samples[index] * (1 - fraction) + samples[index + 1] * fraction;
      this.packet[this.used++] = Math.round(Math.max(-1, Math.min(1, value)) * (value < 0 ? 32768 : 32767));
      if (this.used === this.packet.length) this.flush();
      this.position += ratio;
    }
    this.position -= mono.length; this.previous = mono[mono.length - 1];
    return true;
  }
}
registerProcessor("interview-pcm", InterviewPCM);
