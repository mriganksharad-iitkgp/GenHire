# macOS Executable Build Guide (.dmg)

This guide provides instructions on how to configure, package, and build the macOS executable (`.dmg` file) for the **Genhire Secure Browser Kiosk** application. 

Since Electron is cross-platform, the same codebase works on macOS. However, packaging requires specific configurations and must be built on a macOS operating system.

---

## 📋 1. Prerequisites for macOS Build

1. **A macOS Machine**: You cannot package a macOS application (`.dmg` or `.app` bundle) on Windows due to Apple's tooling requirements. If you do not have a Mac, you can run this command in a macOS runner inside a **CI/CD pipeline** (like GitHub Actions).
2. **Node.js (v16+) & npm**: Installed on the macOS environment.
3. **App Icon (`.icns`)**: macOS uses the `.icns` format rather than the Windows `.ico` format. 
   - Put your macOS icon file in: `secure-browser-kiosk/build/genhire_logo.icns`

---

## 🛠️ 2. Required Changes in `package.json`

To enable macOS packaging, we must add macOS-specific configurations and build scripts to your [package.json](file:///c:/Users/aditya/Documents/GitHub/product-prototyping-lab/secure-browser-kiosk/package.json).

### The Complete Diff

Here are the changes added to support macOS:

```diff
  "scripts": {
    "start": "electron .",
    "start:webgazer-test": "electron ./test-webgazer",
    "smoke:gaze": "npx --yes serve@14 . -l 3333",
    "test": "echo \"Error: no test specified\" && exit 1",
-   "build": "electron-builder --win",
-   "dist": "electron-builder --win --x64"
+   "build": "electron-builder --win",
+   "build:win": "electron-builder --win",
+   "build:mac": "electron-builder --mac",
+   "dist:win": "electron-builder --win --x64",
+   "dist:mac": "electron-builder --mac --universal"
  },
  "build": {
    "appId": "com.genhire.securebrowser",
    "productName": "Genhire",
    "artifactName": "Genhire.${ext}",
    ...
    "win": {
      "target": "nsis",
      "icon": "build/genhire_logo.ico"
    },
    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true,
      "createDesktopShortcut": true,
      "createStartMenuShortcut": true
-   }
+   },
+   "mac": {
+     "target": [
+       "dmg",
+       "zip"
+     ],
+     "category": "public.app-category.utilities",
+     "icon": "build/genhire_logo.icns"
+   },
+   "dmg": {
+     "contents": [
+       {
+         "x": 410,
+         "y": 220,
+         "type": "link",
+         "path": "/Applications"
+       },
+       {
+         "x": 130,
+         "y": 220,
+         "type": "file"
+       }
+     ]
+   }
  }
```

### Explanations of `package.json` Additions

| Key Name | Location | Description |
| :--- | :--- | :--- |
| `"build:mac"` | `scripts` | Triggers the build runner for macOS (`electron-builder --mac`). |
| `"dist:mac"` | `scripts` | Builds a universal production-ready macOS binary (`--mac --universal`) supporting both Intel and Apple Silicon Macs. |
| `"mac"` | `build` | macOS-specific compiler configuration specifying target formats (`dmg`, `zip`), categorizing the app, and linking the `.icns` icon. |
| `"dmg"` | `build` | Configures the visual layout of the DMG installer window. Position `x: 410, y: 220` is the shortcut linking to the Mac's `/Applications` directory, allowing a simple drag-and-drop installation. |

---

## 🚀 3. Step-by-Step Packaging Instructions

Once the configurations are saved, follow these steps on a macOS terminal:

### Step 1: Open the Project Directory
Navigate into the kiosk directory:
```bash
cd secure-browser-kiosk
```

### Step 2: Install Node Dependencies
Install all modules (including `electron-builder` and `electron`):
```bash
npm install
```

### Step 3: Run the Build Script
Run the newly created build script targeting macOS:
```bash
npm run build:mac
```
*Alternatively, for a universal app that supports both Intel and Apple Silicon chips natively, run:*
```bash
npm run dist:mac
```

### Step 4: Locate the Output Executable
After compilation, a new folder named `dist` will be created inside `secure-browser-kiosk/`.
* You will find the installer file here: **`dist/Genhire.dmg`**

---

## 🔒 4. Bypassing macOS Gatekeeper (For Development)

By default, Apple blocks apps not downloaded from the App Store or signed by a verified developer. When trying to run your `.dmg` or `.app` file, you might see a warning saying **"App is damaged and can't be opened"** or **"Unidentified Developer"**.

### Option A: Right-Click to Open (Fastest)
1. Go to your `/Applications` folder where you dragged the app.
2. **Right-click (or Control+Click)** the app icon and select **Open**.
3. In the dialog box, click **Open** to run the app anyway.

### Option B: Terminal Command
Run this in the Mac terminal to remove the Gatekeeper quarantine attribute:
```bash
xattr -cr /Applications/Genhire.app
```

---

## 🔑 5. Code Signing and Notarization (For Production Distribution)

If you plan to release the app to general candidates on macOS without any security warnings, you must sign and notarize it.

### Step 1: Create an Apple Developer Account
Go to [developer.apple.com](https://developer.apple.com/) and register (requires a paid $99/year subscription).

### Step 2: Create a Developer Certificate
1. On your Mac, open **Keychain Access**.
2. Request a certificate from a Certificate Authority.
3. In the Apple Developer portal, create a **Developer ID Application** certificate and download/install it to your Mac Keychain.

### Step 3: Configure Environment Variables
Before running the build, export your Apple ID credentials in the terminal:
```bash
export APPLE_ID="your-apple-id@email.com"
export APPLE_ID_PASSWORD="your-app-specific-password" # Created in appleid.apple.com under security
export APPLE_TEAM_ID="YOUR_TEAM_ID"
```

### Step 4: Run Signed Build
With your certificates present in your Mac's Keychain and environment variables loaded, run:
```bash
npm run dist:mac
```
`electron-builder` will automatically detect your **Developer ID Application** certificate, sign the binary, and upload it to Apple's notarization servers.
