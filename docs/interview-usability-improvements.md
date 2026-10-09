# Interview and application usability improvements

Updated: 9 October 2026.

The existing landing theme remains the reference: indigo and purple actions,
lavender surfaces, rounded white cards and dark slate text. This follow-up fixes
missing interaction and recovery steps in the interview and application flows.

## What changed

| Gap | Resulting behavior |
| --- | --- |
| Typing an answer still ran the voice silence timer, which could skip or submit the question unexpectedly. | Candidates explicitly choose **Speak answer** or **Type answer**. Typing suspends voice auto-submission while camera and microphone monitoring continue. |
| Switching answer formats could discard spoken audio without explanation. | A confirmation explains an unsent recording before switching to typing. Switching away from a typed draft also requires confirmation. Drafts remain on the current page until an answer is accepted. |
| Candidates could not see the server's question deadline. | The active question shows its remaining time when the backend provides a deadline. Switching format or reconnecting does not extend the server deadline. |
| A disconnected device paused the interview without enough help to recover. | The recovery dialog shows camera preview, microphone activity, monitoring connection and phone status, with device and connection retry actions. Resume requires the necessary devices to be ready. |
| A disconnected phone needed another reachable pairing code. | The recovery dialog shows the companion QR code and can refresh the pairing token from the existing session. It does not create or activate a second interview. |
| Recovered spoken text was difficult to find. | An interrupted recording restored through transcription opens the typed answer control for review before submission. |
| Recording uploads could still be pending after report generation. | Closing or refreshing warns while the interview, report generation or recording upload requires attention. A failed upload offers retry and a themed confirmation before leaving without the recording. |
| Returning from the secure browser could leave applications showing an old status. | Applications refresh when the page becomes visible again. A manual Refresh action is also available. Failed refreshes retain previously loaded applications and show Retry. |
| Application cards showed status but little guidance. | Cards show the next step for screening, interview readiness, submitted interviews and final screening status. Invited candidates waiting for a CV are directed to My Profile. |
| Shared confirmation dialogs lacked consistent focus and fullscreen behavior. | Dialogs use the portal theme, labelled dialog semantics, keyboard focus containment and restoration, topmost-dialog dismissal and shared scroll locking. They render inside the fullscreen element when one exists. |

## Interview behavior and boundaries

Voice mode now explains the existing capture rules: begin speaking within
30 seconds, automatic submission after 8 seconds of silence after speech, and a
maximum recording length of 3 minutes. **More thinking time** restarts the local
initial voice countdown; it does not change the server's question deadline.

Typed mode uses manual submission. The server's time limit still applies, and
monitoring continues. Failed submissions retain the exact pending answer for
retry. A typed draft is kept only in the currently mounted interview page; it
is not persisted across reloads or closing the secure browser.

Device recovery resumes the same session. QR refresh uses the existing session
endpoint, and the backend remains responsible for session eligibility, answer
acceptance, billing, deadlines and report generation. This change does not add
cross-instance storage for the live interviewer or make an expired/lost backend
engine recoverable. If the engine is unavailable, use the existing **Finish with
saved answers** path.

Report generation and recording upload are separate operations. A saved report
does not mean the recording has uploaded. A failed recording remains on the
current device/page for retry and is lost when that page is discarded. Browser
close warnings are best-effort; abrupt process termination cannot guarantee
recovery. See the [beforeunload browser behavior](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeunload_event).

Shared dialog behavior follows the keyboard and focus guidance in the
[WAI-ARIA modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/).
Busy confirmations cannot be dismissed while their action is running. Nested
confirmations return focus to the underlying recovery dialog.

## Application navigation

- **Open Positions:** search, save and apply for jobs.
- **My Applications:** track applications, read next steps, take interviews and view available reports.
- **My Profile:** personal details, photo, CV and identity documents, plus the existing profile statistics.
- **Practice:** separate practice interviews and feedback.

The application overview uses returned application data for total applications,
shortlisted interviews and available reports. It does not invent an offer or a
hiring decision. Employer decisions remain authoritative. Existing profile and
application separation, recruiter navigation and landing styling are preserved.

## Verification

Run these from `react-frontend` in PowerShell or Git Bash:

```powershell
npm.cmd test
npm.cmd run test:interview-ui
npm.cmd run test:portals
npm.cmd run lint:ci
npm.cmd run build
npm.cmd run build:kiosk
```

The checks cover:

- 16 frontend contract tests.
- 10 interview/application interaction checks using real React components and
  offline API, socket and media fixtures: typing without auto-submission, exact
  answer retry, format-change confirmations, phone and laptop reconnection,
  failed recording upload recovery, keyboard focus, nested/fullscreen dialogs,
  application refresh and invited-candidate guidance.
- 50 portal regression checks, including resolved responsive styles at
  1366x768, 909x642 and 390x844. Typed controls use 14px desktop and 16px mobile
  text; format controls and confirmation actions have 44px minimum height.
- Lint, production web compilation and secure-browser web compilation.
- The two existing secure-browser runtime/security tests (`npm.cmd test` from
  `secure-browser-kiosk`).

These are component/style and build checks. No browser is connected in this
workspace, so they do not establish real browser geometry, camera quality,
microphone accuracy, phone networking or operating-system installer behavior.
No live accounts, payments, deployments or environment credentials were changed.

## Manual review before release

1. Start a test interview with camera, microphone and speakers enabled. Verify
   that the spoken question is audible and the camera preview is visible.
2. Choose **Type answer**, spend more than 30 seconds composing, and confirm
   that voice silence does not submit or skip the answer. Check the question's
   server deadline separately. Submit and verify that the next question opens.
3. Speak an answer and switch formats before sending it. Verify the confirmation
   and cancel path. Also switch away from a typed draft and confirm its warning.
4. Deny or disconnect a laptop device. Re-enable permission, use **Retry device
   checks**, speak a short sentence and confirm that Resume becomes available.
5. For a role requiring a second camera, background or disconnect the phone.
   Reopen the companion, refresh the QR code if necessary and reconnect. Confirm
   that the original interview ID remains in use and no extra activation occurs.
6. Interrupt an answer submission and retry. Verify that the retained answer is
   sent once for the original question. During report completion, simulate a
   recording upload failure, cancel the leave confirmation and retry the upload.
7. Return to **My Applications** after the kiosk finishes. Verify that status and
   report availability refresh from the API. Test manual Refresh during a
   temporary API failure and confirm that previous cards remain visible.
8. At laptop and mobile sizes, check scrolling, text wrapping, visible focus and
   reachable actions. Use Tab, Shift+Tab and Escape with ordinary confirmations,
   nested recovery confirmations and a fullscreen interview.

## Secure-browser release step

The web application and secure browser share the interview component. Updating
the frontend bundle does not update an already installed Windows executable.
The kiosk web bundle and Windows **1.2.1** installer have now been rebuilt and
verified. See [the installer and local verification record](local-verification-and-kiosk-release.md)
for its path, checksum, runtime repair and test results. The public download
location has not been updated by this task.

To package a Windows installer after review, run from the repository root:

```powershell
cd secure-browser-kiosk
npm.cmd run dist:win
```

Its pre-build hook recompiles the kiosk UI before packaging. Test the generated
installer in `secure-browser-kiosk/dist`, publish the tested installer at the
configured trusted download location, and have existing users reinstall it to
receive this UI. The browser's installation marker remembers a user's setup
confirmation; it does not verify the installed application version.

For environment/service setup, use [environment-configuration.md](environment-configuration.md)
and the existing deployment/setup documentation. No additional environment key
or service is required for these UI changes.
