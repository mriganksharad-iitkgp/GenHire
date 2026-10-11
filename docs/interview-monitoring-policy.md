# Interview monitoring and recovery — kiosk 1.2.4

Updated 12 October 2026. These changes are in the workspace; deploy the backend
and frontend and replace the downloadable installer before testing production.

## Candidate workflow

1. Open the secure browser from the correct application; retries reuse its session.
2. Allow the laptop camera and microphone, speak briefly, and confirm the speaker test.
3. Hold one centered face steady for 1.2 seconds; review the automatic snapshot,
   retake it if needed, then approve its upload. Manual capture remains available.
4. For a required phone, scan the signed private QR code on a reachable HTTPS site.
   Allow its **front camera and microphone**. Position it beside you so its view
   includes you, your laptop and desk; keep it plugged in and its page visible.
5. Read and accept the monitoring rules, then start. Question pacing begins after setup.

## What counts toward the interruption limit

- Leaving the laptop tab, switching windows, or leaving required fullscreen.
- Losing the laptop camera, microphone, monitoring heartbeat, or camera frames.
- Hiding the phone page, switching phone apps, locking its screen, losing camera
  or microphone access, disconnecting it, or stopping its preview frames.
- **Five distinct interruptions end the attempt.** The server stores counts,
  evidence and the terminal status in MongoDB; a reload, reconnect, server restart,
  another socket or another `/start` request cannot reset or reopen that attempt.
- A continuous loss is one episode per device: blur and visibility callbacks,
  stale heartbeats and repeated disconnection messages do not create extra strikes.
- Restore lost monitoring within **60 seconds**. A sustained outage also ends the
  attempt; it is recorded as one outage, not five invented interruptions.
- Setup permission problems, slow providers, and uncertain automated face/object/
  gaze observations are not interruption strikes. Vision warnings remain evidence
  for human review; the system does not automatically declare a candidate cheating.

The attempt's terminal record independently blocks retries for its application,
even if updating the application summary fails. It does not block unrelated jobs.
Submitted answers remain saved. Desktop and phone recordings are stopped and
offered for upload; candidates must keep the pages open while uploads finish.
Recruiters can retrieve a terminated attempt's transcript, coverage and policy
events through the authorized report endpoint. No fabricated interview score is
assigned to a terminated attempt.

## Phone capabilities and limits

The phone requires a live front camera, microphone, visible page, heartbeat and
decoded preview frame before it is ready. A rear camera does not silently replace
the front camera. Heartbeats arrive every five seconds; previews every second.
Readiness expires after 15 seconds without a heartbeat or actual preview.

Screen Wake Lock is requested where supported and reacquired after returning to
the page. Power saving or browser policy may reject it; the UI then explains that
auto-lock needs to be disabled manually. The fullscreen button is available where
the browser supports fullscreen. Once entered, leaving it removes phone readiness
until fullscreen is restored.

An ordinary mobile website **cannot prevent OS app switching, force device lock
settings, or guarantee delivery of an event after the screen locks**. Visibility
events provide immediate notices when possible; expired heartbeat/frame evidence
provides the fallback. The server watchdog checks active sessions every five
seconds, including after a browser closes. Neither browser warnings nor a single
image prove misconduct. Mobile OS lockdown would require a separate managed/native
device solution, not a promise made by this web page.

References: [Screen Wake Lock API](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API),
[HackerRank Proctor Mode](https://support.hackerrank.com/articles/5663779659).
The five-interruption rule is GenHire's configured product policy, not a claimed
HackerRank rule or a certification of equivalence.

## Session restoration

New real and practice sessions persist their source-document snapshots and engine
checkpoints. These contain the same session ID, current question, conversation
context, answers, count and original question deadline. Restoration uses owned
database evidence without another payment or initial LLM call. Captured face
references and saved proctoring evidence are restored for socket monitoring.

Older real sessions can reconstruct documents from their application/job snapshot
and continue from the saved last answer. If the saved current question or source
documents are unavailable, recovery reports that limitation rather than inventing
answers or silently restarting. Older practice sessions without snapshots may
still require ending with their saved answers.

Live question generation and Socket.IO bindings still reside in one process.
Keep one Gunicorn worker and one Cloud Run instance with session affinity as
described in [setup recovery](interview-setup-recovery.md). Checkpoints repair
worker restarts; they do not make parallel answer mutations across multiple
containers safe. Keep `GENHIRE_DISABLE_JOBS=0` in production: disabling jobs also
disables the independent integrity watchdog.

## Release and device acceptance checklist

1. Deploy the changed Python backend with its native threading Gunicorn config;
   check `/health` and the frontend-origin CORS preflight.
2. Deploy the changed frontend so the phone receives the same protocol and front
   camera requirements as the kiosk. Both devices must target the same backend.
3. Upload `secure-browser-kiosk/dist/Genhire.exe` (1.2.4), verify its sibling SHA-256
   file, and install that build on the test laptop. Existing installations do not
   acquire bundled UI changes just by redeploying the website.
4. Test single-camera setup, automatic capture/retake, activation, one answer and end.
5. Test the signed phone link on real Android Chrome and iPhone Safari: verify the
   front camera, both permissions, heartbeat, frames, recording and final upload.
6. Switch laptop tabs/windows once: expect one counted episode and paused answers.
   Restore monitoring, resume, and repeat until the fifth distinct interruption.
7. Switch phone apps, lock it, disconnect network, and revoke camera access in
   separate tests. Expect readiness loss, laptop pause, a counted episode and recovery.
8. Confirm staying disconnected for 60 seconds ends the attempt once.
9. At termination, reload, reconnect, activate, submit, and call `/start` again:
   expect rejection for that same application and a retained recruiter report.
10. Restart the backend during setup and verify same-session recovery with no
    extra debit. Restart during an active question and verify its deadline is retained.
11. Confirm uncertain vision flags generate review notices without termination
    strikes; a required companion phone alone must not trigger an extra-phone flag.

Automated tests cover server state, CAS retries, authorization/terminal guards,
engine restoration, real React components and recording shutdown. They use fixture
media and cannot establish physical device compatibility, real camera positioning,
model accuracy or deployed network readiness. The device checklist remains required.
