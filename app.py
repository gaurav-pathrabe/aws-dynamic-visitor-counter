"""Cloud Resume Visitor Counter Flask app.

This application exposes a minimal REST API and a small, animated UI to
show a running visitor count. The goal is to stay interview-friendly:
- Keep the stack intentionally simple (Flask + SQLite) to highlight AWS
  lift-and-shift or container deployment paths.
- Persist counts on disk so restarts do not lose state.
- Provide CORS-ready APIs so the frontend can be hosted separately if
  desired (e.g., S3/CloudFront hitting an API on EC2).
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Tuple

from flask import Flask, jsonify, make_response
from flask_cors import CORS

# File-system locations are derived from this file so the app can run from
# any working directory (important when used with systemd or Gunicorn).
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "counter.db"

app = Flask(__name__)

# Allow cross-origin requests for all API routes; helpful when the UI is
# hosted separately (S3/CloudFront) and the API sits on EC2 or behind ALB.
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Structured logging keeps deployment logs readable in CloudWatch or stdout.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
app.logger.setLevel(logging.INFO)


def get_db_connection() -> sqlite3.Connection:
    """Return a SQLite connection with WAL enabled for better concurrency."""

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def initialize_database() -> None:
    """Create schema and seed the single counter row if missing."""

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS visitors (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                count INTEGER NOT NULL
            );
            """
        )
        row = conn.execute("SELECT count FROM visitors WHERE id = 1;").fetchone()
        if row is None:
            conn.execute("INSERT INTO visitors (id, count) VALUES (1, 0);")
            conn.commit()
            app.logger.info("Initialized visitor counter at 0")


def increment_and_get_count() -> int:
    """Increment the visitor count atomically and return the new total."""

    with get_db_connection() as conn:
        conn.execute("UPDATE visitors SET count = count + 1 WHERE id = 1;")
        conn.commit()
        row = conn.execute("SELECT count FROM visitors WHERE id = 1;").fetchone()
        return int(row["count"])


def reset_count() -> int:
    """Reset the counter to zero and return the new value."""

    with get_db_connection() as conn:
        conn.execute("UPDATE visitors SET count = 0 WHERE id = 1;")
        conn.commit()
        return 0


@app.route("/api/visitors", methods=["GET"])
def get_visitors() -> Tuple[str, int]:
    """Increment and return the current visitor count."""

    try:
        count = increment_and_get_count()
        return jsonify({"count": count}), 200
    except Exception as exc:  # noqa: BLE001 (explicit logging is useful here)
        app.logger.exception("Failed to increment visitor count")
        return jsonify({"error": "Unable to read visitor count"}), 500


@app.route("/api/reset", methods=["POST"])
def reset_visitors() -> Tuple[str, int]:
    """Reset the visitor count to zero. Treat as an admin action."""

    try:
        count = reset_count()
        app.logger.warning("Visitor counter reset by request")
        return jsonify({"count": count}), 200
    except Exception:  # noqa: BLE001
        app.logger.exception("Failed to reset visitor count")
        return jsonify({"error": "Unable to reset visitor count"}), 500


HOME_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cloud Resume Visitor Counter</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    :root {
      --bg-dark: #0f172a;
      --bg-card: #1e293b;
      --accent: #38bdf8;
      --accent-glow: rgba(56, 189, 248, 0.5);
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --success: #4ade80;
      --danger: #f87171;
      --border: rgba(255, 255, 255, 0.1);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: 'Inter', sans-serif;
      background-color: var(--bg-dark);
      background-image: 
        radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.15) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(168, 85, 247, 0.15) 0px, transparent 50%);
      color: var(--text-main);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .dashboard {
      width: 100%;
      max-width: 1000px;
      background: rgba(30, 41, 59, 0.7);
      backdrop-filter: blur(20px);
      border: 1px solid var(--border);
      border-radius: 24px;
      overflow: hidden;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }
    .header {
      padding: 24px 32px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(15, 23, 42, 0.5);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand i { font-size: 24px; color: var(--accent); }
    .brand h1 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.02em; }
    .status-pill {
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      padding: 6px 12px;
      background: rgba(74, 222, 128, 0.1);
      color: var(--success);
      border: 1px solid rgba(74, 222, 128, 0.2);
      border-radius: 99px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .status-dot { width: 8px; height: 8px; background: currentColor; border-radius: 50%; box-shadow: 0 0 8px currentColor; }
    
    .content {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 0;
    }
    @media (max-width: 768px) { .content { grid-template-columns: 1fr; } }

    .main-panel {
      padding: 40px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      border-right: 1px solid var(--border);
    }
    .counter-card {
      text-align: center;
    }
    .counter-label {
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--text-muted);
      margin-bottom: 16px;
    }
    .counter-value {
      font-family: 'JetBrains Mono', monospace;
      font-size: 80px;
      font-weight: 700;
      color: var(--accent);
      text-shadow: 0 0 30px var(--accent-glow);
      line-height: 1;
      margin-bottom: 8px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .counter-value.bump { transform: scale(1.1); filter: brightness(1.2); }
    
    .controls {
      margin-top: 40px;
      display: flex;
      gap: 12px;
      justify-content: center;
    }
    .btn {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-main);
      padding: 12px 20px;
      border-radius: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
    }
    .btn:hover { background: rgba(255,255,255,0.05); border-color: var(--text-muted); }
    .btn-primary { background: var(--accent); color: #0f172a; border: none; }
    .btn-primary:hover { background: #0ea5e9; box-shadow: 0 0 15px var(--accent-glow); }
    .btn-danger { color: var(--danger); border-color: rgba(248, 113, 113, 0.3); }
    .btn-danger:hover { background: rgba(248, 113, 113, 0.1); }

    .side-panel {
      background: rgba(15, 23, 42, 0.3);
      padding: 32px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }
    .panel-section h3 {
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin: 0 0 16px 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .terminal {
      background: #000;
      border-radius: 12px;
      padding: 16px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      height: 200px;
      overflow-y: auto;
      border: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .log-entry { display: flex; gap: 8px; opacity: 0; animation: fadeIn 0.3s forwards; }
    .log-time { color: var(--text-muted); }
    .log-msg { color: var(--text-main); }
    .log-success { color: var(--success); }
    .log-error { color: var(--danger); }
    
    .tech-stack {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .tag {
      font-size: 12px;
      padding: 4px 10px;
      background: rgba(255,255,255,0.05);
      border-radius: 6px;
      color: var(--text-muted);
      border: 1px solid var(--border);
    }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
    
    /* Scrollbar */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
  </style>
</head>
<body>
  <div class="dashboard">
    <header class="header">
      <div class="brand">
        <i class="fa-brands fa-aws"></i>
        <div>
          <h1>Cloud Resume Counter</h1>
          <div style="font-size: 12px; color: var(--text-muted);">Gaurav Pathrabe</div>
        </div>
      </div>
      <div class="status-pill">
        <div class="status-dot"></div>
        SYSTEM ONLINE
      </div>
    </header>
    
    <div class="content">
      <div class="main-panel">
        <div class="counter-card">
          <div class="counter-label">Total Visitors</div>
          <div id="count" class="counter-value">---</div>
          <div style="color: var(--success); font-size: 14px; display: flex; align-items: center; justify-content: center; gap: 6px;">
            <i class="fa-solid fa-arrow-trend-up"></i>
            <span>Live Tracking</span>
          </div>
        </div>
        
        <div class="controls">
          <button class="btn btn-primary" id="refresh">
            <i class="fa-solid fa-rotate"></i> Refresh
          </button>
          <button class="btn" id="autorefresh">
            <i class="fa-solid fa-clock"></i> Auto
          </button>
          <button class="btn btn-danger" id="reset">
            <i class="fa-solid fa-trash"></i> Reset
          </button>
        </div>
      </div>
      
      <aside class="side-panel">
        <div class="panel-section">
          <h3><i class="fa-solid fa-terminal"></i> System Logs</h3>
          <div class="terminal" id="terminal">
            <div class="log-entry">
              <span class="log-time">[BOOT]</span>
              <span class="log-msg">Initializing Flask application...</span>
            </div>
            <div class="log-entry">
              <span class="log-time">[INFO]</span>
              <span class="log-msg">Connected to SQLite (WAL mode)</span>
            </div>
          </div>
        </div>
        
        <div class="panel-section">
          <h3><i class="fa-solid fa-layer-group"></i> Architecture</h3>
          <div class="tech-stack">
            <span class="tag">Python 3.9+</span>
            <span class="tag">Flask</span>
            <span class="tag">SQLite</span>
            <span class="tag">AWS EC2</span>
            <span class="tag">REST API</span>
          </div>
        </div>
      </aside>
    </div>
  </div>

  <script>
    const countEl = document.getElementById('count');
    const terminal = document.getElementById('terminal');
    const refreshBtn = document.getElementById('refresh');
    const resetBtn = document.getElementById('reset');
    const autoBtn = document.getElementById('autorefresh');
    let autoTimer = null;

    const log = (msg, type = 'info') => {
      const div = document.createElement('div');
      div.className = 'log-entry';
      const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
      
      let colorClass = 'log-msg';
      if (type === 'success') colorClass = 'log-success';
      if (type === 'error') colorClass = 'log-error';
      
      div.innerHTML = `
        <span class="log-time">[${time}]</span>
        <span class="${colorClass}">${msg}</span>
      `;
      terminal.appendChild(div);
      terminal.scrollTop = terminal.scrollHeight;
    };

    const renderCount = (count) => {
      const prev = parseInt(countEl.textContent);
      countEl.textContent = count;
      
      if (!isNaN(prev) && count !== prev) {
        countEl.classList.remove('bump');
        void countEl.offsetWidth;
        countEl.classList.add('bump');
      }
    };

    const fetchCount = async () => {
      log('GET /api/visitors...', 'info');
      try {
        const start = performance.now();
        const res = await fetch('/api/visitors');
        const duration = Math.round(performance.now() - start);
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const data = await res.json();
        renderCount(data.count);
        log(`200 OK - Count: ${data.count} (${duration}ms)`, 'success');
      } catch (err) {
        log(`Error: ${err.message}`, 'error');
      }
    };

    const resetCounter = async () => {
      if (!confirm('Are you sure you want to reset the counter?')) return;
      
      log('POST /api/reset...', 'info');
      try {
        const res = await fetch('/api/reset', { method: 'POST' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const data = await res.json();
        renderCount(data.count);
        log('Counter reset successfully', 'success');
      } catch (err) {
        log(`Reset failed: ${err.message}`, 'error');
      }
    };

    refreshBtn.addEventListener('click', fetchCount);
    resetBtn.addEventListener('click', resetCounter);
    
    autoBtn.addEventListener('click', () => {
      if (autoTimer) {
        clearInterval(autoTimer);
        autoTimer = null;
        autoBtn.classList.remove('btn-primary');
        autoBtn.innerHTML = '<i class="fa-solid fa-clock"></i> Auto';
        log('Auto-refresh stopped', 'info');
      } else {
        fetchCount();
        autoTimer = setInterval(fetchCount, 3000);
        autoBtn.classList.add('btn-primary');
        autoBtn.innerHTML = '<i class="fa-solid fa-stop"></i> Stop';
        log('Auto-refresh started (3s)', 'info');
      }
    });

    // Initial load
    setTimeout(fetchCount, 500);
  </script>
</body>
</html>
"""


@app.route("/")
def home() -> "flask.wrappers.Response":
    """Serve the single-page UI."""

    response = make_response(HOME_TEMPLATE)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response


def create_app() -> Flask:
    """Factory for Gunicorn or tests. Ensures DB exists on import."""

    initialize_database()
    return app


# Ensure schema exists when the module is imported (Gunicorn) or run directly.
create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)