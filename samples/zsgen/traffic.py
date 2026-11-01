"""Normal employee browsing: when people are online, which sites they open, and what each page
load looks like on the wire (one HTML page plus a few scripts, images and API calls).
"""

import math
import random
import time

from zsgen.request import Request
from zsgen.world import Site, User, World, server_ip

HOUR = 3600
VISITS_PER_WORKING_HOUR = 9  # page loads per hour for an average user at their desk

# URL-filtering policy: which sub categories are blocked, for whom, and by which rule.
BLOCK_RULES = [
    # (rule label, sub category, departments it applies to; None = everyone)
    ("Block_Streaming", "Streaming Media", None),
    ("Block_Social_Finance_HR", "Social Networking", {"Finance", "HR"}),
]


def activity_level(user: User, hour_of_day: float, weekday: int) -> float:
    """How active a user is at a given time, as a fraction of a normal working hour."""
    if weekday >= 5:  # Saturday, Sunday
        return 0.03
    if user.start_hour <= hour_of_day < user.end_hour:
        return 0.55 if 12.5 <= hour_of_day < 13.5 else 1.0  # dip over lunch
    if user.start_hour - 1 <= hour_of_day < user.start_hour:
        return 0.15  # checking mail before work
    if user.end_hour <= hour_of_day < user.end_hour + 1.5:
        return 0.15  # and after
    return 0.01


def poisson(rng: random.Random, mean: float) -> int:
    """Random count of events in an interval with the given average (Knuth's method)."""
    limit, count, product = math.exp(-mean), 0, rng.random()
    while product > limit:
        count += 1
        product *= rng.random()
    return count


def simulate_browsing(world: World, rng: random.Random, start_ts: int, days: int) -> list[Request]:
    requests: list[Request] = []
    for user in world.users:
        for hour in range(days * 24):
            hour_start = start_ts + hour * HOUR
            weekday = time.gmtime(hour_start).tm_wday
            level = activity_level(user, hour % 24 + 0.5, weekday)
            for _ in range(poisson(rng, VISITS_PER_WORKING_HOUR * user.activity * level)):
                ts = hour_start + rng.random() * HOUR
                requests += page_load(rng, user, pick_site(rng, world, user), ts)
    return requests


def pick_site(rng: random.Random, world: World, user: User) -> Site:
    if rng.random() < 0.55:  # work tools; the department's own apps are used twice as much
        work = [(s, 1.0) for s in world.shared_sites]
        work += [(s, 2.0) for s in world.dept_sites[user.dept]]
        sites, weights = zip(*work, strict=True)
    else:
        sites, weights = zip(*user.habits, strict=True)
    return rng.choices(sites, weights=weights)[0]


def policy_verdict(user: User, site: Site) -> dict:
    for rule, subcategory, depts in BLOCK_RULES:
        if site.category[1] == subcategory and (depts is None or user.dept in depts):
            return {
                "action": "Blocked",
                "reason": "Not allowed to browse this category",
                "rulelabel": rule,
                "ruletype": "URL Filtering",
            }
    return {
        "action": "Allowed",
        "reason": "Allowed",
        "rulelabel": "Default_Allow",
        "ruletype": "URL Filtering",
    }


def page_load(rng: random.Random, user: User, site: Site, ts: float) -> list[Request]:
    """The page itself, then 1-5 assets (scripts, images, API calls) just after it."""
    verdict = policy_verdict(user, site)
    page = Request.to_site(
        site,
        ts=ts,
        user=user,
        path=rng.choice(site.paths),
        method="GET",
        status=_status(rng, page=True),
        reqsize=_size(rng, 650, 0.3),
        respsize=_size(rng, 45_000, 0.8),
        contenttype="text/html",
        riskscore=rng.randint(0, 10),
        **verdict,
    )
    if page.action == "Blocked":
        # Zscaler answers with its own small block page; the browser never loads assets.
        page.status, page.respsize = 403, rng.randint(1_800, 2_600)
        return [page]

    requests = [page]
    for _ in range(rng.randint(1, 5)):
        kind = rng.choice(["script", "image", "api"])
        host = rng.choice(site.asset_hosts)
        is_post = kind == "api" and rng.random() < 0.3
        requests.append(
            Request.to_site(
                site,
                ts=ts + rng.uniform(0.05, 2.5),
                user=user,
                host=host,
                serverip=server_ip(host),
                path=_asset_path(rng, kind),
                method="POST" if is_post else "GET",
                status=_status(rng, page=False),
                reqsize=_size(rng, 2_500, 0.8) if is_post else _size(rng, 600, 0.3),
                respsize=_size(rng, *ASSET_SIZES[kind]),
                contenttype=CONTENT_TYPES[kind],
                referer=site.host,
                riskscore=rng.randint(0, 10),
                **verdict,
            )
        )
    return requests


CONTENT_TYPES = {
    "script": "application/javascript",
    "image": "image/png",
    "api": "application/json",
}
ASSET_SIZES = {"script": (60_000, 0.7), "image": (18_000, 1.0), "api": (3_000, 0.9)}


def _asset_path(rng: random.Random, kind: str) -> str:
    if kind == "script":
        return f"/static/app.{rng.getrandbits(32):08x}.js"
    if kind == "image":
        return f"/img/{rng.randint(1, 400)}.png"
    return rng.choice(["/api/v1/items", "/api/v1/user", "/api/v2/events", "/api/v1/search"])


def _size(rng: random.Random, typical: float, spread: float) -> int:
    """Log-normal size: most values near `typical`, with a long tail of big ones."""
    return max(1, int(rng.lognormvariate(math.log(typical), spread)))


def _status(rng: random.Random, page: bool) -> int:
    if page:
        return rng.choices([200, 304, 302, 404, 500], weights=[86, 6, 4, 3, 1])[0]
    # Assets are often cached by the browser, so more 304 Not Modified.
    return rng.choices([200, 304, 404, 500], weights=[78, 18, 3, 1])[0]
