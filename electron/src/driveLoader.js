/**
 * Google Drive Data Loader
 * Fetches CSV processor exports from Drive and parses them into
 * transaction arrays for the aggregator dashboard.
 *
 * Setup:
 *   1. Create a Google Cloud project at console.cloud.google.com
 *   2. Enable the Google Drive API
 *   3. Create OAuth 2.0 credentials (Desktop app)
 *   4. Download the credentials JSON and save as electron/credentials.json
 *   5. On first launch, the app will open a browser for you to authorize
 *   6. After authorization, a token.json will be saved locally for future use
 *
 * File naming convention in Drive (Bookkeeping Processors folder):
 *   [LLC Name] - [Mon YYYY] - Processor.csv
 *   e.g. "10th Fairmount LLC - Jan 2026 - Processor.csv"
 */

const FOLDER_ID = '1VciFNCGCC2TAgzBZ9YgopY1V_vx0w99V';

// Parse a single CSV row value (handles quoted fields)
function parseCSVRow(row) {
  const result = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < row.length; i++) {
    if (row[i] === '"') {
      inQuotes = !inQuotes;
    } else if (row[i] === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += row[i];
    }
  }
  result.push(current.trim());
  return result;
}

// Parse a full CSV string into transaction objects
function parseCSV(csvText, llcName, month) {
  const lines = csvText.split('\n').filter(l => l.trim());
  if (lines.length < 2) return [];

  const headers = parseCSVRow(lines[0]).map(h => h.toLowerCase().replace(/\s+/g, '_'));
  const transactions = [];
  let inVendorSection = false;

  for (let i = 1; i < lines.length; i++) {
    const cols = parseCSVRow(lines[i]);
    if (!cols[0] && cols[1] && cols[1].includes('VENDOR')) {
      inVendorSection = true;
      continue;
    }
    if (inVendorSection) continue; // Vendor section handled separately

    const row = {};
    headers.forEach((h, idx) => { row[h] = cols[idx] || ''; });

    if (!row.date && !row.description) continue;

    transactions.push({
      llc: llcName,
      month: row.month || row.mo || month || '',
      date: row.date || '',
      description: row.description || '',
      detail: row.detail || '',
      amount: parseFloat((row.amount || '0').replace(/[+$,]/g, '')) || 0,
      qbAccount: row.qb_account || row['qb_account_→_class'] || '',
      class: row.class || '',
      type: row.type || '',
      checkNum: row['check#'] || '',
      status: row.status || 'matched',
    });
  }
  return transactions;
}

// Main function: fetch all processor CSVs from Drive and return unified dataset
async function loadAllData(accessToken) {
  if (!accessToken) {
    throw new Error('No access token provided. Please authorize the app first.');
  }

  // List all CSV files in the Bookkeeping Processors folder
  const listUrl = `https://www.googleapis.com/drive/v3/files?q=parents+in+'${FOLDER_ID}'+and+mimeType='text/csv'&fields=files(id,name,modifiedTime)`;
  const listResp = await fetch(listUrl, {
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  const listData = await listResp.json();
  const files = listData.files || [];

  const allTransactions = [];
  const fileIndex = [];

  for (const file of files) {
    // Parse LLC name and period from filename
    // Expected: "10th Fairmount LLC - Jan 2026 - Processor.csv"
    const nameParts = file.name.replace('.csv', '').split(' - ');
    const llcName = nameParts[0] || file.name;
    const period = nameParts[1] || '';

    // Download CSV content
    const dlUrl = `https://www.googleapis.com/drive/v3/files/${file.id}?alt=media`;
    const dlResp = await fetch(dlUrl, {
      headers: { Authorization: `Bearer ${accessToken}` }
    });
    const csvText = await dlResp.text();

    const txns = parseCSV(csvText, llcName, period);
    allTransactions.push(...txns);

    fileIndex.push({
      id: file.id,
      name: file.name,
      llc: llcName,
      period,
      modified: file.modifiedTime,
      transactionCount: txns.length,
    });
  }

  return { transactions: allTransactions, files: fileIndex };
}

// OAuth2 helper: get authorization URL
function getAuthURL(clientId, redirectUri) {
  const scopes = ['https://www.googleapis.com/auth/drive.readonly'];
  return `https://accounts.google.com/o/oauth2/v2/auth?` +
    `client_id=${clientId}&` +
    `redirect_uri=${encodeURIComponent(redirectUri)}&` +
    `response_type=code&` +
    `scope=${encodeURIComponent(scopes.join(' '))}&` +
    `access_type=offline&prompt=consent`;
}

// Exchange auth code for tokens
async function exchangeCode(code, clientId, clientSecret, redirectUri) {
  const resp = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      code, client_id: clientId, client_secret: clientSecret,
      redirect_uri: redirectUri, grant_type: 'authorization_code'
    })
  });
  return resp.json();
}

// Refresh an expired access token
async function refreshToken(refreshToken, clientId, clientSecret) {
  const resp = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      refresh_token: refreshToken, client_id: clientId,
      client_secret: clientSecret, grant_type: 'refresh_token'
    })
  });
  return resp.json();
}

module.exports = { loadAllData, parseCSV, getAuthURL, exchangeCode, refreshToken };
