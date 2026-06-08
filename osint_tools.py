"""
osint_tools.py — JARVIS v3 OSINT Toolkit

All tools use free public APIs or standard protocols — no API keys required
for core functionality. Optional API keys (Shodan, HIBP, SecurityTrails) unlock
richer results but nothing breaks without them.

Sources / inspiration:
  crt.sh, HaveIBeenPwned, Shodan, Wayback Machine, GitHub API,
  ipinfo.io, whois, DNS, Subfinder approach via crt.sh,
  OSINTFramework, theHarvester techniques, SpiderFoot concepts,
  Dorkwright, GoodOldSearch, user-scanner, CrossTrace

ETHICAL NOTICE:  These tools query *publicly available* information only.
Use responsibly and in accordance with applicable laws.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import socket
import ssl
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_S = requests.Session()
_S.headers.update({"User-Agent": "Mozilla/5.0 JARVIS-OSINT/3.0"})
_TIMEOUT = 8


# ─────────────────────────────────────────────────────────────────────────────
# USERNAME  /  SOCIAL MEDIA
# ─────────────────────────────────────────────────────────────────────────────

# Platforms to check: {display_name: url_template}
_PLATFORMS = {
    "GitHub":         "https://github.com/{}",
    "Twitter/X":      "https://x.com/{}",
    "Instagram":      "https://www.instagram.com/{}/",
    "Reddit":         "https://www.reddit.com/user/{}",
    "TikTok":         "https://www.tiktok.com/@{}",
    "YouTube":        "https://www.youtube.com/@{}",
    "LinkedIn":       "https://www.linkedin.com/in/{}",
    "Pinterest":      "https://www.pinterest.com/{}/",
    "Twitch":         "https://www.twitch.tv/{}",
    "Steam":          "https://steamcommunity.com/id/{}",
    "Spotify":        "https://open.spotify.com/user/{}",
    "SoundCloud":     "https://soundcloud.com/{}",
    "Medium":         "https://medium.com/@{}",
    "Dev.to":         "https://dev.to/{}",
    "Keybase":        "https://keybase.io/{}",
    "Pastebin":       "https://pastebin.com/u/{}",
    "Hackerone":      "https://hackerone.com/{}",
    "Bugcrowd":       "https://bugcrowd.com/{}",
    "GitLab":         "https://gitlab.com/{}",
    "Bitbucket":      "https://bitbucket.org/{}",
    "HuggingFace":    "https://huggingface.co/{}",
    "npm":            "https://www.npmjs.com/~{}",
    "PyPI":           "https://pypi.org/user/{}/",
    "Replit":         "https://replit.com/@{}",
    "Codepen":        "https://codepen.io/{}",
    "Behance":        "https://www.behance.net/{}",
    "Dribbble":       "https://dribbble.com/{}",
    "Vimeo":          "https://vimeo.com/{}",
    "Flickr":         "https://www.flickr.com/people/{}",
    "Tumblr":         "https://{}.tumblr.com",
    "Substack":       "https://{}.substack.com",
    "Mastodon":       "https://mastodon.social/@{}",
    "ProductHunt":    "https://www.producthunt.com/@{}",
    "About.me":       "https://about.me/{}",
    "Gravatar":       "https://en.gravatar.com/{}",
}


def username_search(username: str, workers: int = 12) -> str:
    """
    Check a username across 35+ platforms concurrently.
    Returns a list of found/not-found results.
    """
    username = username.strip().lstrip("@")
    found, not_found, errors = [], [], []

    def _check(name: str, url_tpl: str) -> tuple[str, str, str]:
        url = url_tpl.format(username)
        try:
            r = _S.get(url, timeout=6, allow_redirects=True)
            if r.status_code == 200:
                return "found", name, url
            elif r.status_code == 404:
                return "miss", name, url
            else:
                return "miss", name, url
        except Exception:
            return "error", name, url

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_check, n, u): n for n, u in _PLATFORMS.items()}
        for future in as_completed(futures):
            status, name, url = future.result()
            if status == "found":
                found.append(f"  ✅  {name:<20} {url}")
            elif status == "error":
                errors.append(name)

    lines = [f"Username search: '{username}'", f"Checked {len(_PLATFORMS)} platforms", ""]
    if found:
        lines.append(f"Found ({len(found)}):")
        lines.extend(sorted(found))
    else:
        lines.append("Not found on any checked platform.")
    if errors:
        lines.append(f"\n(Could not reach: {', '.join(errors[:5])}{'...' if len(errors)>5 else ''})")
    return "\n".join(lines)


def social_search(name: str) -> str:
    """Generate pre-built search URLs to find someone across social platforms."""
    q     = urllib.parse.quote_plus(name)
    name_nospace = name.replace(" ", "")
    lines = [f"Social media search links for: {name}", ""]
    searches = [
        ("Google (general)",     f"https://www.google.com/search?q={q}"),
        ("Google (social)",      f'https://www.google.com/search?q="{q}" site:linkedin.com OR site:twitter.com OR site:facebook.com'),
        ("LinkedIn",             f"https://www.linkedin.com/search/results/people/?keywords={q}"),
        ("Twitter/X",            f"https://x.com/search?q={q}&src=typed_query"),
        ("Facebook",             f"https://www.facebook.com/search/people/?q={q}"),
        ("Instagram (dork)",     f'https://www.google.com/search?q="{q}" site:instagram.com'),
        ("TikTok (dork)",        f'https://www.google.com/search?q="{q}" site:tiktok.com'),
        ("GitHub",               f"https://github.com/search?q={q}&type=users"),
        ("YouTube",              f"https://www.youtube.com/results?search_query={q}"),
        ("Reddit",               f"https://www.reddit.com/search/?q={q}&type=user"),
        ("Wayback Machine",      f"https://web.archive.org/web/*/{q}"),
        ("News mentions",        f'https://news.google.com/search?q="{q}"'),
        ("Pastebin (dork)",      f'https://www.google.com/search?q="{q}" site:pastebin.com'),
        ("Cached pages",         f'https://webcache.googleusercontent.com/search?q=cache:"{q}"'),
    ]
    for label, url in searches:
        lines.append(f"  🔗  {label:<22} {url}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────────────────────────────────────

def email_breach_check(email: str, api_key: str = "") -> str:
    """
    Check email against HaveIBeenPwned.
    Free tier: requires API key for full breach list. Without it, returns
    the public paste check (no key needed).
    Get a free key at: https://haveibeenpwned.com/API/Key
    """
    email = email.strip().lower()
    results = []

    # Paste check — no key needed
    try:
        r = _S.get(
            f"https://haveibeenpwned.com/api/v3/pasteaccount/{urllib.parse.quote(email)}",
            headers={"hibp-api-key": api_key} if api_key else {},
            timeout=_TIMEOUT)
        if r.status_code == 200:
            pastes = r.json()
            results.append(f"📋 Found in {len(pastes)} paste(s):")
            for p in pastes[:5]:
                results.append(f"   {p.get('Source','?')} — {p.get('Title','?')} ({p.get('Date','?')[:10]})")
        elif r.status_code == 404:
            results.append("📋 Not found in any public pastes.")
        elif r.status_code == 401:
            results.append("📋 Paste check: API key required.")
    except Exception as e:
        results.append(f"📋 Paste check error: {e}")

    # Breach check — requires API key
    if api_key:
        try:
            r = _S.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{urllib.parse.quote(email)}",
                headers={"hibp-api-key": api_key},
                timeout=_TIMEOUT)
            if r.status_code == 200:
                breaches = r.json()
                results.append(f"\n🔓 Found in {len(breaches)} breach(es):")
                for b in breaches[:10]:
                    date  = b.get("BreachDate", "?")
                    count = b.get("PwnCount", 0)
                    data  = ", ".join(b.get("DataClasses", [])[:4])
                    results.append(f"   {b['Name']:<25} {date}  {count:,} accounts  [{data}]")
            elif r.status_code == 404:
                results.append("\n🔓 Not found in any known breaches. ✅")
        except Exception as e:
            results.append(f"\n🔓 Breach check error: {e}")
    else:
        results.append("\n🔓 Full breach check: set HIBP_API_KEY in config for breach details.")
        results.append("   Get a free key: https://haveibeenpwned.com/API/Key")

    # Email format validation
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return f"Invalid email format: {email}"

    # MX record check (does the domain accept mail?)
    domain = email.split("@")[1]
    try:
        socket.getaddrinfo(domain, None)
        results.insert(0, f"📧 {email}  (domain resolves ✅)\n")
    except socket.gaierror:
        results.insert(0, f"📧 {email}  (domain does NOT resolve ❌)\n")

    return "\n".join(results)


def email_format_guess(domain: str) -> str:
    """
    Guess common email formats for a company domain.
    Useful for targeted searches or verifying formats.
    """
    domain = domain.strip().lower().lstrip("@")
    # Try to extract company name from domain
    company = domain.split(".")[0]
    formats = [
        f"firstname.lastname@{domain}",
        f"firstname@{domain}",
        f"f.lastname@{domain}",
        f"flastname@{domain}",
        f"firstname_lastname@{domain}",
        f"lastname.firstname@{domain}",
        f"lastname@{domain}",
        f"firstnamelastname@{domain}",
        f"firstlast@{domain}",
    ]
    lines = [f"Common email formats for @{domain}:", ""]
    lines += [f"  {fmt}" for fmt in formats]
    lines += [
        "",
        f"Verify with Hunter.io:  https://hunter.io/domain-search/{domain}",
        f"Verify with Phonebook:  https://phonebook.cz/?q={domain}",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# DOMAIN  /  DNS
# ─────────────────────────────────────────────────────────────────────────────

def whois_lookup(domain: str) -> str:
    """WHOIS lookup via IANA/registrar."""
    domain = domain.strip().lower()
    try:
        import whois as pythonwhois
        w = pythonwhois.whois(domain)
        lines = [f"WHOIS: {domain}", ""]
        fields = {
            "Registrar":      w.registrar,
            "Created":        w.creation_date,
            "Expires":        w.expiration_date,
            "Updated":        w.updated_date,
            "Name Servers":   w.name_servers,
            "Status":         w.status,
            "Registrant Org": getattr(w, "org", None),
            "Country":        getattr(w, "country", None),
            "Emails":         w.emails,
        }
        for k, v in fields.items():
            if v:
                val = v[0] if isinstance(v, list) else v
                lines.append(f"  {k:<18} {str(val)[:80]}")
        return "\n".join(lines)
    except ImportError:
        pass  # fall back to raw socket approach

    # Fallback: raw WHOIS socket
    try:
        tld  = domain.split(".")[-1]
        server = f"whois.iana.org"
        with socket.create_connection((server, 43), timeout=8) as s:
            s.sendall(f"{domain}\r\n".encode())
            response = b""
            while chunk := s.recv(4096):
                response += chunk
        text = response.decode("utf-8", errors="replace")
        # Find the actual whois server from IANA response
        m = re.search(r"whois:\s+(\S+)", text)
        if m:
            real_server = m.group(1)
            with socket.create_connection((real_server, 43), timeout=8) as s:
                s.sendall(f"{domain}\r\n".encode())
                response = b""
                while chunk := s.recv(4096):
                    response += chunk
            text = response.decode("utf-8", errors="replace")
        # Extract key fields
        lines = [f"WHOIS: {domain}", ""]
        for pattern, label in [
            (r"(?:Registrar|registrar):\s*(.+)",          "Registrar"),
            (r"(?:Creation Date|created):\s*(.+)",         "Created"),
            (r"(?:Registry Expiry|expires):\s*(.+)",       "Expires"),
            (r"(?:Name Server|nserver):\s*(.+)",           "Name Server"),
            (r"(?:Registrant Organization|org):\s*(.+)",   "Registrant Org"),
            (r"(?:Registrant Email|e-mail):\s*(.+)",       "Email"),
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                lines.append(f"  {label:<18} {m.group(1).strip()[:80]}")
        return "\n".join(lines) if len(lines) > 2 else f"WHOIS data:\n{text[:1000]}"
    except Exception as e:
        return f"WHOIS error: {e}\nTry: https://lookup.icann.org/en/lookup?name={domain}"


def dns_lookup(domain: str, record_type: str = "ALL") -> str:
    """Query DNS records for a domain. record_type: A, AAAA, MX, TXT, NS, CNAME, ALL"""
    domain = domain.strip().lower()
    try:
        import dns.resolver
        has_dnspython = True
    except ImportError:
        has_dnspython = False

    results = [f"DNS lookup: {domain}", ""]

    if has_dnspython:
        import dns.resolver
        types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"] if record_type.upper() == "ALL" else [record_type.upper()]
        for rtype in types:
            try:
                answers = dns.resolver.resolve(domain, rtype, lifetime=6)
                for rdata in answers:
                    results.append(f"  {rtype:<8} {rdata.to_text()[:120]}")
            except Exception:
                pass
    else:
        # Fallback: use socket for A records only
        try:
            ips = socket.getaddrinfo(domain, None)
            seen = set()
            for info in ips:
                ip = info[4][0]
                if ip not in seen:
                    seen.add(ip)
                    results.append(f"  A        {ip}")
        except Exception as e:
            results.append(f"  DNS error: {e}")
        results.append("\nFor full DNS records: pip install dnspython")

    if len(results) <= 2:
        results.append("  No records found.")
    return "\n".join(results)


def subdomain_enum(domain: str, max_results: int = 100) -> str:
    """
    Enumerate subdomains using certificate transparency logs (crt.sh).
    No API key needed. Same technique as Subfinder's passive mode.
    """
    domain = domain.strip().lower()
    try:
        r = requests.get(
            f"https://crt.sh/?q=%.{domain}&output=json",
            timeout=15,
            headers={"User-Agent": "JARVIS-OSINT/3.0"})
        r.raise_for_status()
        entries = r.json()
        subs = set()
        for entry in entries:
            names = entry.get("name_value", "").split("\n")
            for name in names:
                name = name.strip().lower()
                if name.endswith(f".{domain}") and "*" not in name:
                    subs.add(name)

        if not subs:
            return f"No subdomains found for {domain} via crt.sh"

        sorted_subs = sorted(subs)[:max_results]
        lines = [
            f"Subdomains of {domain} (via crt.sh)",
            f"Found {len(subs)} unique subdomain(s):",
            "",
        ]
        lines.extend(f"  {s}" for s in sorted_subs)
        if len(subs) > max_results:
            lines.append(f"\n  … {len(subs) - max_results} more (increase max_results)")
        lines.append(f"\nFull list: https://crt.sh/?q=%.{domain}")
        return "\n".join(lines)
    except Exception as e:
        return f"Subdomain enum error: {e}"


def ssl_cert_info(domain: str, port: int = 443) -> str:
    """Retrieve and display SSL certificate information for a domain."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

        subject  = dict(x[0] for x in cert.get("subject", []))
        issuer   = dict(x[0] for x in cert.get("issuer", []))
        san      = [v for t, v in cert.get("subjectAltName", []) if t == "DNS"]
        not_after = cert.get("notAfter", "?")
        not_before = cert.get("notBefore", "?")

        lines = [f"SSL Certificate: {domain}:{port}", ""]
        lines.append(f"  Subject CN:    {subject.get('commonName','?')}")
        lines.append(f"  Issuer:        {issuer.get('organizationName','?')}")
        lines.append(f"  Valid from:    {not_before}")
        lines.append(f"  Valid until:   {not_after}")
        if san:
            lines.append(f"  Alt names ({len(san)}):  {', '.join(san[:8])}")
            if len(san) > 8:
                lines.append(f"               … {len(san)-8} more")
        lines.append(f"\n  crt.sh history: https://crt.sh/?q={domain}")
        return "\n".join(lines)
    except ssl.SSLCertVerificationError as e:
        return f"⚠️ SSL certificate invalid: {e}"
    except Exception as e:
        return f"SSL cert error: {e}"


def wayback_lookup(url: str) -> str:
    """Check the Wayback Machine for archived snapshots of a URL."""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    try:
        r = requests.get(
            f"https://archive.org/wayback/available?url={urllib.parse.quote(url)}",
            timeout=_TIMEOUT)
        data = r.json()
        snap = data.get("archived_snapshots", {}).get("closest", {})
        lines = [f"Wayback Machine: {url}", ""]
        if snap.get("available"):
            lines.append(f"  ✅ Closest snapshot: {snap.get('timestamp', '?')[:8]}")
            lines.append(f"  📸 URL: {snap.get('url', '?')}")
        else:
            lines.append("  ❌ No snapshots found.")
        lines.append(f"\n  Full history: https://web.archive.org/web/*/{url}")

        # Also check via CDX API for count
        try:
            cdx = requests.get(
                f"https://web.archive.org/cdx/search/cdx?url={url}&output=json&limit=5&fl=timestamp,statuscode",
                timeout=8)
            if cdx.ok:
                snaps = cdx.json()
                if len(snaps) > 1:
                    lines.append(f"  Recent snapshots ({len(snaps)-1} shown):")
                    for row in snaps[1:]:
                        ts = row[0]
                        sc = row[1]
                        dt = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[8:10]}:{ts[10:12]}"
                        lines.append(f"    {dt}  HTTP {sc}")
        except Exception:
            pass
        return "\n".join(lines)
    except Exception as e:
        return f"Wayback error: {e}"


def tech_stack(domain: str) -> str:
    """
    Detect technologies used on a website using HTTP headers and HTML patterns.
    Inspired by Wappalyzer techniques.
    """
    url = f"https://{domain}" if not domain.startswith("http") else domain
    try:
        r = _S.get(url, timeout=10, allow_redirects=True)
    except Exception as e:
        return f"Tech stack error: {e}"

    headers  = {k.lower(): v for k, v in r.headers.items()}
    body     = r.text[:30000].lower()
    detected = {}

    checks = {
        # Server
        "server":        headers.get("server", ""),
        "x-powered-by":  headers.get("x-powered-by", ""),
        # Frameworks (body)
        "WordPress":     "wp-content" in body or "wordpress" in body,
        "React":         "react" in body or "_next" in body or "reactdom" in body,
        "Vue.js":        "vue.js" in body or "__vue__" in body,
        "Angular":       "ng-version" in body or "angular" in body,
        "jQuery":        "jquery" in body,
        "Bootstrap":     "bootstrap" in body,
        "Next.js":       "_next/static" in body,
        "Nuxt":          "__nuxt" in body,
        "Laravel":       "laravel" in body,
        "Django":        "django" in body or "csrfmiddlewaretoken" in body,
        "Ruby on Rails": "rails" in body,
        "ASP.NET":       "asp.net" in body or "__viewstate" in body,
        "PHP":           ".php" in body or "x-powered-by" in headers.get("x-powered-by","").lower() and "php" in headers.get("x-powered-by","").lower(),
        # Analytics
        "Google Analytics": "google-analytics.com" in body or "gtag" in body,
        "Cloudflare":    "__cfduid" in r.cookies or "cloudflare" in headers.get("server","").lower(),
        "Nginx":         "nginx" in headers.get("server","").lower(),
        "Apache":        "apache" in headers.get("server","").lower(),
        "IIS":           "iis" in headers.get("server","").lower() or "asp.net" in headers.get("x-powered-by","").lower(),
        # CDN
        "Fastly":        "fastly" in str(headers),
        "Akamai":        "akamai" in str(headers) or "x-check-cacheable" in headers,
        "AWS":           "x-amz" in str(headers) or "amazonaws" in str(headers),
        "Vercel":        "x-vercel" in str(headers),
        "Netlify":       "x-nf-request-id" in headers,
    }

    found = []
    for tech, val in checks.items():
        if val is True:
            found.append(tech)
        elif isinstance(val, str) and val:
            found.append(f"{tech}: {val[:60]}")

    lines = [f"Tech stack: {domain}", ""]
    if found:
        for item in found:
            lines.append(f"  🔧 {item}")
    else:
        lines.append("  No common technologies detected.")
    lines.append(f"\n  Full analysis: https://www.wappalyzer.com/lookup/{domain}")
    lines.append(f"  BuiltWith:     https://builtwith.com/{domain}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# IP / HOST
# ─────────────────────────────────────────────────────────────────────────────

def ip_osint(ip_or_host: str) -> str:
    """
    Comprehensive IP/host intelligence:
    geolocation, ASN, reverse DNS, abuse reports, open ports (top 20).
    """
    target = ip_or_host.strip()

    # Resolve hostname to IP
    ip = target
    hostname = None
    try:
        if not re.match(r"^\d+\.\d+\.\d+\.\d+$", target):
            ip = socket.gethostbyname(target)
            hostname = target
    except Exception:
        return f"Cannot resolve: {target}"

    # Reverse DNS
    if not hostname:
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except Exception:
            hostname = "No reverse DNS"

    lines = [f"IP Intelligence: {ip}", f"Hostname: {hostname}", ""]

    # Geolocation via ipinfo.io (free, no key)
    try:
        r = requests.get(f"https://ipinfo.io/{ip}/json", timeout=_TIMEOUT)
        if r.ok:
            d = r.json()
            lines.append(f"  📍 Location:  {d.get('city','?')}, {d.get('region','?')}, {d.get('country','?')}")
            lines.append(f"  🏢 ISP/ASN:   {d.get('org','?')}")
            lines.append(f"  📮 Postal:    {d.get('postal','?')}")
            lines.append(f"  🌐 Timezone:  {d.get('timezone','?')}")
    except Exception as e:
        lines.append(f"  Geo lookup error: {e}")

    # Abuse check via AbuseIPDB (no key needed for basic)
    try:
        r = requests.get(
            f"https://api.abuseipdb.com/api/v2/check",
            params={"ipAddress": ip, "maxAgeInDays": 90},
            headers={"Key": "", "Accept": "application/json"},
            timeout=_TIMEOUT)
        if r.ok:
            data = r.json().get("data", {})
            score = data.get("abuseConfidenceScore", 0)
            reports = data.get("totalReports", 0)
            if reports > 0:
                lines.append(f"\n  ⚠️  AbuseIPDB: {reports} report(s), confidence {score}%")
    except Exception:
        pass

    # Shodan InternetDB (no API key needed!)
    try:
        r = requests.get(f"https://internetdb.shodan.io/{ip}", timeout=_TIMEOUT)
        if r.ok:
            d = r.json()
            ports = d.get("ports", [])
            vulns = d.get("vulns", [])
            cpes  = d.get("cpes", [])
            tags  = d.get("tags", [])
            lines.append(f"\n  🔌 Open ports:  {', '.join(str(p) for p in sorted(ports)) or 'none found'}")
            if cpes:
                lines.append(f"  📦 Software:    {', '.join(cpes[:5])}")
            if vulns:
                lines.append(f"  🔴 CVEs:        {', '.join(list(vulns)[:5])}")
            if tags:
                lines.append(f"  🏷️  Tags:        {', '.join(tags)}")
    except Exception:
        pass

    lines.append(f"\n  Shodan:    https://www.shodan.io/host/{ip}")
    lines.append(f"  GreyNoise: https://www.greynoise.io/viz/ip/{ip}")
    lines.append(f"  VirusTotal:https://www.virustotal.com/gui/ip-address/{ip}")
    lines.append(f"  Censys:    https://search.censys.io/hosts/{ip}")

    return "\n".join(lines)


def port_scan(host: str, ports: str = "21,22,23,25,53,80,110,143,443,445,3306,3389,5432,5900,6379,8080,8443,9200,27017") -> str:
    """
    Quick TCP port scanner. ports = comma-separated list or range like 1-1024.
    """
    host = host.strip()

    # Parse ports
    port_list = []
    for part in ports.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            port_list.extend(range(int(a), int(b) + 1))
        else:
            port_list.append(int(part))

    open_ports, closed_ports = [], []

    def _check(port: int) -> tuple[int, bool, str]:
        try:
            sock = socket.create_connection((host, port), timeout=1.5)
            # Try to grab a banner
            banner = ""
            try:
                sock.settimeout(1)
                data = sock.recv(256)
                banner = data.decode("utf-8", errors="replace").strip()[:60]
            except Exception:
                pass
            sock.close()
            return port, True, banner
        except Exception:
            return port, False, ""

    with ThreadPoolExecutor(max_workers=50) as pool:
        for port, is_open, banner in pool.map(_check, port_list):
            if is_open:
                open_ports.append((port, banner))
            else:
                closed_ports.append(port)

    lines = [f"Port scan: {host}", f"Scanned {len(port_list)} port(s)", ""]
    if open_ports:
        lines.append(f"Open ports ({len(open_ports)}):")
        for port, banner in sorted(open_ports):
            svc = _COMMON_PORTS.get(port, "")
            b = f"  [{banner}]" if banner else ""
            lines.append(f"  ✅  {port:<6} {svc:<12}{b}")
    else:
        lines.append("  No open ports found.")
    lines.append(f"\nFor deeper scanning: nmap -sV -T4 {host}")
    return "\n".join(lines)


_COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
    6379: "Redis", 8080: "HTTP-alt", 8443: "HTTPS-alt",
    9200: "Elasticsearch", 27017: "MongoDB",
}


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE DORKING
# ─────────────────────────────────────────────────────────────────────────────

def generate_dorks(target: str, dork_type: str = "all") -> str:
    """
    Generate Google dork queries for a target (domain, company, or person).
    dork_type: all | files | login | email | sensitive | social | vuln
    """
    t = target.strip()
    is_domain = "." in t and " " not in t

    dorks: dict[str, list[tuple[str, str]]] = {
        "files": [
            ("PDF documents",    f'site:{t} filetype:pdf'),
            ("Word documents",   f'site:{t} filetype:docx OR filetype:doc'),
            ("Excel files",      f'site:{t} filetype:xlsx OR filetype:csv'),
            ("PowerPoints",      f'site:{t} filetype:pptx'),
            ("SQL dumps",        f'site:{t} filetype:sql'),
            ("Config files",     f'site:{t} filetype:env OR filetype:cfg OR filetype:conf'),
            ("Log files",        f'site:{t} filetype:log'),
            ("Backup files",     f'site:{t} filetype:bak OR filetype:backup'),
            ("XML files",        f'site:{t} filetype:xml'),
            ("JSON endpoints",   f'site:{t} filetype:json'),
        ],
        "login": [
            ("Login pages",      f'site:{t} inurl:login OR inurl:signin OR inurl:admin'),
            ("Admin panels",     f'site:{t} inurl:admin OR inurl:administrator OR inurl:wp-admin'),
            ("Dashboard",        f'site:{t} inurl:dashboard OR inurl:panel OR inurl:console'),
            ("Password resets",  f'site:{t} inurl:reset OR inurl:forgot-password'),
            ("Register pages",   f'site:{t} inurl:register OR inurl:signup'),
        ],
        "email": [
            ("Email addresses",  f'site:{t} "@{t if is_domain else ""}"' if is_domain else f'"{t}" email OR "@gmail" OR "@yahoo"'),
            ("Contact pages",    f'site:{t} inurl:contact OR inurl:about'),
            ("Staff directory",  f'site:{t} "staff" OR "team" OR "directory" OR "employees"'),
        ],
        "sensitive": [
            ("API keys/tokens",  f'site:{t} "api_key" OR "api_secret" OR "access_token"'),
            ("Passwords",        f'site:{t} "password" filetype:txt OR filetype:env'),
            ("AWS keys",         f'site:{t} "AKIA" OR "aws_access_key"'),
            ("Connection strings",f'site:{t} "connectionstring" OR "jdbc:" OR "mongodb://"'),
            ("Internal IPs",     f'site:{t} "192.168." OR "10.0." OR "172.16."'),
            ("Error messages",   f'site:{t} "SQL syntax" OR "Warning: mysql" OR "stack trace"'),
            ("Directory listing",f'site:{t} intitle:"Index of /"'),
        ],
        "vuln": [
            ("Open redirects",   f'site:{t} inurl:"redirect=" OR inurl:"url=" OR inurl:"next="'),
            ("PHP files",        f'site:{t} filetype:php inurl:"?"'),
            ("Old/dev sites",    f'site:{t} inurl:dev OR inurl:staging OR inurl:test OR inurl:beta'),
            ("Exposed git",      f'site:{t} inurl:"/.git/"'),
            ("phpMyAdmin",       f'site:{t} inurl:phpmyadmin'),
            ("Exposed .env",     f'site:{t} inurl:".env"'),
        ],
        "social": [
            ("GitHub mentions",  f'"{t}" site:github.com'),
            ("LinkedIn",         f'"{t}" site:linkedin.com'),
            ("Twitter/X",        f'"{t}" site:x.com OR site:twitter.com'),
            ("News",             f'"{t}" site:news.google.com OR inurl:news'),
            ("Pastebin",         f'"{t}" site:pastebin.com'),
            ("Reddit",           f'"{t}" site:reddit.com'),
        ],
    }

    selected = {}
    if dork_type == "all":
        selected = dorks
    elif dork_type in dorks:
        selected = {dork_type: dorks[dork_type]}
    else:
        return f"Unknown dork type: {dork_type}. Use: {', '.join(dorks.keys())} or all"

    lines = [f"Google Dorks for: {target}", ""]
    for category, items in selected.items():
        lines.append(f"── {category.upper()} ──")
        for label, query in items:
            encoded = urllib.parse.quote_plus(query)
            lines.append(f"  {label:<25} https://www.google.com/search?q={encoded}")
        lines.append("")
    lines.append("Tip: Also try https://goodoldsearch.com/ for advanced search")
    return "\n".join(lines)


def google_dork(query: str) -> str:
    """Run a custom Google dork query. Returns the search URL."""
    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={encoded}"
    return f"Search: {query}\nURL: {url}\nOpen in browser: {url}"


# ─────────────────────────────────────────────────────────────────────────────
# GITHUB OSINT
# ─────────────────────────────────────────────────────────────────────────────

def github_user_osint(username: str) -> str:
    """
    Pull public GitHub intelligence: profile, repos, contributions,
    email exposure, commit history.
    Uses GitHub public API — no key needed (60 req/hr).
    """
    username = username.strip().lstrip("@")
    lines = [f"GitHub OSINT: {username}", ""]

    # Profile
    try:
        r = requests.get(f"https://api.github.com/users/{username}",
                         timeout=_TIMEOUT,
                         headers={"Accept": "application/vnd.github.v3+json"})
        if r.status_code == 404:
            return f"GitHub user not found: {username}"
        r.raise_for_status()
        u = r.json()
        lines += [
            f"  Name:          {u.get('name','?')}",
            f"  Bio:           {u.get('bio','') or 'None'}",
            f"  Location:      {u.get('location','?')}",
            f"  Email:         {u.get('email','not public') or 'not public'}",
            f"  Company:       {u.get('company','?')}",
            f"  Blog/Website:  {u.get('blog','?')}",
            f"  Twitter:       {u.get('twitter_username','?')}",
            f"  Followers:     {u.get('followers',0):,}",
            f"  Following:     {u.get('following',0):,}",
            f"  Public repos:  {u.get('public_repos',0)}",
            f"  Public gists:  {u.get('public_gists',0)}",
            f"  Account created: {u.get('created_at','?')[:10]}",
            f"  Last active:   {u.get('updated_at','?')[:10]}",
            f"  Profile:       {u.get('html_url','')}",
            "",
        ]
    except Exception as e:
        lines.append(f"  Profile error: {e}")

    # Recent repos
    try:
        r = requests.get(f"https://api.github.com/users/{username}/repos?sort=updated&per_page=8",
                         timeout=_TIMEOUT,
                         headers={"Accept": "application/vnd.github.v3+json"})
        repos = r.json()
        if isinstance(repos, list) and repos:
            lines.append(f"  Recent repos ({len(repos)}):")
            for repo in repos[:8]:
                stars = repo.get("stargazers_count", 0)
                lang  = repo.get("language") or "?"
                lines.append(f"    ⭐{stars:>4}  [{lang:<12}]  {repo['name']}")
            lines.append("")
    except Exception:
        pass

    # Email hunting via commit history
    try:
        r = requests.get(
            f"https://api.github.com/users/{username}/events/public?per_page=30",
            timeout=_TIMEOUT,
            headers={"Accept": "application/vnd.github.v3+json"})
        events = r.json()
        emails = set()
        if isinstance(events, list):
            for event in events:
                if event.get("type") == "PushEvent":
                    for commit in event.get("payload", {}).get("commits", []):
                        email = commit.get("author", {}).get("email", "")
                        if email and not email.endswith("@users.noreply.github.com"):
                            emails.add(email)
        if emails:
            lines.append(f"  📧 Emails found in commits:")
            for email in sorted(emails):
                lines.append(f"    {email}")
            lines.append("")
        else:
            lines.append("  📧 No emails exposed in recent commits.")
    except Exception:
        pass

    lines.append(f"  Full profile: https://github.com/{username}")
    lines.append(f"  Dork:         https://www.google.com/search?q=site:github.com/{username}")
    return "\n".join(lines)


def github_secret_search(repo: str) -> str:
    """
    Search a public GitHub repo for potential accidentally-committed secrets.
    Uses GitHub code search API (no key needed, rate limited).
    """
    lines = [f"Secret scan: {repo}", ""]
    patterns = [
        "api_key", "api_secret", "password", "secret", "token",
        "AKIA", "private_key", "aws_access", ".env",
    ]
    for p in patterns:
        q  = urllib.parse.quote_plus(f"{p} repo:{repo}")
        url = f"https://github.com/search?q={q}&type=code"
        lines.append(f"  {p:<20} {url}")
    lines.append(f"\nTruffleHog (deep scan): trufflehog github --repo=https://github.com/{repo}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# FILE / DOCUMENT METADATA
# ─────────────────────────────────────────────────────────────────────────────

def extract_metadata(file_path: str) -> str:
    """
    Extract OSINT-relevant metadata from files.
    PDFs: author, creator, creation date.
    Images: GPS coords, camera make/model, timestamps.
    Office docs: author, company, last saved by.
    """
    path = Path(os.path.expanduser(file_path))
    if not path.exists():
        return f"File not found: {file_path}"

    ext  = path.suffix.lower()
    lines = [f"Metadata: {path.name}", ""]

    # PDF
    if ext == ".pdf":
        try:
            import fitz
            doc  = fitz.open(str(path))
            meta = doc.metadata
            doc.close()
            for k, v in meta.items():
                if v:
                    lines.append(f"  {k:<20} {str(v)[:100]}")
        except ImportError:
            lines.append("  PyMuPDF not installed: pip install pymupdf")
        except Exception as e:
            lines.append(f"  PDF metadata error: {e}")

    # Images (EXIF)
    elif ext in (".jpg", ".jpeg", ".tiff", ".png", ".heic"):
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS
            img  = Image.open(path)
            exif = img._getexif() or {}
            gps  = {}
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == "GPSInfo":
                    for gps_tag, gps_val in value.items():
                        gps[GPSTAGS.get(gps_tag, gps_tag)] = gps_val
                elif tag in ("Make", "Model", "Software", "DateTime",
                              "DateTimeOriginal", "Artist", "Copyright",
                              "ImageDescription", "XPAuthor"):
                    lines.append(f"  {tag:<20} {str(value)[:80]}")
            if gps:
                # Convert GPS to decimal degrees
                def _dms(d): return d[0] + d[1]/60 + d[2]/3600
                try:
                    lat  = _dms(gps["GPSLatitude"])
                    lon  = _dms(gps["GPSLongitude"])
                    if gps.get("GPSLatitudeRef")  == "S": lat  = -lat
                    if gps.get("GPSLongitudeRef") == "W": lon  = -lon
                    lines.append(f"  {'GPS Coords':<20} {lat:.6f}, {lon:.6f}")
                    lines.append(f"  {'Google Maps':<20} https://maps.google.com/maps?q={lat},{lon}")
                except Exception:
                    pass
        except ImportError:
            lines.append("  Pillow not installed: pip install Pillow")
        except Exception as e:
            lines.append(f"  Image metadata error: {e}")

    # Office docs
    elif ext in (".docx", ".xlsx", ".pptx"):
        try:
            import zipfile, xml.etree.ElementTree as ET
            with zipfile.ZipFile(str(path)) as zf:
                core_xml = zf.read("docProps/core.xml")
                root = ET.fromstring(core_xml)
                ns = {"dc": "http://purl.org/dc/elements/1.1/",
                      "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"}
                for tag, label in [
                    (".//dc:creator",              "Author"),
                    (".//cp:lastModifiedBy",        "Last saved by"),
                    (".//cp:created",               "Created"),
                    (".//cp:modified",              "Modified"),
                    (".//dc:description",           "Description"),
                    (".//cp:keywords",              "Keywords"),
                ]:
                    el = root.find(tag, ns)
                    if el is not None and el.text:
                        lines.append(f"  {label:<20} {el.text[:100]}")
        except Exception as e:
            lines.append(f"  Office metadata error: {e}")

    if len(lines) <= 2:
        lines.append("  No metadata found.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# REVERSE IMAGE / FACE SEARCH
# ─────────────────────────────────────────────────────────────────────────────

def reverse_image_search(image_path_or_url: str) -> str:
    """
    Generate reverse image search links for an image file or URL.
    Covers Google, TinEye, Bing, Yandex (best for face search), and PimEyes.
    """
    src = image_path_or_url.strip()
    lines = [f"Reverse image search: {Path(src).name if not src.startswith('http') else src}", ""]

    if src.startswith("http"):
        encoded = urllib.parse.quote_plus(src)
        links = [
            ("Google Images",  f"https://images.google.com/searchbyimage?image_url={encoded}"),
            ("TinEye",         f"https://tineye.com/search?url={encoded}"),
            ("Bing Visual",    f"https://www.bing.com/images/search?view=detailv2&iss=sbi&form=SBIVSP&q=imgurl:{encoded}"),
            ("Yandex (faces)", f"https://yandex.com/images/search?url={encoded}&rpt=imageview"),
            ("PimEyes (faces)",  "https://pimeyes.com/en"),
        ]
    else:
        # Local file — give instructions
        lines.append("Local file detected. Upload to an image host first, or use drag-and-drop on:")
        links = [
            ("Google Images",   "https://images.google.com  (click 📷)"),
            ("TinEye",          "https://tineye.com  (drag & drop)"),
            ("Yandex (faces)",  "https://yandex.com/images  (best for faces)"),
            ("PimEyes (faces)", "https://pimeyes.com/en  (face search)"),
            ("FaceCheck.id",    "https://facecheck.id  (face recognition)"),
        ]

    for name, url in links:
        lines.append(f"  🔍  {name:<20} {url}")

    lines.append("\nTip: Yandex is most effective for finding faces of non-public figures.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# PHONE
# ─────────────────────────────────────────────────────────────────────────────

def phone_lookup(number: str) -> str:
    """
    Look up a phone number: country, carrier type, format, and search links.
    Uses phonenumbers library (graceful fallback without it).
    """
    number = re.sub(r"[\s\-\(\)]", "", number.strip())
    if not number.startswith("+"):
        number = "+" + number

    lines = [f"Phone: {number}", ""]

    try:
        import phonenumbers
        from phonenumbers import geocoder, carrier, timezone
        parsed = phonenumbers.parse(number)
        valid  = phonenumbers.is_valid_number(parsed)
        lines.append(f"  Valid:        {'✅' if valid else '❌'}")
        lines.append(f"  Country:      {geocoder.description_for_number(parsed, 'en')}")
        lines.append(f"  Carrier:      {carrier.name_for_number(parsed, 'en') or 'Unknown'}")
        lines.append(f"  Timezones:    {', '.join(timezone.time_zones_for_number(parsed))}")
        lines.append(f"  Type:         {phonenumbers.number_type(parsed).name}")
        lines.append(f"  International:{phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)}")
    except ImportError:
        lines.append("  Install phonenumbers for detailed info: pip install phonenumbers")
    except Exception as e:
        lines.append(f"  Parse error: {e}")

    encoded = urllib.parse.quote_plus(number)
    lines.append(f"\n  Search links:")
    lines.append(f"    Google:       https://www.google.com/search?q={encoded}")
    lines.append(f"    WhoCalled:    https://www.whocalledme.com/PhoneNumber/{number.lstrip('+')}")
    lines.append(f"    Truecaller:   https://www.truecaller.com/search/us/{number.lstrip('+')}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# COMPREHENSIVE TARGET REPORT
# ─────────────────────────────────────────────────────────────────────────────

def full_domain_report(domain: str) -> str:
    """
    Run a full passive OSINT report on a domain:
    WHOIS + DNS + subdomains + SSL cert + tech stack + Wayback.
    """
    domain = domain.strip().lower()
    sections = []

    sections.append(f"{'='*50}")
    sections.append(f"OSINT REPORT: {domain}")
    sections.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sections.append(f"{'='*50}\n")

    for label, fn in [
        ("WHOIS",         lambda: whois_lookup(domain)),
        ("DNS RECORDS",   lambda: dns_lookup(domain, "ALL")),
        ("SSL CERT",      lambda: ssl_cert_info(domain)),
        ("SUBDOMAINS",    lambda: subdomain_enum(domain, max_results=30)),
        ("TECH STACK",    lambda: tech_stack(domain)),
        ("WAYBACK",       lambda: wayback_lookup(domain)),
        ("IP INTEL",      lambda: ip_osint(domain)),
    ]:
        try:
            sections.append(f"── {label} {'─'*(44-len(label))}")
            sections.append(fn())
        except Exception as e:
            sections.append(f"  Error: {e}")
        sections.append("")

    sections.append(f"{'─'*50}")
    sections.append("Additional tools:")
    sections.append(f"  Shodan:        https://www.shodan.io/search?query={domain}")
    sections.append(f"  SecurityTrails:https://securitytrails.com/domain/{domain}/history/a")
    sections.append(f"  SpiderFoot:    https://github.com/smicallef/spiderfoot")
    sections.append(f"  OSINT Framework: https://osintframework.com/")
    return "\n".join(sections)


def full_person_report(name: str, extras: str = "") -> str:
    """
    Passive OSINT report on a person: social search, username check,
    Google dorks, news mentions, image search links.
    """
    sections = []
    sections.append(f"{'='*50}")
    sections.append(f"PERSON OSINT: {name}")
    sections.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sections.append(f"{'='*50}\n")

    # Guess username variants
    parts = name.lower().split()
    usernames = []
    if len(parts) >= 2:
        f, l = parts[0], parts[-1]
        usernames = [f"{f}{l}", f"{f}.{l}", f"{f}_{l}", f"{f[0]}{l}", f"{l}{f[0]}"]

    sections.append("── SOCIAL SEARCH ─────────────────────────────────")
    sections.append(social_search(name))
    sections.append("")

    if usernames:
        sections.append("── LIKELY USERNAMES ───────────────────────────────")
        sections.append(f"Based on '{name}':")
        for u in usernames[:4]:
            sections.append(f"  {u}  →  run: username_search({u})")
        sections.append("")

    sections.append("── GOOGLE DORKS ───────────────────────────────────")
    sections.append(generate_dorks(name, "social"))
    sections.append("")

    sections.append("── REVERSE IMAGE SEARCH ───────────────────────────")
    sections.append(reverse_image_search("upload a photo to search"))
    sections.append("")

    if extras:
        sections.append("── EMAIL / BREACH CHECK ───────────────────────────")
        if "@" in extras:
            sections.append(email_breach_check(extras))
        elif extras.startswith("+") or extras.replace("-","").isdigit():
            sections.append(phone_lookup(extras))
        sections.append("")

    sections.append("── ADDITIONAL RESOURCES ───────────────────────────")
    sections.append(f"  OSINT Framework:   https://osintframework.com/")
    sections.append(f"  IntelTechniques:   https://inteltechniques.com/tools/index.html")
    sections.append(f"  Trace Labs:        https://www.tracelabs.org/")
    return "\n".join(sections)


# ── Mark-XL entry point ────────────────────────────────────────────────────

def run_osint(action: str, target: str, args: dict = None) -> str:
    """
    Unified entry point called by Mark-XL's _execute_tool dispatcher.
    action: whois | dns | subdomains | breach_check | port_scan | dork | geoip | username | ssl | tech
    """
    args = args or {}
    try:
        if action == "whois":
            return whois_lookup(target)
        elif action == "dns":
            return dns_lookup(target, args.get("record_type", "ALL"))
        elif action == "subdomains":
            return subdomain_enum(target)
        elif action == "breach_check":
            return email_breach_check(target)
        elif action == "port_scan":
            return port_scan(target, args.get("ports", "80,443,22,21,8080"))
        elif action == "dork":
            return generate_dorks(target)
        elif action == "geoip":
            return ip_osint(target)
        elif action == "username":
            return username_search(target)
        elif action == "ssl":
            return ssl_cert_info(target)
        elif action == "tech":
            return tech_stack(target)
        elif action == "full_report":
            return full_domain_report(target)
        else:
            return f"Unknown OSINT action: {action}. Available: whois, dns, subdomains, breach_check, port_scan, dork, geoip, username, ssl, tech, full_report"
    except Exception as e:
        return f"OSINT error ({action}): {e}"
