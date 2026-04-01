export const STANDARD_JOB_ROLES = [
  "Software Engineer",
  "Software Developer",
  "Full Stack Developer",
  "Frontend Developer",
  "Backend Developer",
  "DevOps Engineer",
  "Data Scientist",
  "Data Analyst",
  "Machine Learning Engineer",
  "Product Manager",
  "Business Analyst",
  "UI/UX Designer",
  "Finance Analyst",
];

export const PRACTICE_ROLE_OPTIONS = [
  { id: "software-engineer", name: "Software Engineer", icon: "fa-code" },
  { id: "data-scientist", name: "Data Scientist", icon: "fa-line-chart" },
  { id: "product-manager", name: "Product Manager", icon: "fa-tasks" },
  { id: "business-analyst", name: "Business Analyst", icon: "fa-briefcase" },
  {
    id: "fullstack-developer",
    name: "Full Stack Developer",
    icon: "fa-laptop",
  },
  { id: "devops-engineer", name: "DevOps Engineer", icon: "fa-server" },
  { id: "finance-analyst", name: "Finance Analyst", icon: "fa-money" },
  { id: "custom", name: "Custom (Upload JD)", icon: "fa-upload" },
];

export const INDIA_LOCATION_OPTIONS = [
  "Remote (India)",
  "Bangalore, Karnataka",
  "Mumbai, Maharashtra",
  "Delhi, NCR",
  "Hyderabad, Telangana",
  "Chennai, Tamil Nadu",
  "Pune, Maharashtra",
  "Kolkata, West Bengal",
  "Ahmedabad, Gujarat",
  "Gurgaon, Haryana",
  "Noida, Uttar Pradesh",
  "Kochi, Kerala",
  "Indore, Madhya Pradesh",
  "Jaipur, Rajasthan",
  "Lucknow, Uttar Pradesh",
  "Bhubaneswar, Odisha",
  "Coimbatore, Tamil Nadu",
  "Chandigarh, Punjab",
  "Thiruvananthapuram, Kerala",
  "Nagpur, Maharashtra",
  "Surat, Gujarat",
  "Visakhapatnam, Andhra Pradesh",
  "Hybrid - Bangalore, Karnataka",
  "Hybrid - Mumbai, Maharashtra",
  "Hybrid - Delhi, NCR",
  "Hybrid - Hyderabad, Telangana",
  "Hybrid - Pune, Maharashtra",
  "Hybrid - Chennai, Tamil Nadu",
];

const ROLE_NORMALIZATION_RULES = [
  { regex: /(data\s*scientist|ml\s*scientist)/i, canonical: "Data Scientist" },
  {
    regex: /(data\s*analyst|analytics\s*analyst|bi\s*analyst)/i,
    canonical: "Data Analyst",
  },
  {
    regex: /(machine\s*learning\s*engineer|ml\s*engineer|ai\s*engineer)/i,
    canonical: "Machine Learning Engineer",
  },
  { regex: /(software\s*engineer|swe\b)/i, canonical: "Software Engineer" },
  { regex: /(software\s*developer|sde\b)/i, canonical: "Software Developer" },
  { regex: /(full\s*stack|fullstack)/i, canonical: "Full Stack Developer" },
  { regex: /(front\s*end|frontend)/i, canonical: "Frontend Developer" },
  { regex: /(back\s*end|backend)/i, canonical: "Backend Developer" },
  { regex: /(devops)/i, canonical: "DevOps Engineer" },
  { regex: /(product\s*manager|pm\b)/i, canonical: "Product Manager" },
  { regex: /(business\s*analyst|ba\b)/i, canonical: "Business Analyst" },
  {
    regex: /(ui\/?ux|ux\s*designer|ui\s*designer|product\s*designer)/i,
    canonical: "UI/UX Designer",
  },
  {
    regex: /(finance\s*analyst|financial\s*analyst)/i,
    canonical: "Finance Analyst",
  },
  { regex: /(product\s*developer)/i, canonical: "Product Developer" },
];

export const canonicalizeJobRole = (title) => {
  if (!title) return "";
  const value = String(title).trim();
  if (!value || value.toLowerCase() === "shortlisted") return "";

  const matched = ROLE_NORMALIZATION_RULES.find((rule) =>
    rule.regex.test(value),
  );
  if (matched) return matched.canonical;

  let rawTitle = value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());

  const locationsToStrip = [
    "Remote",
    "Noida",
    "Mumbai",
    "Delhi",
    "Pune",
    "Bangalore",
  ];
  locationsToStrip.forEach((loc) => {
    const regex = new RegExp(`\\b${loc}\\b.*$`, "i");
    rawTitle = rawTitle
      .replace(regex, "")
      .replace(/,\s*Maharashtra/gi, "")
      .replace(/,\s*India/gi, "")
      .trim();
  });

  return rawTitle;
};
