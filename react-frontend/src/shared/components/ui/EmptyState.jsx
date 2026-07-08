import React from 'react';
import styles from './EmptyState.module.css';

const EmptyState = ({
  icon = 'inbox',
  title = 'No items found',
  message = 'There are no items to display at the moment.',
  actionText,
  onAction,
  iconComponent,
  size = 'medium'
}) => {
  return (
    <div className={`${styles.container} ${styles[size]}`}>
      <div className={styles.iconWrapper}>
        {iconComponent ? (
          iconComponent
        ) : (
          <i className={`fa fa-${icon} ${styles.icon}`} aria-hidden="true"></i>
        )}
      </div>
      
      <h3 className={styles.title}>{title}</h3>
      
      {message && (
        <p className={styles.message}>{message}</p>
      )}
      
      {actionText && onAction && (
        <button className={styles.actionButton} onClick={onAction}>
          {actionText}
        </button>
      )}
    </div>
  );
};

// Preset Empty States
export const EmptyJobs = ({ onCreateJob }) => (
  <EmptyState
    icon="briefcase"
    title="No Jobs Posted Yet"
    message="Start by creating your first job posting to attract talented candidates."
    actionText="Create Job"
    onAction={onCreateJob}
  />
);

export const EmptyApplications = () => (
  <EmptyState
    icon="file-text-o"
    title="No Applications Yet"
    message="You haven't applied to any jobs yet. Browse open positions and start applying."
    actionText="Browse Jobs"
    onAction={() => window.location.href = '/dashboard'}
  />
);

export const EmptyPractice = ({ onStartPractice }) => (
  <EmptyState
    icon="microphone"
    title="No Practice Sessions"
    message="Start your first practice interview to improve your skills and build confidence."
    actionText="Start Practice"
    onAction={onStartPractice}
  />
);

export const EmptySearchResults = ({ onClearSearch }) => (
  <EmptyState
    icon="search"
    title="No Results Found"
    message="We couldn't find any matches for your search. Try different keywords or filters."
    actionText="Clear Filters"
    onAction={onClearSearch}
    size="small"
  />
);

export const EmptyNotifications = () => (
  <EmptyState
    icon="bell-o"
    title="No Notifications"
    message="You're all caught up! We'll notify you when there's something new."
    size="small"
  />
);

export const EmptyCVs = ({ onUploadCV }) => (
  <EmptyState
    icon="file-pdf-o"
    title="No CVs Uploaded"
    message="Upload your CV to apply for jobs and start practice interviews."
    actionText="Upload CV"
    onAction={onUploadCV}
  />
);

export default EmptyState;
