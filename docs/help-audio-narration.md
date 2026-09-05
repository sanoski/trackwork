# Help & Guide: audio guided tour

The Help & Guide modal (opened from the "?" bar under the portal header) leads with a
branded audio player that plays a spoken narration of the guide. This file is the durable
record of that feature: how it works, how to update the audio, and the narration script.

## How it works (code)

- **Markup:** `app/static/index.html`, `#help-audio-player` at the top of `.help-body`,
  containing `<audio id="help-audio">` plus the play/pause button, seek bar, and time readout.
- **Styles:** `.help-audio*` rules in `app/static/style.css` (the big red circular button is
  `.help-audio-btn`).
- **Behavior:** `setupHelpAudio()` plus `openHelpModal()` / `closeHelpModal()` in
  `app/static/js/help.js`. It **never auto-plays**: opening the modal pauses and resets to 0:00,
  a short post-open guard swallows the synthetic "ghost" click that can ride the modal-open
  tap, and closing the modal pauses it. If the mp3 is missing it drops to a grayed
  "Audio guide coming soon" state instead of showing a broken control.

## The audio file

- Served **and committed** at `app/static/help-narration.mp3`. That tracked copy is the durable
  source of truth (the original ElevenLabs render is generated outside the repo and is not kept).
- The `<audio src>` in `index.html` is cache-busted with a manual version: `help-narration.mp3?v=N`.
- **Browsers and any CDN or caching proxy in front of the app cache the mp3.** Overwriting the
  file alone is not enough; visitors keep getting the stale audio until the cache expires. Bump
  `?v=N` so the URL changes and everything fetches fresh.
- Current: **v3**, ~10 min 59 s, 192 kbps mono, ~15.8 MB (recorded 2026-09-05, covers every screen).

## To update the narration

1. Edit `docs/help-narration-script.txt`. Keep it TTS-friendly: spell out abbreviations and codes the way they
   should sound (e.g. "Vermont Rail System", "Maintenance of Way", "Washington County Railroad's
   Connecticut River Division", "Saint Johnsbury", "nine forty-two", "Sunday through Saturday").
2. Generate a new mp3 from the script (ElevenLabs).
3. Overwrite `app/static/help-narration.mp3` with the new render.
4. Bump the version in `app/static/index.html`: change `help-narration.mp3?v=3` to `?v=4`.
5. Update the player's subtitle in `index.html` if the coverage changed (the line under
   "Listen to the guided tour").
6. Commit both files. Verify it is live:
   `curl -sI "https://YOUR-HOST/static/help-narration.mp3?v=4"` should show the new
   `content-length`.

## Narration script

The spoken text lives in `docs/help-narration-script.txt`, plain text with nothing but the words,
so it can be pasted straight into a text-to-speech tool. It is the script behind the current
recording (version 3). If the wording is tweaked during a future recording, reconcile the text
file so it stays the source of truth. Running time is roughly eleven minutes.
