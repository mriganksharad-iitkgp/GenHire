import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import usePricingCatalog from 'shared/hooks/usePricingCatalog';
import styles from "./InviteCandidatesModal.module.css";
import {
  previewInvites,
  sendInvites,
  getInviteBatchStatus,
  listInvitedCandidates,
} from "features/recruiter/api/inviteApi";

const BATCH_POLL_INTERVAL_MS = 1500;

const TABS = {
  FILE: "file",
  BULK: "bulk",
};

// Recruiter-chosen access window: both the magic link and the Invite ID +
// password login stop working after this many days (re-inviting refreshes it).
const VALIDITY_OPTIONS = [3, 7, 14, 30];
const DEFAULT_VALIDITY_DAYS = 7;

const formatInviteDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
};

const InviteCandidatesModal = ({ isOpen, onClose, job }) => {
  const {catalog:pricing,error:pricingError,reload:reloadPricing}=usePricingCatalog(isOpen);
  const inviteCost=pricing?.credits?.candidate_invite;
  const [inviteType, setInviteType] = useState("apply");
  const [validityDays, setValidityDays] = useState(DEFAULT_VALIDITY_DAYS);
  const [tab, setTab] = useState(TABS.FILE);

  const [file, setFile] = useState(null);
  const [bulkText, setBulkText] = useState("");

  const [preview, setPreview] = useState(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [copiedLink, setCopiedLink] = useState("");
  const [invited, setInvited] = useState(null); // null = loading, [] = none yet
  const [reinviting, setReinviting] = useState("");
  const pollRef = useRef(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => {
    if (!isOpen) {
      stopPolling();
      setFile(null);
      setBulkText("");
      setPreview(null);
      setError("");
      setResult(null);
      setTab(TABS.FILE);
      setInviteType("apply");
      setValidityDays(DEFAULT_VALIDITY_DAYS);
      setCopiedLink("");
      setInvited(null);
      setReinviting("");
    }
  }, [isOpen]);

  // Stop polling if the component unmounts mid-send.
  useEffect(() => () => stopPolling(), []);

  const jobIdForList = job?._id || job?.id;

  const loadInvited = useCallback(async () => {
    if (!jobIdForList) return;
    try {
      const data = await listInvitedCandidates(jobIdForList);
      setInvited(data.invited || []);
    } catch {
      setInvited([]); // list is informational — never block the modal on it
    }
  }, [jobIdForList]);

  useEffect(() => {
    if (isOpen && jobIdForList) loadInvited();
  }, [isOpen, jobIdForList, loadInvited]);

  const jobTitle = job?.title || "this role";
  const sourceForCurrentTab = useMemo(() => {
    if (tab === TABS.FILE) return file?.name?.toLowerCase().endsWith(".xlsx") ? "xlsx" : "csv";
    if (tab === TABS.SINGLE) return "manual";
    return "bulk";
  }, [tab, file]);

  if (!isOpen || !job) return null;

  const handlePreview = async () => {
    setError("");
    setResult(null);
    setIsPreviewing(true);
    try {
      const payload = {};
      if (tab === TABS.FILE) payload.file = file;
      if (tab === TABS.BULK) payload.text = bulkText;
      const data = await previewInvites(job._id || job.id, payload);
      setPreview(data);
    } catch (e) {
      setError(e.message || "Failed to parse emails");
    } finally {
      setIsPreviewing(false);
    }
  };

  const removeFromPreview = (email) => {
    if (!preview) return;
    setPreview({
      ...preview,
      valid: preview.valid.filter((e) => e !== email),
    });
  };

  // Shared by the normal send flow and per-row re-invites: fire the batch,
  // then poll it for live progress. Refreshes the invited-candidates list
  // once the batch completes.
  const startBatch = async (emails, source) => {
    if(!Number.isInteger(inviteCost)){setError('Load the current invite price before sending. Close and reopen to retry.');return;}
    setError("");
    setIsSending(true);
    const jobId = job._id || job.id;
    try {
      // Sending returns immediately (the batch dispatches emails in the
      // background) rather than blocking until every email is sent — poll
      // the batch status endpoint for live progress instead.
      const started = await sendInvites(jobId, {
        emails,
        invite_type: inviteType,
        source,
        validity_days: validityDays,
      });
      setResult({ ...started, totals: { sent: 0, skipped: 0, failed: 0 } });

      const batchId = started.batch_id;
      pollRef.current = setInterval(async () => {
        try {
          const status = await getInviteBatchStatus(jobId, batchId);
          setResult(status);
          if (status.status === "completed") {
            stopPolling();
            setIsSending(false);
            setReinviting("");
            loadInvited();
          }
        } catch (e) {
          stopPolling();
          setIsSending(false);
          setReinviting("");
          setError(e.message || "Failed to check invite progress");
        }
      }, BATCH_POLL_INTERVAL_MS);
    } catch (e) {
      setIsSending(false);
      setReinviting("");
      if (e?.data?.error_code === "insufficient_credits") {
        setError(
          e.data.error ||
            `Insufficient credits: ${e.data.credits_required} needed, ${e.data.credits_remaining} remaining. Recharge your wallet and try again.`,
        );
      } else {
        setError(e.message || "Failed to send invites");
      }
    }
  };

  const handleSend = async () => {
    if (!preview || preview.valid.length === 0) {
      setError("Add at least one valid email before sending.");
      return;
    }
    await startBatch(preview.valid, sourceForCurrentTab);
  };

  // Re-inviting an already-invited candidate is a normal invite for that one
  // email: the backend refreshes their credentials, magic link, and validity
  // window (and it costs 1 credit again, refunded if the email fails).
  const handleReinvite = async (email) => {
    if (isSending) return;
    setReinviting(email);
    await startBatch([email], "reinvite");
  };

  const canPreview =
    (tab === TABS.FILE && !!file) ||
    (tab === TABS.BULK && bulkText.trim().length > 3);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.headerText}>
            <h2>Invite candidates to {jobTitle}</h2>
            <p>Email prospects to apply or to skip straight to the interview.</p>
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        <div className={styles.body}>
          {error && <div className={styles.errorBanner}>{error}</div>}
          {pricingError && <div role="alert">Current invite pricing is unavailable. <button type="button" onClick={reloadPricing}>Retry invite price</button></div>}
          {result && (
            <div className={styles.successBanner}>
              {result.status === "completed"
                ? "Invite batch complete."
                : `Sending invites… (${(result.totals?.sent || 0) + (result.totals?.skipped || 0) + (result.totals?.failed || 0)}/${result.total || "?"})`}
              &nbsp;
              {result.totals?.sent || 0} sent &middot; {result.totals?.skipped || 0} skipped &middot; {result.totals?.failed || 0} failed.
              {result.credits_charged > 0 && (
                <>
                  &nbsp;{result.credits_charged} credit{result.credits_charged === 1 ? "" : "s"} charged
                  {(result.totals?.skipped || 0) + (result.totals?.failed || 0) > 0 &&
                    ` (${((result.totals?.skipped || 0) + (result.totals?.failed || 0)) * result.credits_per_candidate} refunded for undelivered emails)`}
                  .
                </>
              )}
            </div>
          )}

          <div className={styles.section}>
            <div className={styles.sectionLabel}>Invite type</div>
            <div className={styles.toggle}>
              <button
                type="button"
                className={`${styles.toggleOption} ${inviteType === "apply" ? styles.toggleOptionActive : ""}`}
                onClick={() => setInviteType("apply")}
              >
                <strong>Invite to apply</strong>
                <span>Promotional email; candidate goes through normal review.</span>
              </button>
              <button
                type="button"
                className={`${styles.toggleOption} ${inviteType === "interview" ? styles.toggleOptionActive : ""}`}
                onClick={() => setInviteType("interview")}
              >
                <strong>Invite to interview</strong>
                <span>Pre-shortlisted; candidate skips review and moves to interview.</span>
              </button>
            </div>
          </div>

          <div className={styles.section}>
            <div className={styles.sectionLabel}>Access valid for</div>
            <select
              className={styles.input}
              value={validityDays}
              onChange={(e) => setValidityDays(Number(e.target.value))}
              disabled={isSending || !!result}
              aria-label="Invite access validity in days"
            >
              {VALIDITY_OPTIONS.map((days) => (
                <option key={days} value={days}>
                  {days} days{days === DEFAULT_VALIDITY_DAYS ? " (default)" : ""}
                </option>
              ))}
            </select>
            <div className={styles.helperText}>
              The invite link and login stop working after this window. Re-sending an invite refreshes it.
            </div>
          </div>

          {!result && (
            <>
              <div className={styles.section}>
                <div className={styles.tabs}>
                  <button
                    className={`${styles.tab} ${tab === TABS.FILE ? styles.tabActive : ""}`}
                    onClick={() => setTab(TABS.FILE)}
                  >
                    Upload CSV/XLSX
                  </button>
                  <button
                    className={`${styles.tab} ${tab === TABS.BULK ? styles.tabActive : ""}`}
                    onClick={() => setTab(TABS.BULK)}
                  >
                    Paste Emails
                  </button>
                </div>

                {tab === TABS.FILE && (
                  <label className={`${styles.fileDrop} ${file ? styles.fileDropActive : ""}`}>
                    <input
                      type="file"
                      accept=".csv,.xlsx"
                      style={{ display: "none" }}
                      onChange={(e) => {
                        setFile(e.target.files?.[0] || null);
                        setPreview(null);
                      }}
                    />
                    <div>Click to choose a CSV or XLSX file with an "email" column.</div>
                    {file && <div className={styles.fileName}>{file.name}</div>}
                  </label>
                )}

                {tab === TABS.BULK && (
                  <>
                    <textarea
                      className={styles.textarea}
                      placeholder={"Paste one or more emails separated by space, comma, semicolon, or new line.\nexample1@x.com\nexample2@x.com, example3@x.com"}
                      value={bulkText}
                      onChange={(e) => {
                        setBulkText(e.target.value);
                        setPreview(null);
                      }}
                    />
                    <div className={styles.helperText}>One or many. Duplicates and invalid addresses are auto-detected on preview.</div>
                  </>
                )}
              </div>

              <div className={styles.section}>
                <div className={styles.sectionLabel}>
                  Invited candidates{Array.isArray(invited) ? ` (${invited.length})` : ""}
                </div>
                {invited === null ? (
                  <div className={styles.helperText}>Loading invited candidates…</div>
                ) : invited.length === 0 ? (
                  <div className={styles.helperText}>
                    No candidates have been invited to this job yet.
                  </div>
                ) : (
                  <>
                    <div className={styles.invitedTableWrap}>
                      <table className={styles.invitedTable}>
                        <thead>
                          <tr>
                            <th>Invited Candidate</th>
                            <th>Last Invited</th>
                            <th>Valid Until</th>
                            <th>Status</th>
                            <th aria-label="Actions"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {invited.map((row) => (
                            <tr key={row.invite_id || row.email}>
                              <td className={styles.invitedEmail}>{row.email}</td>
                              <td>{formatInviteDate(row.last_invited_at)}</td>
                              <td>{formatInviteDate(row.valid_until)}</td>
                              <td>
                                <span
                                  className={`${styles.chip} ${
                                    row.access_status === "expired"
                                      ? styles.chipInvalid
                                      : styles.chipValid
                                  }`}
                                >
                                  {row.access_status === "expired" ? "Expired" : "Active"}
                                </span>
                                {row.redeemed && (
                                  <span className={styles.invitedMeta}> link used</span>
                                )}
                              </td>
                              <td>
                                <button
                                  type="button"
                                  className={styles.reinviteBtn}
                                  disabled={isSending}
                                  onClick={() => handleReinvite(row.email)}
                                  title={`Sends a fresh invite email with new credentials and validity. Current cost: ${inviteCost ?? 'unavailable'} credits; failed-email credits follow the refund policy.`}
                                >
                                  {reinviting === row.email ? "Re-inviting…" : "Re-invite"}
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className={styles.helperText}>
                      Re-inviting an already-invited candidate refreshes their credentials,
                      magic link, and validity window — current cost: {inviteCost ?? 'load current price'} credits per invite.
                    </div>
                  </>
                )}
              </div>

              {preview && (
                <div className={styles.section}>
                  <div className={styles.sectionLabel}>Preview</div>
                  {preview.valid.length > 0 && (
                    <div className={styles.helperText}>
                      Sending will deduct <strong>{preview.valid.length} credit{preview.valid.length === 1 ? "" : "s"}</strong> (1
                      per candidate) from your wallet. Credits for invites whose email fails to send are refunded automatically.
                    </div>
                  )}
                  <div className={styles.previewBox}>
                    <div className={styles.previewSummary}>
                      <span className={`${styles.chip} ${styles.chipValid}`}>
                        {preview.valid.length} valid
                      </span>
                      {preview.invalid?.length > 0 && (
                        <span className={`${styles.chip} ${styles.chipInvalid}`}>
                          {preview.invalid.length} invalid
                        </span>
                      )}
                      {preview.duplicates?.length > 0 && (
                        <span className={`${styles.chip} ${styles.chipDuplicate}`}>
                          {preview.duplicates.length} duplicates removed
                        </span>
                      )}
                    </div>
                    {preview.valid.length > 0 ? (
                      <ul className={styles.previewList}>
                        {preview.valid.map((email) => (
                          <li key={email} className={styles.previewItem}>
                            <span>{email}</span>
                            <button
                              className={styles.removeChip}
                              onClick={() => removeFromPreview(email)}
                              aria-label={`Remove ${email}`}
                            >
                              &times;
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className={styles.helperText}>No valid emails parsed yet.</div>
                    )}
                    {preview.invalid?.length > 0 && (
                      <div className={styles.detailsBlock}>
                        <strong>Invalid addresses skipped:</strong>
                        <ul>
                          {preview.invalid.map((e) => (
                            <li key={e}>{e}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {result && (
            <div className={styles.section}>
              <div className={styles.sectionLabel}>Send summary</div>
              <div className={styles.resultGrid}>
                <div className={styles.resultCard}>
                  <div className={styles.resultCardLabel}>Sent</div>
                  <div className={`${styles.resultCardValue} ${styles.resultCardValueSent}`}>
                    {result.totals?.sent || 0}
                  </div>
                </div>
                <div className={styles.resultCard}>
                  <div className={styles.resultCardLabel}>Skipped</div>
                  <div className={`${styles.resultCardValue} ${styles.resultCardValueSkipped}`}>
                    {result.totals?.skipped || 0}
                  </div>
                </div>
                <div className={styles.resultCard}>
                  <div className={styles.resultCardLabel}>Failed</div>
                  <div className={`${styles.resultCardValue} ${styles.resultCardValueFailed}`}>
                    {result.totals?.failed || 0}
                  </div>
                </div>
              </div>
              {(result.skipped?.length || 0) > 0 && (
                <div className={styles.detailsBlock}>
                  <strong>Skipped:</strong>
                  <ul>
                    {result.skipped.map((row, idx) => (
                      <li key={idx}>
                        {row.email} &mdash; {row.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {(result.failed?.length || 0) > 0 && (
                <div className={styles.detailsBlock}>
                  <strong>Failed (email could not be delivered):</strong>
                  <ul>
                    {result.failed.map((row, idx) => (
                      <li key={idx}>
                        {row.email} &mdash; {row.error}
                        {row.invite_url && (
                          <button
                            type="button"
                            className={styles.secondary}
                            style={{ marginLeft: 8, padding: "2px 10px", fontSize: 12 }}
                            onClick={() => {
                              navigator.clipboard
                                .writeText(row.invite_url)
                                .then(() => setCopiedLink(row.invite_url))
                                .catch(() => {});
                            }}
                            title="The invite was created — copy its magic link and share it with the candidate yourself."
                          >
                            {copiedLink === row.invite_url ? "✓ Copied" : "Copy invite link"}
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                  <div className={styles.helperText}>
                    Invites marked failed were still created — copy the link to share it manually.
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className={styles.footer}>
          {!result ? (
            <>
              <button className={styles.secondary} onClick={onClose} disabled={isSending}>
                Cancel
              </button>
              {!preview ? (
                <button
                  className={styles.primary}
                  onClick={handlePreview}
                  disabled={!canPreview || isPreviewing}
                >
                  {isPreviewing ? "Parsing..." : "Preview list"}
                </button>
              ) : (
                <button
                  className={styles.primary}
                  onClick={handleSend}
                  disabled={isSending || preview.valid.length === 0 || !Number.isInteger(inviteCost)}
                  title="The current server price applies per invited candidate; failed-email credits follow the refund policy."
                >
                  {isSending
                    ? "Sending..."
                    : `Send ${preview.valid.length} invite${preview.valid.length === 1 ? "" : "s"} (${Number.isInteger(inviteCost) ? preview.valid.length*inviteCost : 'Load price'} credits)`}
                </button>
              )}
            </>
          ) : (
            <button className={styles.primary} onClick={onClose}>
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default InviteCandidatesModal;
