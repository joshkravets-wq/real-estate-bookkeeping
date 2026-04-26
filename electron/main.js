const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const https = require('https');
const os = require('os');

// Load credentials from ~/.realestate-bookkeeping/.env
const credsPath = path.join(os.homedir(), '.realestate-bookkeeping', '.env');
if (fs.existsSync(credsPath)) {
  const lines = fs.readFileSync(credsPath, 'utf-8').split('\n');
  lines.forEach(line => {
    const [key, ...rest] = line.split('=');
    if (key && rest.length) process.env[key.trim()] = rest.join('=').trim();
  });
}

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#f5f5f3',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    icon: path.join(__dirname, 'assets', 'icon.png'),
  });

  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));

  // Auto-refresh every 5 minutes
  setInterval(() => {
    mainWindow.webContents.send('refresh-data');
  }, 5 * 60 * 1000);
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// IPC: Read local CSV files (for dev/offline mode)
ipcMain.handle('read-csv', async (event, filePath) => {
  try {
    return fs.readFileSync(filePath, 'utf-8');
  } catch (e) {
    return null;
  }
});

// IPC: Open external links
ipcMain.handle('open-external', (event, url) => {
  shell.openExternal(url);
});

// Open bank connection window
ipcMain.handle('open-connect-bank', () => {
  const connectWin = new BrowserWindow({
    width: 560,
    height: 520,
    parent: mainWindow,
    modal: true,
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    }
  });
  connectWin.loadFile(path.join(__dirname, 'src', 'connect-bank.html'));
});

// Save Plaid access token to local credentials file
ipcMain.handle('save-plaid-token', (event, accountKey, token) => {
  const tokenPath = path.join(os.homedir(), '.realestate-bookkeeping', `${accountKey}.token`);
  fs.writeFileSync(tokenPath, token, { mode: 0o600 });
  return true;
});

// Read Plaid access token
ipcMain.handle('get-plaid-token', (event, accountKey) => {
  const tokenPath = path.join(os.homedir(), '.realestate-bookkeeping', `${accountKey}.token`);
  if (fs.existsSync(tokenPath)) return fs.readFileSync(tokenPath, 'utf-8').trim();
  return null;
});

// Expose env variable to renderer (secrets only, not full env)
ipcMain.handle('get-env', (event, key) => {
  const allowed = ['PLAID_CLIENT_ID', 'PLAID_SECRET', 'PLAID_ENV'];
  if (allowed.includes(key)) return process.env[key] || null;
  return null;
});
