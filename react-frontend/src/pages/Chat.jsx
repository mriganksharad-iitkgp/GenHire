import React, { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Styles from "./Chat.module.css";

export default function Chat({ interviewId }) {
	const [chatContent, setChatContent] = useState({});
	const [input, setInput] = useState("");
	const [isRecording, setIsRecording] = useState(false);
	const [isSpeaking, setIsSpeaking] = useState(false);
	const [speakingIndex, setSpeakingIndex] = useState(null);

	const navigate = useNavigate();
	const targetRef = useRef();
	const recognitionRef = useRef(null);
	const currentUtteranceRef = useRef(null);

	// Handle logout
	const handleLogout = () => {
		localStorage.removeItem("candidateLoggedIn");
		navigate("/login");
	};

	// Check authentication when component mounts
	useEffect(() => {
		const isLoggedIn = localStorage.getItem("candidateLoggedIn") === "true";
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

	// Send message function
	const onSend = useCallback(
		(e) => {
			e.preventDefault();
			const query = input.trim();
			if (query === "") {
				setInput("");
				return;
			}

			const newChatContent = { ...chatContent };
			const newIndex = Object.keys(newChatContent).length;
			newChatContent[newIndex] = {
				query,
				response: "Loading...",
			};
			setChatContent(newChatContent);
			setInput("");

			if (targetRef.current) {
				targetRef.current.scrollTop = targetRef.current.scrollHeight;
			}

			let history = {};
			Object.keys(newChatContent).forEach((idx) => {
				if (parseInt(idx) === newIndex) return;
				history[idx] = newChatContent[idx];
			});

			fetch("http://localhost:5000/api/answer_question", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({
					question: query,
					history,
					interview_id: interviewId,
				}),
			})
				.then((response) => response.json())
				.then((data) => {
					const updatedChatContent = { ...newChatContent };
					updatedChatContent[newIndex] = {
						query,
						response: data.result,
					};
					setChatContent(updatedChatContent);
				})
				.catch((error) => {
					const updatedChatContent = { ...newChatContent };
					updatedChatContent[newIndex] = {
						query,
						response:
							"⚠️ Error: Could not fetch response. Please try again later.",
					};
					setChatContent(updatedChatContent);
				});
		},
		[chatContent, input, interviewId]
	);

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

	// Load interview data based on interviewId
	useEffect(() => {
		if (interviewId) {
			// This would normally be an API call to fetch interview data
			console.log(`Loading interview ID: ${interviewId}`);

			// For now, just set a message in the chat content
			setChatContent({
				0: {
					response: `Welcome to interview #${interviewId}. This is where the conversation will take place.`,
				},
			});
		}
	}, [interviewId]);

	return (
		<div className={Styles["page-container"]}>
			<div className={Styles["chat-box-container"]}>
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
													<button
														onClick={() =>
															toggleSpeech(
																idx,
																pair.response
															)
														}
														className={
															Styles[
																"speakerButton"
															]
														}
														title={
															isSpeaking &&
															speakingIndex ===
																idx
																? "Stop Speech"
																: "Read Aloud"
														}
													>
														{isSpeaking &&
														speakingIndex ===
															idx ? (
															<i
																className="fa fa-stop"
																aria-hidden="true"
															/>
														) : (
															<i
																className="fa fa-volume-up"
																aria-hidden="true"
															/>
														)}
													</button>
												</div>
											</div>
										)}
									</React.Fragment>
								);
							})
						) : (
							<div className={Styles["message-box-empty"]}>
								Your interview session will begin shortly
							</div>
						)}
					</div>
				</div>

				{/* Input form */}
				<form onSubmit={onSend} className={Styles["chat-box-footer"]}>
					<textarea
						type="text"
						value={input}
						onChange={(e) => setInput(e.target.value)}
						placeholder="Type your message...Press Shift+Enter to send"
					></textarea>
					<button
						type="button"
						onClick={handleVoiceInput}
						className={isRecording ? Styles.recording : ""}
						title={
							isRecording ? "Stop Listening" : "Start Voice Input"
						}
					>
						<i className="fa fa-microphone" aria-hidden="true" />
					</button>
					<button type="submit" title="Send Message">
						<i className="fa fa-paper-plane" aria-hidden="true" />
					</button>
				</form>
			</div>
		</div>
	);
}
