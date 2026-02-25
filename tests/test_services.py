from app.services.letsencrypt import LetsEncryptRequest, build_certbot_command
from app.services.license import LicenseConfig, validate_license
from app.services.nginx import SiteConfig, render_vhost


class _Resp:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_render_vhost_includes_ssl_block_when_enabled():
    config = SiteConfig(domain="example.com", root_path="/var/www/example", ssl_enabled=True)
    out = render_vhost(config)
    assert "listen 443 ssl http2;" in out
    assert "/etc/letsencrypt/live/example.com/fullchain.pem" in out


def test_build_certbot_command():
    cmd = build_certbot_command(LetsEncryptRequest(domain="example.com", email="admin@example.com"))
    assert "certbot certonly --nginx" in cmd
    assert "-d example.com -d www.example.com" in cmd


def test_validate_license_ok(monkeypatch):
    def _post(*args, **kwargs):
        return _Resp({"valid": True, "message": "license active"})

    monkeypatch.setattr("app.services.license.httpx.post", _post)
    ok, msg = validate_license(LicenseConfig(server_url="https://lic", license_key="K", machine_id="M"))
    assert ok is True
    assert msg == "license active"
