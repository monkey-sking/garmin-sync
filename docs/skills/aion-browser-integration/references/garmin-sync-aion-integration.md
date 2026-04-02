# Aion Browser Integration Reference

## Purpose
This note captures the integration pattern that made long-running Garmin and OneDrive browser automation stable on this Mac when Aion/灵汐 was mediating Chrome.

## Public Boundary
- Unix socket: `~/Library/Application Support/Aion/ipc/ai-protection.sock`
- Session flow:
  - `session.hello`
  - `session.ready`
  - `lease.begin`
  - `lease.renew`
  - `lease.end`
- Close-check flow:
  - `lease.can_close.request`
  - `lease.can_close.reply`

Do not assume unsupported localhost HTTP, custom URL schemes, or private XPC helpers.

## Symptoms That Usually Mean Aion Is Involved
- Playwright Chrome opens and closes immediately.
- The user's normal Chrome works, but the automated Chrome does not.
- A protected site behaves differently only in automation.
- Long browser runs get interrupted without a clear site-side failure.

## Integration Pattern
### 1. Reuse one browser session
Avoid opening multiple automated Chrome sessions unless there is a clear reason. Aion-mediated flows are easier to keep stable when one session owns the task.

### 2. Launch the real Chrome channel
`garmin-sync` launches the system Chrome channel instead of Playwright's bundled Chromium. That keeps the browser surface closer to what the user normally sees.

Relevant code:
- [browser.py](../../../../src/garmin_sync/browser.py)

### 3. Create a real page before asking Aion for a lease
This was the most important implementation detail.

Using only `browser.launch()` was not enough. Aion did not reliably recognize the Playwright browser until the code had already created:
- a browser context
- a real page with `new_page()`

In this repo, the order is:
1. launch Chrome
2. create context
3. create page
4. enter the Aion lease context

Relevant code:
- [browser.py](../../../../src/garmin_sync/browser.py)
- [test_browser.py](../../../../tests/test_browser.py)

### 4. Use the Playwright Chrome profile as the first `appKey`
Plain `com.google.Chrome` was not enough for the actual Playwright temp Chrome instance.

The working pattern was:
1. inspect running Chrome processes
2. find the Playwright Chrome command line with `--user-data-dir=...playwright_chromiumdev_profile-*`
3. build the `appKey` as:

```text
com.google.Chrome#profile:<profile_dir_name>
```

`garmin-sync` then falls back through:
1. `com.google.Chrome#profile:<playwright_profile>`
2. `com.google.Chrome`
3. `com.google.Chrome#automation`

Relevant code:
- [aion_lease.py](../../../../src/garmin_sync/aion_lease.py)
- [test_aion_lease.py](../../../../tests/test_aion_lease.py)

### 5. Retry `lease.begin` briefly on `unknown_app`
Even with the right profile-derived `appKey`, Aion could still return `unknown_app` for a short time while the browser settled.

The practical fix was:
- retry `lease.begin` for a short window
- only keep retrying while the rejection code is `unknown_app`

Relevant code:
- [aion_lease.py](../../../../src/garmin_sync/aion_lease.py)

### 6. Renew the lease in the background
Once accepted, `garmin-sync` keeps the lease alive with periodic `lease.renew` calls.

Default values in this repo:
- lease duration: `1800` seconds
- renew interval: `600` seconds

### 7. Answer close checks with `extend_lease`
If Aion asks whether the browser can close, reply with:
- `result = extend_lease`
- the same lease duration

That kept the automation session alive during long Garmin imports.

### 8. End the lease on shutdown
When browser work completes, send `lease.end`, then close the browser transport.

## Minimal Implementation Shape
```python
browser = chromium.launch(channel="chrome", ...)
context = browser.new_context(...)
page = context.new_page()

with maybe_with_aion_lease(site):
    # do the browser work here
    ...
```

The important part is not the syntax. The important part is:
- real page first
- lease second
- one session
- explicit cleanup

## What `garmin-sync` Actually Implemented
- A socket client that handles `hello`, `ready`, `begin`, `renew`, `end`, and close checks
- Automatic detection of Playwright Chrome profile keys
- Short retry window for `unknown_app`
- Browser lifecycle wrapping so Aion lease acquisition happens after page creation
- Safe browser close handling when Playwright has already closed the page or context

Implementation files:
- [aion_lease.py](../../../../src/garmin_sync/aion_lease.py)
- [browser.py](../../../../src/garmin_sync/browser.py)

## Reuse Guidance
If another AI or automation tool wants to reuse this pattern:
1. copy this skill folder
2. keep the public socket contract unchanged
3. adapt only the browser-launch and app-key detection layer
4. validate the page-before-lease ordering first

If the browser still closes immediately, check the `appKey` being sent before changing anything else.
