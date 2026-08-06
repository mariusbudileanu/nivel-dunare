# International GitHub automation

The fail-soft publisher uses `.github/workflows/update-international-data.yml`. Its scheduled selector contains DE, SK, HU and HR at `37 1 * * *`. AT is dispatch-only. Serbia uses the separate `.github/workflows/update-serbia-data.yml`: Windows/Schannel collection, immutable artifact handoff, Linux validation and controlled publication.

Bulgaria is removed from the general selector. `.github/workflows/update-bg-danube-streams.yml` uses UTC triggers `15 6`, `15 7`, `15 18`, `15 19`; a `Europe/Sofia` gate accepts only 09:15 for `manual` and 21:15 for `automatic`, making the schedule DST-safe.

Collection uses `contents: read`. Only a validated live publish job receives `contents: write` and `actions: write`. Publication stages an explicit whitelist, commits only changed international paths, synchronizes with `origin/main`, allows one controlled retry and never forces or resets. Pages dispatch occurs only after a valid pushed data commit.

Contract `1.3-beta` exposes independent access, integration, automation, freshness, validation and coordinate status dimensions plus per-source attempt/success/capture/observation/last-known-good fields and bilingual messages.
