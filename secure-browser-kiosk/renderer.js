// NOTE: The primary console noise filter is in index.html (runs before vendor scripts).
// This catches the rare unhandled-rejection variant of the facemesh error.
window.addEventListener('unhandledrejection', function (event) {
    if (event.reason && typeof event.reason.message === 'string' &&
        event.reason.message.includes('an eye patch had zero width')) {
        event.preventDefault();
    }
});

// Configuration
const REQUIRED_WIDTH = 640;
const REQUIRED_HEIGHT = 480;

// Interview pacing — mirrors react-frontend/src/pages/Chat.jsx: after the AI
// finishes speaking, the candidate has NO_ANSWER_TIMEOUT_SECONDS to START
// speaking (auto-advances on expiry); once they've spoken,
// POST_SPEECH_SILENCE_SECONDS of sustained silence auto-submits the answer.
const NO_ANSWER_TIMEOUT_SECONDS = 30;
const POST_SPEECH_SILENCE_SECONDS = 10;
// Short spoken acknowledgements between an answer and the next question so
// the hand-off doesn't feel like an abrupt topic jump.
const ACKNOWLEDGEMENTS = [
    "Alright, thank you.",
    "Got it.",
    "Okay, thanks for sharing that.",
    "Thanks.",
];
// Client-side ceiling on automatic face-capture retries for recoverable
// issues (bad lighting, no face in frame). The SERVER enforces the real
// mismatch limit (FACE_VERIFY_MAX_ATTEMPTS) — this is just a backstop
// against looping forever if the camera never produces a usable frame.
const FACE_CAPTURE_MAX_ATTEMPTS = 8;

// Local (client-side) face-guide thresholds for the identity-capture preview.
// Normalized (0-1) landmark coordinates from MediaPipe FaceLandmarker.
const FACE_GUIDE_MIN_WIDTH = 0.20;   // face too small/far below this
const FACE_GUIDE_MAX_WIDTH = 0.70;   // face too large/close above this
const FACE_GUIDE_CENTER_TOLERANCE = 0.16; // max allowed offset from frame center
const FACE_GUIDE_STABLE_MS = 550;    // hold a good, centered frame this long before auto-capturing

let video, canvas, ctx;
let objectDetector;
let faceLandmarker;
let myvad;
let optionalModelsPromise = null;

// UI Elements
let loadingOverlay, testingOverlay, startupView, interviewView, resultsView;
let testingSpinner, faceCaptureStage, identityVideo, faceOvalGuide, faceGuideStatus, btnFaceCapture;
let btnStart;
let btnEndInterview, btnDownload;
let timeDisplay, transcriptText;
let gazeWarning, proctoringModal, warningCountEl, proctoringMsg;

// Metrics Tracking
let sessionStartTime = null;
let trackingData = [];
let gazeAlerts = 0;
let objectAlerts = 0;
let voiceAlerts = 0;

let warningCount = 0;
let currentSessionId = null;
let socket = null;

let isInterviewActive = false;
let isAISpeaking = false; // true while TTS audio is playing — blocks send button
let clockInterval = null;

// ═══════════════════════════════════════
//  VIOLATION LOGGING — persisted + ack-confirmed delivery
// ═══════════════════════════════════════
// Previously, every violation type EXCEPT app-switch only called
// showProctoringWarning() locally and incremented an in-memory counter
// (gazeAlerts/objectAlerts) that was shown solely on this app's own results
// screen — nothing but app-switch was ever actually sent to the backend, so
// a recruiter's proctoring report was silently missing gaze/head-turn/
// multi-face/phone violations. logViolation() is now the single choke point
// every violation site goes through. Entries are persisted to localStorage
// BEFORE a send is attempted, so a renderer crash/reload doesn't silently
// drop evidence, and are only cleared once the server acknowledges receipt
// (Flask-SocketIO sends an ack automatically once its handler returns, no
// backend changes needed) — a bare socket.emit() with no ack would have no
// way to know whether a violation raised right as the connection dropped
// actually made it through.
const PENDING_VIOLATIONS_KEY = 'genhire_pending_violations';

function loadPendingViolations() {
    try {
        const raw = localStorage.getItem(PENDING_VIOLATIONS_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch (e) {
        return [];
    }
}

function savePendingViolations(list) {
    try {
        localStorage.setItem(PENDING_VIOLATIONS_KEY, JSON.stringify(list));
    } catch (e) {
        console.warn('Failed to persist pending violations:', e.message);
    }
}

function sendViolationEntry(entry) {
    if (!socket || !socket.connected) return;
    socket.emit('proctoring_violation', {
        session_id: entry.session_id,
        type: entry.type,
        ...entry.extra,
    }, () => {
        // Server acknowledged receipt — safe to drop from the pending queue.
        savePendingViolations(loadPendingViolations().filter((e) => e.id !== entry.id));
    });
}

function logViolation(type, extra = {}) {
    const entry = {
        id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        session_id: currentSessionId,
        type,
        extra,
        loggedAt: Date.now(),
    };
    const pending = loadPendingViolations();
    pending.push(entry);
    savePendingViolations(pending);
    sendViolationEntry(entry);
}

// Retries every not-yet-acknowledged violation — called on every socket
// "connect" event, which Socket.IO also re-fires after automatic
// reconnection, so this covers both the first connect and any recovery from
// a dropped connection without needing separate reconnect-specific logic.
// Entries may belong to an earlier session if the whole app restarted after
// a crash before they were flushed; session_id travels with each entry so
// they're still attributed correctly.
function flushPendingViolations() {
    loadPendingViolations().forEach(sendViolationEntry);
}

// API Data
let apiToken = null;
let apiUrl = null;
let globalSessionData = null; // Store deep link payload globally
let isPracticeMode = false; // Flag for practice mode
let currentQuestion = "";
let questionCount = 0;
let isSubmittingAnswer = false;

// GazeCloud Recorder State
let currentAudioObj = null;
let gazePointsTracker = [];
let gazeStartedAtMs = null;
let gazeEndedAtMs = null;
let gazeRecorderTracking = false;
let lastWebGazerSampleMs = 0;
const WEBGAZER_SAMPLE_INTERVAL_MS = 100;
const WEBGAZER_READY_TIMEOUT_MS = 35000;
const WEBGAZER_READY_POLL_MS = 200;
const WEBGAZER_CALIBRATION_MAX_ATTEMPTS = 600;
let gazePollingTimer = null;
let latestGazeFaceCount = 0;
let webgazerHasPrediction = false;

// Proctoring config from job (defaults all enabled)
let proctoringConfig = {
    voice_detection: true,
    object_detection: true,
    eyeball_tracking: true,
    gaze_heatmap: true,
};

// ── Object detection runs on a slower cadence to avoid blocking the face loop ──
let lastObjectDetectTime = 0;
const OBJECT_DETECT_INTERVAL = 2000;

// ── Cheating detection state (mirrors Python SimpleCheatingDetector) ──
const DURATION_THRESHOLD = 3.5;
const NORMAL_MIN = -0.30;
const NORMAL_MAX = 0.30;
const FACE_ABSENCE_THRESHOLD = 2.0;
const HEAD_TURN_THRESHOLD = 2.0;
const MULTI_FACE_THRESHOLD = 1.5;
const HEAD_TURN_RATIO_THRESHOLD = 0.12;
let suspiciousStartTime = null;
let suspiciousState = null;
let alertTriggered = false;

// MediaPipe landmark indices
const P_LEFT_IRIS = 473;
const P_RIGHT_IRIS = 468;
const P_LEFT_EYE_OUTER = 33;
const P_LEFT_EYE_INNER = 133;
const P_RIGHT_EYE_OUTER = 263;
const P_RIGHT_EYE_INNER = 362;

// Google Cloud Speech State
let mediaRecorder = null;
let audioStream = null;
let videoStream = null;
let currentTranscript = "";
let isRecording = false;
let speechNetworkFailed = false;
let lastSpeechTime = 0;

// Question pacing state (see NO_ANSWER_TIMEOUT_SECONDS / POST_SPEECH_SILENCE_SECONDS)
let pacingInterval = null;
let hasSpokenThisQuestion = false;
let questionListeningStartedAt = null;

// Face identity gate + progress/discard state (mirrors Chat.jsx)
let maxQuestions = 10;
let identityStatus = null;
let discardInfo = null;

document.addEventListener('DOMContentLoaded', async () => {
    // Bind DOM
    video = document.getElementById('webcam');
    canvas = document.getElementById('overlay');
    ctx = canvas.getContext('2d');

    loadingOverlay = document.getElementById('loading-overlay');
    testingOverlay = document.getElementById('testing-overlay');
    startupView = document.getElementById('startup-view');
    interviewView = document.getElementById('interview-view');
    resultsView = document.getElementById('results-view');

    testingSpinner = document.getElementById('testing-spinner');
    faceCaptureStage = document.getElementById('face-capture-stage');
    identityVideo = document.getElementById('identity-video');
    faceOvalGuide = document.getElementById('face-oval-guide');
    faceGuideStatus = document.getElementById('face-guide-status');
    btnFaceCapture = document.getElementById('btn-face-capture');

    btnStart = document.getElementById('btn-start');
    btnEndInterview = document.getElementById('btn-end-interview');
    btnDownload = document.getElementById('btn-download');

    timeDisplay = document.getElementById('time-display');
    transcriptText = document.getElementById('transcript-text');
    gazeWarning = document.getElementById('gaze-warning');
    proctoringModal = document.getElementById('proctoring-modal');
    warningCountEl = document.getElementById('warning-count');
    proctoringMsg = document.getElementById('proctoring-msg');

    canvas.width = REQUIRED_WIDTH;
    canvas.height = REQUIRED_HEIGHT;

    // Events
    btnStart.addEventListener('click', startInterview);
    btnEndInterview.addEventListener('click', endInterview);
    btnDownload.addEventListener('click', saveResultsAsPhoto);

    // Return to GenHire button — updated dynamically after endInterview() based on isPracticeMode
    const btnReturnDashboard = document.getElementById('btn-return-dashboard');
    if (btnReturnDashboard) {
        btnReturnDashboard.addEventListener('click', () => {
            returnToDashboardAndExit();
        });
    }

    document.getElementById('btn-ack-warning').addEventListener('click', () => {
        proctoringModal.style.display = 'none';
    });

    // Setup Google Cloud STT Callbacks
    if (window.electronAPI) {
        // Handle Deep Link Auto-Start
        window.electronAPI.onInitDeepLink((event, initData) => {
            globalSessionData = initData;

            // Since clicking the link might happen before models load, wait until btnStart is enabled
            const attemptStart = setInterval(() => {
                if (!btnStart.disabled && btnStart.textContent === "Begin Interview Setup") {
                    clearInterval(attemptStart);
                    // Force a short delay so user actually sees the Startup logo
                    setTimeout(() => {
                        btnStart.click();
                    }, 1000);
                }
            }, 500);
        });

        window.electronAPI.onTranscript((event, text, isFinal) => {
            if (isFinal) {
                currentTranscript += text + " ";
            }

            if (text) {
                lastSpeechTime = Date.now();
                hasSpokenThisQuestion = true;
            }

            // Show typing/speaking feedback
            transcriptText.textContent = (isFinal ? currentTranscript : currentTranscript + text).trim() || currentQuestion;
            transcriptText.style.fontStyle = "normal";
        });

        window.electronAPI.onSTTError((event, errorMsg) => {
            console.error(`❌ Google STT error: ${errorMsg}`);
            speechNetworkFailed = true;
            stopRecording();
            if (transcriptText) {
                transcriptText.innerHTML = '<span style="color:#f6e05e">⚠️ Voice input error. Check credentials.json or network connection.</span>';
            }
        });
    } else {
        console.warn("⚠️ electronAPI not found! Speech will not work.");
    }

    // Send Answer Button Wire-up
    document.getElementById('send-btn').addEventListener('click', submitAnswer);

    // App-switch proctoring: main process notifies when window loses focus during kiosk
    if (window.electronAPI && window.electronAPI.onAppSwitched) {
        window.electronAPI.onAppSwitched(() => {
            if (isInterviewActive) {
                showProctoringWarning('You switched to another application. This has been recorded.');
                logViolation('app_switch');
            }
        });
    }

    try {
        await setupCamera();
        video.play();
        await loadModels();

        // Models loaded, enable start button
        loadingOverlay.style.display = 'none';

        // Only enable if we also have deep link data (or just enable it to let user click, but it requires link)
        if (globalSessionData) {
            btnStart.textContent = "Begin Interview Setup";
            btnStart.disabled = false;
        } else {
            btnStart.textContent = "Please launch from your browser";
            // Setup an interval to enable it once data drops in
            const waitData = setInterval(() => {
                if (globalSessionData) {
                    btnStart.textContent = "Begin Interview Setup";
                    btnStart.disabled = false;
                    clearInterval(waitData);
                }
            }, 500);
        }

    } catch (e) {
        console.error(e);
        const errMsg = e instanceof Error ? e.message : String(e);
        document.getElementById('loading-text').innerHTML = `<span style="color:red;">Error: ${errMsg}</span>`;
    }
});

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/** Sync the send button's disabled state with current flags. */
function updateSendButtonState() {
    const sendBtn = document.getElementById('send-btn');
    if (!sendBtn) return;
    const shouldDisable = isAISpeaking || isSubmittingAnswer || !isInterviewActive;
    sendBtn.disabled = shouldDisable;
    sendBtn.style.opacity = shouldDisable ? '0.5' : '1';
    sendBtn.style.cursor = shouldDisable ? 'not-allowed' : 'pointer';
}

/**
 * WebGazer needs a live video stream. A second getUserMedia() often fails or never produces
 * frames on Windows/Electron while MediaPipe already holds the camera — this reuses video.srcObject.
 * Also disables saveDataAcrossSessions so begin() does not immediately reload weights from localforage
 * after clearData().
 */
function recordWebGazerCalibrationClick(wg, clientX, clientY, onDone) {
    let attempts = 0;
    const maxAttempts = WEBGAZER_CALIBRATION_MAX_ATTEMPTS;
    const tick = () => {
        attempts++;
        const tracker = wg.getTracker && wg.getTracker();
        const pos = tracker && typeof tracker.getPositions === "function" ? tracker.getPositions() : null;
        const hasFaceMeshFrame = pos && pos.length > 0;
        if (hasFaceMeshFrame) {
            if (typeof wg.recordScreenPosition === "function") {
                wg.recordScreenPosition(clientX, clientY, "click");
            }
            onDone();
            return;
        }
        if (attempts >= maxAttempts) {
            console.warn(
                "WebGazer calibration: no face mesh frame before extended timeout; click may not have trained the model."
            );
            if (typeof wg.recordScreenPosition === "function") {
                wg.recordScreenPosition(clientX, clientY, "click");
            }
            onDone();
            return;
        }
        requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
}

function setWebGazerDebugUI(wg, visible) {
    if (!wg) return;
    if (typeof wg.showVideo === "function") wg.showVideo(visible);
    if (typeof wg.showVideoPreview === "function") wg.showVideoPreview(visible);
    if (typeof wg.showFaceOverlay === "function") wg.showFaceOverlay(visible);
    if (typeof wg.showFaceFeedbackBox === "function") wg.showFaceFeedbackBox(visible);
    if (typeof wg.showPredictionPoints === "function") wg.showPredictionPoints(visible);
}



async function waitForWebGazerPrediction(wg) {
    const startedAt = Date.now();

    while (Date.now() - startedAt < WEBGAZER_READY_TIMEOUT_MS) {
        if (webgazerHasPrediction) {
            return true;
        }

        if (typeof wg.getCurrentPrediction === "function") {
            try {
                const pred = await Promise.resolve(wg.getCurrentPrediction());
                if (pred && Number.isFinite(Number(pred.x)) && Number.isFinite(Number(pred.y))) {
                    webgazerHasPrediction = true;
                    return true;
                }
            } catch (_) {
                /* keep waiting */
            }
        }
        await new Promise((resolve) => setTimeout(resolve, WEBGAZER_READY_POLL_MS));
    }

    return webgazerHasPrediction;
}

/** Throttled append for WebGazer screen coordinates (heatmap upload). */
function maybeRecordWebGazerSample(pred, source) {
    if (!gazeRecorderTracking) return;
    if (latestGazeFaceCount !== 1 || !pred) return;

    const nx = Number(pred.x);
    const ny = Number(pred.y);
    if (!Number.isFinite(nx) || !Number.isFinite(ny)) return;

    const now = Date.now();
    if (now - lastWebGazerSampleMs < WEBGAZER_SAMPLE_INTERVAL_MS) return;
    lastWebGazerSampleMs = now;

    const ts =
        sessionStartTime != null
            ? (now - sessionStartTime) / 1000
            : (now - gazeStartedAtMs) / 1000;
    const x = Math.max(0, Math.min(window.innerWidth - 1, nx));
    const y = Math.max(0, Math.min(window.innerHeight - 1, ny));
    gazePointsTracker.push({
        timestamp: ts,
        x: Math.round(x),
        y: Math.round(y),
    });
    if (gazePointsTracker.length <= 3 || gazePointsTracker.length % 25 === 0) {
        console.log(`✅ WebGazer tracking (${gazePointsTracker.length} samples) — x:${Math.round(x)} y:${Math.round(y)}`);
    }
}

async function beginWebGazerRecording() {
    const wg = window.webgazer;
    gazePointsTracker = [];
    gazeStartedAtMs = Date.now();
    lastWebGazerSampleMs = 0;
    latestGazeFaceCount = 0;
    webgazerHasPrediction = false;

    if (typeof wg.saveDataAcrossSessions === 'function') {
        wg.saveDataAcrossSessions(false);
    }
    if (typeof wg.clearData === 'function') {
        await wg.clearData();
    }

    wg
        .setRegression('ridge')
        .setTracker('TFFacemesh')
        .setGazeListener(function (data) {
            if (data && !webgazerHasPrediction) {
                webgazerHasPrediction = true;
            }
            maybeRecordWebGazerSample(data, "listener");
        })
        .showVideoPreview(false)
        .showPredictionPoints(false);

    const origGUM = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    try {
        navigator.mediaDevices.getUserMedia = async function (constraints) {
            try {
                const existing = video && video.srcObject;
                if (existing && typeof existing.getVideoTracks === 'function' && existing.getVideoTracks().length > 0) {
                    return existing;
                }
            } catch (_) {
                /* use real getUserMedia */
            }
            return origGUM(constraints);
        };
        await wg.begin();
    } finally {
        navigator.mediaDevices.getUserMedia = origGUM;
    }

    // Always hide WebGazer's built-in camera/overlay (prevents double video stream)
    setWebGazerDebugUI(wg, false);

    const calibrationPoints = [
        { x: '10%', y: '10%' }, { x: '90%', y: '10%' },
        { x: '50%', y: '50%' },
        { x: '10%', y: '90%' }, { x: '90%', y: '90%' }
    ];
    let calIdx = 0;

    // ── Phase 1: Wait for face lock (testing overlay already visible) ──
    await waitForWebGazerPrediction(wg);

    // ── Phase 2: Show calibration overlay ──
    testingOverlay.style.display = 'none';

    const overlay = document.createElement('div');
    overlay.style.cssText = `position:fixed; inset:0; background:linear-gradient(135deg, rgba(10,14,23,0.97), rgba(15,20,25,0.97)); z-index:99999; display:flex; flex-direction:column; align-items:center; justify-content:center; color:white; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;`;

    const icon = document.createElement('div');
    icon.textContent = '👁️';
    icon.style.cssText = 'font-size:48px; margin-bottom:16px; filter:drop-shadow(0 0 12px rgba(102,126,234,0.5));';

    const title = document.createElement('h2');
    title.textContent = 'Almost Ready!';
    title.style.cssText = 'font-size:28px; font-weight:700; margin:0 0 10px; letter-spacing:-0.5px;';

    const sub = document.createElement('p');
    sub.textContent = 'Look directly at each dot and click it to calibrate eye tracking.';
    sub.style.cssText = 'font-size:16px; color:#a0aec0; margin:0 0 6px; max-width:480px; text-align:center; line-height:1.5;';

    const progress = document.createElement('div');
    progress.textContent = `Point 1 of ${calibrationPoints.length}`;
    progress.style.cssText = 'font-size:14px; color:#667eea; font-weight:600; margin-bottom:16px;';

    const dot = document.createElement('div');
    dot.style.cssText = `position:absolute; width:36px; height:36px; background:linear-gradient(135deg,#ff4d4d,#ff6b6b); border-radius:50%; cursor:pointer; transition:left 0.4s cubic-bezier(0.4,0,0.2,1), top 0.4s cubic-bezier(0.4,0,0.2,1); left:${calibrationPoints[0].x}; top:${calibrationPoints[0].y}; box-shadow:0 0 20px rgba(255,77,77,0.5), 0 0 60px rgba(255,77,77,0.15); transform:translate(-50%,-50%);`;

    overlay.appendChild(icon);
    overlay.appendChild(title);
    overlay.appendChild(sub);
    overlay.appendChild(progress);
    overlay.appendChild(dot);
    document.body.appendChild(overlay);

    await new Promise((resolve) => {
        dot.addEventListener('click', (ev) => {
            if (dot.dataset.calBusy === '1') return;
            dot.dataset.calBusy = '1';
            sub.textContent = 'Hold still — locking gaze sample…';
            recordWebGazerCalibrationClick(wg, ev.clientX, ev.clientY, () => {
                dot.dataset.calBusy = '0';
                calIdx++;
                if (calIdx >= calibrationPoints.length) {
                    document.body.removeChild(overlay);
                    gazeRecorderTracking = true;
                    setWebGazerDebugUI(wg, false);
                    // Dedicated polling timer for WebGazer predictions
                    if (!gazePollingTimer) {
                        gazePollingTimer = setInterval(() => {
                            if (!gazeRecorderTracking || !window.webgazer) return;
                            if (typeof window.webgazer.getCurrentPrediction !== 'function') return;
                            Promise.resolve(window.webgazer.getCurrentPrediction())
                                .then(pred => maybeRecordWebGazerSample(pred, "polling"))
                                .catch(() => {});
                        }, WEBGAZER_READY_POLL_MS);
                    }
                    finalizeStartInterview();
                    resolve();
                } else {
                    dot.style.left = calibrationPoints[calIdx].x;
                    dot.style.top = calibrationPoints[calIdx].y;
                    sub.textContent = 'Look at the dot and click it.';
                    progress.textContent = `Point ${calIdx + 1} of ${calibrationPoints.length}`;
                }
            });
        });
    });
}

async function startInterview() {
    if (!globalSessionData) {
        alert("Missing session data. Please launch this app directly from the Genhire Dashboard.");
        return;
    }

    let payload;
    try {
        const decoded = atob(globalSessionData);
        payload = JSON.parse(decoded);
        if ((!payload.applicationId && !payload.isPractice) || !payload.token) throw new Error("Invalid payload structure");
    } catch (e) {
        alert("Invalid initialization data.");
        return;
    }

    apiToken = payload.token;
    apiUrl = payload.apiUrl;
    isPracticeMode = payload.isPractice || false;

    // Switch Views to Testing Overlay!
    btnStart.disabled = true;
    startupView.style.display = 'none';
    testingOverlay.style.display = 'flex';

    try {
        if (isPracticeMode) {
            currentSessionId = payload.sessionId;
            currentQuestion = payload.initialQuestion;
            questionCount = 1;

            if (payload.proctoringConfig) {
                proctoringConfig = payload.proctoringConfig;
            }
            if (payload.maxQuestions) {
                maxQuestions = payload.maxQuestions;
            }
        } else if (payload.sessionId && payload.initialQuestion) {
            // Fast path: session was pre-created by the platform — start instantly, no API call needed
            currentSessionId = payload.sessionId;
            currentQuestion = payload.initialQuestion;
            questionCount = 1;
            if (payload.proctoringConfig) {
                proctoringConfig = payload.proctoringConfig;
            }
            if (payload.maxQuestions) {
                maxQuestions = payload.maxQuestions;
            }
        } else {
            // Fallback: create session here (slower — legacy path)
            const response = await fetch(`${apiUrl}/api/interviews/start`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${apiToken}`
                },
                body: JSON.stringify({ application_id: payload.applicationId })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || errData.message || "Failed to start interview");
            }

            const data = await response.json();
            currentSessionId = data.session_id;
            currentQuestion = data.initial_questions[0];
            questionCount = 1;

            if (data.proctoring_config) {
                proctoringConfig = data.proctoring_config;
            }
            if (data.max_questions) {
                maxQuestions = data.max_questions;
            }
        }
    } catch (err) {
        testingOverlay.style.display = 'none';
        startupView.style.display = 'flex';
        alert(`Error starting interview: ${err.message}`);
        btnStart.disabled = false;
        btnStart.textContent = "Begin Interview Setup";
        return;
    }

    // FACE IDENTITY GATE — must happen before kiosk lockdown/gaze calibration.
    // First-ever real interview enrolls this capture as the account's
    // permanent identity; every later real interview must match it or the
    // attempt is blocked. Practice interviews never go through this at all —
    // there's no account identity to protect for a practice session.
    const identityOk = isPracticeMode ? true : await performIdentityCheck();
    if (!identityOk) {
        return; // a blocked/fatal-error screen has already been shown
    }
    document.getElementById('testing-title').textContent = 'Setting Up Your Interview';
    document.getElementById('testing-text').textContent = 'Initializing secure environment — this takes just a moment.';

    // Start Gaze Tracking via WebGazer (only if gaze_heatmap enabled)
    if (proctoringConfig.gaze_heatmap && window.webgazer) {
        beginWebGazerRecording().catch((err) => {
            console.error("WebGazer start error:", err);
            finalizeStartInterview();
        });
    } else {
        finalizeStartInterview();
    }
}

// ═══════════════════════════════════════
//  FACE IDENTITY GATE
// ═══════════════════════════════════════

/** Capture one frame from the live webcam and POST it to the identity gate. */
async function captureAndVerifyFace() {
    if (!video || video.readyState < 3 || video.videoWidth === 0) {
        return { ok: false, blocked: false, fatal: false, message: 'Camera is still initializing.' };
    }

    const snap = document.createElement('canvas');
    snap.width = video.videoWidth;
    snap.height = video.videoHeight;
    snap.getContext('2d').drawImage(video, 0, 0, snap.width, snap.height);
    const imageData = snap.toDataURL('image/jpeg', 0.9);

    try {
        const response = await fetch(`${apiUrl}/api/interviews/${currentSessionId}/register-face`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${apiToken}`
            },
            body: JSON.stringify({ image: imageData })
        });
        const result = await response.json().catch(() => ({}));

        if (!response.ok) {
            if (result.error_code === 'face_mismatch_blocked') {
                return {
                    ok: false,
                    blocked: true,
                    fatal: false,
                    message: result.error || "Face verification failed repeatedly — this interview attempt has been locked because the captured face does not match this account's registered identity."
                };
            }
            if (result.error_code === 'identity_card_required') {
                // No ID card on file — uploading happens on the website, so
                // this attempt cannot proceed inside the kiosk.
                return {
                    ok: false,
                    blocked: true,
                    fatal: false,
                    message: result.error || 'Please upload your identity card in your GenHire profile before starting an interview.'
                };
            }
            if (result.error_code === 'face_mismatch') {
                const attemptsNote = typeof result.attempts_remaining === 'number'
                    ? ` (${result.attempts_remaining} attempt${result.attempts_remaining === 1 ? '' : 's'} remaining)`
                    : '';
                return {
                    ok: false,
                    blocked: false,
                    fatal: false,
                    message: `${result.error || 'Your face does not match the identity card on your account.'}${attemptsNote}`
                };
            }
            if (response.status === 404) {
                // Session genuinely doesn't exist — retrying won't help.
                return { ok: false, blocked: false, fatal: true, message: result.error || 'Interview session not found.' };
            }
            // Quality issues (no_face_detected / multiple_faces_detected / invalid_image) — retryable.
            return { ok: false, blocked: false, fatal: false, message: result.error || 'Face capture failed. Please try again.' };
        }

        const identity = result.identity || {};
        return { ok: true, blocked: false, fatal: false, status: identity.status || null };
    } catch (err) {
        console.error('Face verification request failed:', err);
        return { ok: false, blocked: false, fatal: false, message: 'Network error while verifying identity.' };
    }
}

/** One MediaPipe pass on the live webcam feed; returns the face-guide state
 * used to drive the oval outline + status text under the preview. Reuses the
 * same `faceLandmarker`/`video` the in-interview proctoring loop uses later —
 * that loop is inactive at this point (isInterviewActive is still false), so
 * there's no contention. */
function evaluateFaceFrame() {
    if (!faceLandmarker || !video || video.readyState < 2) {
        return { ok: false, code: 'camera_warming_up', message: 'Starting camera…' };
    }

    const results = faceLandmarker.detectForVideo(video, performance.now());
    const faces = results.faceLandmarks || [];

    if (faces.length > 1) {
        return { ok: false, code: 'multiple_faces', message: 'Only one person should be in frame' };
    }
    if (faces.length === 0) {
        return { ok: false, code: 'no_face', message: 'Position your face in the frame' };
    }

    const { minX, maxX, minY, maxY } = getFaceBounds(faces[0]);
    const width = maxX - minX;
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    if (width < FACE_GUIDE_MIN_WIDTH) {
        return { ok: false, code: 'too_far', message: 'Move a little closer' };
    }
    if (width > FACE_GUIDE_MAX_WIDTH) {
        return { ok: false, code: 'too_close', message: 'Move back a little' };
    }
    if (Math.abs(centerX - 0.5) > FACE_GUIDE_CENTER_TOLERANCE || Math.abs(centerY - 0.5) > FACE_GUIDE_CENTER_TOLERANCE) {
        return { ok: false, code: 'off_center', message: 'Center your face in the frame' };
    }

    return { ok: true, code: 'good', message: 'Hold still…' };
}

/**
 * Drives the live oval guide + status text and resolves once the candidate's
 * face has been centered and steady for FACE_GUIDE_STABLE_MS (auto-capture),
 * or the candidate clicks "Capture Now"/"Retake Photo" themselves. Either way
 * capture only ever happens from a frame the candidate has actually seen
 * themselves centered in the preview — nothing is captured blind.
 */
function waitForCaptureTrigger() {
    return new Promise((resolve) => {
        let rafId = null;
        let stableSince = null;
        let settled = false;

        const finish = () => {
            if (settled) return;
            settled = true;
            if (rafId) cancelAnimationFrame(rafId);
            btnFaceCapture.removeEventListener('click', finish);
            resolve();
        };

        btnFaceCapture.addEventListener('click', finish);

        const tick = () => {
            if (settled) return;
            const state = evaluateFaceFrame();

            faceGuideStatus.textContent = state.message;
            faceOvalGuide.classList.remove('face-ok', 'face-warn');

            if (state.ok) {
                faceOvalGuide.classList.add('face-ok');
                if (stableSince === null) stableSince = performance.now();
                if (performance.now() - stableSince >= FACE_GUIDE_STABLE_MS) {
                    finish();
                    return;
                }
            } else {
                stableSince = null;
                if (state.code !== 'camera_warming_up') {
                    faceOvalGuide.classList.add('face-warn');
                }
            }

            rafId = requestAnimationFrame(tick);
        };

        rafId = requestAnimationFrame(tick);
    });
}

/**
 * Runs the identity gate before the interview can proceed. Returns true once
 * verification clears; returns false if the candidate is blocked or capture
 * fails fatally — in both cases a terminal screen has already been shown and
 * startInterview() must stop. Never called for practice interviews.
 */
async function performIdentityCheck() {
    testingOverlay.style.display = 'flex';
    testingSpinner.style.display = 'none';
    faceCaptureStage.style.display = 'block';
    identityVideo.srcObject = videoStream;

    document.getElementById('testing-title').textContent = 'Verifying Your Identity';
    document.getElementById('testing-text').textContent =
        "Center your face in the frame below — we'll capture automatically once it's steady, or click Capture Now.";
    btnFaceCapture.textContent = 'Capture Now';
    btnFaceCapture.style.display = 'inline-block';

    // Brief moment for the camera to settle exposure/focus after setupCamera().
    await new Promise((resolve) => setTimeout(resolve, 400));

    for (let attempt = 1; attempt <= FACE_CAPTURE_MAX_ATTEMPTS; attempt++) {
        await waitForCaptureTrigger();

        faceGuideStatus.textContent = 'Verifying your photo…';
        faceOvalGuide.classList.remove('face-ok', 'face-warn');
        btnFaceCapture.style.display = 'none';

        const outcome = await captureAndVerifyFace();

        if (outcome.ok) {
            identityStatus = outcome.status;
            faceCaptureStage.style.display = 'none';
            testingSpinner.style.display = 'flex';
            if (identityStatus === 'registered_new') {
                document.getElementById('testing-text').textContent =
                    "Face registered — this photo is now your account's verified identity for future interviews.";
            } else if (identityStatus === 'verified') {
                document.getElementById('testing-text').textContent = 'Identity verified ✓';
            }
            await new Promise((resolve) => setTimeout(resolve, 500));
            return true;
        }

        if (outcome.blocked) {
            showIdentityBlockedScreen(outcome.message);
            return false;
        }

        if (outcome.fatal) {
            resetToStartupView();
            showError(outcome.message);
            return false;
        }

        // Recoverable failure (no face / multiple faces / bad image / mismatch
        // with attempts remaining) — tell the candidate exactly what went
        // wrong and let THEM decide when to retake, instead of silently
        // retrying on a fixed timer.
        faceGuideStatus.textContent = outcome.message;
        faceOvalGuide.classList.add('face-warn');
        btnFaceCapture.textContent = 'Retake Photo';
        btnFaceCapture.style.display = 'inline-block';
    }

    // Exhausted attempts without a definitive verdict (e.g. camera never
    // produced a usable frame) — surface this rather than looping forever.
    faceCaptureStage.style.display = 'none';
    resetToStartupView();
    showError('Could not verify your identity after several attempts. Please check your camera and restart the interview.');
    return false;
}

/** Leaves the candidate on a usable "Begin Interview Setup" screen instead of
 * a blank one after a fatal identity-check error is dismissed. */
function resetToStartupView() {
    testingOverlay.style.display = 'none';
    startupView.style.display = 'flex';
    faceCaptureStage.style.display = 'none';
    testingSpinner.style.display = 'flex';
    btnFaceCapture.style.display = 'none';
    btnStart.disabled = false;
    btnStart.textContent = "Begin Interview Setup";
}

/** Terminal screen for a permanently blocked identity mismatch. No kiosk
 * lockdown was ever engaged at this point, so there is nothing to unlock. */
function showIdentityBlockedScreen(message) {
    testingOverlay.style.display = 'none';
    startupView.style.display = 'none';
    interviewView.style.display = 'none';
    resultsView.style.display = 'none';

    const overlay = document.createElement('div');
    overlay.id = 'identity-blocked-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:linear-gradient(135deg, rgba(10,14,23,0.98), rgba(20,10,10,0.98));z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;text-align:center;padding:40px;';
    overlay.innerHTML = `
      <div style="font-size:48px;margin-bottom:16px;">🔒</div>
      <h2 style="color:#fc8181;font-size:1.8rem;margin-bottom:14px;">Identity Verification Failed</h2>
      <p style="max-width:560px;color:#f8d7d7;line-height:1.6;background:rgba(153,27,27,0.25);border:1px solid rgba(252,129,129,0.4);border-radius:10px;padding:14px 18px;margin-bottom:14px;">${message}</p>
      <p style="max-width:560px;color:#a0aec0;line-height:1.6;margin-bottom:24px;">For fairness and security, interviews must be taken by the account owner whose face was registered during their first interview. This attempt has been recorded. If you believe this is an error, please contact support.</p>
      <button id="identity-blocked-exit" style="background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none;padding:14px 32px;border-radius:10px;font-size:1rem;font-weight:600;cursor:pointer;">Return to Genhire</button>
    `;
    document.body.appendChild(overlay);

    document.getElementById('identity-blocked-exit').addEventListener('click', () => {
        returnToDashboardAndExit();
    });

    if (video && video.srcObject) {
        video.srcObject.getTracks().forEach((t) => t.stop());
        video.srcObject = null;
    }
    if (audioStream) {
        audioStream.getTracks().forEach((t) => t.stop());
        audioStream = null;
    }
}

/** Shared "open the dashboard in the default browser, then quit" action used
 * by both the identity-blocked and interview-discarded terminal screens. */
function returnToDashboardAndExit() {
    const targetPath = isPracticeMode ? '/practice' : '/profile#applications';
    let dashboardUrl = `http://localhost:3000${targetPath}`;
    if (apiUrl) {
        try {
            const urlObj = new URL(apiUrl);
            dashboardUrl = `${urlObj.protocol}//${urlObj.hostname}:3000${targetPath}`;
        } catch (e) {
            console.warn('Could not parse apiUrl, using default:', e);
        }
    }

    if (window.electronAPI && window.electronAPI.openExternal) {
        window.electronAPI.openExternal(dashboardUrl);
    }

    setTimeout(() => {
        if (window.electronAPI && window.electronAPI.quitApp) {
            window.electronAPI.quitApp();
        }
    }, 1500);
}

/** Terminal screen for a zero-answer /end response: the interview was
 * discarded and credits were refunded instead of scored. */
function showDiscardedScreen(info) {
    const refundLine = info.refundSuccess
        ? (isPracticeMode
            ? `The ${info.creditsRefunded || ''} credits deducted for this practice session were refunded to your wallet. You can start a fresh practice interview any time.`
            : 'The credits deducted for this interview were refunded to the recruiter, and your application is unaffected. You can retake the interview from your applications page.')
        : 'No report was generated for this session. You can retake the interview at any time.';

    const overlay = document.createElement('div');
    overlay.id = 'discarded-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:linear-gradient(135deg, rgba(10,14,23,0.98), rgba(30,20,5,0.98));z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;text-align:center;padding:40px;';
    overlay.innerHTML = `
      <div style="font-size:48px;margin-bottom:16px;">📋</div>
      <h2 style="color:#f6e05e;font-size:1.8rem;margin-bottom:14px;">Interview Not Recorded</h2>
      <p style="max-width:560px;color:#fef3c7;line-height:1.6;background:rgba(146,64,14,0.25);border:1px solid rgba(246,224,94,0.4);border-radius:10px;padding:14px 18px;margin-bottom:14px;">${info.message}</p>
      <p style="max-width:560px;color:#a0aec0;line-height:1.6;margin-bottom:24px;">${refundLine}</p>
      <button id="discarded-exit" style="background:linear-gradient(135deg,#10b981,#059669);color:#fff;border:none;padding:14px 32px;border-radius:10px;font-size:1rem;font-weight:600;cursor:pointer;">${isPracticeMode ? '↩ Return to Practice Page' : '↩ Return to My Applications'}</button>
    `;
    document.body.appendChild(overlay);

    document.getElementById('discarded-exit').addEventListener('click', () => {
        returnToDashboardAndExit();
    });
}

// ═══════════════════════════════════════
//  QUESTION PACING (30s no-answer / 10s post-speech silence)
// ═══════════════════════════════════════
function updatePacingStatus(text) {
    const el = document.getElementById('pacing-status');
    if (el) el.textContent = text || '';
}

function beginQuestionPacing() {
    hasSpokenThisQuestion = false;
    questionListeningStartedAt = Date.now();
    lastSpeechTime = Date.now();

    if (pacingInterval) clearInterval(pacingInterval);
    pacingInterval = setInterval(() => {
        if (!isInterviewActive || isSubmittingAnswer) return;
        const now = Date.now();

        if (!hasSpokenThisQuestion) {
            const waited = (now - questionListeningStartedAt) / 1000;
            if (waited >= NO_ANSWER_TIMEOUT_SECONDS) {
                clearInterval(pacingInterval);
                pacingInterval = null;
                submitAnswer();
                return;
            }
            updatePacingStatus(`No answer yet — auto-advancing in ${Math.ceil(NO_ANSWER_TIMEOUT_SECONDS - waited)}s`);
        } else {
            const silentFor = (now - lastSpeechTime) / 1000;
            if (silentFor >= POST_SPEECH_SILENCE_SECONDS && currentTranscript.trim().length > 0) {
                clearInterval(pacingInterval);
                pacingInterval = null;
                submitAnswer();
                return;
            }
            updatePacingStatus(
                silentFor >= 1 ? `Submitting in ${Math.ceil(POST_SPEECH_SILENCE_SECONDS - silentFor)}s…` : 'Listening…'
            );
        }
    }, 1000);
}

function stopQuestionPacing() {
    if (pacingInterval) {
        clearInterval(pacingInterval);
        pacingInterval = null;
    }
    updatePacingStatus('');
}

function finalizeStartInterview() {
    testingOverlay.style.display = 'none';
    interviewView.style.display = 'block';

    isInterviewActive = true;
    sessionStartTime = Date.now();

    // LOCK DOWN: Enable kiosk mode now that the interview is starting
    if (window.electronAPI && window.electronAPI.enableKiosk) {
        window.electronAPI.enableKiosk();
    }

    // Multi-monitor detection — flagged for recruiter review, not blocking:
    // docked laptops and legitimate multi-monitor setups are common enough
    // that hard-blocking risks false positives, so this is recorded through
    // the same violation pipeline as everything else and left for a human
    // to judge, consistent with how every other check in this file works.
    if (window.electronAPI && window.electronAPI.getDisplayInfo) {
        window.electronAPI.getDisplayInfo()
            .then((info) => {
                if (info && info.count > 1) {
                    logViolation('multi_monitor_detected', { display_count: info.count });
                }
            })
            .catch((err) => console.warn('Display info check failed:', err.message));
    }

    // Start Socket connection
    if (!socket) {
        socket = io(apiUrl);
        socket.on("connect", () => {
            socket.emit("start_proctoring", { session_id: currentSessionId });
            socket.emit("control_mobile_recording", { session_id: currentSessionId, action: "start" });
            // Socket.IO re-fires "connect" after every automatic reconnection
            // too, so this single hook covers both the initial connect and
            // recovering from a dropped connection mid-interview.
            flushPendingViolations();
        });
        socket.on("gaze_data", (data) => {
            if (data.is_cheating_alert) {
                showProctoringWarning("Mobile Cam: Suspicious head pose detected.");
            }
        });
    }

    // Speak the very first question with word-by-word reveal
    const finishSetupAndSpeak = async () => {
        if (currentAudioObj) { currentAudioObj.pause(); currentAudioObj.currentTime = 0; }
        isAISpeaking = true;
        updateSendButtonState();

        let base64Audio = null;
        try {
            base64Audio = await window.electronAPI.synthesizeSpeech(currentQuestion);
        } catch (err) {
            console.error("TTS failed for first question:", err);
        }

        currentAudioObj = playQuestionWithReveal(currentQuestion, base64Audio, () => {
            isAISpeaking = false;
            updateSendButtonState();
            // Recording captures the candidate's spoken ANSWER — it must
            // always start regardless of the voice_detection proctoring
            // toggle (that flag only gates the separate VAD proctoring
            // signal below, not answer capture; see submitAnswer's
            // unconditional startRecording() for the next-question case).
            if (isInterviewActive && !isRecording && !speechNetworkFailed) {
                startRecording();
            }
            beginQuestionPacing();
        });
    };
    finishSetupAndSpeak();

    // Start Timer
    clockInterval = setInterval(() => {
        const elapsed = (Date.now() - sessionStartTime) / 1000;
        timeDisplay.textContent = formatTime(elapsed);
    }, 1000);

    document.getElementById('q-count').textContent = questionCount;
    const qMaxEl = document.getElementById('q-max');
    if (qMaxEl) qMaxEl.textContent = maxQuestions;
    transcriptText.textContent = currentQuestion;

    // Start tracking loops conditionally
    if (proctoringConfig.eyeball_tracking || proctoringConfig.gaze_heatmap) {
        requestAnimationFrame(faceLoop);
    }
    if (proctoringConfig.object_detection || proctoringConfig.voice_detection) {
        ensureOptionalModelsLoaded()
            .then(() => {
                if (isInterviewActive && proctoringConfig.object_detection) {
                    objectLoop();
                }
            })
            .catch((err) => {
                console.error("Optional proctoring models failed to initialize", err);
            });
    }
}

async function endInterview() {
    isInterviewActive = false;
    clearInterval(clockInterval);
    stopQuestionPacing();
    discardInfo = null;

    stopRecording();

    const hadGazeRecorderOn = gazeRecorderTracking;

    // Clean up dedicated WebGazer polling timer
    if (gazePollingTimer) {
        clearInterval(gazePollingTimer);
        gazePollingTimer = null;
    }

    if (gazeRecorderTracking && window.webgazer) {
        window.webgazer.pause();
        gazeRecorderTracking = false;
        gazeEndedAtMs = Date.now();
    } else if (!gazeEndedAtMs && gazeStartedAtMs) {
        gazeEndedAtMs = Date.now();
    }

    if (socket && socket.connected) {
        socket.emit("control_mobile_recording", { session_id: currentSessionId, action: "stop" });
        socket.disconnect();
    }

    // Stop Media Streams
    if (video.srcObject) {
        video.srcObject.getTracks().forEach(t => t.stop());
        video.srcObject = null;
    }
    if (audioStream) {
        audioStream.getTracks().forEach(t => t.stop());
        audioStream = null;
    }
    videoStream = null;

    // Tell backend to end interview and send gaze data
    try {
        if (proctoringConfig.gaze_heatmap && gazePointsTracker.length > 0 && !isPracticeMode) {
            const gazeResp = await fetch(`${apiUrl}/api/interviews/${currentSessionId}/gaze-recorder-results`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${apiToken}`
                },
                body: JSON.stringify({
                    session_id: currentSessionId,
                    recordingData: null,
                    gazePoints: gazePointsTracker,
                    startedAtMs: gazeStartedAtMs,
                    endedAtMs: gazeEndedAtMs,
                    viewport: { width: window.innerWidth, height: window.innerHeight }
                })
            });

            if (!gazeResp.ok) {
                const gazeError = await gazeResp.text();
                throw new Error(`Gaze results upload failed (${gazeResp.status}): ${gazeError}`);
            }
        }

        const endpoint = isPracticeMode 
            ? `${apiUrl}/api/practice/${currentSessionId}/end`
            : `${apiUrl}/api/interviews/${currentSessionId}/end`;

        const endResp = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiToken}`
            },
            body: JSON.stringify({
                tracking_data: proctoringConfig.eyeball_tracking ? trackingData : []
            })
        });

        let endData = null;
        try {
            endData = await endResp.json();
        } catch (e) {
            endData = null;
        }

        if (!endResp.ok) {
            throw new Error((endData && (endData.error || endData.message)) || `Interview end request failed (${endResp.status})`);
        }

        if (endData && endData.status === "interview_discarded") {
            // Zero answers were recorded — the backend refunded the
            // start-of-interview credits and discarded the session instead
            // of scoring it.
            discardInfo = {
                message: endData.message || "No answers were recorded, so this interview was discarded and your credits were refunded.",
                refundSuccess: !!(endData.refund && endData.refund.success),
                creditsRefunded: Number((endData.refund && endData.refund.credits_refunded) || 0),
            };
        }
    } catch (e) {
        console.error("Failed to signal backend to end interview or send gaze tracking data", e);
    }

    // UNLOCK: Disable kiosk mode now that interview is over
    if (window.electronAPI && window.electronAPI.disableKiosk) {
        window.electronAPI.disableKiosk();
    }

    interviewView.style.display = 'none';

    if (discardInfo) {
        showDiscardedScreen(discardInfo);
        return;
    }

    // Prepare Results View
    resultsView.style.display = 'flex';

    // Populate Metrics
    document.getElementById('val-gaze').textContent = gazeAlerts;
    document.getElementById('val-obj').textContent = objectAlerts;
    document.getElementById('val-voice').textContent = voiceAlerts;

    let totalElapsed = 0;
    if (sessionStartTime) totalElapsed = (Date.now() - sessionStartTime) / 1000;
    document.getElementById('val-time').textContent = formatTime(totalElapsed);

    // Update completion message and return button based on session type
    const completionHeader = document.querySelector('.evaluation-header h2');
    if (completionHeader) completionHeader.textContent = '✅ Interview Complete';

    const completionSubtitle = document.querySelector('.evaluation-header p');
    if (completionSubtitle) {
        completionSubtitle.textContent = isPracticeMode
            ? 'Your practice session has ended. Return to the Practice Page to view your report.'
            : 'Your interview has ended. Return to My Applications to view your report.';
    }

    const btnReturn = document.getElementById('btn-return-dashboard');
    if (btnReturn) {
        btnReturn.textContent = isPracticeMode
            ? '↩ Return to Practice Page'
            : '↩ Return to My Applications';
    }

    renderChart();
}

async function submitAnswer() {
    // Block if AI is speaking, already submitting, or interview not active
    if (isAISpeaking || isSubmittingAnswer || !isInterviewActive) return;

    const sendBtn = document.getElementById('send-btn');
    isSubmittingAnswer = true;
    updateSendButtonState();
    sendBtn.innerHTML = "Processing...";

    stopQuestionPacing();
    stopRecording();

    try {
        const answerText = currentTranscript.trim() || "(No answer provided)";

        const payload = {
            question: currentQuestion,
            answer: answerText,
            is_intro: false
        };

        const endpoint = isPracticeMode
            ? `${apiUrl}/api/practice/${currentSessionId}/answer`
            : `${apiUrl}/api/interviews/${currentSessionId}/answer`;

        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiToken}`
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error("Failed to submit");

        const data = await response.json();

        if (data.interview_complete || questionCount >= maxQuestions) {
            isSubmittingAnswer = false;
            endInterview();
            return;
        }

        // Mirror the backend's own count instead of blindly incrementing — on
        // a repeated question (data.repeated_question) the backend
        // deliberately leaves progress.questions_asked unchanged, so the
        // visible progress here correctly stays put too.
        if (data.progress && typeof data.progress.questions_asked === 'number') {
            questionCount = data.progress.questions_asked + 1;
        } else if (!data.repeated_question) {
            questionCount++;
        }
        currentQuestion = data.next_question;
        document.getElementById('q-count').textContent = questionCount;

        // Reset speech variables
        currentTranscript = "";
        lastSpeechTime = Date.now();

        // Speak naturally: repeat requests get the question verbatim; a
        // skipped question moves on gently; a real answer earns a brief
        // acknowledgement before the next question.
        let spokenText = currentQuestion;
        if (!data.repeated_question) {
            const ack = answerText && answerText !== "(No answer provided)"
                ? ACKNOWLEDGEMENTS[Math.floor(Math.random() * ACKNOWLEDGEMENTS.length)]
                : "No problem, let's move on.";
            spokenText = `${ack} ${currentQuestion}`;
        }

        if (currentAudioObj) { currentAudioObj.pause(); currentAudioObj.currentTime = 0; }
        isAISpeaking = true;
        updateSendButtonState();

        let base64Audio = null;
        try {
            base64Audio = await window.electronAPI.synthesizeSpeech(spokenText);
        } catch (ttsErr) {
            console.error("Google TTS failed:", ttsErr);
        }

        currentAudioObj = playQuestionWithReveal(spokenText, base64Audio, () => {
            isAISpeaking = false;
            updateSendButtonState();
            if (isInterviewActive && !isRecording && !speechNetworkFailed) {
                startRecording();
            }
            beginQuestionPacing();
        });

    } catch (err) {
        showError("Failed to submit answer: " + err.message);
    } finally {
        isSubmittingAnswer = false;
        updateSendButtonState();
        sendBtn.innerHTML = `
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
          </svg>
          Send Answer`;
    }
}

async function saveResultsAsPhoto() {
    const captureArea = document.getElementById('capture-area');
    btnDownload.disabled = true;
    btnDownload.textContent = "Generating...";

    try {
        const canvas = await html2canvas(captureArea, {
            backgroundColor: '#1a202c', // var(--dark-surface)
            scale: 2
        });

        const imageURL = canvas.toDataURL("image/png");
        const a = document.createElement('a');
        a.href = imageURL;
        a.download = `Proctoring_Results_${Date.now()}.png`;
        a.click();
    } catch (err) {
        console.error("Screenshot failed:", err);
        alert("Failed to capture screenshot. See console.");
    } finally {
        btnDownload.textContent = "Download Results as Photo";
        btnDownload.disabled = false;
    }
}

// ═══════════════════════════════════════
//  Results Chart
// ═══════════════════════════════════════
function renderChart() {
    const ctxChart = document.getElementById('results-chart').getContext('2d');
    let data = trackingData;
    if (data.length > 600) {
        const step = Math.ceil(data.length / 600);
        data = data.filter((_, i) => i % step === 0);
    }
    const labels = data.map(d => d.time.toFixed(1));
    const eyeData = data.map(d => d.gazeRatio);

    new Chart(ctxChart, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Gaze Ratio',
                    data: eyeData,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 2, tension: 0.3, pointRadius: 0,
                    fill: true
                },
                {
                    label: 'Zone Boundary',
                    data: labels.map(() => NORMAL_MAX),
                    borderColor: 'rgba(255,193,7,0.5)', borderWidth: 1, borderDash: [5, 5],
                    pointRadius: 0, fill: false
                },
                {
                    label: 'Zone Boundary 2',
                    data: labels.map(() => NORMAL_MIN),
                    borderColor: 'rgba(255,193,7,0.5)', borderWidth: 1, borderDash: [5, 5],
                    pointRadius: 0, fill: false
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            plugins: {
                title: { display: true, text: 'Gaze Direction Over Time', color: '#e2e8f0', font: { size: 16 } },
                legend: { labels: { color: '#a0aec0' } },
            },
            scales: {
                x: { ticks: { color: '#718096', maxTicksLimit: 10 }, grid: { color: 'rgba(113, 128, 150, 0.2)' } },
                y: { ticks: { color: '#718096' }, grid: { color: 'rgba(113, 128, 150, 0.2)' }, min: -1.5, max: 1.5 }
            }
        }
    });
}

// ═══════════════════════════════════════
//  Alerts System
// ═══════════════════════════════════════
function showProctoringWarning(msg) {
    warningCount++;
    warningCountEl.textContent = warningCount;
    proctoringMsg.textContent = msg;
    proctoringModal.style.display = 'flex';
}

// ═══════════════════════════════════════
//  Camera & ML Models Setup
// ═══════════════════════════════════════
async function setupCamera() {
    videoStream = await navigator.mediaDevices.getUserMedia({
        video: {
            facingMode: 'user',
            width: { ideal: 1280, min: REQUIRED_WIDTH },
            height: { ideal: 720, min: REQUIRED_HEIGHT }
        },
        audio: false,
    });

    audioStream = await navigator.mediaDevices.getUserMedia({
        video: false,
        audio: true,
    });

    video.srcObject = videoStream;
    return new Promise(resolve => { video.onloadedmetadata = () => resolve(video); });
}

// ═══════════════════════════════════════
//  ERROR OVERLAY (replaces alert() during kiosk)
// ═══════════════════════════════════════
function showError(msg) {
    const existing = document.getElementById('genhire-error-overlay');
    if (existing) existing.remove();
    const overlay = document.createElement('div');
    overlay.id = 'genhire-error-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:99999;display:flex;align-items:center;justify-content:center;font-family:inherit';
    overlay.innerHTML = `
      <div style="background:#1e293b;border:2px solid #ef4444;border-radius:16px;padding:32px 36px;max-width:500px;width:90%;text-align:center;color:#f1f5f9;">
        <div style="font-size:2rem;margin-bottom:10px;">⚠️</div>
        <h3 style="color:#ef4444;margin:0 0 12px;font-size:1.1rem;">Something went wrong</h3>
        <p style="margin:0 0 24px;color:#94a3b8;font-size:0.9rem;line-height:1.5">${msg}</p>
        <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
          <button id="err-dismiss" style="padding:10px 20px;background:#334155;border:none;border-radius:8px;color:#f1f5f9;cursor:pointer;font-size:0.9rem">Dismiss</button>
          <button id="err-quit" style="padding:10px 20px;background:#ef4444;border:none;border-radius:8px;color:#fff;cursor:pointer;font-weight:bold;font-size:0.9rem">Exit GenHire (Ctrl+Q)</button>
        </div>
        <p style="margin:16px 0 0;color:#475569;font-size:0.78rem">You can also press <strong>Ctrl+Q</strong> at any time to exit safely.</p>
      </div>`;
    document.body.appendChild(overlay);
    document.getElementById('err-dismiss').onclick = () => overlay.remove();
    document.getElementById('err-quit').onclick = () => { if (window.electronAPI) window.electronAPI.quitApp(); };
}

// ═══════════════════════════════════════
//  TTS + WORD-BY-WORD REVEAL
// ═══════════════════════════════════════
function playQuestionWithReveal(questionText, base64Audio, onEnded) {
    const words = questionText.split(/\s+/).filter(Boolean);

    // Set transcript to a live-reveal container
    transcriptText.style.fontStyle = 'italic';
    transcriptText.innerHTML = `<strong style="color:#7dd3fc;font-style:normal">AI:</strong> <span id="tts-word-reveal"></span>`;
    const revealEl = document.getElementById('tts-word-reveal');

    let wordInterval = null;
    let wordIndex = 0;

    function startReveal(durationSec) {
        if (wordInterval) clearInterval(wordInterval);
        wordIndex = 0;
        const msPerWord = (durationSec > 0 && isFinite(durationSec))
            ? Math.max(60, (durationSec * 1000) / words.length)
            : 400; // fallback ~2.5 words/sec
        const shownWords = [];
        wordInterval = setInterval(() => {
            if (wordIndex < words.length) {
                shownWords.push(words[wordIndex++]);
                if (revealEl) revealEl.textContent = shownWords.join(' ');
            } else {
                clearInterval(wordInterval);
            }
        }, msPerWord);
        // Show first word immediately
        if (words.length > 0 && revealEl) revealEl.textContent = words[0];
        wordIndex = 1;
    }

    function cleanup() {
        if (wordInterval) clearInterval(wordInterval);
        // Guarantee full text is visible
        if (revealEl) revealEl.textContent = questionText;
    }

    if (!base64Audio) {
        // No audio — just do timed word reveal
        startReveal(words.length / 2.5);
        const fallbackMs = Math.max(2000, (words.length / 2.5) * 1000);
        setTimeout(() => { cleanup(); onEnded(); }, fallbackMs);
        return null;
    }

    const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
    let revealStarted = false;

    function tryStartReveal() {
        if (revealStarted) return;
        revealStarted = true;
        startReveal(audio.duration || words.length / 2.5);
    }

    audio.onloadedmetadata = () => tryStartReveal();
    audio.onplay = () => tryStartReveal();

    audio.onended = () => { cleanup(); onEnded(); };
    audio.onerror = (e) => {
        console.error("Audio playback error:", e);
        cleanup();
        onEnded();
    };

    audio.play().catch(e => {
        console.error("Audio play() rejected:", e);
        if (!revealStarted) startReveal(words.length / 2.5);
        setTimeout(() => { cleanup(); onEnded(); }, Math.max(2000, (words.length / 2.5) * 1000));
    });

    return audio;
}

// ═══════════════════════════════════════
//  GOOGLE CLOUD RECORDING HELPERS
// ═══════════════════════════════════════
function startRecording() {
    if (isRecording || !audioStream || !window.electronAPI) return;

    // If the audio track has ended (e.g. after a previous MediaRecorder stop), re-acquire it
    const existingTrack = audioStream.getAudioTracks()[0];
    if (!existingTrack || existingTrack.readyState === 'ended') {
        navigator.mediaDevices.getUserMedia({ video: false, audio: true })
            .then(newStream => {
                audioStream = newStream;
                startRecording();
            })
            .catch(err => console.error("Failed to re-acquire audio stream:", err));
        return;
    }

    isRecording = true;
    currentTranscript = "";
    document.getElementById('mic-btn').classList.add('mic-recording');

    window.electronAPI.startSTTStream();

    // Extract only the audio track to avoid codec mismatch errors
    const recordStream = new MediaStream([existingTrack]);

    let mimeType = 'audio/webm;codecs=opus';
    if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/webm';
        if (!MediaRecorder.isTypeSupported(mimeType)) {
            mimeType = '';
        }
    }

    try {
        mediaRecorder = mimeType
            ? new MediaRecorder(recordStream, { mimeType })
            : new MediaRecorder(recordStream);
    } catch (err) {
        console.error("MediaRecorder creation failed:", err);
        isRecording = false;
        speechNetworkFailed = true;
        return;
    }
    mediaRecorder.ondataavailable = async (e) => {
        if (e.data.size > 0 && isRecording) {
            const arrayBuffer = await e.data.arrayBuffer();
            // Convert ArrayBuffer to standard Buffer/Uint8Array for IPC
            window.electronAPI.sendAudioChunk(new Uint8Array(arrayBuffer));
        }
    };

    // Send data chunks every 250ms for streaming STT
    mediaRecorder.start(250);
    lastSpeechTime = Date.now();
    // Auto-submit pacing (30s no-answer / 10s post-speech silence) is driven
    // by beginQuestionPacing(), called once per question alongside this.
}

function stopRecording() {
    if (!isRecording) return;
    isRecording = false;

    document.getElementById('mic-btn').classList.remove('mic-recording');

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }

    if (window.electronAPI) {
        window.electronAPI.stopSTTStream();
    }
}

async function loadModels() {
    const { FaceLandmarker, FilesetResolver } = await import(
        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.32/vision_bundle.mjs"
    );
    const vision = await FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.32/wasm");
    faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
        baseOptions: {
            modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
            delegate: "CPU",
        },
        outputFaceBlendshapes: false,
        runningMode: "VIDEO",
        numFaces: 2,
    });
    
    // Background pre-initialization of WebGazer to remove start lag
    if (window.webgazer) {
        window.webgazer.setRegression('ridge').setTracker('TFFacemesh').showVideoPreview(false).showPredictionPoints(false);
        const origGUM = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
        navigator.mediaDevices.getUserMedia = async function (c) {
            try { if (video && video.srcObject) return video.srcObject; } catch (_) {}
            return origGUM(c);
        };
        // We don't await this so it happens silently in the background
        window.webgazer.begin().finally(() => { navigator.mediaDevices.getUserMedia = origGUM; }).catch(() => {});
    }
}

/** Dynamically inject a <script> tag and wait for it to load. */
function loadScript(src) {
    return new Promise((resolve, reject) => {
        if (document.querySelector(`script[src="${src}"]`)) {
            resolve();
            return;
        }
        const s = document.createElement('script');
        s.src = src;
        s.onload = resolve;
        s.onerror = () => reject(new Error(`Failed to load: ${src}`));
        document.head.appendChild(s);
    });
}

async function ensureOptionalModelsLoaded() {
    if (optionalModelsPromise) {
        return optionalModelsPromise;
    }

    optionalModelsPromise = (async () => {
        if (proctoringConfig.object_detection && !objectDetector) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.10.0');
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.3');
            objectDetector = await cocoSsd.load();
        }

        if (proctoringConfig.voice_detection && !myvad) {
            myvad = await vad.MicVAD.new({
                stream: audioStream,
                onSpeechStart: () => {
                    if (isInterviewActive) {
                        voiceAlerts++;
                        // We don't trigger a blocking modal for voice since the user is supposed to talk,
                        // but we count it anyway for demonstration/proctoring metrics.
                    }
                }
            });
            myvad.start();
        }
    })().catch((err) => {
        optionalModelsPromise = null;
        throw err;
    });

    return optionalModelsPromise;
}

// ═══════════════════════════════════════
//  OBJECT DETECTION LOOP
// ═══════════════════════════════════════
let lastObjectWarningTime = 0;
const OBJECT_WARNING_COOLDOWN = 30000; // 30 seconds between warnings
let consecutivePhoneFrames = 0;
const PHONE_DETECTION_THRESHOLD = 0.45;
const PHONE_FRAMES_REQUIRED = 2;

async function objectLoop() {
    if (!isInterviewActive) return;
    if (!objectDetector) {
        setTimeout(objectLoop, OBJECT_DETECT_INTERVAL);
        return;
    }
    try {
        // Keep object detection focused on prohibited objects only. Person counting is
        // handled by face landmarks, which is much more reliable for a kiosk webcam.
        const objects = await objectDetector.detect(video);

        const cellPhoneDetected = objects.some(obj =>
            obj.class === 'cell phone' && obj.score >= PHONE_DETECTION_THRESHOLD
        );

        const now = Date.now();
        const cooldownOk = (now - lastObjectWarningTime) > OBJECT_WARNING_COOLDOWN;

        if (cellPhoneDetected) {
            consecutivePhoneFrames++;
        } else {
            consecutivePhoneFrames = 0;
        }

        if (consecutivePhoneFrames >= PHONE_FRAMES_REQUIRED && cooldownOk) {
            objectAlerts++;
            lastObjectWarningTime = now;
            consecutivePhoneFrames = 0;
            showProctoringWarning("📱 Cell Phone Detected in Frame. Please remove it.");
            logViolation('cell_phone_detected');
        }
    } catch (e) { console.error("Object detection error:", e); }
    setTimeout(objectLoop, OBJECT_DETECT_INTERVAL);
}

function setGazeWarning(message) {
    if (!gazeWarning) return;
    if (message) {
        gazeWarning.textContent = message;
        gazeWarning.style.display = 'block';
    } else {
        gazeWarning.style.display = 'none';
    }
}

function getFaceBounds(lm) {
    let minX = 1, maxX = 0, minY = 1, maxY = 0;
    lm.forEach(p => {
        if (p.x < minX) minX = p.x;
        if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y;
        if (p.y > maxY) maxY = p.y;
    });
    return { minX, maxX, minY, maxY };
}

function isHeadTurned(lm) {
    const nose = lm[1];
    if (!nose) return false;

    const leftEyeCenterX = (lm[P_LEFT_EYE_INNER].x + lm[P_LEFT_EYE_OUTER].x) * 0.5;
    const rightEyeCenterX = (lm[P_RIGHT_EYE_INNER].x + lm[P_RIGHT_EYE_OUTER].x) * 0.5;
    const eyeMidX = (leftEyeCenterX + rightEyeCenterX) * 0.5;
    const { minX, maxX } = getFaceBounds(lm);
    const faceWidth = maxX - minX;

    if (faceWidth <= 0) return false;

    const yawRatio = (nose.x - eyeMidX) / faceWidth;
    return Math.abs(yawRatio) > HEAD_TURN_RATIO_THRESHOLD;
}

function buildAttentionState(faceCount, gazeRatio, headTurned) {
    if (faceCount > 1) {
        return {
            code: 'multiple_faces',
            banner: 'Only one face should be visible',
            message: `Multiple faces (${faceCount}) detected in frame.`,
            threshold: MULTI_FACE_THRESHOLD,
        };
    }

    if (faceCount === 0) {
        return {
            code: 'no_face',
            banner: 'Face not detected',
            message: 'Face not detected. Please stay in front of the screen.',
            threshold: FACE_ABSENCE_THRESHOLD,
        };
    }

    if (headTurned) {
        return {
            code: 'head_turned',
            banner: 'Keep your face directed at the screen',
            message: 'Head turned away for too long. Please face the screen.',
            threshold: HEAD_TURN_THRESHOLD,
        };
    }

    if (gazeRatio === null) {
        return {
            code: 'eyes_not_visible',
            banner: 'Eyes not clearly visible',
            message: 'Eyes not clearly visible. Please face the screen.',
            threshold: FACE_ABSENCE_THRESHOLD,
        };
    }

    if (gazeRatio < NORMAL_MIN || gazeRatio > NORMAL_MAX) {
        return {
            code: 'gaze_off_screen',
            banner: 'Please look at the center of the screen',
            message: 'Suspicious gaze held for too long. Please look at the screen.',
            threshold: DURATION_THRESHOLD,
        };
    }

    return null;
}

function evaluateAttentionState(attentionState, currentTime) {
    if (!attentionState) {
        suspiciousStartTime = null;
        suspiciousState = null;
        alertTriggered = false;
        setGazeWarning(null);
        return false;
    }

    setGazeWarning(attentionState.banner);

    if (!suspiciousState || suspiciousState.code !== attentionState.code) {
        suspiciousState = attentionState;
        suspiciousStartTime = currentTime;
        alertTriggered = false;
        return false;
    }

    if (!alertTriggered && suspiciousStartTime !== null) {
        const elapsed = currentTime - suspiciousStartTime;
        if (elapsed > attentionState.threshold) {
            alertTriggered = true;
            return true;
        }
    }

    return false;
}


// ═══════════════════════════════════════
//  FACE / EYE LOOP
// ═══════════════════════════════════════
let lastVideoTime = -1;

async function faceLoop() {
    if (!isInterviewActive) return;
    const now = Date.now();
    const currentTimeSec = now / 1000;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    try {
        const startTimeMs = performance.now();
        if (video.currentTime !== lastVideoTime) {
            lastVideoTime = video.currentTime;
            const results = faceLandmarker.detectForVideo(video, startTimeMs);
            const faceLandmarks = results.faceLandmarks || [];
            const faceCount = faceLandmarks.length;
            latestGazeFaceCount = faceCount;
            const primaryFace = faceCount > 0 ? faceLandmarks[0] : null;

            let gazeRatio = null;
            let headTurned = false;

            if (primaryFace) {
                if (proctoringConfig.eyeball_tracking) {
                    headTurned = isHeadTurned(primaryFace);

                    if (primaryFace.length >= 478) {
                        const lm = primaryFace;

                        const leftIrisX = lm[P_LEFT_IRIS].x;
                        const leftInnerX = lm[P_LEFT_EYE_INNER].x;
                        const leftOuterX = lm[P_LEFT_EYE_OUTER].x;
                        const leftEyeCenterX = (leftInnerX + leftOuterX) * 0.5;
                        const leftEyeSpan = Math.abs(leftInnerX - leftOuterX);
                        const leftGazeRatio = leftEyeSpan !== 0 ? (leftEyeCenterX - leftIrisX) / (leftEyeSpan / 2) : null;

                        const rightIrisX = lm[P_RIGHT_IRIS].x;
                        const rightInnerX = lm[P_RIGHT_EYE_INNER].x;
                        const rightOuterX = lm[P_RIGHT_EYE_OUTER].x;
                        const rightEyeCenterX = (rightInnerX + rightOuterX) * 0.5;
                        const rightEyeSpan = Math.abs(rightInnerX - rightOuterX);
                        const rightGazeRatio = rightEyeSpan !== 0 ? (rightEyeCenterX - rightIrisX) / (rightEyeSpan / 2) : null;

                        if (leftGazeRatio !== null && rightGazeRatio !== null) {
                            gazeRatio = (leftGazeRatio + rightGazeRatio) / 2.0;
                        }
                    }
                }

                if (proctoringConfig.eyeball_tracking || proctoringConfig.gaze_heatmap) {
                    drawFaceBoundingBox(primaryFace);
                }
            }

            if (proctoringConfig.eyeball_tracking) {
                const attentionState = buildAttentionState(faceCount, gazeRatio, headTurned);
                const shouldAlert = evaluateAttentionState(attentionState, currentTimeSec);

                if (shouldAlert && attentionState) {
                    gazeAlerts++;
                    showProctoringWarning(attentionState.message);
                    logViolation(attentionState.code, { message: attentionState.message });
                }

                if (sessionStartTime) {
                    trackingData.push({
                        time: (now - sessionStartTime) / 1000,
                        gazeRatio: faceCount === 1 ? gazeRatio : null
                    });
                }
            }

            if (proctoringConfig.gaze_heatmap && gazeRecorderTracking && window.webgazer && faceCount === 1) {
                const wg = window.webgazer;
                if (typeof wg.getCurrentPrediction === 'function') {
                    Promise.resolve(wg.getCurrentPrediction()).then(function (pred) {
                        maybeRecordWebGazerSample(pred, "polling");
                    }).catch(function () {});
                }
            }
        }
    } catch (e) {
        console.error("Face detection error:", e);
    }
    requestAnimationFrame(faceLoop);
}

// Subtly outline the face to prove proctoring works underneath
function drawFaceBoundingBox(lm) {
    const W = canvas.width;
    const H = canvas.height;
    const { minX, maxX, minY, maxY } = getFaceBounds(lm);

    ctx.save();
    ctx.strokeStyle = '#4CAF50';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.rect(minX * W, minY * H, (maxX - minX) * W, (maxY - minY) * H);
    ctx.stroke();
    ctx.restore();
}
