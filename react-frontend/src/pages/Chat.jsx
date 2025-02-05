import React, { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";

import Styles from "./Chat.module.css";

export default function Chat() {
	const [chatContent, setChatContent] = useState({});

	const [input, setInput] = useState("");

	const targetRef = useRef();

	const [menuOpen, setMenuOpen] = useState(false);

	function onSend(e) {
		e.preventDefault();
		const query = input.trim();

		if (query === "") {
			setInput("");
			return;
		}

		chatContent[Object.keys(chatContent).length] = {
			query,
			response: "Loading...",
		};
		setChatContent(chatContent);
		setInput("");

		// scroll to bottom
		targetRef.current.scrollTop = targetRef.current.scrollHeight;

		// convert chatContent to object and remove last message
		let history = {};
		if (typeof chatContent === "array") {
			chatContent.forEach((pair, idx) => {
				if (idx == chatContent.length - 1) return;
				history[idx] = pair;
			});
		} else {
			Object.keys(chatContent).forEach((idx) => {
				if (idx == Object.keys(chatContent).length - 1) return;
				history[idx] = chatContent[idx];
			});
		}

		// // send chat content to model and get response
		// fetch("http://10.29.8.94:5000/api/anwser_question", {
		// 	method: "POST",
		// 	headers: {
		// 		"Content-Type": "application/json",
		// 	},
		// 	body: JSON.stringify({
		// 		question: query,
		// 		history: history,
		// 	}),
		// })
		// 	.then((response) => {
		// 		response.json().then((data) => {
		// 			// copy chat content and update last message
		// 			let temp = { ...chatContent };
		// 			temp[Object.keys(chatContent).length - 1] = {
		// 				query,
		// 				response: data.result,
		// 			};
		// 		});
		// 	})
		// 	.catch((error) => {
		// 		alert("Error in sending message: " + error.message);

		// 		// remove from chat content and put in input
		// 		let temp = { ...chatContent };
		// 		delete temp[Object.keys(chatContent).length - 1];
		// 		setChatContent(temp);
		// 		setInput(query);
		// 	});
	}

	// form submit on Shift+Enter
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
			className={
				Styles["page-container"] +
				` ${menuOpen ? Styles["menuOpen"] : ""}`
			}
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
				<div className={Styles["messages-list"]} ref={targetRef}>
					{Object.keys(chatContent).length > 0 ? (
						Object.keys(chatContent).map((idx) => {
							let pair = chatContent[idx];
							return (
								<React.Fragment key={idx}>
									{pair.query && (
										<div
											key={1}
											className={
												Styles["message-box"] +
												" " +
												Styles["user"]
											}
										>
											<img
												src={
													"../android-chrome-512x512.png"
												}
												alt="logo"
											/>
											<div className={Styles["message"]}>
												{pair.query}
											</div>
										</div>
									)}
									{pair.response && (
										<div
											key={2}
											className={
												Styles["message-box"] +
												" " +
												Styles["gpt"]
											}
										>
											<img
												src={
													"../android-chrome-512x512.png"
												}
												alt="logo"
											/>
											<div className={Styles["message"]}>
												{pair.response}
											</div>
										</div>
									)}
								</React.Fragment>
							);
						})
					) : (
						<div className={Styles["message-box-empty"]}>
							This could be a good place to start a conversation.
							Ask me anything!
						</div>
					)}
				</div>
				<form onSubmit={onSend} className={Styles["chat-box-footer"]}>
					<textarea
						type="text"
						value={input}
						onChange={(e) => setInput(e.target.value)}
						placeholder="Type your message...Press Shift+Enter to send"
					></textarea>
					<button type="submit">
						<i className="fa fa-paper-plane" aria-hidden="true" />
					</button>
				</form>
			</div>
		</div>
	);
}
