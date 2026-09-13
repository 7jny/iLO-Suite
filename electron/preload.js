const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  isElectron: true,
  onLog: (callback) => {
    ipcRenderer.on('backend-log', (_event, logData) => {
      callback(logData);
    });
  },
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  launchConsoleNative: (type, params) => ipcRenderer.invoke('launch-console-native', { type, params }),
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  clearLogs: () => ipcRenderer.invoke('clear-logs'),
  selectIsoFile: () => ipcRenderer.invoke('select-iso-file')
});
