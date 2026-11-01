"""Benign traffic that *looks* suspicious.

Without these, any detector looks perfect, because the only odd traffic in the file would be
the attacks. With them, the evaluation can show the detectors telling benign from malicious.

- Security-agent heartbeat
    resembles: C2 beaconing (fixed interval, same size, around the clock)
    benign because: every device does it, to the company's own security vendor
- Browser update check
    resembles: beaconing, hourly
    benign because: software-update category, every device
- IT automation scripts
    resembles: scanning / a bot user agent, overnight
    benign because: an IT admin hitting company tools; every call succeeds
- Large video upload
    resembles: data exfiltration (huge uploads, tiny responses)
    benign because: sanctioned company drive, during working hours
"""

import random

from zsgen.request import Request
from zsgen.world import Site, User, World, server_ip

DAY = 24 * 3600
HEARTBEAT_EVERY = 30 * 60
UPDATE_CHECK_EVERY = 60 * 60
ALLOWED = {"rulelabel": "Default_Allow", "ruletype": "URL Filtering"}

# For the answer key: what each look-alike is, in an analyst's words.
DESCRIPTIONS = {
    "security_agent_heartbeat": "Security agent on every laptop checking in every ~30 minutes",
    "update_check": "Browser update check on every laptop, hourly",
    "it_automation": "IT admin scripts: nightly snapshot job and daytime directory queries",
    "large_upload": "Sales uploading a product video to the company drive",
}


def simulate_lookalikes(
    world: World, rng: random.Random, start_ts: int, days: int
) -> list[Request]:
    end_ts = start_ts + days * DAY
    it_admin = next(u for u in world.users if u.dept == "IT")
    uploader = next(u for u in world.users if u.dept == "Sales")
    return [
        *periodic_checkins(
            rng,
            world.users,
            world.site("agent.edrcloud.example"),
            start_ts,
            end_ts,
            every=HEARTBEAT_EVERY,
            method="POST",
            useragent="EDRCloud-Agent/4.2.1",
            reqsize=920,
            respsize=310,
            label="benign:security_agent_heartbeat",
        ),
        *periodic_checkins(
            rng,
            world.users,
            world.site("update.browserco.example"),
            start_ts,
            end_ts,
            every=UPDATE_CHECK_EVERY,
            method="GET",
            useragent="BrowserCo-Updater/131.0",
            reqsize=540,
            respsize=1_150,
            label="benign:update_check",
        ),
        *it_automation(rng, world, it_admin, start_ts, days),
        *large_upload(rng, world, uploader, start_ts),
    ]


def periodic_checkins(
    rng: random.Random,
    users: tuple[User, ...],
    site: Site,
    start_ts: int,
    end_ts: int,
    *,
    every: int,
    method: str,
    useragent: str,
    reqsize: int,
    respsize: int,
    label: str,
) -> list[Request]:
    """Software on every laptop phoning home on a timer, like real agents do."""
    requests = []
    for user in users:
        ts = start_ts + rng.uniform(0, every)  # each device starts at its own moment
        while ts < end_ts:
            requests.append(
                Request.to_site(
                    site,
                    ts=ts,
                    user=user,
                    path=site.paths[0],
                    method=method,
                    status=200,
                    reqsize=reqsize + rng.randint(-20, 20),
                    respsize=respsize + rng.randint(-10, 10),
                    contenttype="application/json",
                    useragent=useragent,
                    label=label,
                    **ALLOWED,
                )
            )
            ts += every * rng.uniform(0.97, 1.03)  # ±3% jitter
    return requests


def it_automation(
    rng: random.Random, world: World, admin: User, start_ts: int, days: int
) -> list[Request]:
    """A nightly backup script (python-requests) and some daytime curl calls by an IT admin."""
    console = world.site("console.cloudhost.example")
    idhub = world.site("admin.idhub.example")
    label = "benign:it_automation"
    requests = []
    for day in range(days):
        # 02:00-02:02: snapshot every cloud server, one API call per server.
        ts = start_ts + day * DAY + 2 * 3600 + rng.uniform(0, 120)
        for server in range(40):
            requests.append(
                _api_call(
                    rng,
                    console,
                    admin,
                    ts,
                    host="api.cloudhost.example",
                    method="POST",
                    path=f"/api/v1/servers/srv-{server:03d}/snapshot",
                    useragent="python-requests/2.32.3",
                    label=label,
                )
            )
            ts += rng.uniform(1, 4)
        # Mid-morning: the admin pages through the user directory with curl.
        ts = start_ts + day * DAY + 10 * 3600 + rng.uniform(0, 4 * 3600)
        for page in range(1, 9):
            requests.append(
                _api_call(
                    rng,
                    idhub,
                    admin,
                    ts,
                    host="api.idhub.example",
                    method="GET",
                    path=f"/api/v1/users?page={page}",
                    useragent="curl/8.7.1",
                    label=label,
                )
            )
            ts += rng.uniform(2, 6)
    return requests


def _api_call(
    rng: random.Random,
    site: Site,
    user: User,
    ts: float,
    *,
    host: str,
    method: str,
    path: str,
    useragent: str,
    label: str,
) -> Request:
    return Request.to_site(
        site,
        ts=ts,
        user=user,
        host=host,
        serverip=server_ip(host),
        path=path,
        method=method,
        status=200,
        reqsize=rng.randint(400, 900),
        respsize=rng.randint(800, 6_000),
        contenttype="application/json",
        useragent=useragent,
        label=label,
        **ALLOWED,
    )


def large_upload(rng: random.Random, world: World, user: User, start_ts: int) -> list[Request]:
    """A salesperson uploads a ~190 MB product video to the company drive, in 8 MB chunks,
    on the first afternoon. Upload-heavy like exfiltration, but to sanctioned storage."""
    drive = world.site("files.officesuite.example")
    ts = start_ts + 15 * 3600 + rng.uniform(0, 1800)
    requests = []
    for chunk in range(24):
        requests.append(
            Request.to_site(
                drive,
                ts=ts,
                user=user,
                path=f"/upload/session/7f3a9c?chunk={chunk}",
                method="PUT",
                status=200,
                reqsize=int(8_000_000 * rng.uniform(0.95, 1.05)),
                respsize=rng.randint(300, 500),
                contenttype="application/octet-stream",
                upload_filename="Q4_product_demo.mp4",
                filetype="MP4 Files",
                label="benign:large_upload",
                **ALLOWED,
            )
        )
        ts += rng.uniform(2, 4)
    return requests
