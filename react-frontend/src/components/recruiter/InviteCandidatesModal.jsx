import React, { useEffect, useMemo, useState } from "react";
import styles from "./InviteCandidatesModal.module.css";
import { previewInvites, sendInvites } from "../../services/inviteApi";

const TABS = {
  FILE: "file",
  BULK: "bulk",
};

const InviteCandidatesModal = ({ isOpen, onClose, job }) => {
  const [inviteType, setInviteType] = useState("apply");
  const [tab, setTab] = useState(TABS.FILE);

  const [file, setFile] = useState(null);
  const [bulkText, setBulkText] = useState("");

  const [preview, setPreview] = useState(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!isOpen) {
      setFile(null);
      setBulkText("");
      setPreview(null);
      setError("");
      setResult(null);
      setTab(TABS.FILE);
      setInviteType("apply");
    }
  }, [isOpen]);

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

  const handleSend = async () => {
    if (!preview || preview.valid.length === 0) {
      setError("Add at least one valid email before sending.");
      return;
    }
    setError("");
    setIsSending(true);
    try {
      const data = await sendInvites(job._id || job.id, {
        emails: preview.valid,
        invite_type: inviteType,
        source: sourceForCurrentTab,
      });
      setResult(data);
    } catch (e) {
      setError(e.message || "Failed to send invites");
    } finally {
      setIsSending(false);
    }
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
          {result && (
            <div className={styles.successBanner}>
              Invite batch processed.&nbsp;
              {result.totals?.sent || 0} sent &middot; {result.totals?.skipped || 0} skipped &middot; {result.totals?.failed || 0} failed.
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

              {preview && (
                <div className={styles.section}>
                  <div className={styles.sectionLabel}>Preview</div>
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
                  <strong>Failed:</strong>
                  <ul>
                    {result.failed.map((row, idx) => (
                      <li key={idx}>
                        {row.email} &mdash; {row.error}
                      </li>
                    ))}
                  </ul>
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
                  disabled={isSending || preview.valid.length === 0}
                >
                  {isSending ? "Sending..." : `Send ${preview.valid.length} invite${preview.valid.length === 1 ? "" : "s"}`}
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
