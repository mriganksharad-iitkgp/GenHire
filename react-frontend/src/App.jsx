import React from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { CandidateDataProvider } from "./contexts/CandidateDataContext";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import Dashboard from "./pages/Dashboard";
import Interview from "./pages/Interview";
import JobDetails from "./pages/JobDetails";
import Register from "./pages/Register";
import RecruiterOnboarding from "./pages/RecruiterOnboarding";
import RecruiterDashboard from "./pages/RecruiterDashboard";
import SubscriptionPlans from "./pages/SubscriptionPlans";
import AdminDashboard from "./pages/AdminDashboard";
import NotFound from "./pages/NotFound";
import ApplicationView from "./pages/ApplicationView";
import VerifyEmail from "./pages/VerifyEmail";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import InviteRedeem from "./pages/InviteRedeem";
import Practice from "./pages/Practice";
import Layout from "./components/Layout";
import MobileRecorder from "./pages/MobileRecorder";
import PaymentSuccess from "./pages/PaymentSuccess";
import PaymentCancel from "./pages/PaymentCancle";
import CandidateSubscriptionPlans from "./pages/candidate/CandidateSubscriptionPlans";
import CandidateCostStatistics from "./pages/candidate/CandidateCostStatistics";
import TeamPage from "./pages/TeamPage";

// Admin Pages
import AdminOverview from "./pages/admin/AdminOverview";
import ManageCandidates from "./pages/admin/ManageCandidates";
import ManageRecruiters from "./pages/admin/ManageRecruiters";
import ManageAdmins from "./pages/admin/ManageAdmins";
import CandidateDetail from "./pages/admin/CandidateDetail";
import RecruiterDetail from "./pages/admin/RecruiterDetail";
import Verification from "./pages/admin/Verification";
import CostStatistics from "./pages/admin/CostStatistics";

// Recruiter Pages
import RecruiterCostStatistics from "./pages/recruiter/RecruiterCostStatistics";
import RecruiterTeam from "./pages/recruiter/RecruiterTeam";

// Landing Page
import LandingPage from "./pages/LandingPage";

import "./App.css";

function App() {
  return (
    <GoogleOAuthProvider clientId={process.env.REACT_APP_GOOGLE_CLIENT_ID}>
      <CandidateDataProvider>
        <Router>
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
            <Route
              path="/dashboard"
              element={
                <Layout>
                  <Dashboard />
                </Layout>
              }
            />
            <Route
              path="/team"
              element={
                <Layout>
                  <TeamPage />
                </Layout>
              }
            />
            <Route
              path="/profile"
              element={
                <Layout>
                  <Profile />
                </Layout>
              }
            />
            <Route
              path="/practice"
              element={
                <Layout>
                  <Practice />
                </Layout>
              }
            />
            <Route path="/interview/:interviewId" element={<Interview />} />
            <Route
              path="/job/:jobId"
              element={
                <Layout>
                  <JobDetails />
                </Layout>
              }
            />
            <Route
              path="/application/:applicationId"
              element={
                <Layout>
                  <ApplicationView />
                </Layout>
              }
            />
            <Route path="/404" element={<NotFound />} />
            <Route path="*" element={<Navigate to="/404" />} />
          </Routes>
        </Router>
      </CandidateDataProvider>
    </GoogleOAuthProvider>
  );
}

export default App;
