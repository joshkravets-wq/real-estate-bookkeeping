#!/bin/bash
# RE Bookkeeping — one-time sync script
# Run this from your realestate-bookkeeping folder

echo "Enter your GitHub token:"
read -s TOKEN

REPO="https://${TOKEN}@github.com/joshkravets-wq/real-estate-bookkeeping.git"

# Update preload.js
cat > electron/preload.js << 'EOF'
const { contextBridge, ipcRenderer } = require('electron');

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
EOF

echo "✓ preload.js updated"

# Commit and push
git add .
git commit -m "fix: connectBank function and preload cleanup"
git remote set-url origin "$REPO"
git push origin main

echo ""
echo "✓ All done! Run: npm start"
