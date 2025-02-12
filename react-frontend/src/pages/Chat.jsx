import React, { useEffect, useState, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import Styles from "./Chat.module.css";

export default function Chat() {
  // State to hold sent messages, input (or draft), and voice recording state
  const [chatContent, setChatContent] = useState({});
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  // Refs for scrolling and for the Speech Recognition instance
  const targetRef = useRef();
  const recognitionRef = useRef(null);

  // Initialize Speech Recognition API (if supported)
  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false; // stop after a pause
      recognitionRef.current.interimResults = false; // use only final results
      recognitionRef.current.lang = "en-US";

      // On speech result, update the input (which is also shown as a draft)
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
      console.error("Speech Recognition API is not supported in this browser.");
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

  // Send message function: adds the new message, clears input/draft, and calls backend API
  const onSend = useCallback(
    (e) => {
      e.preventDefault();
      const query = input.trim();
      if (query === "") {
        setInput("");
        return;
      }

      // Add new message with "Loading..." as the placeholder for the response
      const newChatContent = { ...chatContent };
      const newIndex = Object.keys(newChatContent).length;
      newChatContent[newIndex] = {
        query,
        response: "Loading...",
      };
      setChatContent(newChatContent);
      setInput(""); // Clear the draft

      // Scroll chat to the bottom
      if (targetRef.current) {
        targetRef.current.scrollTop = targetRef.current.scrollHeight;
      }

      // Build conversation history (excluding the current message)
      let history = {};
      Object.keys(newChatContent).forEach((idx) => {
        if (parseInt(idx) === newIndex) return;
        history[idx] = newChatContent[idx];
      });

      // Call backend API to fetch the response
      fetch("http://localhost:5000/api/answer_question", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: query, history }),
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
    <div className={`${Styles["page-container"]} ${menuOpen ? Styles["menuOpen"] : ""}`}>
      <div className={Styles["chat-menu-container"]}>
        <div className={Styles["hamburger"]} onClick={() => setMenuOpen(!menuOpen)}>
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
              const pair = chatContent[idx];
              return (
                <React.Fragment key={idx}>
                  {pair.query && (
                    <div className={`${Styles["message-box"]} ${Styles["user"]}`}>
                      <img src={"../android-chrome-512x512.png"} alt="logo" />
                      <div className={Styles["message"]}>{pair.query}</div>
                    </div>
                  )}
                  {pair.response && (
                    <div className={`${Styles["message-box"]} ${Styles["gpt"]}`}>
                      <img src={"../android-chrome-512x512.png"} alt="logo" />
                      <div className={Styles["message"]}>{pair.response}</div>
                    </div>
                  )}
                </React.Fragment>
              );
            })
          ) : (
            <div className={Styles["message-box-empty"]}>
              This could be a good place to start a conversation. Ask me anything!
            </div>
          )}

          {/* Draft Bubble: Show current input (which might come from speech recognition) */}
          {input.trim() !== "" && (
            <div className={`${Styles["message-box"]} ${Styles["user"]}`}>
              <img src={"../android-chrome-512x512.png"} alt="logo" />
              <div className={Styles["message"]}>{input}</div>
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
          {/* Voice input button with animation when recording */}
          <button
            type="button"
            onClick={handleVoiceInput}
            className={isRecording ? Styles.recording : ""}
          >
            <i className="fa fa-microphone" aria-hidden="true" />
          </button>
          <button type="submit">
            <i className="fa fa-paper-plane" aria-hidden="true" />
          </button>
        </form>
      </div>
    </div>
  );
}
