"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type Intent = {
  id: string;
  recipient_name: string;
  recipient_email: string;
  amount: string;
  currency: string;
  purpose: string;
  condition_summary: string | null;
  approval_fingerprint: string;
  status: string;
  created_at: string;
  approved_at: string | null;
  executed_at: string | null;
  provider_transaction_id: string | null;
  provider_payout_batch_id: string | null;
  failure_code: string | null;
};

type Activity = {
  id: number;
  payment_intent_id: string;
  event_type: string;
  actor_id: string | null;
  details: string;
  created_at: string;
};

const defaultApi = process.env.NEXT_PUBLIC_PROXY_API_URL || "http://localhost:8000";

function money(amount: string, currency = "USD") {
  const value = Number(amount);
  if (!Number.isFinite(value)) return amount + " " + currency;
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(value);
}
function shortId(value: string) {
  return value.length > 15 ? value.slice(0, 8) + "…" + value.slice(-5) : value;
}
function prettyStatus(status: string) {
  return status.replaceAll("_", " ");
}
function errorText(value: unknown) {
  if (value instanceof Error) return value.message;
  return "Request failed. Check the API URL and backend logs.";
}

export default function Home() {
  const [apiUrl, setApiUrl] = useState(defaultApi);
  const [token, setToken] = useState("");
  const [intents, setIntents] = useState<Intent[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [selected, setSelected] = useState<Intent | null>(null);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<"checking" | "online" | "offline">("checking");
  const [notice, setNotice] = useState<{ kind: "success" | "error" | "info"; text: string } | null>(null);
  const [showConnection, setShowConnection] = useState(true);
  const [form, setForm] = useState({
    recipient_name: "",
    recipient_email: "",
    amount: "25.00",
    purpose: "",
    condition_summary: "",
  });

  const base = useMemo(() => apiUrl.trim().replace(/\/+$/, ""), [apiUrl]);
  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    if (!token.trim()) throw new Error("Add a valid bearer token issued by your trusted authentication provider.");
    const response = await fetch(base + path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token.trim(),
        ...(init.headers || {}),
      },
    });
    const raw = await response.text();
    let body: unknown = null;
    try { body = raw ? JSON.parse(raw) : null; } catch { body = raw; }
    if (!response.ok) {
      const detail = typeof body === "object" && body !== null && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : "HTTP " + response.status;
      throw new Error(detail);
    }
    return body;
  }, [base, token]);

  const refresh = useCallback(async () => {
    try {
      const [intentData, activityData] = await Promise.all([
        request("/v1/payment-intents?limit=50").catch(() => []),
        request("/v1/activity?limit=50"),
      ]);
      setIntents(Array.isArray(intentData) ? intentData as Intent[] : []);
      setActivity(Array.isArray(activityData) ? activityData as Activity[] : []);
    } catch (error) {
      setNotice({ kind: "error", text: errorText(error) });
    }
  }, [request]);

  const checkHealth = useCallback(async () => {
    try {
      const response = await fetch(base + "/health", { cache: "no-store" });
      setHealth(response.ok ? "online" : "offline");
    } catch { setHealth("offline"); }
  }, [base]);

  useEffect(() => { void checkHealth(); }, [checkHealth]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      const created = await request("/v1/payment-intents", {
        method: "POST",
        body: JSON.stringify({
          recipient_name: form.recipient_name,
          recipient_email: form.recipient_email,
          amount: form.amount,
          currency: "USD",
          purpose: form.purpose,
          condition_summary: form.condition_summary || null,
        }),
      }) as Intent;
      setSelected(created);
      setNotice({ kind: "success", text: "Payment intent created. It has not been approved or sent." });
      setForm({ recipient_name: "", recipient_email: "", amount: "25.00", purpose: "", condition_summary: "" });
      await refresh();
    } catch (error) { setNotice({ kind: "error", text: errorText(error) }); }
    finally { setBusy(false); }
  }

  async function runAction(action: "approve" | "execute" | "reconcile", intent: Intent) {
    setBusy(true);
    setNotice(null);
    try {
      const body = action === "approve" ? { confirm_fingerprint: intent.approval_fingerprint } : undefined;
      const updated = await request("/v1/payment-intents/" + encodeURIComponent(intent.id) + "/" + action, {
        method: "POST",
        ...(body ? { body: JSON.stringify(body) } : {}),
      }) as Intent;
      setSelected(updated);
      setNotice({
        kind: "success",
        text: action === "approve"
          ? "Approval recorded for this exact intent snapshot. Execution is still a separate step."
          : action === "execute"
            ? "Execution request returned. Check the status and audit trail; ambiguous outcomes must be reconciled, not retried."
            : "Reconciliation checked the existing provider batch. No new payout was submitted by this action.",
      });
      await refresh();
    } catch (error) { setNotice({ kind: "error", text: errorText(error) }); }
    finally { setBusy(false); }
  }

  async function loadActivity() {
    setBusy(true);
    try {
      await refresh();
      await checkHealth();
      setNotice({ kind: "success", text: "Dashboard refreshed." });
    } finally { setBusy(false); }
  }

  const succeeded = intents.filter((intent) => intent.status === "succeeded").length;
  const processing = intents.filter((intent) => intent.status === "processing").length;
  const awaiting = intents.filter((intent) => intent.status === "pending_approval").length;

  return (
    <main className="shell">
      <aside className="sidebar">
        <a className="brand" href="#" aria-label="Proxy home">
          <span className="brand-mark">P<span>.</span></span>
          <span><strong>proxy</strong><small>PAYMENT OPERATOR</small></span>
        </a>
        <div className="workspace-label">WORKSPACE</div>
        <a className="nav-item active" href="#overview"><span className="nav-icon">◫</span> Overview <span className="nav-dot" /></a>
        <a className="nav-item" href="#new-payment"><span className="nav-icon">＋</span> New payment</a>
        <a className="nav-item" href="#activity"><span className="nav-icon">≋</span> Audit activity</a>
        <div className="sidebar-bottom">
          <div className="secure-card"><span className="secure-icon">◇</span><div><strong>Safety first</strong><p>Human approval is required before any payment can execute.</p></div></div>
          <div className="environment"><span className="status-pip" /> SANDBOX MODE <span className="env-lock">⌑</span></div>
          <div className="sidebar-foot">PROXY SYSTEMS <span>v0.1.0</span></div>
        </div>
      </aside>

      <section className="main-area">
        <header className="topbar">
          <div className="crumb">Workspace <span>/</span> <strong>Overview</strong></div>
          <div className="top-actions">
            <span className={"api-status " + health}><i /> API {health}</span>
            <button className="icon-button" onClick={() => void loadActivity()} disabled={busy} aria-label="Refresh dashboard">↻</button>
            <div className="avatar">PO</div>
          </div>
        </header>

        <div className="content">
          <section className="hero" id="overview">
            <div>
              <div className="eyebrow"><span className="eyebrow-line" /> PAYMENT CONTROL CENTER</div>
              <h1>Money moves<br /><em>with intention.</em></h1>
              <p className="hero-copy">A clear view of every request, approval, and provider-confirmed outcome. You stay in control at every step.</p>
              <a className="primary-link" href="#new-payment">Create a payment <span>↗</span></a>
            </div>
            <div className="hero-art" aria-hidden="true">
              <div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit orbit-three" />
              <div className="core"><span>P</span><i /></div>
              <div className="orbit-label label-top">POLICY ENGINE <b>● ACTIVE</b></div>
              <div className="orbit-label label-bottom">PAYMENT RAIL <b>◈ SANDBOX</b></div>
              <div className="hero-number">01 <span>/ SAFETY LAYER</span></div>
            </div>
          </section>

          <div className="notice-bar"><span className="notice-shield">◇</span><span><strong>Protected by design</strong> — every payment requires explicit approval. Unknown provider outcomes stay in processing until reconciled.</span><span className="notice-tag">HUMAN-IN-THE-LOOP</span></div>

          {notice && <div className={"toast " + notice.kind} role="status"><span>{notice.kind === "error" ? "!" : notice.kind === "success" ? "✓" : "i"}</span>{notice.text}<button onClick={() => setNotice(null)} aria-label="Dismiss notification">×</button></div>}

          {showConnection && <section className="connection-panel">
            <div className="section-heading"><div><div className="eyebrow">01 / CONNECTION</div><h2>Connect your workspace</h2></div><button className="text-button" onClick={() => setShowConnection(false)}>Hide</button></div>
            <p className="muted">Use a JWT from your trusted identity provider. Proxy intentionally has no demo-login shortcut. Your token stays in this page's memory and is not saved to local storage.</p>
            <div className="connection-fields">
              <label>API BASE URL<input value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} placeholder="http://localhost:8000" spellCheck={false} /></label>
              <label>BEARER TOKEN<input value={token} onChange={(e) => setToken(e.target.value)} placeholder="Paste trusted JWT for this session" type="password" autoComplete="off" spellCheck={false} /></label>
              <button className="button-dark" onClick={() => { void checkHealth(); void refresh(); }} disabled={busy || !token.trim()}>Connect securely <span>→</span></button>
            </div>
            <div className="connection-note"><span>ⓘ</span> Never paste PayPal client secrets here. Only use an authentication token issued by your configured identity provider.</div>
          </section>}

          <section className="metrics">
            <div className="metric-card"><div className="metric-top"><span>AWAITING APPROVAL</span><span className="metric-symbol amber">◷</span></div><div className="metric-value">{awaiting.toString().padStart(2, "0")}</div><div className="metric-foot"><span className="tiny-dot amber-dot" /> Needs your review</div></div>
            <div className="metric-card"><div className="metric-top"><span>IN PROCESSING</span><span className="metric-symbol blue">↻</span></div><div className="metric-value">{processing.toString().padStart(2, "0")}</div><div className="metric-foot"><span className="tiny-dot blue-dot" /> Reconcile before retry</div></div>
            <div className="metric-card"><div className="metric-top"><span>CONFIRMED SUCCESS</span><span className="metric-symbol green">✓</span></div><div className="metric-value">{succeeded.toString().padStart(2, "0")}</div><div className="metric-foot"><span className="tiny-dot green-dot" /> Provider verified</div></div>
            <div className="metric-card"><div className="metric-top"><span>AUTHORIZATION MODEL</span><span className="metric-symbol violet">⌑</span></div><div className="metric-value metric-word">Human-led</div><div className="metric-foot"><span className="tiny-dot violet-dot" /> AI never self-approves</div></div>
          </section>

          <div className="work-grid">
            <section className="panel create-panel" id="new-payment">
              <div className="section-heading"><div><div className="eyebrow">02 / REQUEST</div><h2>Prepare a payment</h2></div><span className="step-count">STEP 01 <i>OF 03</i></span></div>
              <p className="muted">Create a structured intent. Nothing is sent until you review and approve it.</p>
              <form onSubmit={handleCreate} className="payment-form">
                <div className="form-row"><label>RECIPIENT NAME<input required maxLength={120} value={form.recipient_name} onChange={(e) => setForm({ ...form, recipient_name: e.target.value })} placeholder="e.g. Jordan Lee" /></label><label>RECIPIENT EMAIL<input required type="email" maxLength={254} value={form.recipient_email} onChange={(e) => setForm({ ...form, recipient_email: e.target.value })} placeholder="jordan@example.com" /></label></div>
                <div className="form-row amount-row"><label>AMOUNT<input required type="number" min="0.01" max="99999999.99" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></label><label>CURRENCY<div className="currency-field"><span>🇺🇸</span> USD <span className="currency-lock">⌑</span></div></label></div>
                <label>PURPOSE<input required minLength={3} maxLength={500} value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} placeholder="What is this payment for?" /></label>
                <label>CONDITION / SUPPORTING CONTEXT <span className="optional">(OPTIONAL)</span><textarea rows={3} maxLength={1000} value={form.condition_summary} onChange={(e) => setForm({ ...form, condition_summary: e.target.value })} placeholder="Milestone, invoice reference, or context for the reviewer…" /></label>
                <div className="form-foot"><span><span className="tiny-dot green-dot" /> Backend policy checks apply</span><button className="button-dark" type="submit" disabled={busy || !token.trim()}>Create intent <span>→</span></button></div>
              </form>
            </section>

            <section className="panel selected-panel">
              <div className="section-heading"><div><div className="eyebrow">03 / REVIEW & RELEASE</div><h2>Approval desk</h2></div><span className="approval-mark">✓</span></div>
              {selected ? <div className="review-card">
                <div className="review-top"><span className={"status-pill " + selected.status}>{prettyStatus(selected.status)}</span><span className="review-id">#{shortId(selected.id)}</span></div>
                <div className="review-amount">{money(selected.amount, selected.currency)}</div>
                <div className="review-recipient">{selected.recipient_name}<span>{selected.recipient_email}</span></div>
                <div className="review-purpose"><span>PURPOSE</span><p>{selected.purpose}</p></div>
                {selected.condition_summary && <div className="review-purpose"><span>CONTEXT</span><p>{selected.condition_summary}</p></div>}
                <div className="fingerprint"><span>APPROVAL FINGERPRINT</span><code>{selected.approval_fingerprint}</code></div>
                <div className="review-warning"><span>◇</span><p>Verify recipient, amount, and purpose before approving. Approval is tied to this exact fingerprint.</p></div>
                <div className="review-actions">
                  {selected.status === "pending_approval" && <button className="button-dark full" onClick={() => void runAction("approve", selected)} disabled={busy}>Approve this request <span>→</span></button>}
                  {selected.status === "approved" && <button className="button-dark full" onClick={() => void runAction("execute", selected)} disabled={busy}>Execute in Sandbox <span>→</span></button>}
                  {selected.status === "processing" && <button className="button-outline full" onClick={() => void runAction("reconcile", selected)} disabled={busy}>Reconcile existing payout <span>↻</span></button>}
                  {selected.status === "succeeded" && <div className="settled-box">✓ Provider-confirmed success {selected.provider_transaction_id && <code>{selected.provider_transaction_id}</code>}</div>}
                  {selected.status === "processing" && <p className="small-caution">Do not submit another payment. Reconciliation only reads the existing payout batch.</p>}
                </div>
              </div> : <div className="empty-review"><div className="empty-icon">◎</div><h3>No request selected</h3><p>Create a payment intent to inspect its exact details, approve it, and then execute separately.</p><span>APPROVAL GATE <b>LOCKED</b></span></div>}
            </section>
          </div>

          <section className="panel intents-panel">
            <div className="section-heading"><div><div className="eyebrow">LIVE REGISTER</div><h2>Payment intents</h2></div><button className="text-button" onClick={() => void loadActivity()} disabled={busy}>↻ Refresh</button></div>
            <div className="table-wrap"><table><thead><tr><th>RECIPIENT</th><th>AMOUNT</th><th>PURPOSE</th><th>STATUS</th><th>CREATED</th><th /></tr></thead><tbody>
              {intents.length === 0 ? <tr><td colSpan={6} className="table-empty">No intents loaded. Connect with a trusted token to load your payment register.</td></tr> : intents.map((intent) => <tr key={intent.id} className={selected?.id === intent.id ? "row-selected" : ""}><td><strong>{intent.recipient_name}</strong><small>{intent.recipient_email}</small></td><td className="amount-cell">{money(intent.amount, intent.currency)}</td><td className="purpose-cell">{intent.purpose}</td><td><span className={"status-pill " + intent.status}>{prettyStatus(intent.status)}</span></td><td>{new Date(intent.created_at).toLocaleString()}</td><td><button className="row-action" onClick={() => setSelected(intent)} aria-label={"Review " + intent.recipient_name}>View ↗</button></td></tr>)}
            </tbody></table></div>
          </section>

          <section className="panel activity-panel" id="activity">
            <div className="section-heading"><div><div className="eyebrow">AUDIT TRAIL</div><h2>Recent activity</h2></div><span className="audit-lock">⌑ APPEND-ONLY STYLE LOG</span></div>
            <div className="activity-list">
              {activity.length === 0 ? <div className="activity-empty">Authenticated audit events will appear here after connecting.</div> : activity.slice(0, 8).map((event) => <div className="activity-row" key={event.id}><span className={"activity-icon " + (event.event_type.includes("succeeded") ? "success" : event.event_type.includes("unknown") || event.event_type.includes("unresolved") ? "warning" : "")}>{event.event_type.includes("succeeded") ? "✓" : event.event_type.includes("unknown") || event.event_type.includes("unresolved") ? "!" : "·"}</span><div className="activity-main"><strong>{event.event_type.replaceAll(".", " · ")}</strong><p>{event.details}</p><small>Intent {shortId(event.payment_intent_id)} · {event.actor_id || "system"}</small></div><time>{new Date(event.created_at).toLocaleString()}</time></div>)}
            </div>
          </section>
          <footer className="footer"><span>PROXY <b>●</b> BUILT AROUND DELIBERATE ACTION</span><span>PAYPAL SANDBOX ONLY · NO LIVE PAYMENTS</span></footer>
        </div>
      </section>
    </main>
  );
}