import React, { Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "components/Layout";
import ProtectedRoute from "app/ProtectedRoute";

// Lazy-loaded pages (paths update as pages move into features/)
const Login = React.lazy(() => import("pages/Login"));
const Profile = React.lazy(() => import("pages/Profile"));
const Dashboard = React.lazy(() => import("pages/Dashboard"));
const Interview = React.lazy(() => import("pages/Interview"));
const JobDetails = React.lazy(() => import("pages/JobDetails"));
const Register = React.lazy(() => import("pages/Register"));
const RecruiterOnboarding = React.lazy(() => import("pages/RecruiterOnboarding"));
const RecruiterDashboard = React.lazy(() => import("pages/RecruiterDashboard"));
const SubscriptionPlans = React.lazy(() => import("pages/SubscriptionPlans"));
const NotFound = React.lazy(() => import("pages/NotFound"));
const ApplicationView = React.lazy(() => import("pages/ApplicationView"));
const VerifyEmail = React.lazy(() => import("pages/VerifyEmail"));
const ForgotPassword = React.lazy(() => import("pages/ForgotPassword"));
const ResetPassword = React.lazy(() => import("pages/ResetPassword"));
const InviteRedeem = React.lazy(() => import("pages/InviteRedeem"));
const Practice = React.lazy(() => import("pages/Practice"));
const MobileRecorder = React.lazy(() => import("pages/MobileRecorder"));
const PaymentSuccess = React.lazy(() => import("pages/PaymentSuccess"));
const PaymentCancel = React.lazy(() => import("pages/PaymentCancle"));
const CandidateSubscriptionPlans = React.lazy(() => import("pages/candidate/CandidateSubscriptionPlans"));
const CandidateCostStatistics = React.lazy(() => import("pages/candidate/CandidateCostStatistics"));
const TeamPage = React.lazy(() => import("pages/TeamPage"));

// Admin pages
const AdminOverview = React.lazy(() => import("pages/admin/AdminOverview"));
const ManageCandidates = React.lazy(() => import("pages/admin/ManageCandidates"));
const ManageRecruiters = React.lazy(() => import("pages/admin/ManageRecruiters"));
const ManageAdmins = React.lazy(() => import("pages/admin/ManageAdmins"));
const CandidateDetail = React.lazy(() => import("pages/admin/CandidateDetail"));
const RecruiterDetail = React.lazy(() => import("pages/admin/RecruiterDetail"));
const Verification = React.lazy(() => import("pages/admin/Verification"));
const CostStatistics = React.lazy(() => import("pages/admin/CostStatistics"));

// Recruiter pages
const RecruiterCostStatistics = React.lazy(() => import("pages/recruiter/RecruiterCostStatistics"));
const RecruiterTeam = React.lazy(() => import("pages/recruiter/RecruiterTeam"));

// Landing page
const LandingPage = React.lazy(() => import("pages/LandingPage"));

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
          path="/recruiter-dashboard"
          element={
            <ProtectedRoute allow="recruiter">
              <RecruiterDashboard />
            </ProtectedRoute>
          }
        />
        <Route path="/subscription" element={<SubscriptionPlans />} />
        <Route path="/candidate/subscription" element={<CandidateSubscriptionPlans />} />

        {/* Payment routes */}
        <Route path="/payment/success" element={<PaymentSuccess />} />
        <Route path="/payment/cancel" element={<PaymentCancel />} />

        {/* Admin portal */}
        <Route path="/admin" element={admin(<AdminOverview />)} />
        <Route path="/admin/overview" element={admin(<AdminOverview />)} />
        <Route path="/admin/candidates" element={admin(<ManageCandidates />)} />
        <Route path="/admin/candidates/:candidateId" element={admin(<CandidateDetail />)} />
        <Route path="/admin/recruiters" element={admin(<ManageRecruiters />)} />
        <Route path="/admin/recruiters/:recruiterId" element={admin(<RecruiterDetail />)} />
        <Route path="/admin/admins" element={admin(<ManageAdmins />)} />
        <Route path="/admin/verification" element={admin(<Verification />)} />
        <Route path="/admin/cost-statistics" element={admin(<CostStatistics />)} />

        {/* Role dashboards & stats */}
        <Route path="/recruiter/cost-statistics" element={<RecruiterCostStatistics />} />
        <Route path="/recruiter/team" element={<RecruiterTeam />} />
        <Route path="/candidate/cost-statistics" element={<CandidateCostStatistics />} />

        {/* Landing page - public home */}
        <Route path="/" element={<LandingPage />} />

        <Route path="/mobile-cam/:sessionId" element={<MobileRecorder />} />

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
          <Route path="/profile" element={<Profile />} />
          <Route path="/practice" element={<Practice />} />
          <Route path="/job/:jobId" element={<JobDetails />} />
          <Route path="/application/:applicationId" element={<ApplicationView />} />
        </Route>

        <Route path="/interview/:interviewId" element={<Interview />} />
        <Route path="/404" element={<NotFound />} />
        <Route path="*" element={<Navigate to="/404" />} />
      </Routes>
    </Suspense>
  );
}
