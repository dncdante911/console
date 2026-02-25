from dataclasses import dataclass


@dataclass
class LetsEncryptRequest:
    domain: str
    email: str


def build_certbot_command(req: LetsEncryptRequest) -> str:
    return (
        "certbot certonly --nginx "
        f"-d {req.domain} -d www.{req.domain} "
        f"--agree-tos -m {req.email} --non-interactive"
    )
