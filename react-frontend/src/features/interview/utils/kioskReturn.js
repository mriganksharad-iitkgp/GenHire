// Browser authentication belongs to the launching tab, not the native window.
export function returnFromKiosk(bridge, launch, path) {
  bridge?.disableKiosk();
  if (!launch.returnToExistingTab) bridge?.openExternal(new URL(path, launch.webOrigin).href);
  bridge?.quitApp();
}
