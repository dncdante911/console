import os
import socket
from hashlib import sha256
from pathlib import Path
from subprocess import CompletedProcess, run

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import get_conn, get_setting, init_db, set_setting
from app.services.letsencrypt import LetsEncryptRequest, build_certbot_command
from app.services.license import LicenseConfig, build_machine_id, validate_license
from app.services.mail import MailDomainConfig, render_postfix_virtual_domains
from app.services.nginx import SiteConfig, render_vhost, write_vhost

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(exist_ok=True)

app = FastAPI(title="MiniHost Panel")
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


def current_machine_id() -> str:
    hostname = socket.gethostname()
    server_ip = os.getenv("PANEL_SERVER_IP", "127.0.0.1")
    return build_machine_id(hostname, server_ip)


def get_license_state() -> dict[str, str | bool]:
    url = get_setting("license_server_url") or os.getenv("LICENSE_SERVER_URL", "")
    key = get_setting("license_key") or os.getenv("LICENSE_KEY", "")
    if not url or not key:
        return {
            "active": False,
            "message": "Лицензия не настроена",
            "server_url": url,
            "license_key": key,
        }

    valid, message = validate_license(
        LicenseConfig(server_url=url, license_key=key, machine_id=current_machine_id())
    )
    return {
        "active": valid,
        "message": message,
        "server_url": url,
        "license_key": key,
    }


def require_active_license() -> None:
    state = get_license_state()
    if not state["active"]:
        raise HTTPException(status_code=402, detail=f"Лицензия не активна: {state['message']}")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    with get_conn() as conn:
        websites = conn.execute("SELECT * FROM websites ORDER BY id DESC").fetchall()
        mail_domains = conn.execute("SELECT * FROM mail_domains ORDER BY id DESC").fetchall()
        mailboxes = conn.execute(
            "SELECT m.email, d.domain FROM mailboxes m JOIN mail_domains d ON m.domain_id = d.id ORDER BY m.id DESC"
        ).fetchall()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "websites": websites,
            "mail_domains": mail_domains,
            "mailboxes": mailboxes,
            "license": get_license_state(),
            "machine_id": current_machine_id(),
        },
    )


@app.post("/license/activate")
def activate_license(server_url: str = Form(...), license_key: str = Form(...)):
    set_setting("license_server_url", server_url.strip())
    set_setting("license_key", license_key.strip())
    return RedirectResponse(url="/", status_code=303)


@app.post("/websites")
def create_website(domain: str = Form(...), root_path: str = Form(...), php_version: str = Form("8.2")):
    require_active_license()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO websites(domain, root_path, php_version) VALUES(?, ?, ?)",
            (domain.strip(), root_path.strip(), php_version.strip()),
        )

    conf = render_vhost(SiteConfig(domain=domain, root_path=root_path, ssl_enabled=False))
    write_vhost(domain, conf)
    return RedirectResponse(url="/", status_code=303)


@app.post("/websites/{website_id}/ssl")
def enable_ssl(website_id: int, email: str = Form(...)):
    require_active_license()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM websites WHERE id = ?", (website_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Website not found")
        conn.execute("UPDATE websites SET ssl_enabled = 1 WHERE id = ?", (website_id,))

    command = build_certbot_command(LetsEncryptRequest(domain=row["domain"], email=email))
    conf = render_vhost(SiteConfig(domain=row["domain"], root_path=row["root_path"], ssl_enabled=True))
    write_vhost(row["domain"], conf)

    (RUNTIME_DIR / "last_certbot_command.txt").write_text(command)
    return RedirectResponse(url="/", status_code=303)


@app.post("/mail/domains")
def create_mail_domain(domain: str = Form(...)):
    require_active_license()
    with get_conn() as conn:
        conn.execute("INSERT INTO mail_domains(domain) VALUES(?)", (domain.strip(),))
        domains = [MailDomainConfig(domain=d["domain"]) for d in conn.execute("SELECT domain FROM mail_domains").fetchall()]

    out = render_postfix_virtual_domains(domains)
    postfix_file = RUNTIME_DIR / "mail" / "virtual_domains"
    postfix_file.parent.mkdir(parents=True, exist_ok=True)
    postfix_file.write_text(out)
    return RedirectResponse(url="/", status_code=303)


@app.post("/mail/mailboxes")
def create_mailbox(email: str = Form(...), password: str = Form(...)):
    require_active_license()
    domain = email.split("@")[-1]
    hashed = sha256(password.encode()).hexdigest()

    with get_conn() as conn:
        row = conn.execute("SELECT id FROM mail_domains WHERE domain = ?", (domain,)).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Domain missing. Create mail domain first")
        conn.execute(
            "INSERT INTO mailboxes(email, password_hash, domain_id) VALUES(?, ?, ?)",
            (email.strip(), hashed, row["id"]),
        )
    return RedirectResponse(url="/", status_code=303)


@app.post("/ops/nginx/reload")
def reload_nginx():
    require_active_license()
    result: CompletedProcess = run(["bash", "-lc", "nginx -t && systemctl reload nginx"], capture_output=True, text=True)
    log = RUNTIME_DIR / "nginx_reload.log"
    log.write_text(result.stdout + "\n" + result.stderr)
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr)
    return {"status": "ok", "message": "nginx reloaded"}
