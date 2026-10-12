const guidance = {
  no_face: "Your face is not clearly visible. Face the camera and improve the lighting.",
  multiple_faces: "Another face may be visible. Keep other people and screen reflections out of the camera view.",
  head_turn: "Your face has been turned away for several checks. Look toward the interview screen.",
  phone_detected: "An additional phone may be visible. Put it away; only the paired monitoring phone is permitted.",
  tab_switch: "The interview tab was hidden. Return to this tab and keep it visible.",
  window_blur: "The interview window lost focus. Return to your interview window.",
  fullscreen_exit: "The secure interview view was exited. Restore it to continue normally.",
  mobile_unavailable: "Phone monitoring was interrupted. Reopen its camera page, unlock the screen and keep it visible.",
};
export function proctoringNotice(message, type = "notice", source = "laptop") {
  const phone = source === "mobile" || source === "phone";
  const connection = ["connection", "interruption", "mobile_unavailable"].includes(type);
  const focus = ["tab_switch", "window_blur", "fullscreen_exit"].includes(type);
  const device = source === "monitoring" ? "Interview" : phone ? "Phone" : "Laptop";
  return { title: type === "notice" ? "Interview update" : `${device} ${connection ? "connection" : focus ? "focus" : "camera"} warning`,
    message: guidance[type] || message, recorded: type !== "notice" };
}
