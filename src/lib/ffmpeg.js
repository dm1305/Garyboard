import { FFmpeg } from '@ffmpeg/ffmpeg'
import { toBlobURL } from '@ffmpeg/util'

const CORE_VERSION = '0.12.6'
const CORE_BASE = `https://unpkg.com/@ffmpeg/core@${CORE_VERSION}/dist/esm`

let ffmpegPromise = null

// Lazily loads the single-threaded ffmpeg.wasm core (no SharedArrayBuffer /
// cross-origin-isolation headers required, so it works unmodified on GitHub Pages).
function getFFmpeg() {
  if (!ffmpegPromise) {
    ffmpegPromise = (async () => {
      const ffmpeg = new FFmpeg()
      await ffmpeg.load({
        coreURL: await toBlobURL(`${CORE_BASE}/ffmpeg-core.js`, 'text/javascript'),
        wasmURL: await toBlobURL(`${CORE_BASE}/ffmpeg-core.wasm`, 'application/wasm'),
      })
      return ffmpeg
    })()
  }
  return ffmpegPromise
}

// Extracts the audio track from a video file and returns it as a Blob (mp3).
export async function extractAudioFromVideo(file, onProgress) {
  const ffmpeg = await getFFmpeg()
  const inputName = `input-${Date.now()}.${(file.name.split('.').pop() || 'mp4')}`
  const outputName = 'output.mp3'

  const progressHandler = ({ progress }) => {
    if (onProgress) onProgress(Math.min(1, Math.max(0, progress)))
  }
  ffmpeg.on('progress', progressHandler)

  try {
    await ffmpeg.writeFile(inputName, new Uint8Array(await file.arrayBuffer()))
    await ffmpeg.exec(['-i', inputName, '-vn', '-acodec', 'libmp3lame', '-q:a', '4', outputName])
    const data = await ffmpeg.readFile(outputName)
    return new Blob([data.buffer], { type: 'audio/mpeg' })
  } finally {
    ffmpeg.off('progress', progressHandler)
    await ffmpeg.deleteFile(inputName).catch(() => {})
    await ffmpeg.deleteFile(outputName).catch(() => {})
  }
}
