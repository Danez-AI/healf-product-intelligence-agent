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

---

## Step 1 — Find your Windows PC's local IP

Run this in PowerShell on your Windows machine:

```powershell
ipconfig | Select-String "IPv4"
```

Look for the address under your Wi-Fi or Ethernet adapter (e.g. `192.168.0.42`). This is your `WINDOWS_IP`. The HP server will call this address.

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

**If Windows Firewall blocks the server** (n8n on the home server can't reach it):
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
4. Pick the channel (e.g. `#healf-alerts`) → **Allow**
5. Copy the webhook URL — looks like: `https://hooks.slack.com/services/T.../B.../...`

If you don't have Slack or want to skip alerts for now, set `SLACK_WEBHOOK_URL` to any placeholder — the workflow has error handling so a failed Slack call won't stop the audit.

---

## Step 4 — Restart n8n with the two new environment variables

SSH into the home server:

```bash
ssh daran@192.168.0.87
```

Stop the existing n8n container and restart it with two extra env vars. Replace `<WINDOWS_IP>` and `<SLACK_URL>` with your values:

```bash
docker stop n8n && docker rm n8n

docker run -d \
  --name n8n \
  --restart unless-stopped \
  -e N8N_SECURE_COOKIE=false \
  -e WEBHOOK_URL=https://godfather.daran.in \
  -e N8N_RESTRICT_FILE_ACCESS_TO=/home/node/invoices \
  -e N8N_RUNNERS_DISABLED=true \
  -e HEALF_WEBHOOK_URL=http://<WINDOWS_IP>:8000 \
  -e SLACK_WEBHOOK_URL=<SLACK_URL> \
  -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  -v /home/daran/softlife/data/invoices:/home/node/invoices \
  docker.n8n.io/n8nio/n8n
```

**Example** with `192.168.0.42` and a Slack URL:
```bash
  -e HEALF_WEBHOOK_URL=http://192.168.0.42:8000 \
  -e SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../... \
```

Verify n8n is back up: open `http://192.168.0.87:5678` in a browser.

---

## Step 5 — Import the workflow into n8n

1. Open n8n: `http://192.168.0.87:5678`
2. Click **+** (New Workflow) in the top-left, then the **⋮** menu → **Import from File**
3. Select: `n8n/healf-catalog-audit.json` from this repo
4. The workflow loads — 6 nodes visible: Schedule → URL List → Split In Batches → POST /audit → IF score < 3 → Notify Slack

---

## Step 6 — Verify env vars are visible inside n8n

In the n8n workflow editor, click the **POST /audit** node. The URL field shows:
```
={{ $env.HEALF_WEBHOOK_URL }}/audit
```

To confirm n8n can see the env var: open the n8n **Settings** → **Environment** tab, or add a temporary Code node with:
```javascript
return [{ json: { url: $env.HEALF_WEBHOOK_URL } }];
```
Execute it — if it returns your Windows IP, the env var is wired correctly.

---

## Step 7 — Run a manual test

Click **Execute Workflow** (▶ button, top-right of the editor). This bypasses the schedule and runs immediately.

**What you should see:**

| Node | Expected output |
|------|----------------|
| Schedule | Skipped (manual run) |
| URL List | 1 item: `{url: "https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack"}` |
| Split In Batches | Passes item through (batch 1 of 1) |
| POST /audit | JSON response: `{product_handle, score, gaps, hitl_id, draft}` |
| IF score < 3 | Routes to **true** branch if score < 3, **false** branch otherwise |
| Notify Slack | Fires if score < 3; otherwise skipped |

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

## Step 8 — Add more URLs to the audit list

Open the **URL List** Code node. Edit the array:

```javascript
const urls = [
  'https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack',
  'https://healf.com/en-uk/products/precision-hydration-1500',
  'https://healf.com/en-uk/products/humantra-hydration-electrolytes'
];
return urls.map(url => ({ json: { url } }));
```

Each URL becomes one item — the workflow processes them one at a time (batch size 1) so the webhook server isn't overwhelmed.

---

## Step 9 — Activate for the daily schedule

Once the manual test passes:

1. Click the **Inactive** toggle (top-right of editor) → **Active**
2. The workflow now runs automatically at **09:00 UTC daily**
3. Monitor runs: left sidebar → **Executions**

---

## Score scale

The `score` in the audit response is the average across evaluation dimensions, on a **0–5 scale**:

| Score | Meaning |
|-------|---------|
| 4–5 | Strong listing — no action needed |
| 3–4 | Acceptable — minor improvements possible |
| < 3 | Weak listing — Slack alert fires, draft queued to HITL |

---

## Troubleshooting

**POST /audit node fails with "connection refused"**
- Check webhook server is still running on Windows (`uvicorn` process alive)
- Check Windows Firewall isn't blocking port 8000 (Step 2)
- Confirm `HEALF_WEBHOOK_URL` matches the Windows PC's actual LAN IP (run `ipconfig` again)

**POST /audit returns 400 "URL must be on healf.com"**
- The URL in the Code node must start with `https://healf.com/` — check for typos

**POST /audit times out (> 120s)**
- The webhook runs fetch + eval + rewrite in sequence — this can take 30–90s on first run (cold Playwright + API calls). The 120s timeout should be enough; if not, increase `timeout` in the POST /audit node options.

**Slack node fails**
- Workflow continues anyway (`onError: continueRegularOutput`) — check `SLACK_WEBHOOK_URL` is set correctly and the Slack app is still active

**n8n can't see the `$env.HEALF_WEBHOOK_URL` variable**
- The container was not restarted with the new env var — repeat Step 4
