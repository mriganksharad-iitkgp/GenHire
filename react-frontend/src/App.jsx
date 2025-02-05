import { BrowserRouter, Routes, Route } from "react-router-dom";
import Chat from "./pages/Chat";
import "./App.css";

function App() {
	return (
		<BrowserRouter>
			<Routes>
				<Route path="/" element={<Chat />} />
				<Route exact path="*" element={<h1>404 Page Not Found</h1>} />
			</Routes>
		</BrowserRouter>
	);
}

export default App;
