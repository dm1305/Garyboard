import { useRef, useState } from 'react'

export default function Tile({ tile, onEdit }) {
  const audioRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const filled = Boolean(tile.audio_url)

  function play() {
    if (!filled) {
      onEdit()
      return
    }
    const audio = audioRef.current
    if (!audio) return
    audio.currentTime = 0
    audio.play()
    setPlaying(true)
  }

  return (
    <div className={`tile ${filled ? 'tile-filled' : 'tile-empty'} ${playing ? 'tile-playing' : ''}`}>
      <button className="tile-main" onClick={play}>
        {filled ? (
          <span className="tile-label">{tile.custom_name}</span>
        ) : (
          <span className="tile-plus">+</span>
        )}
      </button>
      {filled && (
        <button className="tile-edit" onClick={onEdit} aria-label="Edit tile">
          ✎
        </button>
      )}
      {filled && (
        <audio
          ref={audioRef}
          src={tile.audio_url}
          onEnded={() => setPlaying(false)}
          onPause={() => setPlaying(false)}
        />
      )}
    </div>
  )
}
