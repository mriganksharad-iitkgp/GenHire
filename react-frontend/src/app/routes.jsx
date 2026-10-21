import React, { Suspense } from "react";
import { Routes, Route, Navigate, useLocation, useParams } from "react-router-dom";

import { legacyCandidateApplications } from "shared/components/layout/navigation";
import Layout from "shared/components/layout/Layout";
import ProtectedRoute from "app/ProtectedRoute";
import { AdminLayoutOutlet } from "features/admin/components/AdminLayout";
// Preserves params + query string when redirecting a legacy path to its
// renamed successor (old links in emails/bookmarks keep working).
function LegacyRedirect({ to }) {
  const params = useParams();
  const location = useLocation();
  let path = to;
  Object.entries(params).forEach(([key, value]) => {
    path = path.replace(`:${key}`, value);
  });
  return <Navigate to={`${path}${location.search}`} replace />;
}


// Lazy-loaded pages (paths update as pages move into features/)
const Login = React.lazy(() => import("features/auth/pages/Login"));
const Profile = React.lazy(() => import("features/candidate/pages/Profile"));
const Applications = React.lazy(() => import("features/candidate/pages/Applications"));
function CandidateProfileRoute() {
  const location = useLocation();
  const destination = legacyCandidateApplications(location);
  return destination ? <Navigate to={destination} replace /> : <Profile />;
}
const Dashboard = React.lazy(() => import("features/candidate/pages/Dashboard"));
const Interview = React.lazy(() => import("features/interview/pages/Interview"));
const Assessment = React.lazy(() => import("features/assessment/pages/Assessment"));
const AssessmentCompanion = React.lazy(() => import("features/assessment/pages/AssessmentCompanion"));
const JobDetails = React.lazy(() => import("features/candidate/pages/JobDetails"));
const Register = React.lazy(() => import("features/auth/pages/Register"));
const RecruiterOnboarding = React.lazy(() => import("features/auth/pages/RecruiterOnboarding"));
const RecruiterDashboard = React.lazy(() => import("features/recruiter/pages/RecruiterDashboard"));
const SubscriptionPlans = React.lazy(() => import("features/payment/pages/SubscriptionPlans"));
const NotFound = React.lazy(() => import("app/NotFound"));
const ApplicationView = React.lazy(() => import("features/candidate/pages/ApplicationView"));
const VerifyEmail = React.lazy(() => import("features/auth/pages/VerifyEmail"));
const ForgotPassword = React.lazy(() => import("features/auth/pages/ForgotPassword"));
const ResetPassword = React.lazy(() => import("features/auth/pages/ResetPassword"));
const InviteRedeem = React.lazy(() => import("features/auth/pages/InviteRedeem"));
const Practice = React.lazy(() => import("features/candidate/pages/Practice"));
const MobileRecorder = React.lazy(() => import("features/interview/pages/MobileRecorder"));
const PaymentSuccess = React.lazy(() => import("features/payment/pages/PaymentSuccess"));
const PaymentCancel = React.lazy(() => import("features/payment/pages/PaymentCancel"));
const CandidateSubscriptionPlans = React.lazy(() => import("features/payment/pages/CandidateSubscriptionPlans"));
const CandidateCostStatistics = React.lazy(() => import("features/candidate/pages/CandidateCostStatistics"));
const TeamPage = React.lazy(() => import("features/recruiter/pages/TeamPage"));

// Admin pages
const AdminOverview = React.lazy(() => import("features/admin/pages/AdminOverview"));
const ManageCandidates = React.lazy(() => import("features/admin/pages/ManageCandidates"));
const ManageRecruiters = React.lazy(() => import("features/admin/pages/ManageRecruiters"));
const ManageAdmins = React.lazy(() => import("features/admin/pages/ManageAdmins"));
const CandidateDetail = React.lazy(() => import("features/admin/pages/CandidateDetail"));
const RecruiterDetail = React.lazy(() => import("features/admin/pages/RecruiterDetail"));
const Verification = React.lazy(() => import("features/admin/pages/Verification"));
const CostStatistics = React.lazy(() => import("features/admin/pages/CostStatistics"));
const CreditStatistics = React.lazy(() => import("features/admin/pages/CreditStatistics"));

// Recruiter pages
const RecruiterCostStatistics = React.lazy(() => import("features/recruiter/pages/RecruiterCostStatistics"));
const RecruiterTeam = React.lazy(() => import("features/recruiter/pages/RecruiterTeam"));

// Landing page
const LandingPage = React.lazy(() => import("features/landing/pages/LandingPage"));

const admin = (page) => <ProtectedRoute allow="admin">{page}</ProtectedRoute>;

export default function AppRoutes() {
  return (
    <Suspense
      fallback={
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', width: '100vw' }}>
          Loading application...
        </div>
      }
    >
      <Routes>
        {/* Public / auth pages */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/recruiter-signup" element={<RecruiterOnboarding />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/invite/redeem" element={<InviteRedeem />} />

        {/* Recruiter */}
        <Route
          path="/recruiter/dashboard"
          element={
            <ProtectedRoute allow="recruiter">
              <RecruiterDashboard />
            </ProtectedRoute>
          }
        />
        <Route path="/recruiter/subscription" element={<SubscriptionPlans />} />
        <Route path="/candidate/subscription" element={<CandidateSubscriptionPlans />} />

        {/* Payment routes */}
        <Route path="/payment/success" element={<PaymentSuccess />} />
        <Route path="/payment/cancel" element={<PaymentCancel />} />

        {/* Admin portal — one persistent AdminLayout (sidebar stays mounted;
            tab switches only swap the <Outlet/> content, no panel reload) */}
        <Route element={admin(<AdminLayoutOutlet />)}>
          <Route path="/admin" element={<AdminOverview />} />
          <Route path="/admin/overview" element={<AdminOverview />} />
          <Route path="/admin/candidates" element={<ManageCandidates />} />
          <Route path="/admin/candidates/:candidateId" element={<CandidateDetail />} />
          <Route path="/admin/recruiters" element={<ManageRecruiters />} />
          <Route path="/admin/recruiters/:recruiterId" element={<RecruiterDetail />} />
          <Route path="/admin/admins" element={<ManageAdmins />} />
          <Route path="/admin/verification" element={<Verification />} />
          <Route path="/admin/cost-statistics" element={<CostStatistics />} />
          <Route path="/admin/credit-statistics" element={<CreditStatistics />} />
        </Route>

        {/* Role dashboards & stats */}
        <Route path="/recruiter/cost-statistics" element={<RecruiterCostStatistics />} />
        <Route path="/recruiter/team" element={<RecruiterTeam />} />
        <Route path="/candidate/cost-statistics" element={<CandidateCostStatistics />} />

        {/* Landing page - public home */}
        <Route path="/" element={<LandingPage />} />

        <Route path="/mobile-camera/:sessionId" element={<MobileRecorder />} />

        {/* Routes with shared Layout (any authenticated user; Layout also
            verifies the token against the backend as before) */}
        <Route
          element={
            <ProtectedRoute allow="any">
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/team" element={<TeamPage />} />
          <Route path="/profile" element={<CandidateProfileRoute />} />
          <Route path="/practice" element={<Practice />} />
          <Route path="/jobs/:jobId" element={<JobDetails />} />
          <Route path="/applications" element={<Applications />} />
          <Route path="/applications/:applicationId" element={<ApplicationView />} />
        </Route>

        <Route path="/interviews/:interviewId" element={<Interview />} />
        <Route path="/assessments/:invitationId" element={<ProtectedRoute allow="candidate"><Assessment /></ProtectedRoute>} />
        <Route path="/oa-companion/:invitationId" element={<AssessmentCompanion />} />

        {/* Legacy paths (renamed 2026-07) — emails/bookmarks keep working */}
        <Route path="/recruiter-dashboard" element={<LegacyRedirect to="/recruiter/dashboard" />} />
        <Route path="/subscription" element={<Navigate to="/recruiter/subscription" replace />} />
        <Route path="/job/:jobId" element={<LegacyRedirect to="/jobs/:jobId" />} />
        <Route path="/application/:applicationId" element={<LegacyRedirect to="/applications/:applicationId" />} />
        <Route path="/interview/:interviewId" element={<LegacyRedirect to="/interviews/:interviewId" />} />
        <Route path="/mobile-cam/:sessionId" element={<LegacyRedirect to="/mobile-camera/:sessionId" />} />

        <Route path="/404" element={<NotFound />} />
        <Route path="*" element={<Navigate to="/404" />} />
      </Routes>
    </Suspense>
  );
}
