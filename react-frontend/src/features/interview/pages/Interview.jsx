import React from "react";
import { useParams } from "react-router-dom";
import Chat from "./Chat";
// Session ownership, identity prerequisites and monitoring policy are checked by the API.
export default function Interview() {
  const { interviewId } = useParams();
  return <Chat interviewId={interviewId} />;
}
