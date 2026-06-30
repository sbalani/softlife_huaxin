# softlife_huaxin

Custom **Odoo 18** module — the **bridge to the Huaxin ice-cream machine cloud**.

Depends on `softlife_machine`. Other modules (`softlife_haccp`, future
orders/VeriFactu) talk to Huaxin only through this one client.

## What it does
- **Fixed-credential auth**: Huaxin issues a static block (`mch_id`, `mch_secret`,
  `nonce_str`, `time_Stamp`, `sign`) that the client sends **verbatim** on every
  call. There is **no** per-request signature computation.
- **Device sync** (daily cron): `/devices` → `softlife.machine` by `device_imei`.
- **Webhook receiver** at `/huaxin/notify` for device **faults** and **orders**.
- **Temperature ingestion** (hourly cron) → HACCP-ready readings.
- **Stub mode**: until credentials are entered, outbound calls return canned data.

## Configure
*Settings → SoftLife → Huaxin*: Cloud Base URL, Merchant ID, Merchant Secret,
**Sign**, Nonce, Timestamp, Webhook URL, plus timezone + Verify SSL.

- UAT base URL: `https://uatapi.huaxinvending.com`
- **The UAT TLS certificate is currently expired** — turn OFF *Verify SSL* for
  UAT testing, and ON for production. Report it to Huaxin.
- Webhook URL = your Odoo address + `/huaxin/notify`
  (e.g. `https://test-amarvida.cloudpepper.site/huaxin/notify`).

## Install
```bash
git clone https://github.com/sbalani/softlife_huaxin.git softlife_huaxin
```
Then in Odoo: **Apps → Update Apps List → install "SoftLife Huaxin Bridge"**
(requires `softlife_machine` to be present on the addons path).
