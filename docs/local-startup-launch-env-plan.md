# Local startup, interview launch and deployment configuration

Preserve the current landing theme and the existing application/payment contracts.

- [x] Fix foreground startup in Windows/Git Bash and diagnose port conflicts.
- [x] Remember secure-browser setup on this device and retain reinstall help.
- [x] Put interview dialogs above navigation with viewport-safe scrolling.
- [x] Align job description, create/edit/view job surfaces with the current theme.
- [x] Run backend, launch/navigation, component and build checks.
- [x] Audit and organize local/production environment files for both apps.
- [x] Validate key parity, placeholders, ignored secrets and deployment instructions.

Initial findings:
- The previous verification backend owns port 5000; stop only that known process.
- Windows os.execv does not keep the original Git Bash command attached.
- The interview guide is at z-index 1200 but navigation is at 9998.
- Job metadata still inherits white text from the old gradient header.
- Edit-job pills/buttons retain pink styling and an additional legacy gaze setting.
- Production environment templates omit local rate-limit/capacity settings.

Update this checklist as implementation and verification finish. Actual credentials
must remain in ignored configuration files and must never be printed in tool output.

## Implementation and checks so far

Windows interpreter handoff now waits for its child and propagates its exit code.
The local launcher executes app.py in its own process. A port check runs before
database initialization; conflicts give a Ctrl+C/restart instruction. Only the
earlier known verification server was stopped. A separate port-5017 test confirmed
that the original command remains alive while /health returns 200, and that a
second command reports the conflict. The test server was stopped afterwards.

The browser cannot reliably detect an installed custom-protocol application.
Installation confirmation is stored as a non-sensitive device/browser preference.
First-time users get setup steps; returning users get Open Secure Browser, with
install/reinstall help always available. This preference never replaces backend
authentication, kiosk trust or readiness checks. Clearing storage, another browser
or another device starts setup again. Storage errors do not block confirmation.

The guide is rendered into document.body above navigation (z-index 10060), locks
page scrolling, traps keyboard focus and scrolls internally within the viewport.
Create/edit share JobForm.module.css, with purple actions, restrained spacing and
sticky headers. The independent legacy gaze checkbox was removed; its compatibility
field is derived from the shared gaze-heatmap setting at submission.

Passed: 9 startup/index tests, 16 frontend contracts, 48 portal fixture checks,
frontend lint and production web build. No native app/real camera test occurred.

## Environment audit completed

All eight files now use matching groups and commented settings. Existing local
values were preserved; production URLs use the supplied Cloud Run service and
custom domain, with the stable Vercel alias allowed by CORS. Local/production
schemas differ only by the two documented Google ADC overrides omitted for Cloud
Run. Private credentials stay in ignored files; example references contain none.

Schema and local configuration checks pass. Production validation reports one
required missing setting, REDIS_URL, plus notices for the missing primary DeepSeek
key, webhook signing secret and object-detection weights. Those external values
must be supplied; production readiness is not claimed. See
[environment configuration](environment-configuration.md) for the exact import,
credential handling, local commands and verification limits.

The final web build embeds the supplied Cloud Run origin and excludes existing
private backend credentials. Kiosk UI and Windows installer packaging passed,
and the installer checksum was refreshed. The production /health probe returned
HTTP 503; diagnosing its deployed runtime requires Cloud Run logs. No deployment
was performed. All eight dotenv files passed parser round-trip and key checks.

Final configuration-validator tests: 6 passed. The current local backend returned
HTTP 200 on port 5000 during a read-only check; it was not restarted or stopped.
Kiosk security tests: 2 passed. The rebuilt installer is 97,001,354 bytes.
