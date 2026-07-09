// One-click download of a job's screening-cleared candidates.

import { requestBlob } from "shared/api/client";

export async function downloadScreeningClearedExport(jobId, format = "xlsx") {
  const blob = await requestBlob(
    `/jobs/${jobId}/screening-cleared/export?format=${format}`
  );
  return blob;
}

/** Trigger a browser download for a blob. */
export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
