import { Navigate } from "react-router-dom";
import { getToken, getUser } from "shared/utils/session";

/**
 * Declarative route guard. Reads the session synchronously (sessionStorage)
 * and reproduces the redirect destinations the pages already used:
 *
 *  - no session                     -> /login
 *  - allow="any", any authenticated -> render (Layout group's behavior)
 *  - allow="admin", non-admin       -> /login (the admin pages' behavior)
 *  - other role mismatch            -> the user's home, matching useAuth():
 *      admin -> /admin, recruiter -> /recruiter-dashboard, else -> /
 *
 * Pages keep their internal checks for now (redundant but harmless); those
 * get removed as each page moves into its feature folder.
 */
export default function ProtectedRoute({ allow = "any", children }) {
  const token = getToken();
  const user = getUser();

  if (!token || !user) {
    return <Navigate to="/login" replace />;
  }

  const userType = user.userType || user.user_type || "candidate";

  if (allow === "any" || userType === allow) {
    return children;
  }

  if (allow === "admin") {
    return <Navigate to="/login" replace />;
  }

  if (userType === "admin") {
    return <Navigate to="/admin" replace />;
  }
  if (userType === "recruiter") {
    return <Navigate to="/recruiter/dashboard" replace />;
  }
  return <Navigate to="/" replace />;
}
