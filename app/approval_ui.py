"""Dependency-free local approval screen for the Associate bonus."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                records.append(value)
        except json.JSONDecodeError:
            continue
    return records


def record_approval(code_dir: Path, trace_id: str, action: str, reviewer: str, note: str = "") -> dict:
    """Append an auditable approval action without changing the Part A decision."""
    if action not in {"approve", "reject", "change"}:
        raise ValueError("action must be approve, reject or change")
    record = {
        "trace_id": trace_id,
        "action": action,
        "reviewer": reviewer[:120],
        "note": note[:1000],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    target = code_dir / "mock_system" / "approvals.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _queue(code_dir: Path) -> list[dict]:
    decisions = _read_jsonl(code_dir / "mock_system" / "claims_decisions.jsonl")
    actions = _read_jsonl(code_dir / "mock_system" / "approvals.jsonl")
    action_by_trace = {item.get("trace_id"): item for item in actions if item.get("trace_id")}
    latest_by_claim: dict[str, dict] = {}
    for decision in decisions:
        claim = str(decision.get("citations", ["unknown"])[0])
        latest_by_claim[claim] = decision
    result = []
    for decision in latest_by_claim.values():
        if decision.get("needs_human"):
            result.append({"decision": decision, "approval": action_by_trace.get(decision.get("trace_id"))})
    return sorted(result, key=lambda item: (item["approval"] is not None, item["decision"].get("case_id", "")))


def _money(value: object) -> str:
    return "Not recorded" if value is None else f"₹{float(value):,.2f}"


def _page(queue: list[dict], notice: str = "") -> str:
    cards = []
    for item in queue:
        decision = item["decision"]
        approval = item["approval"]
        claim = html.escape(str(decision.get("citations", ["Unknown claim"])[0]))
        trace = html.escape(str(decision.get("trace_id", "")))
        outcome = html.escape(str(decision.get("decision", ""))).replace("_", " ")
        reason = html.escape(str(decision.get("reason_code", "")))
        amount = _money(decision.get("amount"))
        citations = ", ".join(html.escape(str(value)) for value in decision.get("citations", [])[1:])
        if approval:
            status = f"<div class='reviewed'>Reviewed: <strong>{html.escape(str(approval.get('action', '')).title())}</strong><br><small>{html.escape(str(approval.get('note', '')))}</small></div>"
        else:
            status = f"""
            <form method='post' action='/review'>
              <input type='hidden' name='trace_id' value='{trace}'>
              <label>Reviewer <input name='reviewer' value='Claims adjuster' maxlength='120'></label>
              <label>Note (optional) <input name='note' maxlength='1000' placeholder='Reason or next step'></label>
              <div class='actions'>
                <button name='action' value='approve' class='approve'>Approve</button>
                <button name='action' value='change' class='change'>Request change</button>
                <button name='action' value='reject' class='reject'>Reject</button>
              </div>
            </form>"""
        cards.append(f"""
        <article class='card'>
          <div class='card-top'><div><p class='eyebrow'>{claim}</p><h2>{outcome}</h2></div><span class='reason'>{reason}</span></div>
          <dl><div><dt>Recommended payment</dt><dd>{amount}</dd></div><div><dt>Case</dt><dd>{html.escape(str(decision.get('case_id', '')))}</dd></div></dl>
          <p class='citations'>Evidence: {citations}</p>{status}
        </article>""")
    body = "".join(cards) or "<div class='empty'><h2>Queue clear</h2><p>No decisions currently require human review. Run a case that is a rejection, referral or payment above ₹50,000 to see it here.</p></div>"
    banner = f"<div class='notice'>{html.escape(notice)}</div>" if notice else ""
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>Banyan Shield | Claims approval</title><style>
    :root{{--navy:#141126;--violet:#5a36dc;--mist:#f7f5fc;--line:#e5e1ef;--green:#117a5e;--red:#b4233d;--amber:#a76300}}*{{box-sizing:border-box}}body{{margin:0;background:var(--mist);color:var(--navy);font:16px/1.5 Arial,sans-serif}}header{{padding:42px max(24px,calc((100vw - 1060px)/2));background:linear-gradient(115deg,#17112b,#4d2fb0);color:white}}header p{{margin:0 0 8px;color:#d9d0ff;font-weight:bold;letter-spacing:.13em;text-transform:uppercase;font-size:.75rem}}h1{{font-size:clamp(2rem,5vw,3.4rem);line-height:1.05;margin:0}}main{{max-width:1060px;margin:0 auto;padding:32px 24px 60px}}.intro{{display:flex;justify-content:space-between;gap:24px;align-items:center;margin-bottom:24px}}.intro p{{margin:0;color:#5e5873;max-width:680px}}.tag{{white-space:nowrap;border:1px solid #cfc6ec;border-radius:999px;padding:7px 12px;color:var(--violet);font-size:.85rem;font-weight:bold}}.notice{{background:#e6f7ef;color:#075c44;padding:12px 16px;border-radius:10px;margin-bottom:20px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}}.card,.empty{{background:white;border:1px solid var(--line);border-radius:16px;padding:22px;box-shadow:0 7px 22px rgba(38,22,79,.06)}}.card-top{{display:flex;gap:14px;justify-content:space-between;align-items:start}}.eyebrow{{margin:0;color:var(--violet);font-size:.76rem;font-weight:bold;letter-spacing:.08em}}h2{{font-size:1.35rem;text-transform:capitalize;margin:5px 0 0}}.reason{{background:#f0ecff;color:#4d2ab8;border-radius:999px;padding:5px 9px;font-size:.72rem;font-weight:bold}}dl{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:20px 0}}dt{{color:#706a82;font-size:.75rem}}dd{{font-weight:bold;margin:2px 0 0}}.citations{{border-top:1px solid var(--line);padding-top:12px;color:#5e5873;font-size:.82rem}}form{{display:grid;gap:10px}}label{{font-size:.8rem;color:#5e5873;font-weight:bold}}input{{display:block;width:100%;margin-top:4px;padding:9px 10px;border:1px solid #cfc9db;border-radius:8px;font:inherit;color:var(--navy)}}.actions{{display:flex;gap:8px;flex-wrap:wrap;margin-top:5px}}button{{border:0;border-radius:8px;padding:10px 13px;font-weight:bold;cursor:pointer}}.approve{{background:var(--green);color:white}}.change{{background:#fff2d8;color:var(--amber)}}.reject{{background:#fff0f2;color:var(--red)}}.reviewed{{border-radius:8px;background:#f3f1f8;color:#514c5f;padding:11px;font-size:.86rem}}.empty{{text-align:center;padding:55px 24px}}@media(max-width:560px){{header{{padding:30px 24px}}.intro{{display:block}}.tag{{display:inline-block;margin-top:12px}}}}</style></head>
    <body><header><p>Banyan Shield General Insurance</p><h1>Claims approval desk</h1></header><main>{banner}<section class='intro'><p>Review decisions that need a claims adjuster: rejections, referrals, and payouts above ₹50,000. Each action is appended to an audit log.</p><span class='tag'>{len(queue)} review item{'s' if len(queue) != 1 else ''}</span></section><section class='grid'>{body}</section></main></body></html>"""


def serve_approval_screen(code_dir: Path, host: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def _respond(self, markup: str, status: int = 200) -> None:
            encoded = markup.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/":
                self._respond("Not found", 404)
                return
            self._respond(_page(_queue(code_dir)))

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/review":
                self._respond("Not found", 404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            values = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            try:
                action = values.get("action", [""])[0]
                trace_id = values.get("trace_id", [""])[0]
                if not trace_id:
                    raise ValueError("Missing decision trace")
                record_approval(code_dir, trace_id, action, values.get("reviewer", ["Claims adjuster"])[0], values.get("note", [""])[0])
                self._respond(_page(_queue(code_dir), f"Action recorded: {action.title()}"))
            except ValueError as exc:
                self._respond(_page(_queue(code_dir), f"Could not record action: {exc}"), 400)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Approval screen available at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
