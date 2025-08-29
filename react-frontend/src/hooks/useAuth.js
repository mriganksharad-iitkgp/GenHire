import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

export default function useAuth(requiredType = "recruiter") {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("companyxyz-token");
    const userData = localStorage.getItem("companyxyz-user");
    if (!token || !userData) {
      navigate("/login");
      return;
    }
    try {
      const parsed = JSON.parse(userData);
      if (requiredType && parsed.userType !== requiredType) {
        navigate("/");
        return;
      }
      setUser(parsed);
      localStorage.setItem("recruiterName", parsed.name || "Recruiter");
    } catch (_) {
      navigate("/login");
    }
  }, [navigate, requiredType]);

  const logout = () => {
    localStorage.removeItem("companyxyz-token");
    localStorage.removeItem("companyxyz-user");
    navigate("/login");
  };

  return { user, logout };
}
