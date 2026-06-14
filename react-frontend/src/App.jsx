import React, { Suspense } from "react";
import "./App.css";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { CandidateDataProvider } from "./contexts/CandidateDataContext";
import ErrorBoundary from "./components/ErrorBoundary";
import Layout from "./components/Layout";

// Lazy-loaded pages
const Login = React.lazy(() => import("./pages/Login"));
const Profile = React.lazy(() => import("./pages/Profile"));
const Dashboard = React.lazy(() => import("./pages/Dashboard"));
const Interview = React.lazy(() => import("./pages/Interview"));
const JobDetails = React.lazy(() => import("./pages/JobDetails"));
const Register = React.lazy(() => import("./pages/Register"));
const RecruiterOnboarding = React.lazy(() => import("./pages/RecruiterOnboarding"));
const RecruiterDashboard = React.lazy(() => import("./pages/RecruiterDashboard"));
const SubscriptionPlans = React.lazy(() => import("./pages/SubscriptionPlans"));
const AdminDashboard = React.lazy(() => import("./pages/AdminDashboard"));
const NotFound = React.lazy(() => import("./pages/NotFound"));
const ApplicationView = React.lazy(() => import("./pages/ApplicationView"));
const VerifyEmail = React.lazy(() => import("./pages/VerifyEmail"));
const ForgotPassword = React.lazy(() => import("./pages/ForgotPassword"));
const ResetPassword = React.lazy(() => import("./pages/ResetPassword"));
const InviteRedeem = React.lazy(() => import("./pages/InviteRedeem"));
const Practice = React.lazy(() => import("./pages/Practice"));
const MobileRecorder = React.lazy(() => import("./pages/MobileRecorder"));
const PaymentSuccess = React.lazy(() => import("./pages/PaymentSuccess"));
const PaymentCancel = React.lazy(() => import("./pages/PaymentCancle"));
const CandidateSubscriptionPlans = React.lazy(() => import("./pages/candidate/CandidateSubscriptionPlans"));
const CandidateCostStatistics = React.lazy(() => import("./pages/candidate/CandidateCostStatistics"));
const TeamPage = React.lazy(() => import("./pages/TeamPage"));

// Admin Pages
const AdminOverview = React.lazy(() => import("./pages/admin/AdminOverview"));
const ManageCandidates = React.lazy(() => import("./pages/admin/ManageCandidates"));
const ManageRecruiters = React.lazy(() => import("./pages/admin/ManageRecruiters"));
const ManageAdmins = React.lazy(() => import("./pages/admin/ManageAdmins"));
const CandidateDetail = React.lazy(() => import("./pages/admin/CandidateDetail"));
const RecruiterDetail = React.lazy(() => import("./pages/admin/RecruiterDetail"));
const Verification = React.lazy(() => import("./pages/admin/Verification"));
const CostStatistics = React.lazy(() => import("./pages/admin/CostStatistics"));

// Recruiter Pages
const RecruiterCostStatistics = React.lazy(() => import("./pages/recruiter/RecruiterCostStatistics"));
const RecruiterTeam = React.lazy(() => import("./pages/recruiter/RecruiterTeam"));

// Landing Page
const LandingPage = React.lazy(() => import("./pages/LandingPage"));

function App() {
  return (
    <GoogleOAuthProvider clientId={process.env.REACT_APP_GOOGLE_CLIENT_ID}>
      <CandidateDataProvider>
        <ErrorBoundary>
          <Router>
            <Suspense fallback={<div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', width: '100vw' }}>Loading application...</div>}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/recruiter-signup" element={<RecruiterOnboarding />} />
                <Route path="/verify-email" element={<VerifyEmail />} />
                <Route path="/forgot-password" element={<ForgotPassword />} />
                <Route path="/reset-password" element={<ResetPassword />} />
                <Route path="/invite/redeem" element={<InviteRedeem />} />
                <Route
                  path="/recruiter-dashboard"
                  element={<RecruiterDashboard />}
                />
                <Route path="/subscription" element={<SubscriptionPlans />} />
                <Route path="/candidate/subscription" element={<CandidateSubscriptionPlans />} />

                {/* Payment Routes */}
                <Route path="/payment/success" element={<PaymentSuccess />} />
                <Route path="/payment/cancel" element={<PaymentCancel />} />
                
                {/* Admin Routes - New Admin Portal */}
                <Route path="/admin" element={<AdminOverview />} />
                <Route path="/admin/overview" element={<AdminOverview />} />
                <Route path="/admin/candidates" element={<ManageCandidates />} />
                <Route path="/admin/candidates/:candidateId" element={<CandidateDetail />} />
                <Route path="/admin/recruiters" element={<ManageRecruiters />} />
                <Route path="/admin/recruiters/:recruiterId" element={<RecruiterDetail />} />
                <Route path="/admin/admins" element={<ManageAdmins />} />
                <Route path="/admin/verification" element={<Verification />} />
                <Route path="/admin/cost-statistics" element={<CostStatistics />} />
                <Route path="/admin/old" element={<AdminDashboard />} />
                
                {/* Recruiter Cost Statistics */}
                <Route path="/recruiter/cost-statistics" element={<RecruiterCostStatistics />} />
                <Route path="/recruiter/team" element={<RecruiterTeam />} />
                <Route path="/candidate/cost-statistics" element={<CandidateCostStatistics />} />
                
                {/* Landing Page - Public Home */}
                <Route path="/" element={<LandingPage />} />
                
                <Route path="/mobile-cam/:sessionId" element={<MobileRecorder />} />
                {/* Routes with shared Layout */}
                <Route element={<Layout />}>
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
          </Router>
        </ErrorBoundary>
      </CandidateDataProvider>
    </GoogleOAuthProvider>
  );
}

export default App;
