"""Planted attacks. Each scenario is a function that returns the requests of one attack, labelled
"attack:<name>" so the answer key knows exactly which log lines are malicious.

Every scenario gets its own random stream (see generate.py), so planting one attack, or a
different subset, never changes the others or the normal traffic around them.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass

from zsgen.request import Request
from zsgen.world import User, World

HOUR = 3600
CRITICAL = "Critical (90–100)"  # with an en dash, exactly as Zscaler writes it


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str  # what happened, in an analyst's words (goes into the answer key)
    plant: Callable[[random.Random, World, int], list[Request]]


def pick_user(rng: random.Random, world: World, dept: str) -> User:
    return rng.choice([u for u in world.users if u.dept == dept])


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
    ]
}
