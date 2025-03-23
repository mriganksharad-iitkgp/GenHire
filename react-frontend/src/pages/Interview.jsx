import React, { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Chat from "./Chat";

const Interview = () => {
	const { interviewId } = useParams();
	const navigate = useNavigate();

	// Check authentication when component mounts
	useEffect(() => {
		const isLoggedIn = localStorage.getItem("candidateLoggedIn") === "true";
		if (!isLoggedIn) {
			navigate("/login");
		}
	}, [navigate]);

	return <Chat interviewId={interviewId} />;
};

export default Interview;
