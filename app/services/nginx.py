from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RUNTIME_DIR = BASE_DIR / "runtime"
NGINX_SITES_DIR = RUNTIME_DIR / "nginx" / "sites-enabled"


@dataclass
class SiteConfig:
    domain: str
    root_path: str
    ssl_enabled: bool


def render_vhost(config: SiteConfig) -> str:
    ssl_server = ""
    if config.ssl_enabled:
        ssl_server = f"""
server {{
    listen 443 ssl http2;
    server_name {config.domain} www.{config.domain};

    ssl_certificate /etc/letsencrypt/live/{config.domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{config.domain}/privkey.pem;

    root {config.root_path};
    index index.php index.html index.htm;

    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}

    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php8.2-fpm.sock;
    }}
}}
"""

    return f"""
server {{
    listen 80;
    server_name {config.domain} www.{config.domain};

    root {config.root_path};
    index index.php index.html index.htm;

    location /.well-known/acme-challenge/ {{
        root /var/www/html;
    }}

    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}

    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php8.2-fpm.sock;
    }}
}}
{ssl_server}
""".strip()


def write_vhost(domain: str, content: str) -> Path:
    NGINX_SITES_DIR.mkdir(parents=True, exist_ok=True)
    path = NGINX_SITES_DIR / f"{domain}.conf"
    path.write_text(content)
    return path
