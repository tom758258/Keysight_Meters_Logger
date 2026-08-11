const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const readline = require("node:readline");

const { app, BrowserWindow, dialog, screen } = require("electron");

const SHUTDOWN_COMMAND = `${JSON.stringify({ command: "shutdown" })}\n`;

let backendProcess = null;
let mainWindow = null;
let allowedOrigin = null;
let backendReady = false;
let shutdownPending = false;
let allowAppExit = false;
let fatalErrorShown = false;

function backendIsRunning() {
  return (
    backendProcess !== null &&
    backendProcess.exitCode === null &&
    backendProcess.signalCode === null
  );
}

function showFatalError(message) {
  if (fatalErrorShown) {
    return;
  }
  fatalErrorShown = true;
  dialog.showErrorBox("Meters Tool", message);
}

function showShutdownIncomplete(message) {
  const options = {
    type: "warning",
    title: "Meters Tool",
    message: "Cleanup is not complete.",
    detail: message || "Close the window again later to retry graceful shutdown.",
  };
  if (mainWindow && !mainWindow.isDestroyed()) {
    void dialog.showMessageBox(mainWindow, options);
  } else {
    void dialog.showMessageBox(options);
  }
}

function requestBackendShutdown() {
  if (!backendIsRunning() || shutdownPending) {
    return;
  }

  shutdownPending = true;
  backendProcess.stdin.write(SHUTDOWN_COMMAND, (error) => {
    if (!error) {
      return;
    }
    shutdownPending = false;
    showShutdownIncomplete(`Could not request graceful shutdown: ${error.message}`);
  });
}

function requestDesktopExit() {
  if (!backendIsRunning()) {
    allowAppExit = true;
    app.quit();
    return;
  }
  requestBackendShutdown();
}

function handleElectronFatalError(message) {
  showFatalError(message);
  if (backendIsRunning()) {
    requestBackendShutdown();
    return;
  }
  allowAppExit = true;
  app.quit();
}

function parseReadyUrl(value) {
  if (typeof value !== "string") {
    return null;
  }
  try {
    const readyUrl = new URL(value);
    if (
      readyUrl.protocol !== "http:" ||
      readyUrl.hostname !== "127.0.0.1" ||
      readyUrl.port === ""
    ) {
      return null;
    }
    return readyUrl;
  } catch {
    return null;
  }
}

function navigationIsAllowed(targetUrl) {
  try {
    return new URL(targetUrl).origin === allowedOrigin;
  } catch {
    return false;
  }
}

async function createMainWindow(readyUrl) {
  const { width: workWidth, height: workHeight } =
    screen.getPrimaryDisplay().workAreaSize;
  const window = new BrowserWindow({
    width: Math.min(1920, workWidth),
    height: Math.min(1080, workHeight),
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
    },
  });
  mainWindow = window;

  const guardNavigation = (event, targetUrl) => {
    if (!navigationIsAllowed(targetUrl)) {
      event.preventDefault();
    }
  };
  window.webContents.on("will-navigate", guardNavigation);
  window.webContents.on("will-redirect", guardNavigation);
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));

  window.on("close", (event) => {
    if (allowAppExit || !backendIsRunning()) {
      return;
    }
    event.preventDefault();
    requestDesktopExit();
  });
  window.on("closed", () => {
    if (mainWindow === window) {
      mainWindow = null;
    }
  });

  try {
    await window.loadURL(readyUrl.href);
    if (!window.isDestroyed()) {
      window.show();
    }
  } catch (error) {
    handleElectronFatalError(`Could not load the Desktop WebUI: ${error.message}`);
  }
}

function handleBackendEvent(event) {
  if (!event || typeof event !== "object" || Array.isArray(event)) {
    return;
  }

  if (event.event === "ready" && !backendReady) {
    const readyUrl = parseReadyUrl(event.url);
    if (!readyUrl) {
      handleElectronFatalError("The Desktop backend returned an invalid local URL.");
      return;
    }
    backendReady = true;
    allowedOrigin = readyUrl.origin;
    void createMainWindow(readyUrl);
    return;
  }

  if (event.event === "shutdown_incomplete") {
    shutdownPending = false;
    showShutdownIncomplete(
      typeof event.message === "string" ? event.message : "Backend cleanup is still running."
    );
    return;
  }

  if (event.event === "error") {
    const message = typeof event.message === "string" ? event.message : "Unknown backend error.";
    showFatalError(`The Desktop backend could not continue: ${message}`);
  }
}

function backendCommand() {
  const repositoryRoot = path.resolve(__dirname, "..");
  if (app.isPackaged) {
    return {
      command: path.join(process.resourcesPath, "backend", "meters-tool-webui-host.exe"),
      args: [],
      cwd: undefined,
    };
  }

  const hostSource = path.join(
    repositoryRoot,
    "src",
    "meters_tool_webui",
    "_desktop_host.py"
  );
  if (!fs.existsSync(hostSource)) {
    throw new Error(`Desktop WebUI host not found: ${hostSource}`);
  }
  return {
    command: path.join(repositoryRoot, ".venv", "Scripts", "python.exe"),
    args: ["-m", "meters_tool_webui._desktop_host"],
    cwd: repositoryRoot,
  };
}

function startBackend() {
  let launch;
  try {
    launch = backendCommand();
    if (!fs.existsSync(launch.command)) {
      throw new Error(`Desktop backend executable not found: ${launch.command}`);
    }
  } catch (error) {
    showFatalError(error.message);
    allowAppExit = true;
    app.quit();
    return;
  }

  const options = {
    windowsHide: true,
    stdio: ["pipe", "pipe", "pipe"],
  };
  if (launch.cwd) {
    options.cwd = launch.cwd;
  }

  const child = spawn(launch.command, launch.args, options);
  backendProcess = child;
  child.stderr.pipe(process.stderr);

  const lines = readline.createInterface({
    input: child.stdout,
    crlfDelay: Infinity,
  });
  lines.on("line", (line) => {
    try {
      handleBackendEvent(JSON.parse(line));
    } catch {
      // The private host contract reserves stdout for JSONL lifecycle events.
    }
  });

  let spawnFailed = false;
  child.once("error", (error) => {
    spawnFailed = true;
    if (backendProcess === child) {
      backendProcess = null;
    }
    showFatalError(`Could not start the Desktop backend: ${error.message}`);
    allowAppExit = true;
    app.quit();
  });
  child.once("close", (code, signal) => {
    if (spawnFailed) {
      return;
    }
    const gracefulExit = shutdownPending && code === 0;
    if (backendProcess === child) {
      backendProcess = null;
    }
    shutdownPending = false;

    if (!gracefulExit && !fatalErrorShown) {
      const detail = signal ? `signal ${signal}` : `exit code ${code}`;
      showFatalError(`The Desktop backend exited unexpectedly (${detail}).`);
    }

    allowAppExit = true;
    app.quit();
  });
}

app.on("before-quit", (event) => {
  if (allowAppExit || !backendIsRunning()) {
    return;
  }
  event.preventDefault();
  requestDesktopExit();
});

app.on("window-all-closed", () => {
  if (!backendIsRunning()) {
    allowAppExit = true;
    app.quit();
  }
});

app.whenReady().then(startBackend).catch((error) => {
  handleElectronFatalError(`Desktop startup failed: ${error.message}`);
});
