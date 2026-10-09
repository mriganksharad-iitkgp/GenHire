import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { redeemInvite } from "features/recruiter/api/inviteApi";
import { setToken, setUser } from "shared/utils/session";

const containerStyle = {
  minHeight: "100vh",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "var(--portal-backdrop)",
  padding: "32px 16px",
  fontFamily:
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
};

const cardStyle = {
  background: "#ffffff",
  borderRadius: 20,
  width: "100%",
  maxWidth: 460,
  boxShadow: "var(--portal-shadow)",
  padding: 32,
  boxSizing: "border-box",
  textAlign: "center",
};

const headingStyle = {
  margin: 0,
  fontSize: 22,
  color: "#111827",
};

const subStyle = {
  margin: "10px 0 24px",
  fontSize: 14,
  color: "#6b7280",
};

const errorStyle = {
  background: "#fef2f2",
  color: "#991b1b",
  border: "1px solid #fecaca",
  padding: "10px 14px",
  borderRadius: 8,
  fontSize: 13,
  textAlign: "left",
  marginBottom: 16,
};

const primaryBtnStyle = {
  width: "100%",
  padding: "12px 16px",
  background: "var(--portal-gradient)",
  color: "#ffffff",
  border: "none",
  borderRadius: 8,
  fontSize: 15,
  fontWeight: 600,
  cursor: "pointer",
};



const InviteRedeem = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";

  const [error, setError] = useState("");
  const ranOnce = useRef(false);

  useEffect(() => {
    // Strict mode in dev double-fires effects; use a ref to guarantee a single
    // POST so we don't accidentally consume + re-consume the token.
    if (ranOnce.current) return;
    ranOnce.current = true;

    if (!token) {
      setError("This invite link is missing a token.");
      return;
    }

    (async () => {
      try {
        const data = await redeemInvite({ token });
        setToken(data.token);
        setUser({
            ...data.user,
            userType: data.user.user_type,
            isVerified: data.user.is_verified,
            permissions: data.user.permissions || [],
          });
        navigate(data.redirect || "/dashboard", { replace: true });
      } catch (err) {
        setError(
          err.status === 410
            ? "This invite link has expired or already been used. You can still sign in with the Invite ID and password from the email."
            : err.message || "Could not redeem this invite link."
        );
      }
    })();
  }, [token, navigate]);

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <h1 style={headingStyle}>Open your invitation</h1>
        <p style={subStyle}>
          {error ? "Unable to open your invitation." : "Signing you in..."}
        </p>

        {error && (
          <>
            <div style={errorStyle}>{error}</div>
            <button style={primaryBtnStyle} onClick={() => navigate("/login")}>
              Go to login
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default InviteRedeem;
