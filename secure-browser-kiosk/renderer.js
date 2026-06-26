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

let video, canvas, ctx;
let objectDetector;
let faceLandmarker;
let myvad;
let optionalModelsPromise = null;

// UI Elements
let loadingOverlay, testingOverlay, startupView, interviewView, resultsView;
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
let clockInterval = null;

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
let silenceInterval = null;

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

    // Return to GenHire Dashboard button
    const btnReturnDashboard = document.getElementById('btn-return-dashboard');
    if (btnReturnDashboard) {
        btnReturnDashboard.addEventListener('click', () => {
            // Build dashboard URL from API URL (strip /api suffix)
            let dashboardUrl = 'http://localhost:3000/profile#applications';
            if (apiUrl) {
                // apiUrl is like "http://127.0.0.1:5000/api" — derive the frontend URL
                // The frontend typically runs on port 3000
                try {
                    const urlObj = new URL(apiUrl);
                    dashboardUrl = `${urlObj.protocol}//${urlObj.hostname}:3000/profile#applications`;
                } catch (e) {
                    console.warn('Could not parse apiUrl, using default:', e);
                }
            }

            // Open in default browser
            if (window.electronAPI && window.electronAPI.openExternal) {
                window.electronAPI.openExternal(dashboardUrl);
            }

            // Close the Electron app after a short delay
            setTimeout(() => {
                if (window.electronAPI && window.electronAPI.quitApp) {
                    window.electronAPI.quitApp();
                }
            }, 1500);
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
        } else {
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

            // Extract proctoring config from server response
            if (data.proctoring_config) {
                proctoringConfig = data.proctoring_config;
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

function finalizeStartInterview() {
    testingOverlay.style.display = 'none';
    interviewView.style.display = 'block';

    isInterviewActive = true;
    sessionStartTime = Date.now();

    // LOCK DOWN: Enable kiosk mode now that the interview is starting
    if (window.electronAPI && window.electronAPI.enableKiosk) {
        window.electronAPI.enableKiosk();
    }

    // Start Socket connection
    if (!socket) {
        socket = io(apiUrl);
        socket.on("connect", () => {
            socket.emit("start_proctoring", { session_id: currentSessionId });
            socket.emit("control_mobile_recording", { session_id: currentSessionId, action: "start" });
        });
        socket.on("gaze_data", (data) => {
            if (data.is_cheating_alert) {
                showProctoringWarning("Mobile Cam: Suspicious head pose detected.");
            }
        });
    }

    // Speak the very first question!
    const finishSetupAndSpeak = async () => {
        try {
            const base64Audio = await window.electronAPI.synthesizeSpeech(currentQuestion);
            const audioDataUrl = `data:audio/mp3;base64,${base64Audio}`;
            if (currentAudioObj) {
                currentAudioObj.pause();
                currentAudioObj.currentTime = 0;
            }
            currentAudioObj = new Audio(audioDataUrl);

            currentAudioObj.onended = () => {
                // start recording when TTS is done speaking FIRST question
                if (isInterviewActive && !isRecording && !speechNetworkFailed) {
                    if (proctoringConfig.voice_detection) startRecording();
                }
            };
            currentAudioObj.play();
        } catch (err) {
            console.error("Failed to speak first question", err);
            // Fallback: Start immediately if speech fails
            if (proctoringConfig.voice_detection && !speechNetworkFailed) {
                startRecording();
            }
        }
    };
    finishSetupAndSpeak();

    // Start Timer
    clockInterval = setInterval(() => {
        const elapsed = (Date.now() - sessionStartTime) / 1000;
        timeDisplay.textContent = formatTime(elapsed);
    }, 1000);

    document.getElementById('q-count').textContent = questionCount;
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
    if (silenceInterval) clearInterval(silenceInterval);

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

        if (!endResp.ok) {
            const endError = await endResp.text();
            throw new Error(`Interview end request failed (${endResp.status}): ${endError}`);
        }
    } catch (e) {
        console.error("Failed to signal backend to end interview or send gaze tracking data", e);
    }

    // UNLOCK: Disable kiosk mode now that interview is over
    if (window.electronAPI && window.electronAPI.disableKiosk) {
        window.electronAPI.disableKiosk();
    }

    // Prepare Results View
    interviewView.style.display = 'none';
    resultsView.style.display = 'flex';

    // Populate Metrics
    document.getElementById('val-gaze').textContent = gazeAlerts;
    document.getElementById('val-obj').textContent = objectAlerts;
    document.getElementById('val-voice').textContent = voiceAlerts;

    let totalElapsed = 0;
    if (sessionStartTime) totalElapsed = (Date.now() - sessionStartTime) / 1000;
    document.getElementById('val-time').textContent = formatTime(totalElapsed);

    renderChart();
}

async function submitAnswer() {
    if (isSubmittingAnswer || !isInterviewActive) return;

    const sendBtn = document.getElementById('send-btn');
    isSubmittingAnswer = true;
    sendBtn.innerHTML = "Wait...";

    stopRecording();

    try {
        // Use speech transcript
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

        if (data.interview_complete || questionCount >= 10) {
            endInterview();
            return;
        }

        // Setup next question
        currentQuestion = data.next_question;
        questionCount++;
        document.getElementById('q-count').textContent = questionCount;

        // Reset speech variables
        currentTranscript = "";
        lastSpeechTime = Date.now();
        transcriptText.innerHTML = `<strong>AI:</strong> ${currentQuestion}`;
        transcriptText.style.fontStyle = "italic";

        // Speak question via Google TTS, then listen again
        try {
            const base64Audio = await window.electronAPI.synthesizeSpeech(currentQuestion);
            const audioDataUrl = `data:audio/mp3;base64,${base64Audio}`;
            if (currentAudioObj) {
                currentAudioObj.pause();
                currentAudioObj.currentTime = 0;
            }
            currentAudioObj = new Audio(audioDataUrl);

            currentAudioObj.onended = () => {
                if (isInterviewActive && !isRecording && !speechNetworkFailed) {
                    startRecording();
                }
            };
            currentAudioObj.play();
        } catch (ttsErr) {
            console.error("Google TTS failed:", ttsErr);
            // Fallback immediately to recording if TTS fails
            if (isInterviewActive && !isRecording && !speechNetworkFailed) {
                startRecording();
            }
        }

    } catch (err) {
        alert("Failed to submit answer. " + err.message);
    } finally {
        isSubmittingAnswer = false;
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
//  GOOGLE CLOUD RECORDING HELPERS
// ═══════════════════════════════════════
function startRecording() {
    if (isRecording || !audioStream || !window.electronAPI) return;

    isRecording = true;
    currentTranscript = "";
    document.getElementById('mic-btn').classList.add('mic-recording');

    window.electronAPI.startSTTStream();

    // Create a new MediaRecorder to send audio chunks. 
    // We must extract ONLY the audio track, otherwise MediaRecorder fails when given a video track with an audio mimeType.
    const audioTrack = audioStream.getAudioTracks()[0];
    const recordStream = new MediaStream([audioTrack]);

    let mimeType = 'audio/webm;codecs=opus';
    if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/webm';
    }

    mediaRecorder = new MediaRecorder(recordStream, { mimeType });
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

    // Silence auto-submit timer
    if (silenceInterval) clearInterval(silenceInterval);
    silenceInterval = setInterval(() => {
        if (!isInterviewActive || isSubmittingAnswer || !isRecording) return;
        const timeSinceLastSpeech = (Date.now() - lastSpeechTime) / 1000;
        if (timeSinceLastSpeech >= 5 && currentTranscript.trim().length > 0) {
            submitAnswer();
        }
    }, 1000);
}

function stopRecording() {
    if (!isRecording) return;
    isRecording = false;

    if (silenceInterval) clearInterval(silenceInterval);
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
