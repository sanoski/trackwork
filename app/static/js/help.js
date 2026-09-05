/* The Help & Guide modal and its audio guided tour. */

let helpOpenedAt = 0;

export function openHelpModal() {
  document.getElementById('help-modal').classList.remove('hidden');
  helpOpenedAt = Date.now();
  const a = document.getElementById('help-audio');   // always open stopped at the start; never auto-play
  if (a) { a.pause(); try { a.currentTime = 0; } catch (_) {} }
}

export function closeHelpModal() {
  document.getElementById('help-modal').classList.add('hidden');
  const a = document.getElementById('help-audio');
  if (a && !a.paused) a.pause();   // do not keep narrating after the modal is dismissed
}

function fmtAudioTime(s) {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60), sec = Math.floor(s % 60);
  return m + ':' + String(sec).padStart(2, '0');
}

/* Branded play/pause + seek bar for the help narration (served at /static/help-narration.mp3). */
export function setupHelpAudio() {
  const wrap = document.getElementById('help-audio-player');
  if (!wrap) return;
  const audio = document.getElementById('help-audio');
  const toggle = document.getElementById('help-audio-toggle');
  const playIcon = toggle.querySelector('.ha-play');
  const pauseIcon = toggle.querySelector('.ha-pause');
  const bar = document.getElementById('help-audio-bar');
  const fill = document.getElementById('help-audio-fill');
  const curEl = document.getElementById('help-audio-cur');
  const durEl = document.getElementById('help-audio-dur');
  const subEl = document.getElementById('help-audio-sub');
  const origSub = subEl ? subEl.textContent : '';

  const showPlaying = (playing) => {
    playIcon.classList.toggle('hidden', playing);
    pauseIcon.classList.toggle('hidden', !playing);
    toggle.setAttribute('aria-label', playing ? 'Pause audio guide' : 'Play audio guide');
  };

  toggle.addEventListener('click', () => {
    if (wrap.classList.contains('is-unavailable')) return;
    if (Date.now() - helpOpenedAt < 350) return;   // swallow any synthetic click riding the modal-open tap
    if (audio.paused) audio.play().catch(() => {}); else audio.pause();
  });
  audio.addEventListener('play', () => showPlaying(true));
  audio.addEventListener('pause', () => showPlaying(false));
  audio.addEventListener('ended', () => { showPlaying(false); fill.style.width = '0%'; curEl.textContent = '0:00'; });
  audio.addEventListener('loadedmetadata', () => {
    durEl.textContent = fmtAudioTime(audio.duration);
    wrap.classList.remove('is-unavailable');       // self-heal if an early or transient error flagged it
    if (subEl) subEl.textContent = origSub;
  });
  audio.addEventListener('timeupdate', () => {
    const d = audio.duration;
    if (isFinite(d) && d > 0) fill.style.width = (audio.currentTime / d * 100) + '%';
    curEl.textContent = fmtAudioTime(audio.currentTime);
  });
  audio.addEventListener('error', () => {        // no mp3: show an intentional placeholder, not a broken control
    wrap.classList.add('is-unavailable');
    if (subEl) subEl.textContent = 'Audio guide coming soon';
  });
  bar.addEventListener('click', (e) => {
    const d = audio.duration;
    if (!isFinite(d) || d <= 0) return;
    const rect = bar.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    audio.currentTime = frac * d;
  });

  // Do not infer availability from networkState: for a preload=metadata <audio> inside a hidden
  // modal it can read NETWORK_NO_SOURCE at init and falsely show "coming soon". Trust events only.
  if (audio.readyState >= 1 && isFinite(audio.duration)) {
    durEl.textContent = fmtAudioTime(audio.duration);
  } else if (audio.error) {
    wrap.classList.add('is-unavailable');
    if (subEl) subEl.textContent = 'Audio guide coming soon';
  } else {
    try { audio.load(); } catch (_) {}
  }
}
