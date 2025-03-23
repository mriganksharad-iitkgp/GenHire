import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import Interview from "./pages/Interview";
import "./App.css";

function App() {
	return (
		<BrowserRouter>
			<Routes>
				<Route path="/login" element={<Login />} />
				<Route path="/profile" element={<Profile />} />
				<Route path="/interview/:interviewId" element={<Interview />} />
				<Route path="/" element={<Dashboard />} />
				<Route path="*" element={<h1>404 Page Not Found</h1>} />
			</Routes>
		</BrowserRouter>
	);
}

export default App;
