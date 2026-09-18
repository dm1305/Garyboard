import { useEffect, useRef, useState } from 'react'
import { extractAudioFromVideo } from '../lib/ffmpeg'
import { decodeToAudioBuffer, trimAudioBuffer, encodeWav, MAX_CLIP_SECONDS } from '../lib/audio'
import { supabase, CLIPS_BUCKET } from '../lib/supabase'
import Waveform from './Waveform'

const MAX_INPUT_BYTES = 150 * 1024 * 1024 // 150MB, guards against the browser hanging on huge files

export default function EditTileModal({ slot, existingTile, onClose, onSaved, onCleared }) {
  const [step, setStep] = useState('pick') // pick | processing | trim | details
  const [error, setError] = useState('')
  const [progress, setProgress] = useState(0)
  const [sourceBlob, setSourceBlob] = useState(null)
  const [audioBuffer, setAudioBuffer] = useState(null)
  const [start, setStart] = useState(0)
  const [end, setEnd] = useState(0)
  const [name, setName] = useState(existingTile?.custom_name || '')
  const [passphrase, setPassphrase] = useState('')
  const [saving, setSaving] = useState(false)
  const [previewUrl, setPreviewUrl] = useState(null)
  const previewAudioRef = useRef(null)

  useEffect(() => {
    if (!sourceBlob) return
    const url = URL.createObjectURL(sourceBlob)
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [sourceBlob])

  async function handleFile(file) {
    setError('')
    if (file.size > MAX_INPUT_BYTES) {
      setError('That file is too large (max 150MB). Try a shorter clip.')
      return
    }
    setStep('processing')
    setProgress(0)
    try {
      const isVideo = file.type.startsWith('video/')
      const audioBlob = isVideo ? await extractAudioFromVideo(file, setProgress) : file
      const buffer = await decodeToAudioBuffer(audioBlob)
      const clampedEnd = Math.min(buffer.duration, MAX_CLIP_SECONDS)

      setSourceBlob(audioBlob)
      setAudioBuffer(buffer)
      setStart(0)
      setEnd(clampedEnd)
      setStep('trim')
    } catch (err) {
      console.error(err)
      setError('Could not read that file as audio or video. Try a different file.')
      setStep('pick')
    }
  }

  function onFileInputChange(e) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  function previewClip() {
    const audioEl = previewAudioRef.current
    if (!audioEl) return
    audioEl.currentTime = start
    audioEl.play()
    const stopAtEnd = () => {
      if (audioEl.currentTime >= end) {
        audioEl.pause()
        audioEl.removeEventListener('timeupdate', stopAtEnd)
      }
    }
    audioEl.addEventListener('timeupdate', stopAtEnd)
  }

  async function handleSaveDetails() {
    if (!name.trim()) {
      setError('Give this clip a name.')
      return
    }
    if (!passphrase.trim()) {
      setError('Enter the shared edit passphrase.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const trimmed = await trimAudioBuffer(audioBuffer, start, end)
      const wavBlob = encodeWav(trimmed)

      const path = `slot-${slot}-${Date.now()}.wav`
      const { error: uploadError } = await supabase.storage
        .from(CLIPS_BUCKET)
        .upload(path, wavBlob, { contentType: 'audio/wav', upsert: true })
      if (uploadError) throw uploadError

      const { data: publicUrlData } = supabase.storage.from(CLIPS_BUCKET).getPublicUrl(path)
      const audioUrl = publicUrlData.publicUrl

      const { error: rpcError } = await supabase.rpc('save_tile', {
        p_slot: slot,
        p_name: name.trim(),
        p_audio_url: audioUrl,
        p_passphrase: passphrase,
      })
      if (rpcError) throw rpcError

      onSaved({ slot_number: slot, custom_name: name.trim(), audio_url: audioUrl })
    } catch (err) {
      console.error(err)
      setError(err.message?.includes('invalid passphrase') ? 'Wrong passphrase.' : 'Could not save. Try again.')
    } finally {
      setSaving(false)
    }
  }

  async function handleClear() {
    if (!passphrase.trim()) {
      setError('Enter the shared edit passphrase to remove this clip.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const { error: rpcError } = await supabase.rpc('clear_tile', {
        p_slot: slot,
        p_passphrase: passphrase,
      })
      if (rpcError) throw rpcError
      onCleared(slot)
    } catch (err) {
      console.error(err)
      setError(err.message?.includes('invalid passphrase') ? 'Wrong passphrase.' : 'Could not remove clip.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h2>{existingTile?.audio_url ? 'Replace clip' : 'Add clip'}</h2>

        {step === 'pick' && (
          <div className="modal-step">
            <p>Pick a video or audio file from your device.</p>
            <input
              type="file"
              accept="video/*,audio/*"
              onChange={onFileInputChange}
            />
            {existingTile?.audio_url && (
              <div className="modal-danger-zone">
                <p>Or remove the current clip from this tile:</p>
                <input
                  type="password"
                  placeholder="Edit passphrase"
                  value={passphrase}
                  onChange={(e) => setPassphrase(e.target.value)}
                />
                <button className="btn btn-danger" onClick={handleClear} disabled={saving}>
                  {saving ? 'Removing…' : 'Remove clip'}
                </button>
              </div>
            )}
          </div>
        )}

        {step === 'processing' && (
          <div className="modal-step">
            <p>Processing your file…</p>
            <div className="progress-bar">
              <div className="progress-bar-fill" style={{ width: `${Math.round(progress * 100)}%` }} />
            </div>
          </div>
        )}

        {step === 'trim' && audioBuffer && (
          <div className="modal-step">
            <p>Drag the handles to pick the part you want (max {MAX_CLIP_SECONDS}s).</p>
            <Waveform
              audioBuffer={audioBuffer}
              start={start}
              end={Math.min(end, start + MAX_CLIP_SECONDS)}
              onChange={(s, e) => {
                setStart(s)
                setEnd(Math.min(e, s + MAX_CLIP_SECONDS, audioBuffer.duration))
              }}
            />
            <audio ref={previewAudioRef} src={previewUrl || undefined} />
            <div className="modal-actions">
              <button className="btn" onClick={previewClip}>▶ Preview</button>
              <button className="btn btn-primary" onClick={() => setStep('details')}>
                Use this clip
              </button>
            </div>
          </div>
        )}

        {step === 'details' && (
          <div className="modal-step">
            <label>
              Tile name
              <input
                type="text"
                value={name}
                maxLength={40}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Airhorn"
              />
            </label>
            <label>
              Edit passphrase
              <input
                type="password"
                value={passphrase}
                onChange={(e) => setPassphrase(e.target.value)}
                placeholder="Shared passphrase"
              />
            </label>
            <div className="modal-actions">
              <button className="btn" onClick={() => setStep('trim')} disabled={saving}>
                Back
              </button>
              <button className="btn btn-primary" onClick={handleSaveDetails} disabled={saving}>
                {saving ? 'Saving…' : 'Save to tile'}
              </button>
            </div>
          </div>
        )}

        {error && <p className="modal-error">{error}</p>}
      </div>
    </div>
  )
}
