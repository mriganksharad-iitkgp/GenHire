// Configuration
const REQUIRED_WIDTH = 640;
const REQUIRED_HEIGHT = 480;

let video, canvas, ctx;
let objectDetector;
let faceLandmarker;
let myvad;

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

let warningCount = 0; 3
let currentSessionId = null;
let socket = null;

let isInterviewActive = false;
let clockInterval = null;

// API Data
let apiToken = null;
let apiUrl = null;
let globalSessionData = null; // Store deep link payload globally
let currentQuestion = "";
let questionCount = 0;
let isSubmittingAnswer = false;

// GazeCloud Recorder State
let gazePointsTracker = [];
let gazeStartedAtMs = null;
let gazeEndedAtMs = null;
let gazeRecorderTracking = false;

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
const NORMAL_MIN = -0.35;
const NORMAL_MAX = 0.35;
let suspiciousStartTime = null;
let isSuspicious = false;
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
    document.getElementById('btn-ack-warning').addEventListener('click', () => {
        proctoringModal.style.display = 'none';
    });

    // Setup Google Cloud STT Callbacks
    if (window.electronAPI) {
        // Handle Deep Link Auto-Start
        window.electronAPI.onInitDeepLink((event, initData) => {
            console.log("Deep link received, session data ready.");
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
                console.log(`🗣️ Heard (final): "${text.trim()}"`);
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
        console.log('✅ Google Cloud STT callbacks registered');
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
        btnStart.textContent = "Begin Interview Setup";
        if (globalSessionData) {
            btnStart.disabled = false;
        } else {
            // Setup an interval to enable it once data drops in
            const waitData = setInterval(() => {
                if (globalSessionData) {
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

async function startInterview() {
    if (!globalSessionData) {
        alert("Missing session data. Please launch this app directly from the Genhire Dashboard.");
        return;
    }

    let payload;
    try {
        const decoded = atob(globalSessionData);
        payload = JSON.parse(decoded);
        if (!payload.applicationId || !payload.token) throw new Error("Invalid payload structure");
    } catch (e) {
        alert("Invalid initialization data.");
        return;
    }

    apiToken = payload.token;
    apiUrl = payload.apiUrl;

    // Switch Views to Testing Overlay!
    btnStart.disabled = true;
    startupView.style.display = 'none';
    testingOverlay.style.display = 'flex';

    try {
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

        console.log(`\n📋 === INTERVIEW STARTED ===`);
        console.log(`   Session ID: ${currentSessionId}`);
        console.log(`   Q${questionCount} FROM SERVER: "${currentQuestion}"`);

        // Extract proctoring config from server response
        if (data.proctoring_config) {
            proctoringConfig = data.proctoring_config;
        }
        console.log(`   Proctoring Config:`, JSON.stringify(proctoringConfig));
        console.log(`================================\n`);

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
        gazePointsTracker = [];
        gazeStartedAtMs = Date.now();

        window.webgazer
            .setRegression('ridge')
            .setTracker('TFFacemesh')
            .setGazeListener(function (data, elapsedMs) {
                if (gazeRecorderTracking && data) {
                    let ts = elapsedMs / 1000;
                    let x = Math.max(0, Math.min(window.innerWidth - 1, data.x));
                    let y = Math.max(0, Math.min(window.innerHeight - 1, data.y));
                    gazePointsTracker.push({
                        timestamp: ts,
                        x: Math.round(x),
                        y: Math.round(y),
                    });
                }
            })
            .showVideoPreview(false)
            .showPredictionPoints(false)
            .begin()
            .then(() => {
                // Run an inline 5-point calibration before finalizing
                let calibrationPoints = [
                    {x: '10%', y: '10%'}, {x: '90%', y: '10%'}, 
                    {x: '50%', y: '50%'}, 
                    {x: '10%', y: '90%'}, {x: '90%', y: '90%'}
                ];
                let calIdx = 0;

                const overlay = document.createElement('div');
                overlay.style.cssText = "position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:99999; display:flex; flex-direction:column; align-items:center; justify-content:center; color:white; font-family:sans-serif;";
                
                const title = document.createElement('h2');
                title.textContent = "👀 Eye Tracking Calibration";
                const sub = document.createElement('p');
                sub.textContent = "Look directly at the red dot and CLICK it to calibrate your eye tracking.";
                
                const dot = document.createElement('div');
                dot.style.cssText = `position:absolute; width:40px; height:40px; background:red; border-radius:50%; cursor:pointer; transition:all 0.3s ease; left:${calibrationPoints[0].x}; top:${calibrationPoints[0].y}; box-shadow: 0 0 10px red;`;

                overlay.appendChild(title);
                overlay.appendChild(sub);
                overlay.appendChild(dot);
                document.body.appendChild(overlay);

                dot.addEventListener('click', () => {
                    calIdx++;
                    if (calIdx >= calibrationPoints.length) {
                        document.body.removeChild(overlay);
                        gazeRecorderTracking = true;
                        finalizeStartInterview();
                    } else {
                        dot.style.left = calibrationPoints[calIdx].x;
                        dot.style.top = calibrationPoints[calIdx].y;
                        sub.textContent = `Point ${calIdx+1} of ${calibrationPoints.length} - Keep looking closely at the dot and click!`;
                    }
                });
            })
            .catch(err => {
                console.error("WebGazer start error:", err);
                finalizeStartInterview();
            });

    } else {
        if (!proctoringConfig.gaze_heatmap) {
            console.log("🔒 Gaze Heatmap proctoring is disabled for this job.");
        } else {
            console.warn("WebGazer not available. Starting without heatmap tracking...");
        }
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
            console.log("WebSocket connected.");
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
            const audioObj = new Audio(audioDataUrl);

            audioObj.onended = () => {
                // start recording when TTS is done speaking FIRST question
                if (isInterviewActive && !isRecording && !speechNetworkFailed) {
                    if (proctoringConfig.voice_detection) startRecording();
                }
            };
            audioObj.play();
        } catch (err) {
            console.error("Failed to speak first question", err);
            // Fallback: Start immediately if speech fails
            if (proctoringConfig.voice_detection && !speechNetworkFailed) {
                startRecording();
            }
        }
    };
    finishSetupAndSpeak();

    if (!proctoringConfig.voice_detection) {
        console.log("🔒 Voice Detection proctoring is disabled for this job.");
    }

    // Start Timer
    clockInterval = setInterval(() => {
        const elapsed = (Date.now() - sessionStartTime) / 1000;
        timeDisplay.textContent = formatTime(elapsed);
    }, 1000);

    document.getElementById('q-count').textContent = questionCount;
    transcriptText.textContent = currentQuestion;

    // Start tracking loops conditionally
    if (proctoringConfig.eyeball_tracking) {
        requestAnimationFrame(faceLoop);
    } else {
        console.log("🔒 Eyeball Tracking proctoring is disabled for this job.");
    }
    if (proctoringConfig.object_detection) {
        objectLoop();
    } else {
        console.log("🔒 Object Detection proctoring is disabled for this job.");
    }
}

async function endInterview() {
    isInterviewActive = false;
    clearInterval(clockInterval);
    if (silenceInterval) clearInterval(silenceInterval);

    stopRecording();
    
    if (gazeRecorderTracking && window.webgazer) {
        window.webgazer.pause();
        gazeRecorderTracking = false;
        gazeEndedAtMs = Date.now();
    }

    if (socket && socket.connected) {
        socket.emit("control_mobile_recording", { session_id: currentSessionId, action: "stop" });
        socket.disconnect();
    }

    // Stop Media Streams
    if (video.srcObject) {
        video.srcObject.getTracks().forEach(t => t.stop());
    }

    // Tell backend to end interview and send gaze data
    try {
        if (proctoringConfig.gaze_heatmap && gazePointsTracker.length > 0) {
            await fetch(`${apiUrl}/api/interviews/${currentSessionId}/gaze-recorder-results`, {
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
        }

        await fetch(`${apiUrl}/api/interviews/${currentSessionId}/end`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiToken}`
            },
            body: JSON.stringify({
                tracking_data: proctoringConfig.eyeball_tracking ? trackingData : []
            })
        });
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

        console.log(`\n📤 === SUBMITTING ANSWER (Q${questionCount}) ===`);
        console.log(`   QUESTION: "${payload.question}"`);
        console.log(`   ANSWER:   "${payload.answer}"`);
        console.log(`==========================================`);

        const response = await fetch(`${apiUrl}/api/interviews/${currentSessionId}/answer`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiToken}`
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error("Failed to submit");

        const data = await response.json();

        if (data.interview_complete || questionCount >= 3) {
            console.log(`\n🏁 === INTERVIEW COMPLETE (after ${questionCount} questions) ===\n`);
            endInterview();
            return;
        }

        // Setup next question
        currentQuestion = data.next_question;
        questionCount++;
        document.getElementById('q-count').textContent = questionCount;

        console.log(`\n📥 Q${questionCount} FROM SERVER: "${currentQuestion}"\n`);

        // Reset speech variables
        currentTranscript = "";
        lastSpeechTime = Date.now();
        transcriptText.innerHTML = `<strong>AI:</strong> ${currentQuestion}`;
        transcriptText.style.fontStyle = "italic";

        // Speak question via Google TTS, then listen again
        try {
            const base64Audio = await window.electronAPI.synthesizeSpeech(currentQuestion);
            const audioDataUrl = `data:audio/mp3;base64,${base64Audio}`;
            const audioObj = new Audio(audioDataUrl);

            audioObj.onended = () => {
                if (isInterviewActive && !isRecording && !speechNetworkFailed) {
                    startRecording();
                }
            };
            audioObj.play();
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
    audioStream = await navigator.mediaDevices.getUserMedia({
        video: { width: REQUIRED_WIDTH, height: REQUIRED_HEIGHT },
        audio: true,
    });
    video.srcObject = audioStream;
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
            console.log("⏱️ 5 seconds of silence detected. Auto-submitting...");
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
    objectDetector = await cocoSsd.load();
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
        numFaces: 1,
    });

    myvad = await vad.MicVAD.new({
        stream: video.srcObject,
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

// ═══════════════════════════════════════
//  OBJECT DETECTION LOOP
// ═══════════════════════════════════════
async function objectLoop() {
    if (!isInterviewActive) return;
    try {
        const objects = await objectDetector.detect(video);
        let personCount = 0, cellPhoneDetected = false;
        objects.forEach(obj => {
            // Require high confidence to avoid background noise triggering it
            if (obj.class === 'person' && obj.score > 0.65) personCount++;
            if (obj.class === 'cell phone' && obj.score > 0.55) cellPhoneDetected = true;
        });

        if (cellPhoneDetected) {
            objectAlerts++;
            showProctoringWarning("📱 Cell Phone Detected in Frame. Please remove it.");
        } else if (personCount > 1) {
            objectAlerts++;
            showProctoringWarning(`Multiple people (${personCount}) detected in frame.`);
        } else if (personCount === 0) {
            // Missing person could just be head turning too far
        }
    } catch (e) { console.error("Object detection error:", e); }
    setTimeout(objectLoop, OBJECT_DETECT_INTERVAL);
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

            if (results.faceLandmarks && results.faceLandmarks.length > 0) {
                const rawLandmarks = results.faceLandmarks[0];
                let gazeRatio = null;

                if (rawLandmarks.length >= 478) {
                    const lm = rawLandmarks;

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

                    drawFaceBoundingBox(lm);
                }

                let gazeDirection = "Center";
                if (gazeRatio !== null) {
                    if (gazeRatio < NORMAL_MIN) gazeDirection = "Right";
                    else if (gazeRatio > NORMAL_MAX) gazeDirection = "Left";
                }

                // Show Gaze Warning UI dynamically
                if (gazeDirection !== "Center") {
                    gazeWarning.style.display = 'block';
                } else {
                    gazeWarning.style.display = 'none';
                }

                // Check Cheating Duration threshold
                const isCheating = checkCheatingGaze(gazeRatio, currentTimeSec);
                if (isCheating && !alertTriggered) {
                    gazeAlerts++;
                    alertTriggered = true;
                    showProctoringWarning("Suspicious Gaze held for too long. Please look at the screen.");
                }

                if (sessionStartTime) {
                    trackingData.push({ time: (now - sessionStartTime) / 1000, gazeRatio: gazeRatio });
                }

            } else {
                checkCheatingGaze(null, currentTimeSec);
                gazeWarning.style.display = 'none';
                if (sessionStartTime) trackingData.push({ time: (now - sessionStartTime) / 1000, gazeRatio: null });
            }
        }
    } catch (e) {
        console.error("Face detection error:", e);
    }
    requestAnimationFrame(faceLoop);
}

function checkCheatingGaze(gazeRatio, currentTime) {
    if (gazeRatio === null) {
        if (isSuspicious) { isSuspicious = false; suspiciousStartTime = null; alertTriggered = false; }
        return false;
    }
    if (!(NORMAL_MIN < gazeRatio && gazeRatio < NORMAL_MAX)) {
        if (!isSuspicious) { isSuspicious = true; suspiciousStartTime = currentTime; }
        else {
            const elapsed = currentTime - suspiciousStartTime;
            if (elapsed > DURATION_THRESHOLD) return true;
        }
    } else {
        if (isSuspicious) { isSuspicious = false; suspiciousStartTime = null; alertTriggered = false; }
    }
    return false;
}

// Subtly outline the face to prove proctoring works underneath
function drawFaceBoundingBox(lm) {
    const W = canvas.width;
    const H = canvas.height;

    // Find min max X and Y
    let minX = 1, maxX = 0, minY = 1, maxY = 0;
    lm.forEach(p => {
        if (p.x < minX) minX = p.x;
        if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y;
        if (p.y > maxY) maxY = p.y;
    });

    ctx.save();
    ctx.strokeStyle = '#4CAF50';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.rect(minX * W, minY * H, (maxX - minX) * W, (maxY - minY) * H);
    ctx.stroke();
    ctx.restore();
}
