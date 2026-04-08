import React from 'react';
import { Scatter } from 'react-chartjs-2';
import { Chart as ChartJS, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import styles from './ProctoringResultModal.module.css';

ChartJS.register(LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const PROCTORING_FEATURES = [
  { key: 'voice_detection', label: 'Voice Activity Detection', icon: '🎤', color: '#8b5cf6' },
  { key: 'object_detection', label: 'Object Detection', icon: '📷', color: '#3b82f6' },
  { key: 'eyeball_tracking', label: 'Eyeball Tracking', icon: '👁️', color: '#10b981' },
  { key: 'gaze_heatmap', label: 'Gaze Cloud Heatmap', icon: '🗺️', color: '#f59e0b' },
];

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:5000";

const ProctoringResultModal = ({ isOpen, onClose, report }) => {
  if (!isOpen || !report) return null;

  const config = report.proctoring_config || {
    voice_detection: true,
    object_detection: true,
    eyeball_tracking: true,
    gaze_heatmap: true,
  };

  const gazeData = report.gaze_metrics || { left_eye: [], right_eye: [] };
  const infractions = report.manual_infractions || [];

  // Backend file paths
  const gazePlotUrl = report.gaze_plot_path ? `${API_URL}/api/view-file?path=${encodeURIComponent(report.gaze_plot_path)}` : null;
  const gazeHeatmapUrl = report.gaze_recorder_analysis_path ? `${API_URL}/api/view-file?path=${encodeURIComponent(report.gaze_recorder_analysis_path)}` : null;

  // Categorize infractions
  const objectInfractions = infractions.filter(i => ['phone_detected', 'multiple_people', 'object_detected'].includes(i.type));
  const voiceInfractions = infractions.filter(i => ['silence_warning', 'voice_anomaly'].includes(i.type));
  const gazeInfractions = infractions.filter(i => !['phone_detected', 'multiple_people', 'object_detected', 'silence_warning', 'voice_anomaly'].includes(i.type));

  const enabledCount = Object.values(config).filter(Boolean).length;

  return (
    <div className={styles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className={styles.modal}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h2>🛡️ Proctoring Report</h2>
            <span className={styles.enabledBadge}>{enabledCount}/4 modules active</span>
          </div>
          <button onClick={onClose} className={styles.closeBtn}>&times;</button>
        </div>
        <div className={styles.modalBody}>
          {report.gaze_proctoring === false ? (
            <div style={{ textAlign: 'center', padding: '2rem 0', color: '#6b7280' }}>
              <h3>Proctoring is off by company</h3>
            </div>
          ) : (
            <>
              <h4>Gaze Plot</h4>
              <Scatter options={options} data={chartData} />
              <hr />
          <h4>Proctoring Summary</h4>
          <p><strong>Proctoring Score:</strong> {report.proctoring_score !== undefined ? `${report.proctoring_score}%` : 'N/A'}</p>
          <p><strong>Manual Infractions:</strong></p>
          <ul>
            {(report.manual_infractions || []).map((infraction, index) => (
              <li key={index}>{infraction.type} at {new Date(infraction.timestamp).toLocaleString()}</li>
            ))}
             {(report.manual_infractions || []).length === 0 && <p>No manual infractions recorded.</p>}
          </ul>
            </>
          )}
        </div>

        {/* Feature Cards */}
        <div className={styles.featuresGrid}>
          {PROCTORING_FEATURES.map(feature => {
            const isEnabled = config[feature.key];

            if (!isEnabled) {
              // Disabled card
              return (
                <div key={feature.key} className={`${styles.featureCard} ${styles.disabledCard}`}>
                  <div className={styles.featureHeader}>
                    <span className={styles.featureIcon}>{feature.icon}</span>
                    <span className={styles.featureLabel}>{feature.label}</span>
                    <span className={styles.disabledBadge}>Disabled</span>
                  </div>
                  <div className={styles.disabledBody}>
                    <span className={styles.lockIcon}>🔒</span>
                    <p>Not enabled by the company for this position</p>
                  </div>
                </div>
              );
            }

            // Enabled cards
            return (
              <div key={feature.key} className={styles.featureCard} style={{ borderTopColor: feature.color }}>
                <div className={styles.featureHeader}>
                  <span className={styles.featureIcon}>{feature.icon}</span>
                  <span className={styles.featureLabel}>{feature.label}</span>
                  <span className={styles.enabledBadgeSmall} style={{ background: feature.color }}>Active</span>
                </div>
                <div className={styles.featureBody}>
                  {/* Voice Detection */}
                  {feature.key === 'voice_detection' && (
                    <>
                      {voiceInfractions.length > 0 ? (
                        <ul className={styles.infractionList}>
                          {voiceInfractions.map((inf, i) => (
                            <li key={i}>
                              <span className={styles.infractionType}>{inf.type.replace(/_/g, ' ')}</span>
                              <span className={styles.infractionTime}>{new Date(inf.timestamp).toLocaleTimeString()}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className={styles.noIssues}>✅ No voice anomalies detected</p>
                      )}
                    </>
                  )}

                  {/* Object Detection */}
                  {feature.key === 'object_detection' && (
                    <>
                      {objectInfractions.length > 0 ? (
                        <ul className={styles.infractionList}>
                          {objectInfractions.map((inf, i) => (
                            <li key={i}>
                              <span className={styles.infractionType}>{inf.type.replace(/_/g, ' ')}</span>
                              <span className={styles.infractionTime}>{new Date(inf.timestamp).toLocaleTimeString()}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className={styles.noIssues}>✅ No prohibited objects detected</p>
                      )}
                    </>
                  )}

                  {/* Eyeball Tracking */}
                  {feature.key === 'eyeball_tracking' && (
                    <>
                      {gazePlotUrl ? (
                        <div className={styles.chartContainer} style={{ background: 'transparent' }}>
                          <img src={gazePlotUrl} alt="Eyeball Gaze Plot" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                        </div>
                      ) : (
                        <p className={styles.noIssues}>✅ Gaze data collected — no anomalies flagged</p>
                      )}
                      {gazeInfractions.length > 0 && (
                        <ul className={styles.infractionList}>
                          {gazeInfractions.slice(0, 5).map((inf, i) => (
                            <li key={i}>
                              <span className={styles.infractionType}>{inf.type.replace(/_/g, ' ')}</span>
                              <span className={styles.infractionTime}>{new Date(inf.timestamp).toLocaleTimeString()}</span>
                            </li>
                          ))}
                          {gazeInfractions.length > 5 && (
                            <li className={styles.moreItems}>+{gazeInfractions.length - 5} more...</li>
                          )}
                        </ul>
                      )}
                    </>
                  )}

                  {/* Gaze Heatmap */}
                  {feature.key === 'gaze_heatmap' && (
                    <>
                      {gazeHeatmapUrl ? (
                        <div className={styles.chartContainer} style={{ background: 'transparent' }}>
                          <img src={gazeHeatmapUrl} alt="Gaze Heatmap Result" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                        </div>
                      ) : (
                        <p className={styles.noIssues}>✅ Heatmap data recorded</p>
                      )}
                      {report.gaze_recorder_score !== undefined && (
                        <div style={{ marginTop: '8px', fontSize: '13px', color: '#e2e8f0' }}>
                          Engagement Score: <strong>{report.gaze_recorder_score}%</strong>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <button onClick={onClose} className={styles.closeButton}>Close Report</button>
        </div>
      </div>
    </div>
  );
};

export default ProctoringResultModal;