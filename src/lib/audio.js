export const MAX_CLIP_SECONDS = 15

let sharedContext = null
function getAudioContext() {
  if (!sharedContext) {
    const Ctx = window.AudioContext || window.webkitAudioContext
    sharedContext = new Ctx()
  }
  return sharedContext
}

export async function decodeToAudioBuffer(blob) {
  const ctx = getAudioContext()
  const arrayBuffer = await blob.arrayBuffer()
  return ctx.decodeAudioData(arrayBuffer)
}

// Renders [start, end] seconds of an AudioBuffer into a new mono AudioBuffer.
export async function trimAudioBuffer(audioBuffer, start, end) {
  const sampleRate = audioBuffer.sampleRate
  const startFrame = Math.floor(start * sampleRate)
  const endFrame = Math.min(audioBuffer.length, Math.ceil(end * sampleRate))
  const frameCount = Math.max(1, endFrame - startFrame)

  const OfflineCtx = window.OfflineAudioContext || window.webkitOfflineAudioContext
  const offline = new OfflineCtx(1, frameCount, sampleRate)

  const trimmed = offline.createBuffer(1, frameCount, sampleRate)
  const channelCount = audioBuffer.numberOfChannels
  const mixed = trimmed.getChannelData(0)
  for (let i = 0; i < frameCount; i++) {
    let sum = 0
    for (let c = 0; c < channelCount; c++) {
      sum += audioBuffer.getChannelData(c)[startFrame + i] || 0
    }
    mixed[i] = sum / channelCount
  }

  const source = offline.createBufferSource()
  source.buffer = trimmed
  source.connect(offline.destination)
  source.start(0)
  return offline.startRendering()
}

// Encodes a (mono) AudioBuffer as a 16-bit PCM WAV Blob.
export function encodeWav(audioBuffer) {
  const samples = audioBuffer.getChannelData(0)
  const sampleRate = audioBuffer.sampleRate
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)

  const writeString = (offset, str) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
  }

  writeString(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // byte rate
  view.setUint16(32, 2, true) // block align
  view.setUint16(34, 16, true) // bits per sample
  writeString(36, 'data')
  view.setUint32(40, samples.length * 2, true)

  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    offset += 2
  }

  return new Blob([buffer], { type: 'audio/wav' })
}

// Downsamples an AudioBuffer's first channel into min/max peak pairs for waveform drawing.
export function computePeaks(audioBuffer, bucketCount) {
  const data = audioBuffer.getChannelData(0)
  const bucketSize = Math.max(1, Math.floor(data.length / bucketCount))
  const peaks = []
  for (let i = 0; i < bucketCount; i++) {
    const start = i * bucketSize
    let min = 0
    let max = 0
    for (let j = start; j < Math.min(start + bucketSize, data.length); j++) {
      const v = data[j]
      if (v < min) min = v
      if (v > max) max = v
    }
    peaks.push([min, max])
  }
  return peaks
}
