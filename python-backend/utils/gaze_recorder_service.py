import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


class GazeRecorderService:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def build_session_page(self, session_id: str, submit_url: str, auth_token: str = "") -> str:
        html = GAZE_RECORDER_HTML_TEMPLATE
        html = html.replace("__SESSION_ID__", session_id)
        html = html.replace("__SUBMIT_URL__", submit_url)
        html = html.replace("__AUTH_TOKEN__", auth_token or "")
        return html

    def analyze_gaze_patterns(
        self,
        gaze_points: List[Dict[str, Any]],
        window_width: int,
        window_height: int,
        started_at_ms: Optional[float] = None,
        ended_at_ms: Optional[float] = None,
    ) -> Dict[str, Any]:
        # This mirrors the heatmap/clustering logic used in screen_track.py.
        if not gaze_points:
            return {
                "duration": 0.0,
                "totalGazePoints": 0,
                "suspiciousRegions": [],
                "cheatingScore": 0,
            }

        grid_size = 20
        cell_width = max(1.0, float(window_width) / grid_size)
        cell_height = max(1.0, float(window_height) / grid_size)

        heatmap = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
        for point in gaze_points:
            px = float(point.get("x", 0))
            py = float(point.get("y", 0))
            cell_x = int(px // cell_width)
            cell_y = int(py // cell_height)
            if 0 <= cell_x < grid_size and 0 <= cell_y < grid_size:
                heatmap[cell_y][cell_x] += 1

        avg_visits = len(gaze_points) / float(grid_size * grid_size)
        threshold = avg_visits * 3.0
        visited = [[False for _ in range(grid_size)] for _ in range(grid_size)]
        clusters: List[List[Dict[str, Any]]] = []

        def explore_cluster(y: int, x: int) -> List[Dict[str, Any]]:
            if y < 0 or y >= grid_size or x < 0 or x >= grid_size:
                return []
            if visited[y][x] or heatmap[y][x] < threshold:
                return []

            visited[y][x] = True
            cells = [{"x": x, "y": y, "count": heatmap[y][x]}]
            cells += explore_cluster(y - 1, x)
            cells += explore_cluster(y + 1, x)
            cells += explore_cluster(y, x - 1)
            cells += explore_cluster(y, x + 1)
            return cells

        for y in range(grid_size):
            for x in range(grid_size):
                if not visited[y][x] and heatmap[y][x] >= threshold:
                    cluster = explore_cluster(y, x)
                    if len(cluster) >= 2:
                        clusters.append(cluster)

        suspicious_regions: List[Dict[str, Any]] = []
        for idx, cluster in enumerate(clusters):
            min_x = min(c["x"] for c in cluster) * cell_width
            max_x = (max(c["x"] for c in cluster) + 1) * cell_width
            min_y = min(c["y"] for c in cluster) * cell_height
            max_y = (max(c["y"] for c in cluster) + 1) * cell_height

            total_visits = sum(c["count"] for c in cluster)
            avg_x = sum(c["x"] * c["count"] for c in cluster) / total_visits
            avg_y = sum(c["y"] * c["count"] for c in cluster) / total_visits

            visits = [
                p for p in gaze_points
                if min_x <= float(p.get("x", 0)) <= max_x and min_y <= float(p.get("y", 0)) <= max_y
            ]
            timestamps = [float(v.get("timestamp", 0)) for v in visits]
            time_gaps = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
            avg_gap = (sum(time_gaps) / len(time_gaps)) if time_gaps else 0.0
            is_repeated = len([gap for gap in time_gaps if 2 < gap < 15]) >= 3
            severity = "high" if is_repeated else ("medium" if total_visits > avg_visits * 5 else "low")

            suspicious_regions.append({
                "id": idx + 1,
                "bounds": {
                    "left": min_x,
                    "top": min_y,
                    "width": max_x - min_x,
                    "height": max_y - min_y,
                },
                "center": {
                    "x": avg_x * cell_width + cell_width / 2,
                    "y": avg_y * cell_height + cell_height / 2,
                },
                "visits": total_visits,
                "percentage": round((total_visits / len(gaze_points)) * 100.0, 1),
                "avgTimeGap": round(avg_gap, 1),
                "isRepeated": is_repeated,
                "severity": severity,
            })

        suspicious_regions.sort(key=lambda region: region["visits"], reverse=True)

        cheating_score = 0
        for region in suspicious_regions:
            if region["severity"] == "high":
                cheating_score += 30
            elif region["severity"] == "medium":
                cheating_score += 15
            else:
                cheating_score += 5
        cheating_score = min(100, cheating_score)

        duration = 0.0
        if started_at_ms and ended_at_ms and ended_at_ms >= started_at_ms:
            duration = (ended_at_ms - started_at_ms) / 1000.0
        elif len(gaze_points) > 1:
            duration = float(gaze_points[-1].get("timestamp", 0)) - float(gaze_points[0].get("timestamp", 0))

        return {
            "duration": round(duration, 2),
            "totalGazePoints": len(gaze_points),
            "suspiciousRegions": suspicious_regions,
            "cheatingScore": cheating_score,
        }

    def save_payload_files(
        self,
        session_id: str,
        user_id: str,
        recording_data: Optional[Dict[str, Any]],
        analysis_result: Dict[str, Any],
        gaze_points: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Persist the gaze artifacts to GCS (gs:// URIs returned; served back
        through /api/view-file's signed-URL redirect). Nothing is kept on
        local disk — GCS is mandatory platform-wide, so an upload failure
        raises rather than silently writing a file the next container restart
        would destroy."""
        from services import gcs_service

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        base_name = f"{session_id}_{user_id}_{timestamp}"

        def _upload_json(payload: Any, filename: str) -> str:
            blob = json.dumps(payload, indent=2).encode("utf-8")
            return gcs_service.upload_file(
                blob,
                f"proctoring/gaze_recorder/{filename}",
                content_type="application/json",
            )

        recording_path = ""
        if recording_data is not None:
            recording_path = _upload_json(recording_data, f"{base_name}_gaze_recorder_recording.json")

        analysis_path = _upload_json(analysis_result, f"{base_name}_gaze_analysis.json")
        points_path = _upload_json(gaze_points, f"{base_name}_gaze_points.json")

        return {
            "recording_path": recording_path,
            "analysis_path": analysis_path,
            "points_path": points_path,
        }


GAZE_RECORDER_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Smart Gaze Recorder</title>
<script src="https://app.gazerecorder.com/GazeCloudAPI.js"></script>
<script src="https://app.gazerecorder.com/GazeRecorderAPI.js"></script>
<script src="https://app.gazerecorder.com/GazePlayer.js"></script>
<style>
body { margin: 0; padding: 0; font-family: Arial, sans-serif; overflow: hidden; }
#controls {
    position: fixed; top: 10px; right: 10px; background: rgba(0, 0, 0, 0.85);
    color: #fff; border-radius: 8px; padding: 14px; z-index: 1000; width: 320px;
}
#status { background: rgba(50, 50, 50, 0.85); padding: 8px; border-radius: 4px; font-weight: bold; margin-bottom: 10px; }
.btn { width: 100%; margin: 6px 0; padding: 10px; border: none; border-radius: 4px; color: #fff; cursor: pointer; font-weight: 700; }
.btn-start { background: #2f9e44; }
.btn-stop { background: #c92a2a; }
.btn-analyze { background: #1971c2; }
.btn-play { background: #6741d9; }
.btn-submit { background: #0b7285; }
#metrics { margin-top: 10px; background: rgba(32, 32, 32, 0.9); border-radius: 4px; padding: 10px; font-size: 12px; }
.metric-row { display: flex; justify-content: space-between; margin: 4px 0; }
.warning { background: #e03131 !important; }
.suspicious-region { position: absolute; border: 3px solid #e03131; background: rgba(224, 49, 49, 0.2); pointer-events: none; z-index: 500; display: none; }
.region-label { position: absolute; top: -23px; left: 0; background: #e03131; color: #fff; padding: 3px 7px; border-radius: 3px; font-size: 11px; font-weight: bold; }
#playerdiv { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: #fff; display: none; z-index: 999; }
#interview-content { padding: 100px 56px; max-width: 900px; margin: 0 auto; line-height: 1.45; }
.question { background: #f1f3f5; border-left: 4px solid #1971c2; border-radius: 8px; padding: 18px; margin: 18px 0; }
</style>
<script>
const SESSION_ID = "__SESSION_ID__";
const SUBMIT_URL = "__SUBMIT_URL__";
const AUTH_TOKEN = "__AUTH_TOKEN__";

var recordingData = null;
var isRecording = false;
var startTime = null;
var startedAtMs = null;
var endedAtMs = null;
var gazePoints = [];
var analysisResult = null;

function updateStatus(msg, warning = false) {
    var statusEl = document.getElementById("status");
    statusEl.innerText = msg;
    if (warning) statusEl.classList.add("warning");
    else statusEl.classList.remove("warning");
}

function updateMetrics() {
    if (!isRecording) return;
    var duration = ((Date.now() - startTime) / 1000).toFixed(1);
    document.getElementById("duration").innerText = duration + "s";
    document.getElementById("gaze-points").innerText = gazePoints.length;
}

function trackGazePoint(gazeData) {
    if (!isRecording) return;
    var timestamp = (Date.now() - startTime) / 1000;
    var gazeX = gazeData.docX || 0;
    var gazeY = gazeData.docY || 0;
    gazePoints.push({ timestamp: timestamp, x: gazeX, y: gazeY });
    updateMetrics();
}

if (typeof GazeCloudAPI !== "undefined") {
    var originalCallback = GazeCloudAPI.OnResult;
    GazeCloudAPI.OnResult = function(gazeData) {
        trackGazePoint(gazeData);
        if (originalCallback) originalCallback(gazeData);
    };
}

function startCalibrationAndRecording() {
    updateStatus("Starting calibration...");
    gazePoints = [];
    analysisResult = null;
    recordingData = null;
    startedAtMs = Date.now();
    endedAtMs = null;
    document.querySelectorAll(".suspicious-region").forEach(el => el.remove());
    GazeCloudAPI.StartEyeTracking();
    GazeCloudAPI.OnCalibrationComplete = function() {
        updateStatus("Recording...");
        startRecording();
    };
}

function startRecording() {
    GazeRecorderAPI.Rec();
    isRecording = true;
    startTime = Date.now();
    document.getElementById("btn-start").style.display = "none";
    document.getElementById("btn-stop").style.display = "block";
    document.getElementById("metrics").style.display = "block";
}

function stopRecording() {
    if (!isRecording) {
        updateStatus("No recording in progress");
        return;
    }
    GazeRecorderAPI.StopRec();
    GazeCloudAPI.StopEyeTracking();
    recordingData = GazeRecorderAPI.GetRecData();
    isRecording = false;
    endedAtMs = Date.now();
    updateStatus("Recording stopped. Click Analyze Patterns");
    document.getElementById("btn-stop").style.display = "none";
    document.getElementById("btn-analyze").style.display = "block";
}

function analyzeGazePatterns() {
    if (gazePoints.length === 0) {
        updateStatus("No gaze data to analyze");
        return;
    }
    updateStatus("Analyzing gaze patterns...");
    var windowWidth = window.innerWidth;
    var windowHeight = window.innerHeight;
    var gridSize = 20;
    var cellWidth = windowWidth / gridSize;
    var cellHeight = windowHeight / gridSize;
    var heatmap = Array(gridSize).fill(0).map(() => Array(gridSize).fill(0));

    gazePoints.forEach(point => {
        var cellX = Math.floor(point.x / cellWidth);
        var cellY = Math.floor(point.y / cellHeight);
        if (cellX >= 0 && cellX < gridSize && cellY >= 0 && cellY < gridSize) heatmap[cellY][cellX]++;
    });

    var avgVisits = gazePoints.length / (gridSize * gridSize);
    var threshold = avgVisits * 3;
    var clusters = [];
    var visited = Array(gridSize).fill(0).map(() => Array(gridSize).fill(false));

    function exploreCluster(y, x) {
        if (y < 0 || y >= gridSize || x < 0 || x >= gridSize) return [];
        if (visited[y][x] || heatmap[y][x] < threshold) return [];
        visited[y][x] = true;
        var cells = [{x: x, y: y, count: heatmap[y][x]}];
        cells = cells.concat(exploreCluster(y - 1, x));
        cells = cells.concat(exploreCluster(y + 1, x));
        cells = cells.concat(exploreCluster(y, x - 1));
        cells = cells.concat(exploreCluster(y, x + 1));
        return cells;
    }

    for (var y = 0; y < gridSize; y++) {
        for (var x = 0; x < gridSize; x++) {
            if (!visited[y][x] && heatmap[y][x] >= threshold) {
                var cluster = exploreCluster(y, x);
                if (cluster.length >= 2) clusters.push(cluster);
            }
        }
    }

    var suspiciousRegions = [];
    clusters.forEach((cluster, idx) => {
        var minX = Math.min(...cluster.map(c => c.x)) * cellWidth;
        var maxX = (Math.max(...cluster.map(c => c.x)) + 1) * cellWidth;
        var minY = Math.min(...cluster.map(c => c.y)) * cellHeight;
        var maxY = (Math.max(...cluster.map(c => c.y)) + 1) * cellHeight;
        var totalVisits = cluster.reduce((sum, c) => sum + c.count, 0);
        var avgX = cluster.reduce((sum, c) => sum + c.x * c.count, 0) / totalVisits;
        var avgY = cluster.reduce((sum, c) => sum + c.y * c.count, 0) / totalVisits;
        var visits = gazePoints.filter(p => p.x >= minX && p.x <= maxX && p.y >= minY && p.y <= maxY);
        var timestamps = visits.map(v => v.timestamp);
        var timeGaps = [];
        for (var i = 1; i < timestamps.length; i++) timeGaps.push(timestamps[i] - timestamps[i - 1]);
        var avgGap = timeGaps.length > 0 ? timeGaps.reduce((a, b) => a + b, 0) / timeGaps.length : 0;
        var isRepeated = timeGaps.filter(gap => gap > 2 && gap < 15).length >= 3;

        suspiciousRegions.push({
            id: idx + 1,
            bounds: { left: minX, top: minY, width: maxX - minX, height: maxY - minY },
            center: { x: avgX * cellWidth + cellWidth / 2, y: avgY * cellHeight + cellHeight / 2 },
            visits: totalVisits,
            percentage: (totalVisits / gazePoints.length * 100).toFixed(1),
            avgTimeGap: avgGap.toFixed(1),
            isRepeated: isRepeated,
            severity: isRepeated ? "high" : (totalVisits > avgVisits * 5 ? "medium" : "low")
        });
    });

    suspiciousRegions.sort((a, b) => b.visits - a.visits);
    var cheatingScore = 0;
    suspiciousRegions.forEach(region => {
        if (region.severity === "high") cheatingScore += 30;
        else if (region.severity === "medium") cheatingScore += 15;
        else cheatingScore += 5;
    });
    cheatingScore = Math.min(100, cheatingScore);

    analysisResult = {
        duration: (Date.now() - startTime) / 1000,
        totalGazePoints: gazePoints.length,
        suspiciousRegions: suspiciousRegions,
        cheatingScore: cheatingScore
    };

    displayAnalysisResults();
}

function displayAnalysisResults() {
    if (!analysisResult) return;
    var score = analysisResult.cheatingScore;
    var regions = analysisResult.suspiciousRegions;
    if (score < 30) updateStatus("Analysis complete - Low risk");
    else if (score < 60) updateStatus("Analysis complete - Medium risk", true);
    else updateStatus("Analysis complete - High risk", true);

    document.getElementById("cheating-score").innerText = score + "/100";
    document.getElementById("suspicious-regions").innerText = regions.length;

    regions.forEach(region => {
        var div = document.createElement("div");
        div.className = "suspicious-region";
        div.style.left = region.bounds.left + "px";
        div.style.top = region.bounds.top + "px";
        div.style.width = region.bounds.width + "px";
        div.style.height = region.bounds.height + "px";
        div.style.display = "block";
        var label = document.createElement("div");
        label.className = "region-label";
        label.innerText = "Region " + region.id + ": " + region.visits + " visits (" + region.percentage + "%)";
        div.appendChild(label);
        document.body.appendChild(div);
    });

    document.getElementById("btn-analyze").style.display = "none";
    document.getElementById("btn-play").style.display = "block";
    document.getElementById("btn-submit").style.display = "block";
}

function playRecording() {
    if (!recordingData) {
        updateStatus("No recording data available");
        return;
    }
    updateStatus("Playing recording heatmap...");
    document.getElementById("interview-content").style.display = "none";
    document.getElementById("controls").style.display = "none";
    document.querySelectorAll(".suspicious-region").forEach(el => el.style.display = "none");
    var playerDiv = document.getElementById("playerdiv");
    playerDiv.style.display = "block";
    GazePlayer.SetCountainer(playerDiv);
    GazePlayer.PlayResultsData(recordingData);
}

async function submitResults() {
    if (!analysisResult) {
        updateStatus("Analyze patterns first");
        return;
    }
    updateStatus("Submitting results to backend...");
    try {
        const headers = { "Content-Type": "application/json" };
        if (AUTH_TOKEN) headers["Authorization"] = "Bearer " + AUTH_TOKEN;

        const response = await fetch(SUBMIT_URL, {
            method: "POST",
            headers: headers,
            body: JSON.stringify({
                session_id: SESSION_ID,
                recordingData: recordingData,
                analysisResult: analysisResult,
                gazePoints: gazePoints,
                startedAtMs: startedAtMs,
                endedAtMs: endedAtMs,
                viewport: { width: window.innerWidth, height: window.innerHeight }
            })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Submission failed");
        updateStatus("Submitted successfully");
        if (window.opener) {
            window.opener.postMessage({
                type: "GAZE_RECORDER_SUBMITTED",
                sessionId: SESSION_ID,
                analysis: analysisResult
            }, "*");
        }
        console.log(payload);
    } catch (error) {
        updateStatus("Submit failed: " + error.message, true);
        if (window.opener) {
            window.opener.postMessage({
                type: "GAZE_RECORDER_SUBMIT_FAILED",
                sessionId: SESSION_ID,
                error: error.message
            }, "*");
        }
    }
}

async function finalizeAndSubmit() {
    try {
        if (isRecording) {
            stopRecording();
        }
        if (!analysisResult && gazePoints.length > 0) {
            analyzeGazePatterns();
        }
        if (analysisResult) {
            await submitResults();
            return true;
        }
        updateStatus("No gaze data captured for submission", true);
        return false;
    } catch (error) {
        updateStatus("Finalize failed: " + error.message, true);
        return false;
    }
}

window.addEventListener("message", async function(event) {
    var payload = event.data || {};
    if (!payload || payload.type !== "GAZE_RECORDER_COMMAND") return;

    if (payload.command === "start") {
        startCalibrationAndRecording();
        return;
    }
    if (payload.command === "stop") {
        stopRecording();
        return;
    }
    if (payload.command === "analyze") {
        analyzeGazePatterns();
        return;
    }
    if (payload.command === "submit") {
        await submitResults();
        return;
    }
    if (payload.command === "finalize_submit") {
        await finalizeAndSubmit();
    }
});

window.onload = function() {
    updateStatus("Ready. Click Start Interview Recording");
    if (window.opener) {
        window.opener.postMessage({ type: "GAZE_RECORDER_READY", sessionId: SESSION_ID }, "*");
    }
};
setInterval(function() { if (isRecording) updateMetrics(); }, 500);
</script>
</head>
<body>
<div id="controls">
    <div id="status">Ready</div>
    <button id="btn-start" class="btn btn-start" onclick="startCalibrationAndRecording()">Start Interview Recording</button>
    <button id="btn-stop" class="btn btn-stop" onclick="stopRecording()" style="display:none;">Stop Recording</button>
    <button id="btn-analyze" class="btn btn-analyze" onclick="analyzeGazePatterns()" style="display:none;">Analyze Patterns</button>
    <button id="btn-play" class="btn btn-play" onclick="playRecording()" style="display:none;">Play Heatmap</button>
    <button id="btn-submit" class="btn btn-submit" onclick="submitResults()" style="display:none;">Submit To Backend</button>
    <div id="metrics" style="display:none;">
        <div class="metric-row"><span>Duration:</span><span id="duration">0s</span></div>
        <div class="metric-row"><span>Gaze Points:</span><span id="gaze-points">0</span></div>
        <div class="metric-row"><span>Cheating Score:</span><span id="cheating-score">-</span></div>
        <div class="metric-row"><span>Suspicious Regions:</span><span id="suspicious-regions">-</span></div>
    </div>
</div>

<div id="interview-content">
    <h1>Online Interview - Technical Round</h1>
    <div class="question"><h3>Question 1</h3><p>Explain the difference between stack and queue with examples.</p></div>
    <div class="question"><h3>Question 2</h3><p>What is Big O notation? Explain O(1), O(n), O(n2), O(log n).</p></div>
    <div class="question"><h3>Question 3</h3><p>Design a schema for users, products, orders, and payments.</p></div>
    <div class="question"><h3>Question 4</h3><p>Reverse a linked list and explain complexity.</p></div>
    <div class="question"><h3>Question 5</h3><p>How would you design a URL shortener service?</p></div>
</div>

<div id="playerdiv"></div>
</body>
</html>
"""
