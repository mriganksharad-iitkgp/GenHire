// Identity-card endpoints. The upload is one-time: once a card is on file the
// backend answers 409 and only an admin can replace or reset it.

import { request, requestBlob } from "shared/api/client";

export const getIdentityCardStatus = () => request("/identity-card");

export const uploadIdentityCard = (file) => {
  const formData = new FormData();
  formData.append("identity_card", file);
  return request("/identity-card", { method: "POST", body: formData });
};

export const viewIdentityCard = () => requestBlob("/identity-card/image");
