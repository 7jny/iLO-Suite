const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const http = require('http');

let mainWindow = null;
let pythonProcess = null;
const ROOT_DIR = path.resolve(__dirname, '..');
const PORT = 5050;
const logHistory = [];
const MAX_LOG_HISTORY = 1000;

function addLog(source, level, message) {
  const timestamp = new Date().toLocaleTimeString('en-GB', { hour12: false });
  const logEntry = {
    id: Date.now() + Math.random().toString(36).substr(2, 4),
    timestamp,
    source,
    level,
    message: message.trimEnd()
  };

  logHistory.push(logEntry);
  if (logHistory.length > MAX_LOG_HISTORY) {
    logHistory.shift();
  }

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('backend-log', logEntry);
  }
}

function startPythonBackend() {
  addLog('SYSTEM', 'INFO', `Starting Python Backend on port ${PORT}...`);

  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
  const scriptPath = path.join(ROOT_DIR, 'backend', 'server.py');

  pythonProcess = spawn(pythonCmd, [scriptPath, String(PORT)], {
    cwd: ROOT_DIR,
    windowsHide: true,
    stdio: ['pipe', 'pipe', 'pipe']
  });

  pythonProcess.stdout.on('data', (data) => {
    const lines = data.toString().split(/\r?\n/);
    lines.forEach((line) => {
      if (!line.trim()) return;
      let level = 'INFO';
      let source = 'BACKEND';
      if (line.includes('[TlsBridge]')) {
        source = 'BRIDGE';
      } else if (line.includes('[ConsoleLauncher]')) {
        source = 'CONSOLE';
      }
      if (line.toLowerCase().includes('error') || line.toLowerCase().includes('fail')) {
        level = 'ERROR';
      } else if (line.toLowerCase().includes('warn')) {
        level = 'WARN';
      } else if (line.toLowerCase().includes('success') || line.includes('[OK]')) {
        level = 'OK';
      }
      addLog(source, level, line);
    });
  });

  pythonProcess.stderr.on('data', (data) => {
    const lines = data.toString().split(/\r?\n/);
    lines.forEach((line) => {
      if (!line.trim()) return;
      addLog('BACKEND', 'ERROR', line);
    });
  });

  pythonProcess.on('error', (err) => {
    addLog('SYSTEM', 'ERROR', `Failed to start Python process: ${err.message}`);
  });

  pythonProcess.on('exit', (code, signal) => {
    addLog('SYSTEM', 'WARN', `Python process exited with code ${code}, signal: ${signal}`);
    pythonProcess = null;
  });
}

function waitForServer(callback, maxAttempts = 30) {
  let attempts = 0;
  const check = () => {
    attempts++;
    const req = http.get(`http://127.0.0.1:${PORT}/api/status`, (res) => {
      if (res.statusCode === 200) {
        addLog('SYSTEM', 'OK', `Backend server is online and responding at http://127.0.0.1:${PORT}`);
        callback(true);
      } else {
        retry();
      }
    });

    req.on('error', () => retry());
    req.setTimeout(800, () => {
      req.destroy();
      retry();
    });
  };

  const retry = () => {
    if (attempts >= maxAttempts) {
      addLog('SYSTEM', 'WARN', 'Backend took longer than expected to start; loading UI anyway...');
      callback(false);
    } else {
      setTimeout(check, 300);
    }
  };

  check();
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1340,
    height: 860,
    minWidth: 1040,
    minHeight: 640,
    backgroundColor: '#0a0c10',
    title: 'iLO Suite',
    icon: path.join(__dirname, 'icon.png'),
    autoHideMenuBar: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    // Send historical logs collected during startup
    logHistory.forEach((log) => {
      mainWindow.webContents.send('backend-log', log);
    });
  });

  // Handle external link clicks (open in default system browser)
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Load the web app served by our local Python backend
  mainWindow.loadURL(`http://127.0.0.1:${PORT}/`);

  mainWindow.on('close', () => {
    cleanupProcesses();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC Handlers
ipcMain.handle('open-external', (_event, url) => {
  if (url) shell.openExternal(url);
  return true;
});

ipcMain.handle('get-backend-status', () => {
  return {
    running: pythonProcess !== null,
    port: PORT,
    logCount: logHistory.length
  };
});

ipcMain.handle('clear-logs', () => {
  logHistory.length = 0;
  return true;
});

ipcMain.handle('launch-console-native', async (_event, { type, params }) => {
  addLog('SYSTEM', 'INFO', `Native console launch requested: ${type}`);
  return { success: true };
});

ipcMain.handle('select-iso-file', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
    title: 'Select ISO Image',
    properties: ['openFile'],
    filters: [
      { name: 'Disk Images (*.iso, *.img)', extensions: ['iso', 'img'] },
      { name: 'All Files (*.*)', extensions: ['*'] }
    ]
  });
  if (!canceled && filePaths && filePaths.length > 0) {
    return filePaths[0];
  }
  return null;
});

// App Lifecycle
app.whenReady().then(() => {
  startPythonBackend();
  waitForServer(() => {
    createWindow();
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

let isShuttingDown = false;

function cleanupProcesses(doneCallback) {
  if (isShuttingDown) {
    if (doneCallback) doneCallback();
    return;
  }
  isShuttingDown = true;
  addLog('SYSTEM', 'INFO', 'Clean shutdown initiated. Terminating proxy and backend services...');

  // 1. Notify Python backend to shutdown all services gracefully
  try {
    const req = http.request({
      hostname: '127.0.0.1',
      port: PORT,
      path: '/api/shutdown',
      method: 'POST',
      timeout: 300
    });
    req.on('error', () => {});
    req.end();
  } catch (_) {}

  // 2. Kill Python backend process tree
  if (pythonProcess) {
    try {
      const pid = pythonProcess.pid;
      if (process.platform === 'win32') {
        exec(`taskkill /F /T /PID ${pid}`, () => {});
      } else {
        pythonProcess.kill('SIGKILL');
      }
    } catch (_) {}
    pythonProcess = null;
  }

  // 3. Guarantee all proxy, bridge, and backend listeners are stopped
  if (process.platform === 'win32') {
    try {
      exec(`powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 5050,8089,8443,8088 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"`, () => {
        if (doneCallback) doneCallback();
      });
      return;
    } catch (_) {}
  }

  if (doneCallback) doneCallback();
}

app.on('before-quit', (e) => {
  cleanupProcesses();
});

app.on('will-quit', () => {
  cleanupProcesses();
});

process.on('exit', () => {
  cleanupProcesses();
});

app.on('window-all-closed', () => {
  cleanupProcesses(() => {
    app.quit();
  });
});
