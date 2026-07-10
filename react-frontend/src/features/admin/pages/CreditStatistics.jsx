import React, { useMemo, useState, useEffect } from 'react';
import AdminLayout from 'features/admin/components/AdminLayout';
import styles from './CostStatistics.module.css';
import {
  getCandidateCreditSummary,
  getCandidateCreditLines,
  getRecruiterCreditSummary,
  getRecruiterCreditLines,
} from 'features/admin/api/adminApi';

// Credits are whole numbers everywhere in GenHire — never money. This page is
// deliberately separate from Cost Statistics (₹) so the two never blur.
const formatCredits = (value) => {
  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) return '0';
  return String(Math.trunc(numericValue));
};

const formatDateInput = (date) => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const CreditStatistics = () => {
  const todayDate = useMemo(() => new Date(), []);
  const defaultStartDate = useMemo(() => {
    const date = new Date();
    date.setDate(date.getDate() - 30);
    return formatDateInput(date);
  }, []);

  const [startDate, setStartDate] = useState(defaultStartDate);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [candidateCreditRows, setCandidateCreditRows] = useState([]);
  const [recruiterCreditRows, setRecruiterCreditRows] = useState([]);
  const [expandedCandidateCredits, setExpandedCandidateCredits] = useState({});
  const [expandedRecruiterCredits, setExpandedRecruiterCredits] = useState({});
  const [candidateCreditLines, setCandidateCreditLines] = useState({});
  const [recruiterCreditLines, setRecruiterCreditLines] = useState({});
  const [candidateCreditLineLoading, setCandidateCreditLineLoading] = useState({});
  const [recruiterCreditLineLoading, setRecruiterCreditLineLoading] = useState({});
  const [candidateCreditLineError, setCandidateCreditLineError] = useState({});
  const [recruiterCreditLineError, setRecruiterCreditLineError] = useState({});

  const endDate = formatDateInput(todayDate);

  useEffect(() => {
    const fetchCreditStats = async () => {
      setLoading(true);
      setError(null);

      try {
        const queryParams = { start_date: startDate, end_date: endDate };
        const [candidateCreditResult, recruiterCreditResult] = await Promise.allSettled([
          getCandidateCreditSummary(queryParams),
          getRecruiterCreditSummary(queryParams),
        ]);

        setCandidateCreditRows(candidateCreditResult.status === 'fulfilled' ? (candidateCreditResult.value?.rows || []) : []);
        setRecruiterCreditRows(recruiterCreditResult.status === 'fulfilled' ? (recruiterCreditResult.value?.rows || []) : []);

        const fetchErrors = [];
        if (candidateCreditResult.status === 'rejected') fetchErrors.push('candidate credits');
        if (recruiterCreditResult.status === 'rejected') fetchErrors.push('recruiter credits');
        if (fetchErrors.length > 0) {
          setError(`${fetchErrors.join(' and ')} data is currently unavailable (backend may need restart/deploy).`);
        }
        setExpandedCandidateCredits({});
        setExpandedRecruiterCredits({});
        setCandidateCreditLines({});
        setRecruiterCreditLines({});
        setCandidateCreditLineLoading({});
        setRecruiterCreditLineLoading({});
        setCandidateCreditLineError({});
        setRecruiterCreditLineError({});
      } catch (fetchError) {
        setError(fetchError.message || 'Failed to fetch admin credit statistics.');
        setCandidateCreditRows([]);
        setRecruiterCreditRows([]);
      } finally {
        setLoading(false);
      }
    };

    fetchCreditStats();
  }, [startDate, endDate]);

  const summaryTotals = useMemo(() => {
    const sum = (rows, field) => rows.reduce((total, row) => total + Number(row?.[field] || 0), 0);
    return {
      candidateBalance: sum(candidateCreditRows, 'current_balance_inr'),
      candidateUsage: sum(candidateCreditRows, 'total_usage_inr'),
      recruiterBalance: sum(recruiterCreditRows, 'current_balance_inr'),
      recruiterUsage: sum(recruiterCreditRows, 'total_usage_inr'),
    };
  }, [candidateCreditRows, recruiterCreditRows]);

  const toggleCandidateCreditExpand = async (candidateId) => {
    const nextExpanded = !expandedCandidateCredits[candidateId];
    setExpandedCandidateCredits((previous) => ({ ...previous, [candidateId]: nextExpanded }));
    if (!nextExpanded || candidateCreditLines[candidateId] || candidateCreditLineLoading[candidateId]) return;

    try {
      setCandidateCreditLineLoading((previous) => ({ ...previous, [candidateId]: true }));
      setCandidateCreditLineError((previous) => ({ ...previous, [candidateId]: null }));
      const response = await getCandidateCreditLines(candidateId, {
        start_date: startDate,
        end_date: endDate,
      });
      setCandidateCreditLines((previous) => ({ ...previous, [candidateId]: response }));
    } catch (lineError) {
      setCandidateCreditLineError((previous) => ({
        ...previous,
        [candidateId]: lineError.message || 'Failed to fetch candidate credit lines.',
      }));
    } finally {
      setCandidateCreditLineLoading((previous) => ({ ...previous, [candidateId]: false }));
    }
  };

  const toggleRecruiterCreditExpand = async (recruiterId) => {
    const nextExpanded = !expandedRecruiterCredits[recruiterId];
    setExpandedRecruiterCredits((previous) => ({ ...previous, [recruiterId]: nextExpanded }));
    if (!nextExpanded || recruiterCreditLines[recruiterId] || recruiterCreditLineLoading[recruiterId]) return;

    try {
      setRecruiterCreditLineLoading((previous) => ({ ...previous, [recruiterId]: true }));
      setRecruiterCreditLineError((previous) => ({ ...previous, [recruiterId]: null }));
      const response = await getRecruiterCreditLines(recruiterId, {
        start_date: startDate,
        end_date: endDate,
      });
      setRecruiterCreditLines((previous) => ({ ...previous, [recruiterId]: response }));
    } catch (lineError) {
      setRecruiterCreditLineError((previous) => ({
        ...previous,
        [recruiterId]: lineError.message || 'Failed to fetch recruiter credit lines.',
      }));
    } finally {
      setRecruiterCreditLineLoading((previous) => ({ ...previous, [recruiterId]: false }));
    }
  };

  const renderCreditCategories = (categories = []) => {
    const deductionCategory = categories.find((category) => category.key === 'deductions');
    const rows = deductionCategory?.lines || [];

    return (
      <div className={styles.usageCategoryCard}>
        <div className={styles.usageCategoryHeader}>
          <strong>Recent Credit Activity</strong>
          <span>Real wallet transactions only. No synthetic or estimated rows.</span>
        </div>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Activity Type</th>
                <th>Credits Deducted</th>
                <th>Remaining Balance</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((line) => (
                <tr key={`credit-${line.id}-${line.timestamp || 'na'}`}>
                  <td>{line.timestamp ? new Date(line.timestamp).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '-'}</td>
                  <td>{line.type}</td>
                  <td>{formatCredits(line.amount_inr)}</td>
                  <td>{formatCredits(line.balance_after)}</td>
                </tr>
              ))}
              {!rows.length && (
                <tr>
                  <td colSpan={4} className={styles.emptyCell}>No credit activity in selected timeline.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <AdminLayout activeTab="credit-statistics">
      <div className={styles.wrapper}>
        <div className={styles.headerBlock}>
          <h1>Admin Credit Statistics</h1>
          <p>Live wallet balances and credit usage for every candidate and recruiter — credits only, no money. Rupee costs and income live on the Cost Statistics page.</p>
        </div>

        <section className={styles.card}>
          <div className={styles.sectionTitleRow}>
            <h2>Timeline</h2>
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
        </section>

        {loading && <div className={styles.status}>Loading credit statistics...</div>}
        {error && <div className={`${styles.status} ${styles.error}`}>{error}</div>}

        {!loading && (
          <>
            <section className={styles.card}>
              <h2>Credit Overview</h2>
              <div className={styles.kpiGrid}>
                <div className={styles.kpiCard}>
                  <h3>Candidate Balances (Total)</h3>
                  <p>{formatCredits(summaryTotals.candidateBalance)} credits</p>
                  <small>Across {candidateCreditRows.length} candidate wallet{candidateCreditRows.length === 1 ? '' : 's'}</small>
                </div>
                <div className={styles.kpiCard}>
                  <h3>Candidate Usage (Timeline)</h3>
                  <p>{formatCredits(summaryTotals.candidateUsage)} credits</p>
                  <small>Practice interviews and proctored practice</small>
                </div>
                <div className={styles.kpiCard}>
                  <h3>Recruiter Balances (Total)</h3>
                  <p>{formatCredits(summaryTotals.recruiterBalance)} credits</p>
                  <small>Across {recruiterCreditRows.length} recruiter wallet{recruiterCreditRows.length === 1 ? '' : 's'}</small>
                </div>
                <div className={styles.kpiCard}>
                  <h3>Recruiter Usage (Timeline)</h3>
                  <p>{formatCredits(summaryTotals.recruiterUsage)} credits</p>
                  <small>Real interviews, proctored interviews, AI JD generation</small>
                </div>
              </div>
            </section>

            <section className={styles.card}>
              <h2>Credit Usage by Candidate</h2>
              <p className={styles.subText}>Per-candidate credit balance, recharge history, and usage for the selected timeline.</p>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Expand</th>
                      <th>Candidate</th>
                      <th>Current Balance</th>
                      <th>Last Recharge Date</th>
                      <th>Last Recharge Plan</th>
                      <th>Total Credit Usage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidateCreditRows.map((row) => (
                      <React.Fragment key={row.candidate_id}>
                        <tr>
                          <td>
                            <button
                              type="button"
                              className={styles.expandBtn}
                              onClick={() => toggleCandidateCreditExpand(row.candidate_id)}
                            >
                              {expandedCandidateCredits[row.candidate_id] ? 'Hide' : 'Show'}
                            </button>
                          </td>
                          <td>
                            <div>{row.name}</div>
                            <small>{row.email}</small>
                          </td>
                          <td>{formatCredits(row.current_balance_inr)}</td>
                          <td>{row.last_recharge_date ? new Date(row.last_recharge_date).toLocaleDateString('en-IN') : '-'}</td>
                          <td>{row.last_recharge_plan || '-'}</td>
                          <td>{formatCredits(row.total_usage_inr)}</td>
                        </tr>
                        {expandedCandidateCredits[row.candidate_id] && (
                          <tr>
                            <td colSpan={6} className={styles.expandPanelCell}>
                              {candidateCreditLineLoading[row.candidate_id] && <div className={styles.inlineStatus}>Loading candidate credit lines...</div>}
                              {candidateCreditLineError[row.candidate_id] && <div className={styles.inlineError}>{candidateCreditLineError[row.candidate_id]}</div>}
                              {!candidateCreditLineLoading[row.candidate_id] && !candidateCreditLineError[row.candidate_id] && renderCreditCategories(candidateCreditLines[row.candidate_id]?.categories || [])}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                    {!candidateCreditRows.length && (
                      <tr>
                        <td colSpan={6} className={styles.emptyCell}>No candidate credit rows for selected timeline.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <section className={styles.card}>
              <h2>Credit Usage by Recruiter</h2>
              <p className={styles.subText}>Per-recruiter credit balance, recharge history, and usage for the selected timeline.</p>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Expand</th>
                      <th>Recruiter</th>
                      <th>Current Balance</th>
                      <th>Last Recharge Date</th>
                      <th>Last Recharge Plan</th>
                      <th>Total Credit Usage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recruiterCreditRows.map((row) => (
                      <React.Fragment key={row.recruiter_id}>
                        <tr>
                          <td>
                            <button
                              type="button"
                              className={styles.expandBtn}
                              onClick={() => toggleRecruiterCreditExpand(row.recruiter_id)}
                            >
                              {expandedRecruiterCredits[row.recruiter_id] ? 'Hide' : 'Show'}
                            </button>
                          </td>
                          <td>
                            <div>{row.name}</div>
                            <small>{row.email}</small>
                          </td>
                          <td>{formatCredits(row.current_balance_inr)}</td>
                          <td>{row.last_recharge_date ? new Date(row.last_recharge_date).toLocaleDateString('en-IN') : '-'}</td>
                          <td>{row.last_recharge_plan || '-'}</td>
                          <td>{formatCredits(row.total_usage_inr)}</td>
                        </tr>
                        {expandedRecruiterCredits[row.recruiter_id] && (
                          <tr>
                            <td colSpan={6} className={styles.expandPanelCell}>
                              {recruiterCreditLineLoading[row.recruiter_id] && <div className={styles.inlineStatus}>Loading recruiter credit lines...</div>}
                              {recruiterCreditLineError[row.recruiter_id] && <div className={styles.inlineError}>{recruiterCreditLineError[row.recruiter_id]}</div>}
                              {!recruiterCreditLineLoading[row.recruiter_id] && !recruiterCreditLineError[row.recruiter_id] && renderCreditCategories(recruiterCreditLines[row.recruiter_id]?.categories || [])}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                    {!recruiterCreditRows.length && (
                      <tr>
                        <td colSpan={6} className={styles.emptyCell}>No recruiter credit rows for selected timeline.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </AdminLayout>
  );
};

export default CreditStatistics;
