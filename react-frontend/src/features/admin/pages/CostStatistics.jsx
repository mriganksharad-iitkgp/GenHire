import React, { useMemo, useState, useEffect } from 'react';
import AdminLayout from 'features/admin/components/AdminLayout';
import styles from './CostStatistics.module.css';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar, Doughnut } from 'react-chartjs-2';
import {
  getCostStatistics,
  getCandidateUsageSummary,
  getCandidateUsageLines,
  getRecruiterUsageSummary,
  getRecruiterUsageLines,
} from 'features/admin/api/adminApi';
import { nowInIST } from 'shared/utils/format';

const formatInrNumber = (value) => `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const formatInrCompact = (value) => {
  const amount = Number(value || 0);
  const absAmount = Math.abs(amount);

  if (absAmount >= 10000000) return `₹${(amount / 10000000).toFixed(2)}Cr`;
  if (absAmount >= 100000) return `₹${(amount / 100000).toFixed(2)}L`;
  if (absAmount >= 1000) return `₹${(amount / 1000).toFixed(2)}K`;
  return `₹${amount.toFixed(2)}`;
};

const truncateTo2Decimals = (value) => {
  const numericValue = Number(value || 0);
  const truncatedValue = Math.trunc(numericValue * 100) / 100;
  return truncatedValue.toFixed(2);
};

const chartValueLabelPlugin = {
  id: 'chartValueLabelPlugin',
  afterDatasetsDraw(chart) {
    const { ctx } = chart;
    const chartType = chart.config.type;

    if (chartType === 'bar') {
      chart.data.datasets.forEach((dataset, datasetIndex) => {
        const meta = chart.getDatasetMeta(datasetIndex);
        if (meta.hidden) return;

        meta.data.forEach((element, dataIndex) => {
          const rawValue = Number(dataset.data[dataIndex] || 0);
          const valueText = formatInrNumber(rawValue);
          const x = element.x;
          const y = rawValue >= 0 ? element.y - 8 : element.y + 16;

          ctx.save();
          ctx.font = '600 11px Inter, system-ui, sans-serif';
          ctx.fillStyle = '#0f172a';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(valueText, x, y);
          ctx.restore();
        });
      });
    }

    if (chartType === 'doughnut') {
      const dataset = chart.data.datasets?.[0];
      if (!dataset) return;
      const meta = chart.getDatasetMeta(0);
      if (meta.hidden) return;

      const values = dataset.data?.map((value) => Number(value || 0)) || [];
      const total = values.reduce((sum, value) => sum + value, 0);
      const chartTop = chart.chartArea?.top ?? 0;
      const chartBottom = chart.chartArea?.bottom ?? chart.height;

      const labelPoints = meta.data.map((arc, index) => {
        const rawValue = values[index] || 0;
        const angle = (arc.startAngle + arc.endAngle) / 2;
        const ratio = total > 0 ? rawValue / total : 0;
        const isTinySlice = ratio > 0 && ratio < 0.06;
        const side = Math.cos(angle) >= 0 ? 'right' : 'left';

        return {
          arc,
          side,
          text: isTinySlice ? formatInrCompact(rawValue) : formatInrNumber(rawValue),
          lineStartX: arc.x + Math.cos(angle) * (arc.outerRadius + 2),
          lineStartY: arc.y + Math.sin(angle) * (arc.outerRadius + 2),
          lineMidX: arc.x + Math.cos(angle) * (arc.outerRadius + 16),
          lineMidY: arc.y + Math.sin(angle) * (arc.outerRadius + 16),
          textX: arc.x + Math.cos(angle) * (arc.outerRadius + (isTinySlice ? 36 : 28)),
          textY: arc.y + Math.sin(angle) * (arc.outerRadius + (isTinySlice ? 26 : 18)),
        };
      });

      ['left', 'right'].forEach((side) => {
        const points = labelPoints
          .filter((point) => point.side === side)
          .sort((first, second) => first.textY - second.textY);

        const minGap = 14;
        for (let index = 1; index < points.length; index += 1) {
          if (points[index].textY - points[index - 1].textY < minGap) {
            points[index].textY = points[index - 1].textY + minGap;
          }
        }

        points.forEach((point) => {
          point.textY = Math.max(chartTop + 10, Math.min(chartBottom - 10, point.textY));
        });
      });

      labelPoints.forEach((point) => {
        const lineEndX = point.side === 'right' ? point.textX - 6 : point.textX + 6;

        ctx.save();
        ctx.strokeStyle = '#64748b';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(point.lineStartX, point.lineStartY);
        ctx.lineTo(point.lineMidX, point.lineMidY);
        ctx.lineTo(lineEndX, point.textY);
        ctx.stroke();

        ctx.font = '600 10px Inter, system-ui, sans-serif';
        ctx.fillStyle = '#0f172a';
        ctx.textAlign = point.side === 'right' ? 'left' : 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(point.text, point.textX, point.textY);
        ctx.restore();
      });
    }
  },
};

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Title, Tooltip, Legend, chartValueLabelPlugin);

const formatDateInput = (date) => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const formatMoney = (value) => formatInrNumber(value);
const formatOptionalMoney = (value) => (
  value === null || value === undefined ? '-' : formatInrNumber(value)
);

const planIncomingPalette = ['#8b5cf6', '#7c3aed', '#0ea5e9', '#0284c7', '#16a34a', '#15803d'];

const toCsvValue = (value) => {
  if (value === null || value === undefined) return '';
  const stringValue = String(value).replace(/"/g, '""');
  return `"${stringValue}"`;
};

const downloadCsv = (filename, rows) => {
  const csvContent = rows.map((row) => row.map((cell) => toCsvValue(cell)).join(',')).join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const CostStatistics = () => {
  // Timeline defaults to the CURRENT MONTH in Indian time (IST).
  const todayDate = useMemo(() => nowInIST(), []);
  const defaultStartDate = useMemo(() => {
    const ist = nowInIST();
    return formatDateInput(new Date(ist.getFullYear(), ist.getMonth(), 1));
  }, []);

  const [startDate, setStartDate] = useState(defaultStartDate);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [costData, setCostData] = useState(null);
  const [candidateUsageRows, setCandidateUsageRows] = useState([]);
  const [recruiterUsageRows, setRecruiterUsageRows] = useState([]);
  const [expandedCandidates, setExpandedCandidates] = useState({});
  const [expandedRecruiters, setExpandedRecruiters] = useState({});
  const [candidateUsageLines, setCandidateUsageLines] = useState({});
  const [recruiterUsageLines, setRecruiterUsageLines] = useState({});
  const [candidateLineLoading, setCandidateLineLoading] = useState({});
  const [recruiterLineLoading, setRecruiterLineLoading] = useState({});
  const [candidateLineError, setCandidateLineError] = useState({});
  const [recruiterLineError, setRecruiterLineError] = useState({});

  const endDate = formatDateInput(todayDate);

  useEffect(() => {
    const fetchCostStats = async () => {
      setLoading(true);
      setError(null);

      try {
        const queryParams = {
          start_date: startDate,
          end_date: endDate,
        };

        const [costStatsResult, candidateUsageResult, recruiterUsageResult] = await Promise.allSettled([
          getCostStatistics(queryParams),
          getCandidateUsageSummary(queryParams),
          getRecruiterUsageSummary(queryParams),
        ]);

        if (costStatsResult.status !== 'fulfilled') {
          throw costStatsResult.reason;
        }

        setCostData(costStatsResult.value);
        setCandidateUsageRows(candidateUsageResult.status === 'fulfilled' ? (candidateUsageResult.value?.rows || []) : []);
        setRecruiterUsageRows(recruiterUsageResult.status === 'fulfilled' ? (recruiterUsageResult.value?.rows || []) : []);

        const usageFetchErrors = [];
        if (candidateUsageResult.status === 'rejected') usageFetchErrors.push('candidate usage');
        if (recruiterUsageResult.status === 'rejected') usageFetchErrors.push('recruiter usage');
        if (usageFetchErrors.length > 0) {
          setError(`Loaded core cost statistics, but ${usageFetchErrors.join(' and ')} data is currently unavailable (backend may need restart/deploy).`);
        }
        setExpandedCandidates({});
        setExpandedRecruiters({});
        setCandidateUsageLines({});
        setRecruiterUsageLines({});
        setCandidateLineLoading({});
        setRecruiterLineLoading({});
        setCandidateLineError({});
        setRecruiterLineError({});
      } catch (fetchError) {
        setError(fetchError.message || 'Failed to fetch admin cost statistics.');
        setCostData(null);
        setCandidateUsageRows([]);
        setRecruiterUsageRows([]);
      } finally {
        setLoading(false);
      }
    };

    fetchCostStats();
  }, [startDate, endDate]);

  const aiCostRows = useMemo(() => costData?.cost_statistics?.ai_costs || [], [costData]);
  const infraCosts = useMemo(() => costData?.cost_statistics?.infrastructure_costs || {}, [costData]);
  const incoming = useMemo(() => costData?.incoming_money || {}, [costData]);
  const profitability = useMemo(() => costData?.profitability || {}, [costData]);
  const costMethodology = useMemo(() => costData?.cost_methodology || [], [costData]);
  const llmPricingReference = useMemo(() => costData?.llm_pricing_reference || null, [costData]);
  const infraPlanReference = useMemo(() => costData?.infra_plan_reference || null, [costData]);

  const overviewBarData = useMemo(() => ({
    labels: ['Total Incoming', 'Net Incoming', 'Total Cost', 'Gross Profit', 'Net Profit'],
    datasets: [
      {
        label: 'INR',
        data: [
          incoming?.total_incoming_inr || 0,
          incoming?.net_incoming_after_refunds_inr || 0,
          costData?.cost_statistics?.total_cost_inr || 0,
          profitability?.profit_gross_inr || 0,
          profitability?.profit_net_inr || 0,
        ],
        backgroundColor: ['#6366f1', '#8b5cf6', '#ef4444', '#22c55e', '#16a34a'],
        borderRadius: 8,
      },
    ],
  }), [incoming, profitability, costData]);

  const aiMixData = useMemo(() => ({
    labels: aiCostRows.map((item) => item.title),
    datasets: [
      {
        data: aiCostRows.map((item) => item.total_cost_inr || 0),
        backgroundColor: ['#6366f1', '#8b5cf6', '#0ea5e9', '#06b6d4', '#10b981', '#f59e0b'],
        borderWidth: 0,
      },
    ],
  }), [aiCostRows]);

  const planIncomingData = useMemo(() => {
    const candidatePlans = incoming?.candidate?.plans || [];
    const recruiterPlans = incoming?.recruiter?.plans || [];

    const matchAmount = (plans, candidateSlugs = [], candidateNames = []) => {
      const row = plans.find((plan) => {
        const slug = String(plan.plan_slug || '').toLowerCase();
        const name = String(plan.plan_name || '').toLowerCase();
        const slugMatched = candidateSlugs.some((value) => slug.includes(value));
        const nameMatched = candidateNames.some((value) => name.includes(value));
        return slugMatched || nameMatched;
      });
      return row?.incoming_amount_inr || 0;
    };

    const candidateProIncoming = matchAmount(candidatePlans, ['candidate-pro'], ['candidate pro']);
    const candidateMaxIncoming = matchAmount(candidatePlans, ['candidate-max'], ['candidate max']);
    const recruiterProIncoming = matchAmount(recruiterPlans, ['professional', 'recruiter-pro'], ['recruiter pro', 'professional']);
    const recruiterMaxIncoming = matchAmount(recruiterPlans, ['recruiter-max'], ['recruiter max']);

    return {
      labels: [
        'Candidate Pro',
        'Candidate Max',
        'Recruiter Pro',
        'Recruiter Max',
        'Candidate Total',
        'Recruiter Total',
      ],
      datasets: [
        {
          label: 'Incoming INR',
          data: [
            candidateProIncoming,
            candidateMaxIncoming,
            recruiterProIncoming,
            recruiterMaxIncoming,
            incoming?.candidate?.total_incoming_inr || 0,
            incoming?.recruiter?.total_incoming_inr || 0,
          ],
          backgroundColor: planIncomingPalette,
          borderRadius: 8,
        },
      ],
    };
  }, [incoming]);

  const sharedBarOptions = {
    responsive: true,
    maintainAspectRatio: false,
    layout: {
      padding: {
        top: 24,
      },
    },
    plugins: {
      legend: { display: false },
    },
    scales: {
      y: {
        beginAtZero: true,
      },
    },
  };

  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    layout: {
      padding: {
        top: 18,
        right: 32,
        bottom: 18,
        left: 32,
      },
    },
    plugins: {
      legend: {
        position: 'bottom',
      },
      tooltip: {
        callbacks: {
          label: (context) => `${context.label}: ${formatInrNumber(context.raw)}`,
        },
      },
    },
  };

  const handleExportCsv = () => {
    if (!costData) return;

    const timeline = costData.timeline || {};
    const rows = [
      ['Section', 'Metric', 'Value', 'Model', 'Count', 'Avg Cost INR', 'Total Cost INR', 'Formula'],
      ['Timeline', 'Start Date', timeline.start_date || '', '', '', '', '', ''],
      ['Timeline', 'End Date', timeline.end_date || '', '', '', '', '', ''],
      ['Timeline', 'Days', timeline.days || 0, '', '', '', '', ''],
    ];

    (costData?.cost_statistics?.ai_costs || []).forEach((item) => {
      rows.push([
        'AI Costs',
        item.title || item.key,
        '',
        item.model || '',
        item.count || 0,
        item.avg_cost_inr || 0,
        item.total_cost_inr || 0,
        item.formula || '',
      ]);
    });

    rows.push(['AI Costs', 'Total AI Cost', '', '', '', '', costData?.cost_statistics?.total_ai_cost_inr || 0, '']);
    Object.entries(infraCosts || {}).forEach(([infraKey, entry]) => {
      if (infraKey === 'total_infrastructure_cost_inr' || !entry || typeof entry !== 'object') return;
      rows.push(['Infrastructure', `${entry.label || infraKey} Monthly`, entry.monthly_assumption_inr || 0, '', '', '', '', '']);
      rows.push(['Infrastructure', `${entry.label || infraKey} Pro-rated`, entry.prorated_cost_inr || 0, '', '', '', '', '']);
      (entry.breakdown || []).forEach((item) => {
        rows.push(['Infrastructure', `  ${entry.label || infraKey} — ${item.label} Monthly`, item.monthly_assumption_inr || 0, '', '', '', '', '']);
      });
    });
    rows.push(['Infrastructure', 'Total Infrastructure Cost', infraCosts?.total_infrastructure_cost_inr || 0, '', '', '', '', '']);

    (incoming?.candidate?.plans || []).forEach((plan) => {
      rows.push([
        'Incoming Candidate',
        plan.plan_name || '',
        plan.incoming_amount_inr || 0,
        '',
        plan.succeeded_payment_count || 0,
        plan.migration_payment_count || 0,
        '',
        'Succeeded payments in selected timeline',
      ]);
    });
    rows.push(['Incoming Candidate', 'Candidate Total Incoming', incoming?.candidate?.total_incoming_inr || 0, '', incoming?.candidate?.succeeded_payment_count || 0, incoming?.candidate?.migration_payment_count || 0, '', '']);

    (incoming?.recruiter?.plans || []).forEach((plan) => {
      rows.push([
        'Incoming Recruiter',
        plan.plan_name || '',
        plan.incoming_amount_inr || 0,
        '',
        plan.succeeded_payment_count || 0,
        plan.migration_payment_count || 0,
        '',
        'Succeeded payments in selected timeline',
      ]);
    });
    rows.push(['Incoming Recruiter', 'Recruiter Total Incoming', incoming?.recruiter?.total_incoming_inr || 0, '', incoming?.recruiter?.succeeded_payment_count || 0, incoming?.recruiter?.migration_payment_count || 0, '', '']);
    rows.push(['Incoming Total', 'Total Incoming', incoming?.total_incoming_inr || 0, '', '', '', '', '']);
    rows.push(['Incoming Total', 'Refunded Total', incoming?.refund_adjustments?.total_refunded_inr || 0, '', incoming?.refund_adjustments?.refund_events_count || 0, '', '', '']);
    rows.push(['Incoming Total', 'Net Incoming After Refunds', incoming?.net_incoming_after_refunds_inr || 0, '', '', '', '', '']);

    rows.push(['Profitability', 'Total Cost', profitability?.cost_total_inr || 0, '', '', '', '', '']);
    rows.push(['Profitability', 'Gross Profit', profitability?.profit_gross_inr || 0, '', '', '', '', '']);
    rows.push(['Profitability', 'Gross Margin %', profitability?.margin_gross_pct || 0, '', '', '', '', '']);
    rows.push(['Profitability', 'Net Profit', profitability?.profit_net_inr || 0, '', '', '', '', '']);
    rows.push(['Profitability', 'Net Margin %', profitability?.margin_net_pct || 0, '', '', '', '', '']);

    candidateUsageRows.forEach((row) => {
      rows.push([
        'Candidate Usage',
        row.name || '',
        row.total_usage_cost_inr || 0,
        row.enrolled_plan || '',
        row.total_actions || 0,
        row.avg_usage_cost_inr || 0,
        '',
        'Practice interview + practice evaluation totals in selected timeline',
      ]);
    });

    recruiterUsageRows.forEach((row) => {
      rows.push([
        'Recruiter Usage',
        row.name || '',
        row.total_usage_cost_inr || 0,
        row.enrolled_plan || '',
        row.total_actions || 0,
        row.avg_usage_cost_inr || 0,
        '',
        'Real interview + eval + AI JD + CV score totals in selected timeline',
      ]);
    });

    const safeStart = String(timeline.start_date || startDate).slice(0, 10);
    const safeEnd = String(timeline.end_date || endDate).slice(0, 10);
    downloadCsv(`admin-cost-statistics-${safeStart}-to-${safeEnd}.csv`, rows);
  };

  const toggleCandidateExpand = async (candidateId) => {
    const nextExpanded = !expandedCandidates[candidateId];
    setExpandedCandidates((previous) => ({ ...previous, [candidateId]: nextExpanded }));
    if (!nextExpanded || candidateUsageLines[candidateId] || candidateLineLoading[candidateId]) return;

    try {
      setCandidateLineLoading((previous) => ({ ...previous, [candidateId]: true }));
      setCandidateLineError((previous) => ({ ...previous, [candidateId]: null }));
      const response = await getCandidateUsageLines(candidateId, {
        start_date: startDate,
        end_date: endDate,
      });
      setCandidateUsageLines((previous) => ({ ...previous, [candidateId]: response }));
    } catch (lineError) {
      setCandidateLineError((previous) => ({
        ...previous,
        [candidateId]: lineError.message || 'Failed to fetch candidate usage lines.',
      }));
    } finally {
      setCandidateLineLoading((previous) => ({ ...previous, [candidateId]: false }));
    }
  };

  const toggleRecruiterExpand = async (recruiterId) => {
    const nextExpanded = !expandedRecruiters[recruiterId];
    setExpandedRecruiters((previous) => ({ ...previous, [recruiterId]: nextExpanded }));
    if (!nextExpanded || recruiterUsageLines[recruiterId] || recruiterLineLoading[recruiterId]) return;

    try {
      setRecruiterLineLoading((previous) => ({ ...previous, [recruiterId]: true }));
      setRecruiterLineError((previous) => ({ ...previous, [recruiterId]: null }));
      const response = await getRecruiterUsageLines(recruiterId, {
        start_date: startDate,
        end_date: endDate,
      });
      setRecruiterUsageLines((previous) => ({ ...previous, [recruiterId]: response }));
    } catch (lineError) {
      setRecruiterLineError((previous) => ({
        ...previous,
        [recruiterId]: lineError.message || 'Failed to fetch recruiter usage lines.',
      }));
    } finally {
      setRecruiterLineLoading((previous) => ({ ...previous, [recruiterId]: false }));
    }
  };

  const renderUsageCategories = (categories = []) => (
    <div className={styles.usageLineWrap}>
      {categories.map((category) => (
        (() => {
          const showSpeechColumns = ['ai_interview', 'practice_interview'].includes(category.key);
          // Face-match similarity (ID card vs interview capture) is scored in
          // the background for real interviews only — advisory, never blocking.
          const showFaceMatch = category.key === 'ai_interview';
          const emptyColSpan = 7 + (showSpeechColumns ? 2 : 0) + (showFaceMatch ? 1 : 0);

          return (
            <div key={category.key} className={styles.usageCategoryCard}>
              <div className={styles.usageCategoryHeader}>
                <strong>{category.title}</strong>
                <span>
                  Count: {category.count} | Calculated Avg: {formatMoney(category.avg_calculated_cost_inr ?? category.avg_cost_inr)} | Calculated Total: {formatMoney(category.total_calculated_cost_inr ?? category.total_cost_inr)} | Actual Avg: {formatOptionalMoney(category.avg_actual_cost_inr)} | Actual Total: {formatOptionalMoney(category.total_actual_cost_inr)}
                </span>
              </div>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Source</th>
                      <th>Model</th>
                      <th>Prompt Tokens</th>
                      <th>Completion Tokens</th>
                      {showSpeechColumns && <th>STT (sec, spoken answers)</th>}
                      {showSpeechColumns && <th>TTS (chars)</th>}
                      {showFaceMatch && <th>Face Match (ID vs capture)</th>}
                      <th>Formula</th>
                      <th>Calculated Cost</th>
                      <th>Actual Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(category.lines || []).map((line) => (
                      <tr key={`${category.key}-${line.id}-${line.timestamp || 'na'}`}>
                        <td>{line.timestamp ? new Date(line.timestamp).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '-'}</td>
                        <td>{line.source?.label || line.source?.type || '-'}</td>
                        <td>{line.model || '-'}</td>
                        <td>{line.prompt_tokens || 0}</td>
                        <td>{line.completion_tokens || 0}</td>
                        {showSpeechColumns && <td>{truncateTo2Decimals(line.stt_seconds)}</td>}
                        {showSpeechColumns && <td>{line.tts_characters || 0}</td>}
                        {showFaceMatch && (
                          <td>{typeof line.face_match_score === 'number' ? `${Math.round(line.face_match_score)}%` : '-'}</td>
                        )}
                        <td>{line.formula}</td>
                        <td>{formatMoney(line.calculated_cost_inr ?? line.cost_inr)}</td>
                        <td>{formatOptionalMoney(line.actual_cost_inr)}</td>
                      </tr>
                    ))}
                    {!category.lines?.length && (
                      <tr>
                        <td colSpan={emptyColSpan + 1} className={styles.emptyCell}>No rows found for this category in selected timeline.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })()
      ))}
    </div>
  );

  return (
    <AdminLayout activeTab="cost-statistics">
      <div className={styles.wrapper}>
        <div className={styles.headerBlock}>
          <h1>Admin Cost Statistics</h1>
          <p>Select a timeline and review complete cost (₹), incoming money, and profitability. Credit balances and usage moved to the separate Credit Statistics page.</p>
        </div>

        <section className={styles.card}>
          <div className={styles.sectionTitleRow}>
            <h2>Timeline</h2>
            <button
              type="button"
              className={styles.exportBtn}
              onClick={handleExportCsv}
              disabled={loading || !costData}
            >
              Export CSV
            </button>
          </div>
          <div className={styles.timelineGrid}>
            <label className={styles.field}>
              <span>From Date</span>
              <input
                type="date"
                value={startDate}
                max={endDate}
                onChange={(event) => setStartDate(event.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>To Date (Present)</span>
              <input type="date" value={endDate} disabled />
            </label>
          </div>
          {costData?.timeline && (
            <div className={styles.timelineMeta}>
              <span>Applied Range: {new Date(costData.timeline.start_date).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })} - {new Date(costData.timeline.end_date).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })}</span>
              <span>Days: {costData.timeline.days}</span>
            </div>
          )}
        </section>

        {loading && <div className={styles.status}>Loading cost statistics...</div>}
        {error && <div className={`${styles.status} ${styles.error}`}>{error}</div>}

        {!loading && !error && (
          <>
            <section className={styles.card}>
              <h2>Visual Overview</h2>
              <p className={styles.subText}>Quick visual insight for cost, incoming, AI mix, and top plans in selected timeline.</p>
              <div className={styles.vizGrid}>
                <div className={styles.chartCard}>
                  <h3>Incoming vs Cost vs Profit</h3>
                  <div className={styles.chartWrap}>
                    <Bar data={overviewBarData} options={sharedBarOptions} />
                  </div>
                </div>
                <div className={styles.chartCard}>
                  <h3>AI Cost Share</h3>
                  <div className={`${styles.chartWrap} ${styles.doughnutWrap}`}>
                    <Doughnut data={aiMixData} options={doughnutOptions} />
                  </div>
                </div>
                <div className={`${styles.chartCard} ${styles.fullWidthChart}`}>
                  <h3>Plan-Wise Incoming (Candidate + Recruiter)</h3>
                  <div className={styles.chartWrap}>
                    <Bar data={planIncomingData} options={sharedBarOptions} />
                  </div>
                  <div className={styles.planLegend}>
                    {planIncomingData.labels.map((label, index) => (
                      <div key={label} className={styles.planLegendItem}>
                        <span
                          className={styles.planLegendDot}
                          style={{ backgroundColor: planIncomingPalette[index] || '#94a3b8' }}
                        />
                        <span>{label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </section>

            <section className={styles.card}>
              <h2>AI Cost Lines</h2>
              <p className={styles.subText}>Each line includes count, model, average cost, and total cost for selected timeline.</p>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Cost Category</th>
                      <th>Model</th>
                      <th>Count</th>
                      <th>Avg Cost</th>
                      <th>Total Cost</th>
                      <th>Formula</th>
                    </tr>
                  </thead>
                  <tbody>
                    {aiCostRows.map((row) => (
                      <tr key={row.key}>
                        <td>{row.title}</td>
                        <td>{row.model}</td>
                        <td>{row.count}</td>
                        <td>{formatMoney(row.avg_cost_inr)}</td>
                        <td>{formatMoney(row.total_cost_inr)}</td>
                        <td>{row.formula}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className={styles.totalLine}>Total AI Cost: <strong>{formatMoney(costData?.cost_statistics?.total_ai_cost_inr)}</strong></div>
            </section>

            {costMethodology.length > 0 && (
              <section className={styles.card}>
                <h2>How These Numbers Are Calculated</h2>
                <p className={styles.subText}>Plain-English methodology for each cost category above, so every figure on this page is traceable to a formula.</p>
                <div className={styles.methodologyList}>
                  {costMethodology.map((item) => (
                    <div key={item.key} className={styles.methodologyItem}>
                      <h3>{item.title}</h3>
                      <p>{item.explanation}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {llmPricingReference && (
              <section className={styles.card}>
                <h2>AI Model & Speech Pricing Reference</h2>
                <p className={styles.subText}>
                  Live provider fallback chain (<code>{llmPricingReference.chain_env_var}</code>) and the official per-1M-token rates used to price every AI cost line above.
                </p>
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Provider</th>
                        <th>Model</th>
                        <th>Role in chain</th>
                        <th>Input $/1M tokens</th>
                        <th>Output $/1M tokens</th>
                        <th>Tier notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {llmPricingReference.providers.map((provider) => (
                        <tr key={provider.provider}>
                          <td>{provider.provider}</td>
                          <td>{provider.model}</td>
                          <td>{provider.role}</td>
                          <td>${provider.input_usd_per_1m_tokens.toFixed(3)}</td>
                          <td>${provider.output_usd_per_1m_tokens.toFixed(3)}</td>
                          <td>{provider.tier_note}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className={styles.subText}>{llmPricingReference.note}</p>

                <h3 className={styles.subsectionTitle}>Face Match (Identity Verification) Vision Models</h3>
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr><th>Provider</th><th>Model</th></tr>
                    </thead>
                    <tbody>
                      {llmPricingReference.face_match_vision_models.map((model) => (
                        <tr key={model.provider}>
                          <td>{model.provider}</td>
                          <td>{model.model}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <h3 className={styles.subsectionTitle}>Speech Pricing (Google Cloud)</h3>
                <div className={styles.kpiGrid}>
                  <div className={styles.kpiCard}>
                    <h3>Speech-to-Text</h3>
                    <p>${llmPricingReference.speech.stt.usd_per_minute_equivalent.toFixed(3)}/min</p>
                    <small>{llmPricingReference.speech.stt.billing_unit} — ${llmPricingReference.speech.stt.usd_per_unit}/unit</small>
                  </div>
                  <div className={styles.kpiCard}>
                    <h3>Text-to-Speech (Standard)</h3>
                    <p>${llmPricingReference.speech.tts_standard.usd_per_1m_chars_equivalent.toFixed(2)}/1M chars</p>
                    <small>{llmPricingReference.speech.tts_standard.billing_unit}</small>
                  </div>
                  <div className={styles.kpiCard}>
                    <h3>Text-to-Speech (Neural2)</h3>
                    <p>${llmPricingReference.speech.tts_neural.usd_per_1m_chars_equivalent.toFixed(2)}/1M chars</p>
                    <small>{llmPricingReference.speech.tts_neural.billing_unit}</small>
                  </div>
                </div>
              </section>
            )}

            <section className={styles.card}>
              <h2>Infrastructure & Provider Cost</h2>
              <p className={styles.subText}>
                GCP and OpenAI show <strong>actual fetched spend</strong> for the selected timeline when their billing integrations are configured (each card shows its source); other providers use env-entered monthly figures pro-rated over the timeline. See <code>docs/costfetch.md</code> for setup.
              </p>
              <div className={styles.kpiGrid}>
                {['gcp', 'vercel', 'mongodb', 'zeptomail', 'openai', 'gemini', 'groq', 'cloudflare'].map((infraKey) => {
                  const entry = infraCosts?.[infraKey];
                  if (!entry) return null;
                  const isActual = entry.usage_source && entry.usage_source !== 'env_placeholder';
                  return (
                    <div key={infraKey} className={styles.kpiCard}>
                      <h3>{entry.label || infraKey.toUpperCase()} (Monthly)</h3>
                      <p>{formatMoney(entry.monthly_assumption_inr)}</p>
                      <small>
                        {isActual ? 'Actual (timeline): ' : 'Pro-rated: '}
                        {formatMoney(entry.prorated_cost_inr)}
                      </small>
                      {entry.usage_source && (
                        <small className={isActual ? styles.sourceActual : styles.sourcePlaceholder}>
                          Source: {entry.usage_source === 'billing_export'
                            ? 'GCP Billing export (actual)'
                            : entry.usage_source === 'costs_api'
                              ? 'OpenAI Costs API (actual)'
                              : 'env placeholder'}
                        </small>
                      )}
                      {entry.outstanding_current_month_inr !== undefined && (
                        <small>
                          Outstanding (month {entry.outstanding_invoice_month}): {formatMoney(entry.outstanding_current_month_inr)}
                        </small>
                      )}
                      {entry.credit_balance_inr !== undefined && (
                        <small>
                          Credit balance: {formatMoney(entry.credit_balance_inr)} (${entry.credit_balance_usd}) — manually mirrored
                        </small>
                      )}
                      {entry.pricing_note && <small>{entry.pricing_note}</small>}
                      {(entry.breakdown || []).map((item) => (
                        <small key={item.key}>
                          {item.label}: {formatMoney(item.prorated_cost_inr)}
                        </small>
                      ))}
                    </div>
                  );
                })}
                <div className={styles.kpiCard}>
                  <h3>Total Infrastructure Cost</h3>
                  <p>{formatMoney(infraCosts?.total_infrastructure_cost_inr)}</p>
                  <small>All entries above, for the selected timeline</small>
                </div>
              </div>
            </section>

            {infraPlanReference && (
              <section className={styles.card}>
                <h2>Provider Plans & Free-Tier Benefits</h2>
                <p className={styles.subText}>What each infrastructure provider plan includes — context for why the monthly figures above are what they are.</p>
                <div className={styles.vizGrid}>
                  <div className={styles.chartCard}>
                    <h3>Vercel — {infraPlanReference.vercel.plan} (${infraPlanReference.vercel.monthly_price_usd}/mo)</h3>
                    <ul className={styles.benefitsList}>
                      {infraPlanReference.vercel.benefits.map((benefit) => <li key={benefit}>{benefit}</li>)}
                    </ul>
                  </div>
                  {infraPlanReference.zeptomail && (
                    <div className={styles.chartCard}>
                      <h3>ZeptoMail — {infraPlanReference.zeptomail.plan} (₹{infraPlanReference.zeptomail.assumed_monthly_cost_inr}/mo assumed)</h3>
                      <ul className={styles.benefitsList}>
                        {infraPlanReference.zeptomail.benefits.map((benefit) => <li key={benefit}>{benefit}</li>)}
                      </ul>
                    </div>
                  )}
                  <div className={styles.chartCard}>
                    <h3>GCP — Project {infraPlanReference.gcp.project}</h3>
                    <p className={styles.subText}>{infraPlanReference.gcp.billing_console_note}</p>
                    <div className={styles.tableWrap}>
                      <table className={styles.table}>
                        <thead>
                          <tr><th>Service</th><th>What it's for</th><th>Free tier</th></tr>
                        </thead>
                        <tbody>
                          {infraPlanReference.gcp.services_billed.map((service) => (
                            <tr key={service.service}>
                              <td>{service.service}</td>
                              <td>{service.what_for}</td>
                              <td>{service.free_tier}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </section>
            )}

            <section className={styles.card}>
              <h2>Incoming Money - Candidates</h2>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Plan</th>
                      <th>Plan Price</th>
                      <th>Succeeded Payments</th>
                      <th>Migration Payments</th>
                      <th>Incoming Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(incoming?.candidate?.plans || []).map((plan) => (
                      <tr key={`${plan.plan_slug}-${plan.plan_price_inr}`}>
                        <td>{plan.plan_name}</td>
                        <td>{formatMoney(plan.plan_price_inr)}</td>
                        <td>{plan.succeeded_payment_count}</td>
                        <td>{plan.migration_payment_count || 0}</td>
                        <td>{formatMoney(plan.incoming_amount_inr)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className={styles.totalLine}>
                Candidate Incoming Total: <strong>{formatMoney(incoming?.candidate?.total_incoming_inr)}</strong>
                <span className={styles.totalMeta}>Migration payments: {incoming?.candidate?.migration_payment_count || 0}</span>
              </div>
            </section>

            <section className={styles.card}>
              <h2>Incoming Money - Recruiters</h2>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Plan</th>
                      <th>Plan Price</th>
                      <th>Succeeded Payments</th>
                      <th>Migration Payments</th>
                      <th>Incoming Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(incoming?.recruiter?.plans || []).map((plan) => (
                      <tr key={`${plan.plan_slug}-${plan.plan_price_inr}`}>
                        <td>{plan.plan_name}</td>
                        <td>{formatMoney(plan.plan_price_inr)}</td>
                        <td>{plan.succeeded_payment_count}</td>
                        <td>{plan.migration_payment_count || 0}</td>
                        <td>{formatMoney(plan.incoming_amount_inr)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className={styles.totalLine}>
                Recruiter Incoming Total: <strong>{formatMoney(incoming?.recruiter?.total_incoming_inr)}</strong>
                <span className={styles.totalMeta}>Migration payments: {incoming?.recruiter?.migration_payment_count || 0}</span>
              </div>
            </section>

            <section className={styles.card}>
              <h2>Actual Usage by Candidate</h2>
              <p className={styles.subText}>Per-candidate practice interview usage with count, average, total, and row-level transparency. STT seconds come from real measured audio when logged, otherwise derived from the candidate's spoken answers (never wall-clock time); TTS uses spoken-question characters.</p>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Expand</th>
                      <th>Candidate</th>
                      <th>Practice Interview Count</th>
                      <th>Practice Interview Avg</th>
                      <th>Practice Interview Total</th>
                      <th>Practice Interview Eval Count</th>
                      <th>Practice Interview Eval Avg</th>
                      <th>Practice Interview Eval Total</th>
                      <th>Calculated Cost</th>
                      <th>Actual Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidateUsageRows.map((row) => (
                      <React.Fragment key={row.candidate_id}>
                        <tr>
                          <td>
                            <button
                              type="button"
                              className={styles.expandBtn}
                              onClick={() => toggleCandidateExpand(row.candidate_id)}
                            >
                              {expandedCandidates[row.candidate_id] ? 'Hide' : 'Show'}
                            </button>
                          </td>
                          <td>
                            <div>{row.name}</div>
                            <small>{row.email}</small>
                          </td>
                          <td>{row.practice_interview_count}</td>
                          <td>{formatMoney(row.practice_interview_avg_cost_inr)}</td>
                          <td>{formatMoney(row.practice_interview_total_cost_inr)}</td>
                          <td>{row.practice_interview_evaluation_count}</td>
                          <td>{formatMoney(row.practice_interview_evaluation_avg_cost_inr)}</td>
                          <td>{formatMoney(row.practice_interview_evaluation_total_cost_inr)}</td>
                          <td>{formatMoney(row.total_usage_cost_inr)}</td>
                          <td>{formatOptionalMoney(row.total_actual_usage_cost_inr)}</td>
                        </tr>
                        {expandedCandidates[row.candidate_id] && (
                          <tr>
                            <td colSpan={10} className={styles.expandPanelCell}>
                              {candidateLineLoading[row.candidate_id] && <div className={styles.inlineStatus}>Loading candidate rows...</div>}
                              {candidateLineError[row.candidate_id] && <div className={styles.inlineError}>{candidateLineError[row.candidate_id]}</div>}
                              {!candidateLineLoading[row.candidate_id] && !candidateLineError[row.candidate_id] && renderUsageCategories(candidateUsageLines[row.candidate_id]?.categories || [])}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                    {!candidateUsageRows.length && (
                      <tr>
                        <td colSpan={10} className={styles.emptyCell}>No candidate usage rows for selected timeline.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <section className={styles.card}>
              <h2>Actual Usage by Recruiter</h2>
              <p className={styles.subText}>Per-recruiter real interview, evaluation, CV scoring, and AI JD generation usage with row-level transparency.</p>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Expand</th>
                      <th>Recruiter</th>
                      <th>Real Interview Count</th>
                      <th>Real Interview Avg</th>
                      <th>Real Interview Total</th>
                      <th>Real Eval Count</th>
                      <th>Real Eval Avg</th>
                      <th>Real Eval Total</th>
                      <th>AI JD Count</th>
                      <th>AI JD Avg</th>
                      <th>AI JD Total</th>
                      <th>CV Score Count</th>
                      <th>CV Score Avg</th>
                      <th>CV Score Total</th>
                      <th>Calculated Cost</th>
                      <th>Actual Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recruiterUsageRows.map((row) => (
                      <React.Fragment key={row.recruiter_id}>
                        <tr>
                          <td>
                            <button
                              type="button"
                              className={styles.expandBtn}
                              onClick={() => toggleRecruiterExpand(row.recruiter_id)}
                            >
                              {expandedRecruiters[row.recruiter_id] ? 'Hide' : 'Show'}
                            </button>
                          </td>
                          <td>
                            <div>{row.name}</div>
                            <small>{row.email}</small>
                          </td>
                          <td>{row.real_interview_count}</td>
                          <td>{formatMoney(row.real_interview_avg_cost_inr)}</td>
                          <td>{formatMoney(row.real_interview_total_cost_inr)}</td>
                          <td>{row.real_interview_evaluation_count}</td>
                          <td>{formatMoney(row.real_interview_evaluation_avg_cost_inr)}</td>
                          <td>{formatMoney(row.real_interview_evaluation_total_cost_inr)}</td>
                          <td>{row.ai_jd_generation_count}</td>
                          <td>{formatMoney(row.ai_jd_generation_avg_cost_inr)}</td>
                          <td>{formatMoney(row.ai_jd_generation_total_cost_inr)}</td>
                          <td>{row.cv_score_count}</td>
                          <td>{formatMoney(row.cv_score_avg_cost_inr)}</td>
                          <td>{formatMoney(row.cv_score_total_cost_inr)}</td>
                          <td>{formatMoney(row.total_usage_cost_inr)}</td>
                          <td>{formatOptionalMoney(row.total_actual_usage_cost_inr)}</td>
                        </tr>
                        {expandedRecruiters[row.recruiter_id] && (
                          <tr>
                            <td colSpan={16} className={styles.expandPanelCell}>
                              {recruiterLineLoading[row.recruiter_id] && <div className={styles.inlineStatus}>Loading recruiter rows...</div>}
                              {recruiterLineError[row.recruiter_id] && <div className={styles.inlineError}>{recruiterLineError[row.recruiter_id]}</div>}
                              {!recruiterLineLoading[row.recruiter_id] && !recruiterLineError[row.recruiter_id] && renderUsageCategories(recruiterUsageLines[row.recruiter_id]?.categories || [])}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                    {!recruiterUsageRows.length && (
                      <tr>
                        <td colSpan={16} className={styles.emptyCell}>No recruiter usage rows for selected timeline.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <section className={styles.card}>
              <h2>Net Incoming & Profitability</h2>
              <div className={styles.kpiGrid}>
                <div className={styles.kpiCard}>
                  <h3>Total Incoming</h3>
                  <p>{formatMoney(incoming?.total_incoming_inr)}</p>
                  <small>Candidate + Recruiter succeeded payments</small>
                </div>
                <div className={styles.kpiCard}>
                  <h3>Refund Adjustments</h3>
                  <p>{formatMoney(incoming?.refund_adjustments?.total_refunded_inr)}</p>
                  <small>Refund events: {incoming?.refund_adjustments?.refund_events_count || 0}</small>
                </div>
                <div className={styles.kpiCard}>
                  <h3>Net Incoming (After Refunds)</h3>
                  <p>{formatMoney(incoming?.net_incoming_after_refunds_inr)}</p>
                  <small>Gross incoming - refunds</small>
                </div>
                <div className={styles.kpiCard}>
                  <h3>Total Cost (AI + Infra)</h3>
                  <p>{formatMoney(costData?.cost_statistics?.total_cost_inr)}</p>
                  <small>Selected timeline total cost</small>
                </div>
                <div className={styles.kpiCard}>
                  <h3>Profit (Gross)</h3>
                  <p className={profitability?.profit_gross_inr >= 0 ? styles.positive : styles.negative}>{formatMoney(profitability?.profit_gross_inr)}</p>
                  <small>Margin: {profitability?.margin_gross_pct || 0}%</small>
                </div>
                <div className={styles.kpiCard}>
                  <h3>Profit (Net)</h3>
                  <p className={profitability?.profit_net_inr >= 0 ? styles.positive : styles.negative}>{formatMoney(profitability?.profit_net_inr)}</p>
                  <small>Margin: {profitability?.margin_net_pct || 0}%</small>
                </div>
              </div>
            </section>

          </>
        )}
      </div>
    </AdminLayout>
  );
};

export default CostStatistics;
