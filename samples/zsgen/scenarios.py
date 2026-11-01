"""Planted attacks. Each scenario is a function that returns the requests of one attack, labelled
"attack:<name>" so the answer key knows exactly which log lines are malicious.

Every scenario gets its own random stream (see generate.py), so planting one attack, or a
different subset, never changes the others or the normal traffic around them.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass, replace

from zsgen.request import Request
from zsgen.world import UNCATEGORIZED, User, World

HOUR = 3600
CRITICAL = "Critical (90–100)"  # with an en dash, exactly as Zscaler writes it


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str  # what happened, in an analyst's words (goes into the answer key)
    plant: Callable[[random.Random, World, int], list[Request]]


def pick_user(rng: random.Random, world: World, dept: str, exclude: User | None = None) -> User:
    """A random member of `dept`, avoiding `exclude` unless they're the only one."""
    members = [u for u in world.users if u.dept == dept]
    return rng.choice([u for u in members if u != exclude] or members)


def malware_download(rng: random.Random, world: World, start_ts: int) -> list[Request]:
    """An emailed link leads to an uncategorized site; the .exe it serves is blocked as malware,
    and the user tries again."""
    victim = pick_user(rng, world, "Sales")
    site = world.site("dl.quickfiles-cdn.example")
    label = "attack:malware_download"
    ts = start_ts + 11 * HOUR + 20 * 60 + rng.uniform(0, 300)
    sha256 = f"{rng.getrandbits(256):064x}"
    requests = [
        Request.to_site(
            site,
            ts=ts,
            user=victim,
            path="/invoice/8812",
            method="GET",
            status=200,
            reqsize=rng.randint(600, 800),
            respsize=rng.randint(4_000, 6_000),
            contenttype="text/html",
            referer="mail.officesuite.example",
            riskscore=72,
            rulelabel="Default_Allow",
            ruletype="URL Filtering",
            label=label,
        )
    ]
    for attempt in range(2):
        requests.append(
            Request.to_site(
                site,
                ts=ts + 3 + attempt * rng.uniform(30, 60),
                user=victim,
                path="/invoice/8812/Invoice_8812.exe",
                method="GET",
                status=403,
                reqsize=rng.randint(600, 800),
                respsize=rng.randint(1_800, 2_600),
                contenttype="application/x-msdownload",
                referer=site.host,
                action="Blocked",
                reason="Malicious Content",
                rulelabel="Malware_Protection",
                ruletype="Malware Protection",
                riskscore=95,
                threatname="Trojan.Win32.Emotet",
                threatseverity=CRITICAL,
                malwarecategory="Trojan",
                malwareclass="Sandbox",
                filename="Invoice_8812.exe",
                filetype="Windows Executables",
                sha256=sha256,
                label=label,
            )
        )
    return requests


def phishing(rng: random.Random, world: World, start_ts: int) -> list[Request]:
    """A link in an email opens a look-alike login page; the user proceeds past Zscaler's caution
    page and submits the sign-in form (credentials posted to the attacker)."""
    victim = pick_user(rng, world, "HR")
    site = world.site("officesuite-login.example")
    label = "attack:phishing"
    verdict = {
        "rulelabel": "Caution_Suspected_Phishing",
        "ruletype": "URL Filtering",
        "reason": "User Proceeded After Caution",
        "riskscore": 88,
    }
    ts = start_ts + 10 * HOUR + 40 * 60 + rng.uniform(0, 300)
    requests = [
        Request.to_site(
            site,
            ts=ts,
            user=victim,
            path="/signin",
            method="GET",
            status=200,
            reqsize=rng.randint(600, 800),
            respsize=rng.randint(20_000, 30_000),
            contenttype="text/html",
            referer="mail.officesuite.example",
            label=label,
            **verdict,
        )
    ]
    for path, ctype in [("/assets/login.css", "text/css"), ("/assets/logo.png", "image/png")]:
        requests.append(
            Request.to_site(
                site,
                ts=ts + rng.uniform(0.2, 1.5),
                user=victim,
                path=path,
                method="GET",
                status=200,
                reqsize=rng.randint(500, 700),
                respsize=rng.randint(3_000, 15_000),
                contenttype=ctype,
                referer=site.host,
                label=label,
                **verdict,
            )
        )
    requests.append(
        Request.to_site(  # the user types their password and clicks "Sign in"
            site,
            ts=ts + rng.uniform(15, 40),
            user=victim,
            path="/signin",
            method="POST",
            status=302,
            reqsize=rng.randint(1_200, 1_600),
            respsize=rng.randint(300, 600),
            contenttype="application/x-www-form-urlencoded",
            referer=site.host,
            label=label,
            **verdict,
        )
    )
    return requests


def policy_probing(rng: random.Random, world: World, start_ts: int) -> list[Request]:
    """Someone keeps trying anonymizers and free VPNs to get around the web filter; every
    attempt is blocked."""
    user = pick_user(rng, world, "Engineering")
    hosts = ["www.hidemyway.example", "unblock-proxy.example", "freevpn-now.example"]
    ts = start_ts + 16 * HOUR + rng.uniform(0, 1_800)
    requests = []
    for _ in range(22):
        site = world.site(rng.choice(hosts))
        requests.append(
            Request.to_site(
                site,
                ts=ts,
                user=user,
                path=rng.choice(site.paths),
                method="GET",
                status=403,
                reqsize=rng.randint(600, 800),
                respsize=rng.randint(1_800, 2_600),
                contenttype="text/html",
                action="Blocked",
                reason="Not allowed to browse this category",
                rulelabel="Block_Anonymizers",
                ruletype="URL Filtering",
                riskscore=rng.randint(60, 80),
                label="attack:policy_probing",
            )
        )
        ts += rng.uniform(10, 60)
    return requests


SENSITIVE_FILES = [
    ("Q3_payroll.xlsx", "Microsoft Excel"),
    ("employee_salaries_2026.xlsx", "Microsoft Excel"),
    ("customer_accounts_export.csv", "CSV Files"),
    ("vendor_bank_details.pdf", "PDF Files"),
    ("board_minutes_confidential.docx", "Microsoft Word"),
]


def data_exfiltration(rng: random.Random, world: World, start_ts: int) -> list[Request]:
    """Late at night a Finance employee uploads sensitive documents to a personal file-sharing
    site: large uploads, tiny responses."""
    user = pick_user(rng, world, "Finance")
    site = world.site("www.dropbin.example")
    label = "attack:data_exfiltration"
    ts = start_ts + 23 * HOUR + rng.uniform(0, 600)
    requests = [
        Request.to_site(
            site,
            ts=ts,
            user=user,
            path="/",
            method="GET",
            status=200,
            reqsize=rng.randint(600, 800),
            respsize=rng.randint(30_000, 50_000),
            contenttype="text/html",
            rulelabel="Default_Allow",
            ruletype="URL Filtering",
            riskscore=40,
            label=label,
        )
    ]
    for _ in range(14):
        ts += rng.uniform(30, 120)
        filename, filetype = rng.choice(SENSITIVE_FILES)
        requests.append(
            Request.to_site(
                site,
                ts=ts,
                user=user,
                path="/api/upload",
                method="POST",
                status=200,
                reqsize=rng.randint(4_000_000, 18_000_000),
                respsize=rng.randint(200, 400),
                contenttype="multipart/form-data",
                referer=site.host,
                rulelabel="Default_Allow",
                ruletype="URL Filtering",
                riskscore=40,
                upload_filename=filename,
                filetype=filetype,
                label=label,
            )
        )
    return requests


SCAN_PATHS = (
    "/admin /login /.env /.git/config /wp-login.php /wp-admin/ /phpmyadmin/ /server-status "
    "/backup.zip /backup.sql /db.sql /config.json /config.php /api/v1/users /api/v1/admin "
    "/actuator/health /console /debug /test /old /dev /staging /uploads/ /cgi-bin/ "
    "/.aws/credentials"
).split()


def scanning(rng: random.Random, world: World, start_ts: int) -> list[Request]:
    """A script on an engineer's laptop brute-forces paths on a partner's web portal: 500+
    requests in about two minutes, mostly 404s, with a python-requests user agent."""
    user = pick_user(rng, world, "Engineering", exclude=patient_zero(world))
    site = world.site("portal.partnerhub.example")
    ts = start_ts + 14 * HOUR + 30 * 60 + rng.uniform(0, 600)
    requests = []
    for i in range(520):
        path = SCAN_PATHS[i % len(SCAN_PATHS)]
        if i >= len(SCAN_PATHS):  # after the basic list, try numbered variants
            path = f"{path.rstrip('/')}{i // len(SCAN_PATHS)}"
        status = rng.choices([404, 403, 200], weights=[85, 7, 8])[0]
        requests.append(
            Request.to_site(
                site,
                ts=ts,
                user=user,
                path=path,
                method="GET",
                status=status,
                reqsize=rng.randint(250, 350),
                respsize=rng.randint(400, 700) if status != 200 else rng.randint(2_000, 9_000),
                contenttype="text/html",
                useragent="python-requests/2.31.0",
                rulelabel="Default_Allow",
                ruletype="URL Filtering",
                riskscore=rng.randint(0, 10),
                label="attack:scanning",
            )
        )
        ts += rng.uniform(0.1, 0.32)  # ~5 requests a second
    return requests


# The infected laptop: malware on it first searches for its command server with generated
# domain names (DGA), then beacons to the one that answers. Both scenarios use this device.
C2_DOMAIN = "x9fq2kd7wz.example"
MALWARE_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"  # browser-ish, but truncated


def patient_zero(world: World) -> User:
    """Deterministic, so the DGA and beaconing scenarios agree on the infected device even
    though each has its own random stream."""
    return min((u for u in world.users if u.dept == "Engineering"), key=lambda u: u.login)


def generated_domains(rng: random.Random, world: World, start_ts: int) -> list[Request]:
    """Malware tries ~60 random-looking domains in three minutes; almost none exist. The last
    one that answers is its command server."""
    infected = patient_zero(world)
    ts = start_ts + 3 * HOUR + 5 * 60 + rng.uniform(0, 60)
    requests = []
    for attempt in range(60):
        if attempt == 59:  # found it: the command server
            host, serverip, status = C2_DOMAIN, world.site(C2_DOMAIN).serverip, 200
        elif rng.random() < 0.08:  # a few generated names happen to exist (parked domains)
            host, serverip, status = _random_domain(rng), f"203.0.113.{rng.randint(200, 254)}", 200
        else:  # most don't resolve, so the proxy answers with an error page
            host, serverip, status = _random_domain(rng), None, 502
        requests.append(
            Request(
                ts=ts,
                user=infected,
                host=host,
                path="/",
                method="GET",
                status=status,
                reqsize=rng.randint(300, 400),
                respsize=rng.randint(100, 300) if status == 200 else 1_200,
                contenttype="text/html",
                category=UNCATEGORIZED,
                appname="General Browsing",
                appclass="General Browsing",
                serverip=serverip,
                country="Romania" if status == 200 else None,
                useragent=MALWARE_USER_AGENT,
                rulelabel="Default_Allow",
                ruletype="URL Filtering",
                riskscore=rng.randint(20, 40),
                label="attack:generated_domains",
            )
        )
        ts += rng.uniform(1, 5)
    return requests


def _random_domain(rng: random.Random) -> str:
    return "".join(rng.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=12)) + ".example"


def c2_beaconing(rng: random.Random, world: World, start_ts: int) -> list[Request]:
    """From 03:12 the infected laptop checks in with its command server every ~60 s (±5%),
    with near-constant sizes, for the rest of the simulated period."""
    infected = patient_zero(world)
    site = world.site(C2_DOMAIN)
    agent_id = f"{rng.getrandbits(32):08x}"
    ts = start_ts + 3 * HOUR + 12 * 60 + rng.uniform(0, 30)
    end_ts = start_ts + 24 * HOUR
    requests = []
    while ts < end_ts:
        requests.append(
            Request.to_site(
                site,
                ts=ts,
                user=infected,
                path=f"/api/v2/sync?id={agent_id}",
                method="GET",
                status=200,
                reqsize=380 + rng.randint(-8, 8),
                respsize=140 + rng.randint(-8, 8),
                contenttype="application/octet-stream",
                useragent=MALWARE_USER_AGENT,
                rulelabel="Default_Allow",
                ruletype="URL Filtering",
                riskscore=rng.randint(20, 40),
                label="attack:c2_beaconing",
            )
        )
        ts += 60 * rng.uniform(0.95, 1.05)
    return requests


ATTACKER_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0"


def compromised_account(rng: random.Random, world: World, start_ts: int) -> list[Request]:
    """A salesperson's stolen credentials are used at 03:20 from an unknown Linux machine:
    the attacker searches the mailbox and exports CRM reports."""
    victim = pick_user(rng, world, "Sales")
    # Same login, different everything else.
    attacker = replace(
        victim,
        device="DESKTOP-7Q2K9LM",
        ip="10.88.14.201",
        location="Remote",
        useragent=ATTACKER_USER_AGENT,
    )
    mail, crm = world.site("mail.officesuite.example"), world.site("crm.salescloud.example")
    actions = [
        (mail, "/mail/inbox", 40_000),
        *[(mail, f"/mail/search?q={q}", 25_000) for q in ("password", "invoice", "wire", "vpn")],
        (crm, "/leads", 60_000),
        *[
            (crm, f"/reports/{r}/export?format=csv", 12_000_000)
            for r in ("pipeline", "customers", "contracts", "pricing")
        ],
    ]
    ts = start_ts + 3 * HOUR + 20 * 60 + rng.uniform(0, 300)
    requests = []
    for _ in range(4):  # the attacker goes through the list a few times over half an hour
        for site, path, typical in actions:
            requests.append(
                Request.to_site(
                    site,
                    ts=ts,
                    user=attacker,
                    path=path,
                    method="GET",
                    status=200,
                    reqsize=rng.randint(600, 900),
                    respsize=int(typical * rng.uniform(0.6, 1.4)),
                    contenttype="text/csv" if "export" in path else "text/html",
                    rulelabel="Default_Allow",
                    ruletype="URL Filtering",
                    riskscore=rng.randint(0, 10),
                    label="attack:compromised_account",
                )
            )
            ts += rng.uniform(10, 60)
    return requests


SCENARIOS = {
    s.name: s
    for s in [
        Scenario(
            "malware_download",
            "Malware download from an emailed link, blocked twice",
            malware_download,
        ),
        Scenario(
            "phishing", "Credential phishing: look-alike login page, form submitted", phishing
        ),
        Scenario(
            "policy_probing",
            "Repeated attempts to reach anonymizers / VPNs, all blocked",
            policy_probing,
        ),
        Scenario(
            "data_exfiltration",
            "Late-night uploads of sensitive files to a personal file-sharing site",
            data_exfiltration,
        ),
        Scenario(
            "scanning",
            "Path brute-forcing of a partner portal: 500+ requests in ~2 minutes,"
            " mostly 404s, python-requests",
            scanning,
        ),
        Scenario(
            "generated_domains",
            "Malware trying ~60 random domain names (DGA) to find its command server",
            generated_domains,
        ),
        Scenario(
            "c2_beaconing",
            "Infected laptop checking in with its command server every"
            " ~60 seconds, around the clock",
            c2_beaconing,
        ),
        Scenario(
            "compromised_account",
            "Stolen credentials used at 03:20 from an unknown device"
            " to search mail and export CRM reports",
            compromised_account,
        ),
    ]
}
