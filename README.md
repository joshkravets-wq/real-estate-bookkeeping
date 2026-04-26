# Real Estate Bookkeeping Dashboard

A desktop app for real-time portfolio bookkeeping across multiple LLCs. Reads processed transaction CSVs from Google Drive and renders an interactive dashboard.

## Architecture

```
Google Drive (source of truth)
  └── Bookkeeping Processors/
      ├── 10th Fairmount LLC - Jan 2026 - Processor.csv
      ├── 10th Fairmount LLC - Feb 2026 - Processor.csv
      ├── GJ Holdings LLC - Jan-Mar 2026 - Processor.csv
      └── [future months / LLCs...]

Electron Desktop App (this repo)
  ├── Reads CSVs from Drive via Google Drive API
  ├── Parses and aggregates all transaction data
  ├── Renders dashboard with 9 views
  └── Auto-refreshes every 5 minutes
```

## Folder Structure

```
real-estate-bookkeeping/
├── electron/
│   ├── main.js          ← Electron main process
│   ├── preload.js       ← Secure IPC bridge
│   └── src/
│       ├── index.html   ← Dashboard UI (aggregator)
│       └── driveLoader.js ← Google Drive API client
├── processors/          ← Individual HTML processor files (archived)
│   ├── 10th_Fairmount_Jan2026_FINAL.html
│   ├── 10th_Fairmount_Feb2026_FINAL.html
│   ├── 10th_Fairmount_Mar2026_FINAL.html
│   └── GJ_Holdings_JanMar2026_FINAL.html
├── aggregator/
│   └── Portfolio_Aggregator_JanMar2026.html  ← Standalone aggregator
├── rules/
│   └── Bookkeeping_Rules.md  ← All routing rules and system documentation
├── package.json
└── README.md
```

## Setup

### 1. Prerequisites
- Node.js v18+ (check: `node --version`)
- A Google account with the bookkeeping Drive folder

### 2. Install dependencies
```bash
npm install
```

### 3. Google Drive API setup
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project called "RE Bookkeeping"
3. Enable the **Google Drive API**
4. Go to **Credentials** → Create credentials → **OAuth 2.0 Client ID**
5. Application type: **Desktop app**
6. Download the JSON and save as `electron/credentials.json`

> ⚠️ `credentials.json` and `token.json` are in `.gitignore` — never commit these.

### 4. Run the app
```bash
npm start
```

On first launch, the app will open a browser window asking you to authorize Google Drive access. After authorizing, a `token.json` is saved locally and you won't need to authorize again.

### 5. Build a distributable .app
```bash
npm run build-mac
```
The `.dmg` installer will be in the `dist/` folder.

## Adding New Data

When a new month is reconciled:
1. Open the processor HTML file for that LLC/month
2. Click **Export CSV** in the processor
3. Save the CSV to your Drive **Bookkeeping Processors** folder
4. Name it: `[LLC Name] - [Mon YYYY] - Processor.csv`
5. The app will pick it up automatically on next refresh (or relaunch)

## LLCs in System

| LLC | Processed | Bank Accounts |
|---|---|---|
| 10th Fairmount LLC | Jan–Mar 2026 ✓ | TD Bank 430-3139011, Penn Community XXXXXXX3869 |
| GJ Holdings LLC | Jan–Mar 2026 ✓ | Penn Community XXXXXXX3395 |
| Cambria Group LLC | Pending | — |
| Veit LLC | Pending | — |
| Phily Properties LLC | Pending | — |
| VJ Assets LLC | Pending | — |

## Drive Folder IDs (for reference)

| Folder | ID |
|---|---|
| Bank Statements root | 1WvWqQr1o1yLXn3fs066nsSedl45oJ45F |
| Bookkeeping Processors | 1VciFNCGCC2TAgzBZ9YgopY1V_vx0w99V |
| RentRedi | 1M9o5sorXCSdrKQ25FR7GyWTzQ6BHipzO |

## Version History

| Version | Date | Notes |
|---|---|---|
| v1.0.0 | Apr 2026 | Initial release — 10th Fairmount + GJ Holdings Jan–Mar 2026 |

## Bookkeeping Rules

See `rules/Bookkeeping_Rules.md` for all routing rules, property classifications, and system decisions. This file is updated each bookkeeping session.
