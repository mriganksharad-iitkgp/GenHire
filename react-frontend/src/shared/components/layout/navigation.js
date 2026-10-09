export const recruiterTabs = ["overview", "jobs", "candidates", "profile"];
export function recruiterTab(search = "") {
  const tab = new URLSearchParams(search).get("tab");
  return recruiterTabs.includes(tab) ? tab : "overview";
}
export function navigationItems(role, inviteOnly = false) {
  if (role === "recruiter") return [
    { id:"overview", label:"Overview", to:"/recruiter/dashboard?tab=overview" },
    { id:"jobs", label:"Jobs", to:"/recruiter/dashboard?tab=jobs" },
    { id:"candidates", label:"Candidates", to:"/recruiter/dashboard?tab=candidates" },
    { id:"profile", label:"Company profile", to:"/recruiter/dashboard?tab=profile" },
    { id:"cost", label:"Cost statistics", to:"/recruiter/cost-statistics" },
    { id:"team", label:"Team", to:"/recruiter/team" },
  ];
  return [
    { id:"jobs", label:"Open Positions", to:"/dashboard" },
    { id:"applications", label:"My Applications", to:"/applications" },
    { id:"profile", label:"My Profile", to:"/profile" },
    ...(!inviteOnly ? [
      { id:"practice", label:"Practice", to:"/practice" },
      { id:"cost", label:"Cost Statistics", to:"/candidate/cost-statistics" },
      { id:"team", label:"Team", to:"/team" },
    ] : []),
  ];
}
export function navigationActive(item, location) {
  if (item.to.startsWith("/recruiter/dashboard")) return location.pathname === "/recruiter/dashboard" && recruiterTab(location.search) === item.id;
  if (item.id === "applications") return location.pathname === "/applications" || location.pathname.startsWith("/applications/");
  if (item.id === "jobs") return location.pathname === "/dashboard" || location.pathname.startsWith("/jobs/");
  return location.pathname === item.to;
}

// Migrate old applications bookmarks before mounting any profile/CV features.
export function legacyCandidateApplications(location) {
  const params = new URLSearchParams(location.search);
  const section = location.hash.slice(1) || params.get("tab");
  if (location.pathname !== "/profile" || section !== "applications") return null;
  params.delete("tab");
  return `/applications${params.size ? `?${params}` : ""}`;
}
