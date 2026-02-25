from dataclasses import dataclass


@dataclass
class MailDomainConfig:
    domain: str


def render_postfix_virtual_domains(domains: list[MailDomainConfig]) -> str:
    return "\n".join(d.domain for d in domains)


def render_dovecot_userdb(users: list[tuple[str, str]]) -> str:
    return "\n".join(f"{email}:{password_hash}" for email, password_hash in users)
