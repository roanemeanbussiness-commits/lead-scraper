from __future__ import annotations

import dns.resolver


def has_mx_record(email: str) -> bool:
    if not email or "@" not in email:
        return False

    domain = email.rsplit("@", maxsplit=1)[1].strip().lower()
    if not domain:
        return False

    try:
        records = dns.resolver.resolve(domain, "MX")
    except Exception:
        return False
    return len(records) > 0

