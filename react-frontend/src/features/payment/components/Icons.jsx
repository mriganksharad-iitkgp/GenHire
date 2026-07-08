/**
 * Payment Icons - Reusable SVG icons for payment components
 */
import React from "react";

const iconProps = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
};

export const ArrowLeftIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M19 12H5M12 19l-7-7 7-7" />
  </svg>
);

export const StarIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M12 2L15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2z" />
  </svg>
);

export const GridIcon = (props) => (
  <svg {...iconProps} {...props}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M3 9h18M9 21V9" />
  </svg>
);

export const ClockIcon = (props) => (
  <svg {...iconProps} {...props}>
    <circle cx="12" cy="12" r="10" />
    <polyline points="12,6 12,12 16,14" />
  </svg>
);

export const AlertCircleIcon = (props) => (
  <svg {...iconProps} {...props}>
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="8" x2="12" y2="12" />
    <line x1="12" y1="16" x2="12.01" y2="16" />
  </svg>
);

export const CheckIcon = (props) => (
  <svg {...iconProps} {...props}>
    <polyline points="20,6 9,17 4,12" />
  </svg>
);

export const XIcon = (props) => (
  <svg {...iconProps} {...props}>
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

export const CalendarIcon = (props) => (
  <svg {...iconProps} {...props}>
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </svg>
);

export const LockIcon = (props) => (
  <svg {...iconProps} {...props}>
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);

export const InfoIcon = (props) => (
  <svg {...iconProps} {...props}>
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="16" x2="12" y2="12" />
    <line x1="12" y1="8" x2="12.01" y2="8" />
  </svg>
);
