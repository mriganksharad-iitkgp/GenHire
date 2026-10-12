# Interview monitoring, scoring and recovery — kiosk 1.2.6

Updated 13 October 2026. Five-interruption and 60-second automatic termination
rules remain removed. Deploy the backend and frontend, publish the new
installer, and reinstall the kiosk before testing production.

## Candidate workflow

1. Open the interview from the correct application; retries reuse its session.
2. Allow the laptop camera and microphone, speak briefly, and confirm the speaker test.
3. Hold one centered face steady for 1.2 seconds; review the automatic snapshot,
   retake it if needed, then approve its upload. Manual capture remains available.
4. If a phone is required, scan the signed private QR code on a reachable HTTPS
   site. Allow its **front camera and microphone** and position it beside you,
   showing you, your laptop and desk. Keep its page visible and screen unlocked.
5. Accept the rules and start. Read the AI question and speak your answer; the
   conversation shows live captions, with a corrected transcript after submission.
6. Choose **Send answer**, or let silence submit after you have spoken. Recordings
   and submitted answers are retained for retry when the network fails.

## Interruption accounting

Interruptions no longer automatically terminate an interview, regardless of
their count or duration. Camera observations also do not automatically end it.
Leaving the laptop tab, switching windows, exiting required fullscreen, losing
devices, stale monitoring, and unavailable phone coverage are recorded by type.
Counts remain visible during the interview and appear in the recruiter report.

One continuous absence is one episode per device until healthy monitoring is
restored. Blur followed by a tab-switch event refines that episode's category;
repeated callbacks, stale heartbeats and disconnection messages do not add counts.
Setup problems and unmonitored practice sessions do not accumulate interruptions.
MongoDB stores the counts and current losses using versioned compare-and-swap
updates, so worker restarts and simultaneous callbacks do not reset the totals.

Network and phone gaps display a transient warning and allow laptop recording
to continue. Loss of the actual laptop camera, microphone or answer recorder
still opens a recovery dialog because a voice answer cannot be recorded safely
without working devices. The original question deadline remains in force.
The interrupted recording can be transcribed and sent after reconnection.

The candidate can end voluntarily; completion and explicit historical terminal
states remain final. Attempts already terminated by an older release are **not
automatically reopened** or erased. The new policy governs active/new attempts.

## Proctoring score

The report starts at 100 and deducts the weighted recorded observations and
interruption episodes, bounded at zero. The score is a review signal, not a
probability that a candidate cheated or a substitute for interview performance.
Technical outages are explicitly labelled and carry smaller deductions.

| Interruption category | Deduction per episode |
| --- | ---: |
| Laptop tab switch | 2 |
| Window blur | 1 |
| Fullscreen exit | 2 |
| Camera or microphone lost | 1 |
| Laptop monitoring unavailable | 0.5 |
| Phone monitoring unavailable | 0.5 |

Confirmed camera observations retain the existing weights: no face/head turn
0.5, multiple faces/extra phone 2, prohibited object 1, and identity mismatch 5.
Legacy manual focus observations are excluded when durable interruption counts
already describe the same episode. The report includes counts, weights, events,
coverage, and missing detector capabilities. No analyzed laptop frames means
**score unavailable**, rather than a fabricated perfect score.

## Camera warnings and false positives

OpenCV Haar face detections now reject weak/small/implausible rectangles and
suppress overlapping duplicate boxes before counting distinct faces. A
multiple-face warning requires four consecutive observations; other vision
warnings require two. A confirmed type/source emits at most once every 15 seconds.
Warnings identify the laptop or phone, distinguish camera/focus/connection issues,
and give a concrete recovery instruction without claiming cheating is proven.
The candidate's warning popup dismisses after **1.8 seconds**; report evidence
and totals remain saved. These filters reduce noise but do not guarantee accuracy.

A phone's side view can include both the candidate and their laptop preview.
Haar rectangles alone therefore do not declare multiple people on the phone;
additional-person warnings require the independent available person detector.
The required companion phone alone is allowed by the existing object rules.
Unavailable object/identity/gaze modules appear as missing checks, not detections.

## Phone capabilities

Phone readiness requires a live front camera, microphone, visible page, heartbeat
and decoded preview. A rear camera does not silently replace the front camera.
Heartbeats arrive every five seconds and previews every second; readiness expires
after 15 seconds without either heartbeat or preview evidence. Camera re-enabling
after an active-session loss restarts the phone recorder and retains earlier parts.

Screen Wake Lock is requested where supported and reacquired after returning.
If browser/power-saving policy rejects it, disable auto-lock manually. Optional
fullscreen is offered where supported; leaving entered fullscreen removes readiness
until restored. Mobile browsers cannot prevent OS app switching or guarantee an
event after locking. Visibility notices and server-side stale-evidence checks
record the coverage gap; no claim of mobile OS lockdown is made.

See [Screen Wake Lock](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API)
and [HackerRank Proctor Mode](https://support.hackerrank.com/articles/5663779659).
GenHire's advisory weights and dual-camera flow are its own product policy.

## Session restoration and deployment

Owned MongoDB source snapshots and engine checkpoints retain session ID, current
question, answer history and original deadline without another debit/initial LLM
call. Older sessions without sufficient snapshots report the recovery limitation.
Live engine and Socket.IO state still require one Gunicorn worker, one Cloud Run
instance and session affinity; follow [setup recovery](interview-setup-recovery.md).
Keep `GENHIRE_DISABLE_JOBS=0` in production for the five-second coverage watchdog.
See [voice/captions implementation](interview-voice-and-captions.md) for audio setup.

## Device acceptance after deployment

1. Verify backend `/health`, frontend-origin CORS, native gthread logs and persistent sockets.
2. Install kiosk 1.2.6; deploy the matching phone website against the same backend.
3. Test single-camera setup, automatic capture/retake, activation, spoken answer and completion.
4. Test a physical Android Chrome and iPhone Safari phone: front camera, microphone,
   private pairing, live frames, recorder start, reconnect and final upload.
5. Test a single candidate and a second person in each camera; confirm no duplicate
   laptop-preview false alarm and confirmed warnings hide after 1.8 seconds.
6. Switch laptop tabs/windows repeatedly, restoring focus between episodes; verify
   counts/types persist and more than five episodes never automatically end the attempt.
7. Switch phone apps, lock it, disconnect its network and revoke permissions separately;
   verify warnings, coverage gaps, automatic recovery and uninterrupted laptop answers.
8. Leave phone/network monitoring unavailable beyond 60 seconds; the interview stays active.
9. Remove the laptop microphone/camera; recover devices and send the retained answer.
10. Restart the backend; verify owned same-session restoration without a second debit.
11. Finish, verify both uploads, and inspect the recruiter report's counts, score and coverage.

Fixture tests cover state, authorization, recovery, real React UI and recording
cleanup. Native Electron tests exercise WebGL, analysers and the AudioWorklet under
the kiosk CSP. They do not establish physical camera accuracy, provider recognition
quality or production network readiness; the device checks above remain necessary.
