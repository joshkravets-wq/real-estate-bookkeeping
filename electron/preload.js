const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  readCSV: (filePath) => ipcRenderer.invoke('read-csv', filePath),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  onRefresh: (callback) => ipcRenderer.on('refresh-data', callback),
  platform: process.platform,
});

// Plaid connection helpers
contextBridge.exposeInMainWorld('electronAPI', {
  readCSV: (filePath) => ipcRenderer.invoke('read-csv', filePath),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  onRefresh: (callback) => ipcRenderer.on('refresh-data', callback),
  openConnectBank: () => ipcRenderer.invoke('open-connect-bank'),
  savePlaidToken: (key, token) => ipcRenderer.invoke('save-plaid-token', key, token),
  getPlaidToken: (key) => ipcRenderer.invoke('get-plaid-token', key),
  getEnv: (key) => ipcRenderer.invoke('get-env', key),
  platform: process.platform,
});
