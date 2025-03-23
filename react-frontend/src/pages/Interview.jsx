import React from "react";
import { useParams } from "react-router-dom";
import Chat from "./Chat";

const Interview = () => {
	const { interviewId } = useParams();

	return <Chat interviewId={interviewId} />;
};

export default Interview;
