/**
 * Plaid Integration Module
 * Pulls transactions directly from connected bank accounts.
 *
 * Banks connected:
 *   - TD Bank #430-3139011 (10th Fairmount LLC)
 *   - Penn Community #XXXXXXX3869 (10th Fairmount LLC)
 *   - Penn Community #XXXXXXX3395 (GJ Holdings LLC)
 *
 * Setup:
 *   Credentials are stored in ~/.realestate-bookkeeping/.env
 *   Never hardcode credentials in this file.
 */

const PLAID_BASE_URL = 'https://sandbox.plaid.com'; // change to production.plaid.com when ready

// Read credentials from environment
function getCredentials() {
  return {
    client_id: process.env.PLAID_CLIENT_ID,
    secret: process.env.PLAID_SECRET,
  };
}

// Create a link token — used to launch Plaid Link (the bank login UI)
async function createLinkToken(userId) {
  const creds = getCredentials();
  const resp = await fetch(`${PLAID_BASE_URL}/link/token/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...creds,
      user: { client_user_id: userId },
      client_name: 'RE Bookkeeping',
      products: ['transactions'],
      country_codes: ['US'],
      language: 'en',
    }),
  });
  const data = await resp.json();
  if (data.error_code) throw new Error(`Plaid error: ${data.error_message}`);
  return data.link_token;
}

// Exchange public token (from Plaid Link) for access token
async function exchangePublicToken(publicToken) {
  const creds = getCredentials();
  const resp = await fetch(`${PLAID_BASE_URL}/item/public_token/exchange`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...creds, public_token: publicToken }),
  });
  const data = await resp.json();
  if (data.error_code) throw new Error(`Plaid error: ${data.error_message}`);
  return data.access_token;
}

// Pull transactions for a connected account
async function getTransactions(accessToken, startDate, endDate) {
  const creds = getCredentials();
  let transactions = [];
  let hasMore = true;
  let cursor = null;

  // Use transactions/sync for incremental updates
  while (hasMore) {
    const body = { ...creds, access_token: accessToken };
    if (cursor) body.cursor = cursor;

    const resp = await fetch(`${PLAID_BASE_URL}/transactions/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (data.error_code) throw new Error(`Plaid error: ${data.error_message}`);

    transactions = transactions.concat(data.added || []);
    hasMore = data.has_more;
    cursor = data.next_cursor;
  }

  // Filter by date range
  return transactions
    .filter(t => t.date >= startDate && t.date <= endDate)
    .map(t => ({
      date: t.date,
      description: t.name,
      amount: -t.amount, // Plaid uses positive for debits, we flip it
      pending: t.pending,
      accountId: t.account_id,
      transactionId: t.transaction_id,
      category: t.category,
      merchantName: t.merchant_name,
    }));
}

// Get account balances
async function getBalances(accessToken) {
  const creds = getCredentials();
  const resp = await fetch(`${PLAID_BASE_URL}/accounts/balance/get`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...creds, access_token: accessToken }),
  });
  const data = await resp.json();
  if (data.error_code) throw new Error(`Plaid error: ${data.error_message}`);

  return data.accounts.map(a => ({
    accountId: a.account_id,
    name: a.name,
    mask: a.mask, // last 4 digits
    type: a.type,
    subtype: a.subtype,
    currentBalance: a.balances.current,
    availableBalance: a.balances.available,
  }));
}

module.exports = { createLinkToken, exchangePublicToken, getTransactions, getBalances };
