# Cloud Resume Visitor Counter (Flask + SQLite)

A production-ready yet interview-friendly Flask application that tracks resume visitors with a persistent SQLite backend and a modern dark UI. Designed for deployment on AWS EC2 (or containers) with minimal setup.

## Features
- REST API: `GET /api/visitors` increments + returns the count, `POST /api/reset` clears it, `GET /` serves the UI.
- SQLite persistence with auto schema creation; WAL mode enabled for smoother writes.
- CORS enabled for hosting the UI separately (e.g., S3/CloudFront) while the API sits on EC2/ALB.
- Structured logging for CloudWatch-friendly output.
- Responsive, animated dark UI highlighting Gaurav Pathrabe and the AWS stack choices.

## Prerequisites
- Python 3.9+
- `pip` (and `python3-venv` on Linux)

## Run Locally (Windows, macOS, Linux)
1. Clone or copy the repo into your machine.
2. Create and activate a virtual environment:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - **macOS/Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the app (Flask built-in server for local testing):
   ```bash
   python app.py
   ```
   The UI will be available at http://localhost:5000 and will create `counter.db` on first run.

## Deploy to AWS EC2 (Gunicorn + systemd)
1. **Launch EC2** (Amazon Linux 2023 or Ubuntu 22.04 recommended):
   - Instance security group: allow inbound TCP 80 (HTTP) from 0.0.0.0/0 for demo; restrict for production.
   - Optional: allow SSH (TCP 22) from your IP.
2. **Install system packages** (on EC2):
   ```bash
   sudo dnf -y update || sudo apt-get update
   sudo dnf -y install python3 python3-venv git || sudo apt-get -y install python3 python3-venv git
   ```
3. **Fetch code and set up venv**:
   ```bash
   git clone <your-repo-url> cloud-resume
   cd cloud-resume
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. **Test with Gunicorn** (production-grade WSGI server):
   ```bash
   ./venv/bin/gunicorn -b 0.0.0.0:8000 app:app
   ```
   If you prefer the factory, use `app:create_app()`: `gunicorn -b 0.0.0.0:8000 'app:create_app()'`.
5. **Create a systemd service** to keep the app running and auto-restart:
   ```bash
   sudo tee /etc/systemd/system/cloud-resume.service > /dev/null <<'EOF'
   [Unit]
   Description=Cloud Resume Visitor Counter
   After=network.target

   [Service]
   User=ec2-user
   WorkingDirectory=/home/ec2-user/cloud-resume
   Environment="PATH=/home/ec2-user/cloud-resume/venv/bin"
   ExecStart=/home/ec2-user/cloud-resume/venv/bin/gunicorn -b 0.0.0.0:8000 'app:create_app()'
   Restart=always
   RestartSec=3

   [Install]
   WantedBy=multi-user.target
   EOF

   sudo systemctl daemon-reload
   sudo systemctl enable --now cloud-resume.service
   sudo systemctl status cloud-resume.service
   ```
6. **Expose via port 80** (optional simple approach):
   ```bash
   sudo dnf -y install nginx || sudo apt-get -y install nginx
   # Basic reverse proxy
   sudo tee /etc/nginx/conf.d/cloud-resume.conf > /dev/null <<'EOF'
   server {
       listen 80;
       server_name _;
       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   EOF
   sudo nginx -t
   sudo systemctl reload nginx
   ```
7. Browse to your EC2 public DNS/IP on port 80. Logs stream to `journalctl -u cloud-resume.service`.

## Operational Notes
- SQLite database file: `counter.db` (ignored by git). WAL mode improves concurrent reads/writes.
- API contract: `GET /api/visitors` increments + returns `{ "count": <int> }`; `POST /api/reset` resets to `{ "count": 0 }`.
- CORS is open for `/api/*`; tighten origins in production as needed.
- To reset locally without API: delete `counter.db` or call the reset endpoint.

## Project Structure
- `app.py` — Flask app, API routes, embedded UI, database bootstrap.
- `requirements.txt` — Python dependencies (Flask, flask-cors, gunicorn).
- `.gitignore` — ignores virtualenv, SQLite db, caches, and local env files.

## Testing
- Manual: open `http://localhost:5000`, click **Refresh Count** and **Reset Counter** (confirm prompt).
- Programmatic: `curl http://localhost:5000/api/visitors` and `curl -X POST http://localhost:5000/api/reset`.

## Next Steps (optional interview talking points)
- Replace SQLite with DynamoDB for serverless scalability and atomic counters.
- Containerize with Docker + ECS Fargate; place behind ALB with TLS (ACM certificates).
- Add IAM-bound secrets manager for configuration instead of environment files.
