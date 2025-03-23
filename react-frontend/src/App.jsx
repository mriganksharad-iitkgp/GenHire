import React from "react";
import {
	BrowserRouter as Router,
	Routes,
	Route,
	Navigate,
} from "react-router-dom";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import Dashboard from "./pages/Dashboard";
import Interview from "./pages/Interview";
import JobDetails from "./pages/JobDetails";
import Register from "./pages/Register";
import NotFound from "./pages/NotFound";
import Layout from "./components/Layout";
import "./App.css";

function App() {
	return (
		<Router>
			<Routes>
				<Route path="/login" element={<Login />} />
				<Route path="/register" element={<Register />} />
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
					path="/interview/:interviewId"
					element={
						<Layout>
							<Interview />
						</Layout>
					}
				/>
				<Route
					path="/job/:jobId"
					element={
						<Layout>
							<JobDetails />
						</Layout>
					}
				/>
				<Route path="/404" element={<NotFound />} />
				<Route path="*" element={<Navigate to="/404" />} />
			</Routes>
		</Router>
	);
}

export default App;
