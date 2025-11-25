import React from "react";
import {
	BrowserRouter as Router,
	Routes,
	Route,
	Navigate,
} from "react-router-dom";
import { GoogleOAuthProvider } from "@react-oauth/google";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import Dashboard from "./pages/Dashboard";
import Interview from "./pages/Interview";
import JobDetails from "./pages/JobDetails";
import Register from "./pages/Register";
import RecruiterDashboard from "./pages/RecruiterDashboard";
import NotFound from "./pages/NotFound";
import ApplicationView from "./pages/ApplicationView";
import VerifyEmail from "./pages/VerifyEmail";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Practice from "./pages/Practice";
import Layout from "./components/Layout";
import MobileRecorder from "./pages/MobileRecorder";
import "./App.css";


function App() {
	return (
		<GoogleOAuthProvider clientId={process.env.REACT_APP_GOOGLE_CLIENT_ID}>
			<Router>
				<Routes>
					<Route path="/login" element={<Login />} />
					<Route path="/register" element={<Register />} />
					<Route path="/verify-email" element={<VerifyEmail />} />
					<Route path="/forgot-password" element={<ForgotPassword />} />
					<Route path="/reset-password" element={<ResetPassword />} />
					<Route path="/recruiter-dashboard" element={<RecruiterDashboard />} />
					<Route path="/mobile-cam/:sessionId" element={<MobileRecorder />} />
					<Route
						path="/"
						element={
							<Layout>
								<Dashboard />
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
		</GoogleOAuthProvider>
	);
}

export default App;
