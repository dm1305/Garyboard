import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'
import Tile from './components/Tile'
import EditTileModal from './components/EditTileModal'
import './App.css'

const SLOTS = Array.from({ length: 9 }, (_, i) => i + 1)

export default function App() {
  const [tiles, setTiles] = useState(() =>
    Object.fromEntries(SLOTS.map((slot) => [slot, { slot_number: slot, custom_name: null, audio_url: null }]))
  )
  const [loadError, setLoadError] = useState('')
  const [editingSlot, setEditingSlot] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      const { data, error } = await supabase.from('tiles').select('*').order('slot_number')
      if (cancelled) return
      if (error) {
        setLoadError("Couldn't sync with the shared board — showing your last known tiles. Reload to retry.")
      } else {
        setTiles((prev) => {
          const next = { ...prev }
          data.forEach((row) => {
            next[row.slot_number] = row
          })
          return next
        })
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  function handleSaved(tile) {
    setTiles((prev) => ({ ...prev, [tile.slot_number]: tile }))
    setEditingSlot(null)
  }

  function handleCleared(slot) {
    setTiles((prev) => ({ ...prev, [slot]: { slot_number: slot, custom_name: null, audio_url: null } }))
    setEditingSlot(null)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Garyboard</h1>
        <p>Tap a tile to play. Tap ✎ to replace it.</p>
      </header>

      {loadError && <p className="load-error">{loadError}</p>}

      <main className="grid">
        {SLOTS.map((slot) => (
          <Tile key={slot} tile={tiles[slot]} onEdit={() => setEditingSlot(slot)} />
        ))}
      </main>

      {editingSlot && (
        <EditTileModal
          slot={editingSlot}
          existingTile={tiles[editingSlot]}
          onClose={() => setEditingSlot(null)}
          onSaved={handleSaved}
          onCleared={handleCleared}
        />
      )}
    </div>
  )
}
