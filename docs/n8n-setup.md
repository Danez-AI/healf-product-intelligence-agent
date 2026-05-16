# n8n Catalog Audit — End-to-End Setup Guide

This guide walks through running the full Healf catalog audit automation: your Windows PC runs the `webhook.py` FastAPI server, your HP home server runs n8n, and the workflow ties them together.

---

## Architecture

```
HP Home Server (192.168.0.87)          Windows PC (your LAN IP)
┌─────────────────────────┐            ┌──────────────────────────────┐
│  n8n (Docker, port 5678) │──POST──→  │  webhook.py (uvicorn, :8000)  │
│  godfather.daran.in      │           │  → fetch_product              │
│                          │           │  → evaluate_listing_quality   │
│  Schedule: daily 09:00   │  ←JSON─── │  → draft_rewrite              │
│  IF score < 3 → Slack    │           │  → enqueue_hitl               │
└─────────────────────────┘            └──────────────────────────────┘
```

**Workflow nodes:** Schedule → Config → URL List → Split In Batches → POST /audit → IF score < 3 → Notify Slack

The **Config** node holds your two URLs in one place — no environment variables needed.

---

## Step 1 — Find your Windows PC's local IP

Run this in PowerShell on your Windows machine:

```powershell
ipconfig | Select-String "IPv4"
```

Look for the address under your Wi-Fi or Ethernet adapter (e.g. `192.168.0.42`). The HP home server will call this address to reach the webhook.

---

## Step 2 — Start the webhook server on your Windows PC

From the worktree directory:

```powershell
cd "C:\Users\Daran\AI\Healf AI Agent\.claude\worktrees\feat-healf-agent"
python -m uv run uvicorn webhook:app --host 0.0.0.0 --port 8000
```

Confirm it's up — you should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**Quick smoke test from another terminal:**
```powershell
Invoke-RestMethod -Uri http://localhost:8000/health
# Expected: {"status":"ok"}
```

**If Windows Firewall blocks the connection** (n8n on the home server can't reach port 8000):
```powershell
# Run once in an elevated PowerShell
New-NetFirewallRule -DisplayName "Healf Webhook" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

---

## Step 3 — Get a Slack incoming webhook URL

If you want Slack alerts when a listing scores below 3/5:

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Pick a name (e.g. "Healf Audit Bot") and your workspace
3. **Incoming Webhooks** → toggle **On** → **Add New Webhook to Workspace**
4. Pick a channel (e.g. `#healf-alerts`) → **Allow**
5. Copy the webhook URL — looks like: `https://hooks.slack.com/services/T.../B.../...`

If you want to skip Slack for now, leave the placeholder in the Config node — the workflow has error handling so a failed Slack call won't stop the audit.

---

## Step 4 — Import the workflow into n8n

1. Open n8n: `http://192.168.0.87:5678`
2. Click **+** (New Workflow) in the top-left
3. Click the **⋮** menu (top-right) → **Import from File**
4. Select `n8n/healf-catalog-audit.json` from this repo
5. The workflow loads — 7 nodes visible

---

## Step 5 — Fill in the Config node

This is the only configuration step. Everything else is already wired.

1. Click the **Config** node (second from left, after Schedule)
2. You'll see two fields:

| Field | Placeholder | Replace with |
|-------|-------------|--------------|
| `webhookUrl` | `http://YOUR_WINDOWS_IP:8000` | Your Windows PC's LAN IP, e.g. `http://192.168.0.42:8000` |
| `slackUrl` | `https://hooks.slack.com/services/REPLACE_ME` | Your Slack incoming webhook URL from Step 3 |

3. Click **Save** (or click outside the node panel)

That's it — no environment variables, no Docker restart needed.

---

## Step 6 — Run a manual test

Click **Execute Workflow** (▶ button, top-right of the editor). This bypasses the schedule and runs immediately.

**What you should see step by step:**

| Node | Expected output |
|------|----------------|
| Schedule | Skipped (manual trigger) |
| Config | 1 item: `{webhookUrl: "http://...", slackUrl: "https://..."}` |
| URL List | 1 item: `{url: "https://healf.com/en-uk/products/lmnt-..."}` |
| Split In Batches | Passes item through (batch 1 of 1) |
| POST /audit | JSON response: `{product_handle, score, gaps, hitl_id, draft}` |
| IF score < 3 | Routes **true** if score < 3, **false** otherwise |
| Notify Slack | Fires if score < 3; skipped otherwise |

**Typical audit response from the webhook:**
```json
{
  "product_handle": "lmnt-recharge-electrolytes-variety-pack",
  "score": 2.4,
  "gaps": ["Description too short", "No mg figures", "No serving count"],
  "hitl_id": 1,
  "draft": "LMNT Recharge Electrolytes cuts through the noise..."
}
```

A `score` of `2.4` is below the `3.0` threshold → Notify Slack fires.

---

## Step 7 — Add more product URLs

Open the **URL List** Code node and edit the array:

```javascript
const urls = [
  'https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack',
  'https://healf.com/en-uk/products/precision-hydration-1500',
  'https://healf.com/en-uk/products/humantra-hydration-electrolytes'
];
return urls.map(url => ({ json: { url } }));
```

Each URL is processed one at a time (batch size 1) so the webhook server isn't overwhelmed.

---

## Step 8 — Activate for the daily schedule

Once the manual test passes:

1. Click the **Inactive** toggle (top-right of editor) → **Active**
2. The workflow now runs automatically at **09:00 UTC daily**
3. Monitor runs: left sidebar → **Executions**

---

## Score scale

The `score` in the audit response is averaged across evaluation dimensions, on a **0–5 scale**:

| Score | Meaning |
|-------|---------|
| 4–5 | Strong listing — no action needed |
| 3–4 | Acceptable — minor improvements possible |
| < 3 | Weak listing — Slack alert fires, draft queued to HITL |

---

## Troubleshooting

**POST /audit node fails with "connection refused"**
- Check the webhook server is still running on Windows (`uvicorn` process alive in the terminal)
- Check Windows Firewall isn't blocking port 8000 (Step 2)
- Confirm the `webhookUrl` in the Config node matches your Windows PC's actual LAN IP — run `ipconfig` again if unsure

**POST /audit returns 400 "URL must be on healf.com"**
- The URL in the URL List Code node must start with `https://healf.com/` — check for typos

**POST /audit times out (> 120s)**
- The webhook runs fetch + eval + rewrite in sequence — 30–90s on first run is normal (cold Playwright + API calls). If it consistently times out, increase `timeout` in the POST /audit node → Options

**Slack node fails**
- Workflow continues anyway (`onError: continueRegularOutput`) — verify the `slackUrl` in the Config node is the full `https://hooks.slack.com/services/...` URL and the Slack app is still active

**Config node values not reaching POST /audit**
- The expression `={{ $('Config').first().json.webhookUrl }}` references the Config node by name — if you renamed the node, update the expression in POST /audit and Notify Slack to match
