import React, { useEffect, useState, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import Styles from "./Chat.module.css";

export default function Chat() {
	const [chatContent, setChatContent] = useState({});
	const [input, setInput] = useState("");
	const [isRecording, setIsRecording] = useState(false);
	const [isSpeaking, setIsSpeaking] = useState(false);
	const [speakingIndex, setSpeakingIndex] = useState(null);
	const [menuOpen, setMenuOpen] = useState(false);
	const [jdFile, setJdFile] = useState(null);
	const [cvFile, setCvFile] = useState(null);

	const targetRef = useRef();
	const recognitionRef = useRef(null);
	const currentUtteranceRef = useRef(null);

	// temporary state to store file paths
	const [jd_file_path, setJdFilePath] = useState(null);
	const [cv_file_path, setCvFilePath] = useState(null);

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
				console.log(transcript);
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

	// Handle file upload
	const handleFileUpload = async (e) => {
		e.preventDefault();
		if (!jdFile || !cvFile) {
			alert("Please upload both JD and CV files.");
			return;
		}

		const formData = new FormData();
		formData.append("jd", jdFile);
		formData.append("cv", cvFile);

		try {
			const response = await fetch("http://localhost:5000/api/upload", {
				method: "POST",
				body: formData,
			});
			const data = await response.json();
			if (response.ok) {
				alert(data.message);
				setJdFilePath(data.jd_file_path);
				setCvFilePath(data.cv_file_path);
			} else {
				alert(data.error);
			}
		} catch (error) {
			alert("Error uploading files. Please try again.");
		}
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

			if (!jd_file_path || !cv_file_path) {
				alert("Please upload JD and CV files first.");
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
					jd_file_path,
					cv_file_path,
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
		[chatContent, input]
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

	return (
		<div
			className={`${Styles["page-container"]} ${
				menuOpen ? Styles["menuOpen"] : ""
			}`}
		>
			<div className={Styles["chat-menu-container"]}>
				<div
					className={Styles["hamburger"]}
					onClick={() => setMenuOpen(!menuOpen)}
				>
					<i className="fa fa-bars" aria-hidden="true" />
				</div>
				{menuOpen && <div className={Styles["chat-list"]}></div>}
			</div>
			<div className={Styles["chat-box-container"]}>
				<div className={Styles["chat-box-header"]}>
					<Link to="/">
						<h1>
							<img
								src="../android-chrome-512x512.png"
								alt="logo"
								height={50}
								width={50}
							/>
							HR Tech
						</h1>
					</Link>
				</div>
				<div className={Styles["chat-content"]}>
					{/* File Upload Section */}
					<div className={Styles["file-upload-container"]}>
						<div className={Styles["upload-header"]}>
							<i
								className="fa fa-cloud-upload"
								aria-hidden="true"
							/>
							<h3>Upload Documents</h3>
							<p>Supported formats: PDF</p>
						</div>
						<form
							onSubmit={handleFileUpload}
							className={Styles["upload-form"]}
						>
							<div className={Styles["file-input-group"]}>
								<div className={Styles["file-card"]}>
									<label
										className={Styles["file-input-label"]}
									>
										<i
											className="fa fa-file-text"
											aria-hidden="true"
										/>
										<span>Job Description</span>
										<input
											type="file"
											accept=".pdf,.docx"
											onChange={(e) =>
												setJdFile(e.target.files[0])
											}
											className={Styles["hidden-input"]}
										/>
										<div className={Styles["file-info"]}>
											{jdFile
												? jdFile.name
												: "No file selected"}
										</div>
									</label>
									{jd_file_path && (
										<div className={Styles["file-info"]}>
											<a
												target="_blank"
												rel="noopener noreferrer"
												href={`http://localhost:5000/api/view-file?path=${encodeURIComponent(
													jd_file_path
												)}`}
											>
												View Uploaded JD
											</a>
										</div>
									)}
								</div>

								<div className={Styles["file-card"]}>
									<label
										className={Styles["file-input-label"]}
									>
										<i
											className="fa fa-user"
											aria-hidden="true"
										/>
										<span>Candidate CV</span>
										<input
											type="file"
											accept=".pdf,.docx"
											onChange={(e) =>
												setCvFile(e.target.files[0])
											}
											className={Styles["hidden-input"]}
										/>
										<div className={Styles["file-info"]}>
											{cvFile
												? cvFile.name
												: "No file selected"}
										</div>
									</label>
									{cv_file_path && (
										<div className={Styles["file-info"]}>
											<a
												target="_blank"
												rel="noopener noreferrer"
												href={`http://localhost:5000/api/view-file?path=${encodeURIComponent(
													cv_file_path
												)}`}
											>
												View Uploaded CV
											</a>
										</div>
									)}
								</div>
							</div>
							<button
								type="submit"
								className={Styles["upload-button"]}
							>
								<i
									className="fa fa-upload"
									aria-hidden="true"
								/>
								Upload Documents
							</button>
						</form>
					</div>

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
														"../android-chrome-512x512.png"
													}
													alt="logo"
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
													alt="logo"
												/>
												<div
													className={
														Styles["message"]
													}
												>
													{pair.response}
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
								This could be a good place to start a
								conversation. Ask me anything!
							</div>
						)}
					</div>
				</div>
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
