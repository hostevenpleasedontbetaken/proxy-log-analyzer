"""One simulated web request, in plain Python types. zscaler.py turns it into a log line."""

from dataclasses import dataclass

from zsgen.world import Site, User


@dataclass
class Request:
    ts: float  # seconds since 1970, UTC
    user: User
    host: str
    path: str
    method: str
    status: int
    reqsize: int  # bytes sent by the client
    respsize: int  # bytes returned by the server
    contenttype: str
    category: tuple[str, str, str]  # (super category, sub category, url class)
    appname: str
    appclass: str
    serverip: str
    country: str
    referer: str | None = None
    proto: str = "HTTPS"
    useragent: str | None = None  # None = the user's normal browser
    # Policy verdict
    action: str = "Allowed"
    reason: str = "Allowed"
    rulelabel: str | None = None
    ruletype: str | None = None
    # Threat and file details (empty for ordinary traffic)
    riskscore: int = 0
    threatname: str | None = None
    threatseverity: str | None = None
    malwarecategory: str | None = None
    malwareclass: str | None = None
    filename: str | None = None
    filetype: str | None = None
    upload_filename: str | None = None
    sha256: str | None = None

    @classmethod
    def to_site(cls, site: Site, **fields) -> "Request":
        """A request to `site`, copying its host, category, app, IP and country.
        Any of those can be overridden, e.g. `host=` for a CDN the page loads from."""
        defaults = {
            "host": site.host,
            "category": site.category,
            "appname": site.appname,
            "appclass": site.appclass,
            "serverip": site.serverip,
            "country": site.country,
        }
        return cls(**{**defaults, **fields})
