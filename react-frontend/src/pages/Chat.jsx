import React, { useEffect, useState, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import Styles from "./Chat.module.css";

export default function Chat() {
  // State to hold sent messages, input (or draft), and voice recording state
  const [chatContent, setChatContent] = useState({});
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  // isSpeaking tracks if any response is currently being spoken
  const [isSpeaking, setIsSpeaking] = useState(false);
  // speakingIndex is used to know which response is being read out
  const [speakingIndex, setSpeakingIndex] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);

  // Refs for scrolling and for the Speech Recognition instance
  const targetRef = useRef();
  const recognitionRef = useRef(null);
  const currentUtteranceRef = useRef(null);

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

  // Toggle Text-to-Speech: If the provided message is already speaking, stop it;
  // otherwise, cancel any current utterance and start speaking this message.
  const toggleSpeech = (idx, text) => {
    if (!window.speechSynthesis) {
      console.error("Speech Synthesis API is not supported in this browser.");
      return;
    }
    // If this message is already speaking, stop it.
    if (isSpeaking && speakingIndex === idx) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      setSpeakingIndex(null);
      return;
    }
    // If some other utterance is speaking, cancel it.
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
                        src={"../android-chrome-512x512.png"}
                        alt="logo"
                      />
                      <div className={Styles["message"]}>{pair.query}</div>
                    </div>
                  )}
                  {pair.response && (
                    <div
                      className={`${Styles["message-box"]} ${Styles["gpt"]}`}
                    >
                      <img
                        src={"../android-chrome-512x512.png"}
                        alt="logo"
                      />
                      <div className={Styles["message"]}>
                        {pair.response}
                        {/* Speaker/Stop Button to control text-to-speech */}
                        <button
                          onClick={() => toggleSpeech(idx, pair.response)}
                          className={Styles["speakerButton"]}
                          title={
                            isSpeaking && speakingIndex === idx
                              ? "Stop Speech"
                              : "Read Aloud"
                          }
                        >
                          {isSpeaking && speakingIndex === idx ? (
                            <i className="fa fa-stop" aria-hidden="true" />
                          ) : (
                            <i className="fa fa-volume-up" aria-hidden="true" />
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
              This could be a good place to start a conversation. Ask me
              anything!
            </div>
          )}

          {/* Uncomment if you want to show a draft bubble for the current input */}
          {/* {input.trim() !== "" && (
            <div className={`${Styles["message-box"]} ${Styles["user"]}`}>
              <img src={"../android-chrome-512x512.png"} alt="logo" />
              <div className={Styles["message"]}>{input}</div>
            </div>
          )} */}
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
            title={isRecording ? "Stop Listening" : "Start Voice Input"}
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
