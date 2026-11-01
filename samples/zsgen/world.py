"""The simulated company: employees, their devices and habits, and the websites they visit.

Everything is fictional. Hostnames use the reserved `.example` top-level domain (RFC 2606) and
server IPs come from the documentation ranges (RFC 5737), so sample files never point at real
infrastructure. Category names follow Zscaler's style but are representative, not exhaustive.
"""

import ipaddress
import random
from dataclasses import dataclass, replace

COMPANY_DOMAIN = "acme.example"
TIMEZONE = "GMT"  # the company is modelled in London, so local time == UTC

DOCUMENTATION_NETWORKS = [
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
]

# (url super category, url sub category, url class): Zscaler classifies every URL three ways.
WEB_MAIL = ("Internet Communication", "Web Mail", "Business Use")
CHAT = ("Internet Communication", "Online Chat", "Business Use")
COLLABORATION = ("Information Technology", "Web Collaboration", "Business Use")
CORPORATE = ("Business and Economy", "Corporate Marketing", "Business Use")
PROFESSIONAL = ("Business and Economy", "Professional Services", "Business Use")
FINANCE = ("Business and Economy", "Finance", "Business Use")
DEVELOPER = ("Information Technology", "Computer and Internet Info", "Business Use")
SEARCH = ("Information Technology", "Web Search", "General Surfing")
NEWS = ("News and Media", "News and Media", "General Surfing")
REFERENCE = ("Education", "Reference Sites", "General Surfing")
TRAVEL = ("Travel", "Travel", "General Surfing")
SHOPPING = ("Shopping and Auctions", "Online Shopping", "Productivity Loss")
SOCIAL = ("Social Networking", "Social Networking", "Productivity Loss")
STREAMING = ("Entertainment/Recreation", "Streaming Media", "Bandwidth Loss")
SECURITY = ("Information Technology", "Computer and Internet Security", "Business Use")
UPDATES = ("Information Technology", "Operating System and Software Updates", "Business Use")
UNCATEGORIZED = ("Miscellaneous", "Miscellaneous or Unknown", "General Surfing")
PHISHING = ("Security", "Phishing", "Security Risk")
ANONYMIZER = ("Security", "Anonymizer", "Security Risk")
FILE_HOST = ("Information Technology", "File Host", "Privacy Risk")


@dataclass(frozen=True)
class Site:
    host: str
    category: tuple[str, str, str]
    appname: str
    appclass: str
    country: str
    paths: tuple[str, ...]
    # Hosts a browser also contacts when it loads a page here (CDN, API).
    asset_hosts: tuple[str, ...]
    serverip: str = ""


@dataclass(frozen=True)
class User:
    login: str
    dept: str
    location: str
    device: str
    ip: str
    useragent: str
    start_hour: float  # usual start of the working day (UTC hours, e.g. 8.6 = 08:36)
    end_hour: float
    activity: float  # >1 = busier than average
    habits: tuple[tuple[Site, float], ...]  # personal sites and how much they're preferred


@dataclass(frozen=True)
class World:
    users: tuple[User, ...]
    shared_sites: tuple[Site, ...]  # corporate SaaS used by everyone
    dept_sites: dict[str, tuple[Site, ...]]  # corporate SaaS per department
    general_sites: tuple[Site, ...]
    service_sites: tuple[Site, ...]  # contacted by software rather than people
    attack_sites: tuple[Site, ...]  # used only by the planted attack scenarios

    def site(self, host: str) -> Site:
        sites = [*self.shared_sites, *self.general_sites, *self.service_sites, *self.attack_sites]
        sites += [site for dept in self.dept_sites.values() for site in dept]
        return next(site for site in sites if site.host == host)


US, UK, DE, IE = "United States", "United Kingdom", "Germany", "Ireland"

# The site tables are kept one entry per row for readability, so the formatter skips them.
# fmt: off

# Shared corporate SaaS: everyone uses these during the working day.
SHARED_SITES = [
    Site("mail.officesuite.example", WEB_MAIL, "Outlook Web", "Business", US,
         ("/mail/inbox", "/mail/sent", "/calendar"),
         ("cdn.officesuite.example", "api.officesuite.example")),
    Site("docs.officesuite.example", COLLABORATION, "Office Docs", "Business", US,
         ("/d/quarterly-plan", "/d/meeting-notes", "/sheets/budget"),
         ("cdn.officesuite.example", "api.officesuite.example")),
    Site("chat.teamtalk.example", CHAT, "TeamTalk", "Collaboration", US,
         ("/client", "/channels/general", "/channels/team"),
         ("files.teamtalk.example", "api.teamtalk.example")),
    Site("intranet.acme.example", CORPORATE, "General Browsing", "General Browsing", UK,
         ("/", "/news", "/people", "/policies"),
         ("static.acme.example",)),
]

DEPT_SITES = {
    "Sales": [
        Site("crm.salescloud.example", PROFESSIONAL, "SalesCloud", "Sales and Marketing", US,
             ("/leads", "/opportunities", "/reports/pipeline"),
             ("static.salescloud.example", "api.salescloud.example")),
    ],
    "Engineering": [
        Site("git.codehub.example", DEVELOPER, "CodeHub", "IT Services", US,
             ("/acme/api", "/acme/web/pulls", "/acme/infra"),
             ("assets.codehub.example", "api.codehub.example")),
        Site("ci.buildbox.example", DEVELOPER, "BuildBox", "IT Services", DE,
             ("/pipelines", "/jobs/latest"),
             ("api.buildbox.example",)),
    ],
    "Finance": [
        Site("app.ledgerly.example", FINANCE, "Ledgerly", "Finance", IE,
             ("/invoices", "/ledger", "/reports/monthly"),
             ("static.ledgerly.example", "api.ledgerly.example")),
    ],
    "HR": [
        Site("hr.peopleworks.example", PROFESSIONAL, "PeopleWorks", "Human Resources", US,
             ("/employees", "/time-off", "/onboarding"),
             ("static.peopleworks.example",)),
    ],
    "IT": [
        Site("admin.idhub.example", DEVELOPER, "IdHub Admin", "IT Services", US,
             ("/users", "/groups", "/audit"),
             ("api.idhub.example",)),
        Site("console.cloudhost.example", DEVELOPER, "CloudHost Console", "IT Services", US,
             ("/compute", "/storage", "/billing"),
             ("api.cloudhost.example",)),
    ],
}

# Ordinary browsing; each user picks a personal handful of these as habits.
GENERAL_SITES = [
    Site("www.searchly.example", SEARCH, "Searchly", "General Browsing", US,
         ("/search?q=quarterly+report", "/search?q=weather", "/search?q=python+dates"),
         ("img.searchly.example",)),
    Site("www.dailynews.example", NEWS, "General Browsing", "General Browsing", UK,
         ("/", "/business", "/world"), ("cdn.dailynews.example", "ads.adnet.example")),
    Site("www.technews.example", NEWS, "General Browsing", "General Browsing", US,
         ("/", "/security", "/cloud"), ("cdn.technews.example", "ads.adnet.example")),
    Site("www.wikiref.example", REFERENCE, "General Browsing", "General Browsing", US,
         ("/wiki/Spreadsheet", "/wiki/Tax", "/wiki/HTTP"), ("upload.wikiref.example",)),
    Site("docs.devref.example", REFERENCE, "General Browsing", "General Browsing", US,
         ("/python/datetime", "/js/fetch", "/sql/joins"), ("cdn.devref.example",)),
    Site("www.travelbook.example", TRAVEL, "General Browsing", "General Browsing", IE,
         ("/flights", "/hotels"), ("cdn.travelbook.example",)),
    Site("www.shopmart.example", SHOPPING, "ShopMart", "Consumer", US,
         ("/", "/deals", "/cart"), ("img.shopmart.example", "ads.adnet.example")),
    Site("www.friendbook.example", SOCIAL, "FriendBook", "Social Networking", US,
         ("/feed", "/messages"), ("static.friendbook.example",)),
    Site("www.picshare.example", SOCIAL, "PicShare", "Social Networking", US,
         ("/explore", "/p/sunset"), ("cdn.picshare.example",)),
    Site("www.streamflix.example", STREAMING, "StreamFlix", "Streaming Media", US,
         ("/browse", "/watch/123"), ("video.streamflix.example",)),
]

# Contacted by installed software and IT tooling rather than by people browsing.
SERVICE_SITES = [
    Site("agent.edrcloud.example", SECURITY, "EDRCloud", "IT Services", US,
         ("/v1/heartbeat",), ()),
    Site("update.browserco.example", UPDATES, "BrowserCo Update", "IT Services", US,
         ("/v1/check",), ()),
    Site("files.officesuite.example", COLLABORATION, "Office Drive", "Business", US,
         ("/upload/session",), ()),
]

# Attacker-controlled or risky destinations used by the planted attack scenarios.
ATTACK_SITES = [
    Site("dl.quickfiles-cdn.example", UNCATEGORIZED, "General Browsing", "General Browsing",
         "Russia", ("/invoice/8812",), ()),
    Site("officesuite-login.example", PHISHING, "General Browsing", "General Browsing",
         "Netherlands", ("/signin",), ()),
    Site("www.hidemyway.example", ANONYMIZER, "HideMyWay", "Anonymizer", "Panama",
         ("/", "/browse"), ()),
    Site("unblock-proxy.example", ANONYMIZER, "General Browsing", "Anonymizer", "Seychelles",
         ("/", "/go"), ()),
    Site("freevpn-now.example", ANONYMIZER, "FreeVPN Now", "Anonymizer", "Panama",
         ("/download/client",), ()),
    Site("www.dropbin.example", FILE_HOST, "DropBin", "File Sharing", US,
         ("/", "/api/upload"), ()),
]

# fmt: on

DEPARTMENTS = {  # department → share of employees
    "Sales": 0.27,
    "Engineering": 0.30,
    "Finance": 0.13,
    "HR": 0.10,
    "IT": 0.20,
}
LOCATIONS = [("London HQ", 0.8), ("Remote", 0.2)]
USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36",
        0.5,
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        0.25,
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.1 Safari/605.1.15",
        0.25,
    ),
]
FIRST_NAMES = (
    "alice ben carla dev elena farid grace hiro isla jonas kemi liam maya nikhil olga pedro "
    "quinn rosa sam tara umar vera wei ximena yusuf zoe aaron bea chen dina"
).split()
LAST_NAMES = (
    "adams baker costa diaz evans fischer garcia hughes ito jensen khan lopez moreau novak "
    "okafor patel quinn reyes silva tanaka usman vance walsh xu young zhang"
).split()


def _assign_server_ips() -> dict[str, str]:
    """Give every host a fixed documentation-range IP, in a stable order."""
    hosts: list[str] = []
    dept_sites = [site for sites in DEPT_SITES.values() for site in sites]
    # Newer tables go last so adding them never changes an existing host's IP.
    for site in (*SHARED_SITES, *dept_sites, *GENERAL_SITES, *SERVICE_SITES, *ATTACK_SITES):
        hosts += [site.host, *site.asset_hosts]
    unique_hosts = list(dict.fromkeys(hosts))  # de-duplicates but keeps order (a set wouldn't)
    pool = [str(ip) for net in DOCUMENTATION_NETWORKS for ip in list(net.hosts())[9:]]
    return dict(zip(unique_hosts, pool, strict=False))


SERVER_IPS = _assign_server_ips()


def server_ip(host: str) -> str:
    return SERVER_IPS[host]


def _with_ip(site: Site) -> Site:
    return replace(site, serverip=server_ip(site.host))


def _weighted(rng: random.Random, options: list[tuple[str, float]]) -> str:
    values, weights = zip(*options, strict=True)
    return rng.choices(values, weights=weights)[0]


def headcount_by_department(n_users: int) -> dict[str, int]:
    """Split employees by department share. Every department keeps at least one person
    (scenarios need e.g. a Finance user), and the counts always add up to `n_users`."""
    if n_users < len(DEPARTMENTS):
        raise ValueError(f"need at least {len(DEPARTMENTS)} users, one per department")
    counts = {d: max(1, round(n_users * share)) for d, share in DEPARTMENTS.items()}
    while sum(counts.values()) > n_users:  # rounding overshot: shrink the biggest department
        counts[max(counts, key=counts.get)] -= 1
    while sum(counts.values()) < n_users:  # undershot: grow the biggest department
        counts[max(DEPARTMENTS, key=DEPARTMENTS.get)] += 1
    return counts


def build_world(rng: random.Random, n_users: int) -> World:
    shared = tuple(_with_ip(s) for s in SHARED_SITES)
    dept_sites = {d: tuple(_with_ip(s) for s in sites) for d, sites in DEPT_SITES.items()}
    general = tuple(_with_ip(s) for s in GENERAL_SITES)
    services = tuple(_with_ip(s) for s in SERVICE_SITES)
    attacks = tuple(_with_ip(s) for s in ATTACK_SITES)

    depts = list(DEPARTMENTS)
    counts = headcount_by_department(n_users)

    names = [(first, last) for first in FIRST_NAMES for last in LAST_NAMES]
    rng.shuffle(names)

    users = []
    for dept in depts:
        for _ in range(counts[dept]):
            index = len(users) + 1
            first, last = names[index - 1]
            # Personal habits: 4-7 general sites, a few strongly preferred (Zipf-like weights).
            picks = rng.sample(general, k=rng.randint(4, 7))
            habits = tuple((site, 1 / (rank + 1)) for rank, site in enumerate(picks))
            users.append(
                User(
                    login=f"{first}.{last}@{COMPANY_DOMAIN}",
                    dept=dept,
                    location=_weighted(rng, LOCATIONS),
                    device=f"ACME-LT-{index:04d}",
                    ip=f"10.20.{depts.index(dept) + 1}.{index + 10}",
                    useragent=_weighted(rng, USER_AGENTS),
                    start_hour=rng.gauss(8.5, 0.5),
                    end_hour=rng.gauss(17.5, 0.6),
                    activity=rng.lognormvariate(0, 0.35),
                    habits=habits,
                )
            )
    return World(tuple(users), shared, dept_sites, general, services, attacks)
