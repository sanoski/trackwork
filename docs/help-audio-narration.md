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
- Current: **v2**, ~7 min 31 s, 192 kbps mono, ~10.8 MB.

## To update the narration

1. Edit the script below. Keep it TTS-friendly: spell out abbreviations and codes the way they
   should sound (e.g. "Vermont Rail System", "Maintenance of Way", "Washington County Railroad's
   Connecticut River Division", "Saint Johnsbury", "nine forty-two", "Sunday through Saturday").
2. Generate a new mp3 from the script (ElevenLabs).
3. Overwrite `app/static/help-narration.mp3` with the new render.
4. Bump the version in `app/static/index.html`: change `help-narration.mp3?v=2` to `?v=3`.
5. Commit both files. Verify it is live:
   `curl -sI "https://YOUR-HOST/static/help-narration.mp3?v=3"` should show the new
   `content-length`.

## Narration script (source text for TTS)

Note: the current recording was made before the Log Work, Correct a Day, Switches & Derails,
Worksites, Projects, and Users & Settings screens existed. It covers the sidebar and the report
wizard accurately; the written help in the modal covers the rest. Re-record when convenient.

This is the script used to generate the current audio. If the wording was tweaked during
recording, reconcile it here so this stays the source of truth.

---

Welcome to the Vermont Rail System Maintenance of Way Tracker. If you spend your days putting in railroad ties, setting switches, and keeping the line in shape, this one was built for you. Think of it as command central for the crew's work. It keeps a running record of every tie, every switch, and every derail you install, and at the end of the week it turns all of that into a clean, professional report that lands in the office's inbox. No more clipboards flapping in the wind, and no more squinting at a coffee-stained spreadsheet. Just the numbers, the charts, and the credit your crew has earned. Let's take a quick tour.

The tracker organizes everything into two kinds of work. The first is a company line. That's ongoing railroad maintenance, like the Washington County Railroad's Connecticut River Division. A line can have worksites underneath it, such as Saint Johnsbury, so you can zoom in on one location or step back and see the whole line at once. The second kind is a sponsored job. That's a focused project with a tie goal and a deadline, like job nine forty-two. For those, the tracker keeps score against the goal, and even projects your finish date, so everyone knows exactly where things stand.

On the left, you'll find the sidebar. Think of it as your map of the work. Click a line, and you'll see everything on it, all worksites combined. Click a worksite beneath it, and you'll focus on just that site. Here's the part worth remembering: whatever you select in the sidebar is what your report will cover. Pick the whole line, and you get the whole line. Pick one worksite, and the report narrows to match. Simple.

When you're ready, look at the Generate Report button at the top. It's smarter than it looks. It actually tells you what it's about to do, right there on the button. It might say "Full line," or it might name a worksite like Saint Johnsbury, so you always know the scope before you click. Give it a tap, and the report wizard opens. On the right side of the screen, or just below it on your phone, you'll see a live preview that updates the moment you change a setting. What you see is what the office gets.

Inside the wizard, the first choice is scope. You can build a report for the whole line, or for a single worksite. It starts on whatever you had selected in the sidebar, but you're free to change your mind right here, without backing out.

Next is the time period, and you've got four ways to slice it. "Most recent reported week" gives you the latest Sunday-through-Saturday week with work logged. That's your standard weekly report. "Pick a week" lets you grab any week you want; just choose a date inside it. "Full project" covers everything from the first day of work to the last, which is perfect for wrapping up a finished job, or showing off a full progress summary. And "Date range" lets you set a custom start and end. However you want to look at the work, the report won't judge.

Then comes the fun part: deciding what goes in. Start with ties. You can include new and relay ties together, new only, relay only, or none at all. Quick refresher. New ties are exactly that, freshly installed. Relay ties are reclaimed and reused, cleaned up and given a second life on the rail. The recycling program of the tie world. Next, switches and derails. Toggle these on to include your turnout and derail timber work on company lines. There's also a verbose option called "Itemize switches and derails." Leave it off, and the report stays short and tidy: all your switches are summed into one neat "timbers by length" chart and a single table, and your derails do the same. Turn it on, and every single switch and derail gets its own diagram and its own table. That makes for a much longer report, so save it for when someone really needs every piece broken out. You can also include the charts: weekly production, cumulative totals, work composition, and a breakdown by worksite. The office folks do love a good chart. And finally, equipment downtime, which is your machine downtime log. One note there. Downtime is tracked at the line level, so if you've zoomed into a single worksite, it switches itself off automatically. One less thing to think about.

Once it looks right in the preview, sending it is easy. Type in the recipient's email address, and hit "Generate and Send." The tracker renders everything to a polished PDF and emails it on the spot. And notice the email field always starts blank. That's on purpose, so you never accidentally fire a report off to the wrong person first thing in the morning. You decide who gets it, every time.

So what shows up in the finished report? That depends on the kind of work. A company line leads with the headline number, "Total Timbers Installed," followed by a row of cards: switch timbers, switches, derails, new and relay ties, and days worked. After that come the charts, the switch and derail sections, the tie log, and the downtime table. A sponsored job leads with goal progress instead: how many ties remain, the percent complete, and a projected finish date, followed by your output against the target and the daily log. And remember those switches and derails? By default, the report consolidates them into one chart and one table, and simply lists which ones are included, instead of running on for pages. If you ever need the full breakdown, that's exactly what the "Itemize" toggle is for.

One last thing you might notice. Down in the wizard, there's an option called "Rail installation projects," and it's grayed out. That's a placeholder for a new kind of work coming down the line. It doesn't do anything yet, so feel free to admire it, but don't bother clicking just yet.

And that's the tour. You log the work, the tracker does the math, and the office gets a sharp, professional report every week without you lifting a pen. Now go put in some ties, and let the numbers tell the story. Welcome aboard.
