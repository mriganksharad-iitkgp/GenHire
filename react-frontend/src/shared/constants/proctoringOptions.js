// Shared recruiter labels; option keys remain the API contract.
export const PROCTORING_OPTIONS = [
  { key:"dual_camera", label:"Require a second camera", desc:"Pair a phone to provide a side view of the workspace. Both cameras must be ready before the interview.", icon:"fa-mobile" },
  { key:"voice_detection", label:"Audio monitoring", desc:"Review speech activity, pauses and additional audio signals.", icon:"fa-microphone" },
  { key:"object_detection", label:"Camera monitoring", desc:"Flag additional faces, phones and supported objects for review.", icon:"fa-video-camera" },
  { key:"eyeball_tracking", label:"Gaze monitoring", desc:"Track estimated gaze direction when this check is available.", icon:"fa-eye" },
  { key:"gaze_heatmap", label:"Gaze heatmap", desc:"Include a visual summary of estimated screen attention when available.", icon:"fa-map-o" },
  { key:"ai_detection", label:"Answer-pattern review", desc:"Flag response patterns for review. This signal does not establish AI use.", icon:"fa-commenting-o" },
];
