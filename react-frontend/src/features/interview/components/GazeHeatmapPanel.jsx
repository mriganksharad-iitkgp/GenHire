import React, { memo, useCallback, useEffect, useRef, useState } from 'react';
import styles from './GazeHeatmapPanel.module.css';

const GRID = 36;

// Converts the numeric analysis into a 2-3 sentence recruiter-readable summary.
function interpretGaze(analysis) {
  if (!analysis || !analysis.totalGazePoints) {
    return 'No gaze data was recorded for this session (eye-tracking may have been disabled or calibration failed).';
  }
  const score = analysis.cheatingScore || 0;
  const regions = analysis.suspiciousRegions || [];
  const totalPts = analysis.totalGazePoints || 0;
  const duration = analysis.duration || 0;
  const highRisk = regions.filter((r) => r.severity === 'high');
  const medRisk = regions.filter((r) => r.severity === 'medium');

  let intro;
  if (score < 20) {
    intro = 'Low risk — the candidate maintained consistent, natural focus throughout the session.';
  } else if (score < 50) {
    intro = 'Moderate risk — some gaze patterns are slightly unusual but may be within normal variance.';
  } else {
    intro = 'High risk — significant suspicious gaze patterns were detected during the interview.';
  }

  let detail = '';
  if (highRisk.length > 0) {
    detail += ` Repeated off-screen glancing was flagged in ${highRisk.length} screen region${highRisk.length > 1 ? 's' : ''} — these may indicate note-checking or a second screen.`;
  }
  if (medRisk.length > 0) {
    detail += ` ${medRisk.length} area${medRisk.length > 1 ? 's' : ''} showed elevated focus concentration beyond expected reading behaviour.`;
  }
  if (regions.length === 0 && score < 20) {
    detail = ' Gaze was distributed naturally; no suspicious clusters were identified.';
  }

  const stats = ` (${totalPts.toLocaleString()} samples captured over ${Math.round(duration)}s)`;
  return intro + detail + stats;
}

function inferSourceSize(points, regions) {
  let srcW = 0;
  let srcH = 0;
  if (points && points.length) {
    for (const p of points) {
      srcW = Math.max(srcW, Number(p.x) || 0);
      srcH = Math.max(srcH, Number(p.y) || 0);
    }
  }
  if (regions && regions.length) {
    for (const r of regions) {
      const b = r.bounds || {};
      srcW = Math.max(srcW, (Number(b.left) || 0) + (Number(b.width) || 0));
      srcH = Math.max(srcH, (Number(b.top) || 0) + (Number(b.height) || 0));
    }
  }
  if (srcW < 1) srcW = 1920;
  if (srcH < 1) srcH = 1080;
  return { srcW: Math.ceil(srcW * 1.02), srcH: Math.ceil(srcH * 1.02) };
}

function drawCanvas(ctx, W, H, points, regions, sourceSize) {
  if (!ctx) return;
  const { srcW, srcH } = sourceSize;

  ctx.fillStyle = '#0c1222';
  ctx.fillRect(0, 0, W, H);

  // Draw a faint screen-outline so recruiters understand the spatial context.
  ctx.strokeStyle = 'rgba(148,163,184,0.15)';
  ctx.lineWidth = 1;
  ctx.strokeRect(2, 2, W - 4, H - 4);

  if (points && points.length > 0) {
    const cells = Array.from({ length: GRID }, () => Array(GRID).fill(0));
    const cw = srcW / GRID;
    const ch = srcH / GRID;
    for (const p of points) {
      const px = Number(p.x) || 0;
      const py = Number(p.y) || 0;
      const gx = Math.min(GRID - 1, Math.max(0, Math.floor(px / cw)));
      const gy = Math.min(GRID - 1, Math.max(0, Math.floor(py / ch)));
      cells[gy][gx] += 1;
    }
    let maxC = 0;
    for (let y = 0; y < GRID; y++)
      for (let x = 0; x < GRID; x++) maxC = Math.max(maxC, cells[y][x]);

    const cellW = W / GRID;
    const cellH = H / GRID;
    for (let y = 0; y < GRID; y++) {
      for (let x = 0; x < GRID; x++) {
        const c = cells[y][x];
        if (!c) continue;
        const t = maxC ? c / maxC : 0;
        const hue = 210 - t * 210;
        ctx.fillStyle = `hsla(${hue}, 82%, 52%, ${0.2 + t * 0.72})`;
        ctx.fillRect(x * cellW, y * cellH, Math.ceil(cellW) + 1, Math.ceil(cellH) + 1);
      }
    }
  }

  if (regions && regions.length) {
    regions.forEach((r) => {
      const b = r.bounds || {};
      const x = ((Number(b.left) || 0) / srcW) * W;
      const y = ((Number(b.top) || 0) / srcH) * H;
      const w = ((Number(b.width) || 0) / srcW) * W;
      const h = ((Number(b.height) || 0) / srcH) * H;
      const sev = r.severity;
      ctx.strokeStyle =
        sev === 'high'
          ? 'rgba(239,68,68,0.95)'
          : sev === 'medium'
          ? 'rgba(245,158,11,0.95)'
          : 'rgba(234,179,8,0.9)';
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);
      ctx.fillStyle = 'rgba(239,68,68,0.08)';
      ctx.fillRect(x, y, w, h);
    });
  }
}

function GazeHeatmapPanel({ analysis, pointsPath, apiUrl }) {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);
  const [points, setPoints] = useState(null);
  const [loadState, setLoadState] = useState('idle');

  const regions = analysis?.suspiciousRegions || [];

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const rect = wrap.getBoundingClientRect();
    const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
    const cssW = Math.max(320, Math.floor(rect.width));
    const cssH = 320;
    canvas.style.width = `${cssW}px`;
    canvas.style.height = `${cssH}px`;
    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const resolvedPoints = points || [];
    const sourceSize = inferSourceSize(
      resolvedPoints.length ? resolvedPoints : null,
      regions
    );
    drawCanvas(
      ctx,
      cssW,
      cssH,
      resolvedPoints.length ? resolvedPoints : null,
      regions,
      sourceSize
    );
  }, [points, regions]);

  useEffect(() => {
    if (!pointsPath || !apiUrl) {
      setPoints(null);
      setLoadState(analysis ? 'ready' : 'no-data');
      return;
    }
    let cancelled = false;
    setLoadState('loading');
    const url = `${apiUrl}/api/view-file?path=${encodeURIComponent(pointsPath)}`;
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((data) => {
        if (cancelled) return;
        if (!Array.isArray(data) || data.length === 0) {
          setPoints([]);
          setLoadState(analysis ? 'ready' : 'no-data');
          return;
        }
        setPoints(data);
        setLoadState('ready');
      })
      .catch(() => {
        if (cancelled) return;
        setPoints(null);
        setLoadState(analysis ? 'ready' : 'error');
      });
    return () => { cancelled = true; };
  }, [pointsPath, apiUrl, analysis]);

  useEffect(() => { redraw(); }, [redraw, loadState]);

  useEffect(() => {
    const ro =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(() => redraw())
        : null;
    if (wrapRef.current && ro) ro.observe(wrapRef.current);
    return () => ro?.disconnect();
  }, [redraw]);

  const hasAnalysis = analysis && typeof analysis === 'object';
  const totalPts = hasAnalysis ? analysis.totalGazePoints : (points?.length ?? 0);
  const cheatingScore = hasAnalysis ? (analysis.cheatingScore || 0) : 0;
  const showEmpty =
    loadState === 'no-data' ||
    (!hasAnalysis && loadState === 'error' && (!points || points.length === 0));

  if (showEmpty && !hasAnalysis && (!points || points.length === 0)) {
    return (
      <p className={styles.muted}>
        No gaze heatmap data for this interview. Eye-tracking may have been
        disabled or calibration failed to complete.
      </p>
    );
  }

  // Risk zone colour: green below 30, amber 30-60, red above 60
  const riskColor =
    cheatingScore < 30 ? '#22c55e' : cheatingScore < 60 ? '#f59e0b' : '#ef4444';
  const riskLabel =
    cheatingScore < 30 ? 'Low Risk' : cheatingScore < 60 ? 'Moderate Risk' : 'High Risk';

  return (
    <div className={styles.root}>
      {/* Plain-English interpretation — shown first so recruiters read it before the visual */}
      {hasAnalysis && (
        <div className={styles.interpretation}>
          <span className={styles.interpretationLabel} style={{ color: riskColor }}>
            {riskLabel}
          </span>
          <p className={styles.interpretationText}>
            {interpretGaze(analysis)}
          </p>
        </div>
      )}

      {/* Risk score meter */}
      {hasAnalysis && (
        <div className={styles.riskMeter}>
          <div className={styles.riskMeterTrack}>
            {/* Colour zones */}
            <div className={styles.riskMeterGreen} />
            <div className={styles.riskMeterAmber} />
            <div className={styles.riskMeterRed} />
            {/* Marker */}
            <div
              className={styles.riskMeterMarker}
              style={{ left: `${Math.min(100, cheatingScore)}%` }}
              title={`Risk score: ${cheatingScore}/100`}
            />
          </div>
          <div className={styles.riskMeterLabels}>
            <span>0</span>
            <span>Safe</span>
            <span>Suspicious</span>
            <span>100</span>
          </div>
        </div>
      )}

      {/* Stats row */}
      {hasAnalysis && (
        <div className={styles.stats}>
          {analysis.duration != null && (
            <span><strong>Duration</strong> {analysis.duration}s</span>
          )}
          {totalPts != null && (
            <span><strong>Samples</strong> {totalPts.toLocaleString()}</span>
          )}
          {analysis.cheatingScore != null && (
            <span>
              <strong>Risk score</strong>{' '}
              <span style={{ color: riskColor, fontWeight: 700 }}>
                {cheatingScore}/100
              </span>
            </span>
          )}
        </div>
      )}

      {/* Heatmap canvas */}
      <div className={styles.canvasWrap} ref={wrapRef}>
        <canvas
          ref={canvasRef}
          className={styles.canvas}
          aria-label="Candidate gaze focus heatmap"
        />
        <div className={styles.canvasLabel}>
          Candidate Focus Map — brighter = more time spent looking here
        </div>
      </div>

      <div className={styles.legend}>
        <span className={styles.legendCold}>Low attention</span>
        <span className={styles.legendArrow} aria-hidden />
        <span className={styles.legendHot}>High attention</span>
        {regions.length > 0 && (
          <span className={styles.legendRegions}>
            Outlined boxes: flagged suspicious-focus clusters
          </span>
        )}
      </div>

      {loadState === 'loading' && (
        <p className={styles.hint}>Loading raw gaze samples…</p>
      )}
      {loadState === 'error' && (!points || points.length === 0) && hasAnalysis && (
        <p className={styles.hint}>
          Could not load raw gaze points; showing flagged regions only.
        </p>
      )}

      {regions.length > 0 && (
        <ul className={styles.regionList}>
          {regions.slice(0, 5).map((r) => (
            <li key={r.id ?? `${r.bounds?.left}-${r.bounds?.top}`}>
              <span
                className={`${styles.severity} ${styles[`sev_${r.severity}`] || ''}`}
              >
                {r.severity || 'low'}
              </span>
              <span>
                {r.percentage != null ? `${r.percentage}% of gazes` : '—'}
                {r.isRepeated ? ' · repeated pattern' : ''}
                {r.visits != null ? ` · ${r.visits} samples` : ''}
              </span>
            </li>
          ))}
          {regions.length > 5 && (
            <li className={styles.more}>+{regions.length - 5} more clusters</li>
          )}
        </ul>
      )}
    </div>
  );
}

export default memo(GazeHeatmapPanel);
