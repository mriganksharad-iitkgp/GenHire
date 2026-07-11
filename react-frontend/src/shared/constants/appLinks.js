// External/static app links, env-overridable per deployment.
// KIOSK_DOWNLOAD_URL: the secure-browser (Electron kiosk) installer download.
export const KIOSK_DOWNLOAD_URL =
  process.env.REACT_APP_KIOSK_DOWNLOAD_URL ||
  'https://storage.googleapis.com/genhire-downloads/Genhire.exe';
