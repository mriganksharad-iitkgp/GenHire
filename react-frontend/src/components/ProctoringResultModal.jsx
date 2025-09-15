import React from 'react';
import { Scatter } from 'react-chartjs-2';
import { Chart as ChartJS, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import styles from './JobDetailsModal.module.css'; // Reusing styles for consistency

ChartJS.register(LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const ProctoringResultModal = ({ isOpen, onClose, report }) => {
  if (!isOpen || !report) return null;

  const gazeData = report.gaze_metrics || { left_eye: [], right_eye: [] };

  const chartData = {
    datasets: [
      {
        label: 'Left Eye',
        data: gazeData.left_eye.map(p => ({ x: p[0], y: p[1] })),
        backgroundColor: 'rgba(255, 99, 132, 1)',
      },
      {
        label: 'Right Eye',
        data: gazeData.right_eye.map(p => ({ x: p[0], y: p[1] })),
        backgroundColor: 'rgba(54, 162, 235, 1)',
      },
    ],
  };

  const options = {
    scales: {
      x: {
        type: 'linear',
        position: 'bottom',
        title: {
          display: true,
          text: 'X Coordinate'
        }
      },
      y: {
          title: {
              display: true,
              text: 'Y Coordinate'
          }
      }
    },
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: 'Eyeball Gaze Coordinates',
      },
    },
  };

  return (
    <div className={styles.modalOverlay}>
      <div className={styles.modalContent} style={{width: '600px'}}>
        <div className={styles.modalHeader}>
          <h2>Proctoring Results</h2>
          <button onClick={onClose} className={styles.closeButton}>&times;</button>
        </div>
        <div className={styles.modalBody}>
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
        </div>
        <div className={styles.modalFooter}>
          <button onClick={onClose} className={styles.secondaryButton}>Close</button>
        </div>
      </div>
    </div>
  );
};

export default ProctoringResultModal;