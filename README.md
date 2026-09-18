# Garyboard

A shared, public 9-tile soundboard. Anyone with the link can play the tiles;
anyone with the shared edit passphrase can upload a new clip to a tile.

## How it works

- **Frontend**: React + Vite, hosted for free on GitHub Pages.
- **Backend**: [Supabase](https://supabase.com) (free tier) stores the 9 tile
  records (name + audio URL) in Postgres and the trimmed audio clips in
  Storage.
- **Upload flow**: pick a video or audio file on your phone or computer. If
  it's a video, the audio track is extracted in-browser with
  [ffmpeg.wasm](https://ffmpegwasm.netlify.app/) (no server involved). Drag
  the waveform handles to pick up to 15 seconds, preview it, name the tile,
  enter the shared passphrase, and save.
- **Access control**: reading tiles is fully public. Writing (uploading,
  renaming, clearing a tile) requires the shared passphrase, checked
  server-side by a Postgres function (`save_tile` / `clear_tile`) — the
  passphrase itself is never stored or sent in plain text to the client.

## Local development

```bash
npm install
npm run dev
```

The Supabase project URL and public (anon) API key live in `.env` — safe to
commit, since real access control is enforced by Postgres row-level security
and the passphrase-gated RPC functions, not by keeping the key secret.

## Deployment

Pushing to `main` triggers `.github/workflows/deploy.yml`, which builds the
app and publishes `dist/` to GitHub Pages via GitHub Actions.

Supabase's free tier pauses a project after a week with no activity. If the
board stops loading, restore it from the Supabase dashboard (or ask Claude to
run `restore_project`), then reload the page.
