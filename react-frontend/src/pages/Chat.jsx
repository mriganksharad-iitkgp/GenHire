import React, { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Styles from "./Chat.module.css";

export default function Chat({ interviewId }) {
	const [chatContent, setChatContent] = useState({});
	const [input, setInput] = useState("");
	const [isRecording, setIsRecording] = useState(false);
	const [isSpeaking, setIsSpeaking] = useState(false);
	const [speakingIndex, setSpeakingIndex] = useState(null);
	const [sessionId, setSessionId] = useState(null);
	const [currentQuestion, setCurrentQuestion] = useState("");
	const [interviewStatus, setInterviewStatus] = useState("starting"); // starting, active, ending, completed
	const [evaluation, setEvaluation] = useState(null);
	const [similarityScore, setSimilarityScore] = useState(null);

	const navigate = useNavigate();
	const targetRef = useRef();
	const recognitionRef = useRef(null);
	const currentUtteranceRef = useRef(null);

	// Handle logout
	const handleLogout = () => {
		localStorage.removeItem("companyxyz-token");
		localStorage.removeItem("companyxyz-user");
		navigate("/login");
	};

	// Check authentication when component mounts
	useEffect(() => {
		const isLoggedIn = localStorage.getItem("companyxyz-token") !== null;
		if (!isLoggedIn) {
			navigate("/login");
		}
	}, [navigate]);

	// Initialize Speech Recognition API (if supported)
	useEffect(() => {
		const SpeechRecognition =
			window.SpeechRecognition || window.webkitSpeechRecognition;
		if (SpeechRecognition) {
			recognitionRef.current = new SpeechRecognition();
			recognitionRef.current.continuous = false;
			recognitionRef.current.interimResults = false;
			recognitionRef.current.lang = "en-US";

			recognitionRef.current.onresult = (event) => {
				const transcript = event.results[0][0].transcript;
				setInput(transcript);
				setIsRecording(false);
			};

			recognitionRef.current.onerror = (event) => {
				console.error("Speech recognition error", event);
				setIsRecording(false);
			};

			recognitionRef.current.onend = () => {
				setIsRecording(false);
			};
		} else {
			console.error(
				"Speech Recognition API is not supported in this browser."
			);
		}
	}, []);

	// Toggle voice input on/off
	const handleVoiceInput = () => {
		if (!recognitionRef.current) return;
		if (isRecording) {
			recognitionRef.current.stop();
			setIsRecording(false);
		} else {
			recognitionRef.current.start();
			setIsRecording(true);
		}
	};

	// Toggle Text-to-Speech
	const toggleSpeech = (idx, text) => {
		if (!window.speechSynthesis) {
			console.error(
				"Speech Synthesis API is not supported in this browser."
			);
			return;
		}
		if (isSpeaking && speakingIndex === idx) {
			window.speechSynthesis.cancel();
			setIsSpeaking(false);
			setSpeakingIndex(null);
			return;
		}
		if (isSpeaking) {
			window.speechSynthesis.cancel();
		}
		const utterance = new SpeechSynthesisUtterance(text);
		utterance.lang = "en-US";
		utterance.onstart = () => {
			setIsSpeaking(true);
			setSpeakingIndex(idx);
		};
		utterance.onend = () => {
			setIsSpeaking(false);
			setSpeakingIndex(null);
		};
		utterance.onerror = () => {
			setIsSpeaking(false);
			setSpeakingIndex(null);
		};
		currentUtteranceRef.current = utterance;
		window.speechSynthesis.speak(utterance);
	};

	// Initialize the interview session
	useEffect(() => {
		if (interviewId && !sessionId && interviewStatus === "starting") {
			// Start a new interview session
			const token = localStorage.getItem("companyxyz-token");
			fetch("http://localhost:5000/api/interviews/start", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					Authorization: token,
				},
				body: JSON.stringify({
					// Using default values, these would come from the database in production
					cv_path: "uploads/cv/PeterConnollyResume-2.pdf",
					jd_path: "uploads/jd/JD1.pdf",
					reference_path: "Eric Ries - The Lean Startup.pdf",
				}),
			})
				.then((response) => response.json())
				.then((data) => {
					setSessionId(data.session_id);
					setSimilarityScore(data.similarity_score);
					setInterviewStatus("active");

					// Add initial questions as system messages
					const newChatContent = {};
					newChatContent[0] = {
						response: `Welcome to your AI interview session. Your CV has a ${Math.round(
							data.similarity_score * 100
						)}% match with the job description. I'll be asking you several questions to assess your fit for this role.`,
					};

					// Add first question
					if (
						data.initial_questions &&
						data.initial_questions.length > 0
					) {
						setCurrentQuestion(data.initial_questions[0]);
						newChatContent[1] = {
							response: data.initial_questions[0],
						};
					}

					setChatContent(newChatContent);
				})
				.catch((error) => {
					console.error("Error starting interview:", error);
					setChatContent({
						0: {
							response:
								"⚠️ Error: Could not start the interview session. Please try again later.",
						},
					});
				});
		}
	}, [interviewId, sessionId, interviewStatus]);

	// Send message function - modified to work with interview API
	const onSend = useCallback(
		(e) => {
			e.preventDefault();
			const answer = input.trim();
			if (
				answer === "" ||
				!currentQuestion ||
				!sessionId ||
				interviewStatus !== "active"
			) {
				setInput("");
				return;
			}

			const newChatContent = { ...chatContent };
			const newIndex = Object.keys(newChatContent).length;
			newChatContent[newIndex] = {
				query: answer,
				response: "Analyzing your response...",
			};
			setChatContent(newChatContent);
			setInput("");

			if (targetRef.current) {
				targetRef.current.scrollTop = targetRef.current.scrollHeight;
			}

			// Submit the answer to the interview API
			fetch(`http://localhost:5000/api/interviews/${sessionId}/answer`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({
					question: currentQuestion,
					answer: answer,
				}),
			})
				.then((response) => response.json())
				.then((data) => {
					const updatedChatContent = { ...newChatContent };

					// Add evaluation feedback
					if (data.evaluation && data.evaluation.feedback) {
						updatedChatContent[newIndex] = {
							query: answer,
							evaluation: data.evaluation,
						};
						newIndex + 1;
					}

					// Add next question
					if (data.next_question) {
						setCurrentQuestion(data.next_question);
						updatedChatContent[newIndex + 1] = {
							response: data.next_question,
						};
					}

					setChatContent(updatedChatContent);
				})
				.catch((error) => {
					console.error("Error submitting answer:", error);
					const updatedChatContent = { ...newChatContent };
					updatedChatContent[newIndex] = {
						query: answer,
						response:
							"⚠️ Error: Could not process your answer. Please try again.",
					};
					setChatContent(updatedChatContent);
				});
		},
		[chatContent, input, currentQuestion, sessionId, interviewStatus]
	);

	// End the interview
	const endInterview = () => {
		if (!sessionId || interviewStatus !== "active") return;

		setInterviewStatus("ending");

		const token = localStorage.getItem("companyxyz-token");
		fetch(`http://localhost:5000/api/interviews/${sessionId}/end`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				Authorization: token,
			},
		})
			.then((response) => response.json())
			.then((data) => {
				setInterviewStatus("completed");
				setEvaluation(data.evaluation);

				const newChatContent = { ...chatContent };
				const newIndex = Object.keys(newChatContent).length;
				newChatContent[newIndex] = {
					response:
						"Thank you for completing the interview. Here's your evaluation:",
				};

				if (data.evaluation && data.evaluation.qualitative_assessment) {
					newChatContent[newIndex + 1] = {
						response: data.evaluation.qualitative_assessment,
					};
				}

				setChatContent(newChatContent);
			})
			.catch((error) => {
				console.error("Error ending interview:", error);
				setInterviewStatus("active"); // Revert to active if error

				const newChatContent = { ...chatContent };
				const newIndex = Object.keys(newChatContent).length;
				newChatContent[newIndex] = {
					response:
						"⚠️ Error: Could not end the interview. Please try again.",
				};
				setChatContent(newChatContent);
			});
	};

	// Optionally send the message on Shift+Enter key press
	useEffect(() => {
		function handleKeyDown(e) {
			if (e.shiftKey && e.key === "Enter") {
				onSend(e);
			}
		}
		document.addEventListener("keydown", handleKeyDown);
		return () => {
			document.removeEventListener("keydown", handleKeyDown);
		};
	}, [onSend]);

	return (
		<div className={Styles["page-container"]}>
			<div className={Styles["chat-box-container"]}>
				{/* Header with info */}
				<div className={Styles["chat-header"]}>
					<h2>
						AI Interview Session {sessionId ? `#${sessionId}` : ""}
					</h2>
					{similarityScore !== null && (
						<div className={Styles["similarity-score"]}>
							CV-JD Match: {Math.round(similarityScore * 100)}%
						</div>
					)}
					{interviewStatus === "active" && (
						<button
							className={Styles["end-interview-btn"]}
							onClick={endInterview}
						>
							End Interview
						</button>
					)}
				</div>

				{/* Main chat interface */}
				<div className={Styles["chat-content"]}>
					{/* Chat Messages */}
					<div className={Styles["messages-list"]} ref={targetRef}>
						{Object.keys(chatContent).length > 0 ? (
							Object.keys(chatContent).map((idx) => {
								const pair = chatContent[idx];
								return (
									<React.Fragment key={idx}>
										{pair.query && (
											<div
												className={`${Styles["message-box"]} ${Styles["user"]}`}
											>
												<img
													src={
														"../android-chrome-192x192.png"
													}
													alt="User Avatar"
												/>
												<div
													className={
														Styles["message"]
													}
												>
													{pair.query}
												</div>
											</div>
										)}
										{pair.evaluation && (
											<div
												className={`${Styles["message-box"]} ${Styles["evaluation"]}`}
											>
												<div
													className={
														Styles[
															"evaluation-content"
														]
													}
												>
													<div
														className={
															Styles["score"]
														}
													>
														Relevance:{" "}
														{Math.round(
															pair.evaluation
																.relevance_score *
																100
														)}
														%
													</div>
													<div
														className={
															Styles["feedback"]
														}
													>
														{
															pair.evaluation
																.feedback
														}
													</div>
												</div>
											</div>
										)}
										{pair.response && (
											<div
												className={`${Styles["message-box"]} ${Styles["gpt"]}`}
											>
												<img
													src={
														"../android-chrome-512x512.png"
													}
													alt="AI Avatar"
												/>
												<div
													className={
														Styles["message"]
													}
												>
													{pair.response
														.split("\n")
														.map((line, index) => (
															<React.Fragment
																key={index}
															>
																{line}
																<br />
															</React.Fragment>
														))}
													<div
														className={
															Styles[
																"message-actions"
															]
														}
													>
														<button
															className={
																isSpeaking &&
																speakingIndex ===
																	idx
																	? Styles[
																			"btn-stop"
																	  ]
																	: Styles[
																			"btn-speak"
																	  ]
															}
															onClick={() =>
																toggleSpeech(
																	idx,
																	pair.response
																)
															}
														>
															{isSpeaking &&
															speakingIndex ===
																idx
																? "Stop"
																: "Speak"}
														</button>
													</div>
												</div>
											</div>
										)}
									</React.Fragment>
								);
							})
						) : (
							<div className={Styles["loading-chat"]}>
								Initializing interview session...
							</div>
						)}
					</div>

					{/* Input area */}
					<div className={Styles["input-area"]}>
						<form onSubmit={onSend}>
							<textarea
								value={input}
								onChange={(e) => setInput(e.target.value)}
								placeholder={
									interviewStatus === "active"
										? "Type your answer here..."
										: interviewStatus === "completed"
										? "Interview completed"
										: "Starting interview..."
								}
								disabled={interviewStatus !== "active"}
								className={Styles["chat-input"]}
							/>
							<div className={Styles["input-actions"]}>
								<button
									type="button"
									className={Styles["voice-input-button"]}
									onClick={handleVoiceInput}
									disabled={interviewStatus !== "active"}
								>
									{isRecording ? "Stop" : "Voice"}
								</button>
								<button
									type="submit"
									className={Styles["send-button"]}
									disabled={
										interviewStatus !== "active" ||
										!input.trim()
									}
								>
									Send
								</button>
							</div>
						</form>
					</div>
				</div>
			</div>

			{/* Evaluation results */}
			{interviewStatus === "completed" && evaluation && (
				<div className={Styles["evaluation-container"]}>
					<h3>Interview Evaluation</h3>
					{evaluation.quantitative && (
						<div className={Styles["quantitative-metrics"]}>
							<div className={Styles["metric"]}>
								<span>Average Score:</span>
								<span>
									{Math.round(
										evaluation.quantitative
											.average_relevance_score * 100
									)}
									%
								</span>
							</div>
							<div className={Styles["metric"]}>
								<span>Questions Answered:</span>
								<span>
									{
										evaluation.quantitative
											.number_of_questions
									}
								</span>
							</div>
						</div>
					)}
					<div className={Styles["qualitative-assessment"]}>
						{evaluation.qualitative_assessment
							.split("\n")
							.map((line, index) => (
								<p key={index}>{line}</p>
							))}
					</div>

					<button
						className={Styles["back-to-dashboard"]}
						onClick={() => navigate("/dashboard")}
					>
						Return to Dashboard
					</button>
				</div>
			)}
		</div>
	);
}
