"""Write a simulated request the way Zscaler NSS does with Elastic's v12 web template:

    {"version":"v12","sourcetype":"zscalernss-web","event":{"time":"Tue Oct 20 09:14:03 2026",...}}

Real-format details reproduced on purpose, because the parser has to cope with them:
- every value is a string, even numbers ("reqsize":"1300")
- missing values are the placeholder "None", not null
- the URL is base64 (`b64url`) of "host/path", without the scheme
- two time fields: human-readable `time` + `tz`, and `epochtime` (seconds since 1970)
"""

import base64
import json
import time

from zsgen.request import Request
from zsgen.world import TIMEZONE

# Our ~40 fields, in the order they appear in Elastic's published v12 template.
FIELDS = (
    "time host serverip action recordid reason threatseverity tz sha256 filename "
    "upload_filename filetype devicehostname reqsize reqmethod respsize respcode proto "
    "rulelabel cltip threatname b64url useragent login appclass appname contenttype dept "
    "dstip_country epochtime location malwarecategory malwareclass refererhost riskscore "
    "ruletype urlsubcat urlsupercat urlclass"
).split()

NONE = "None"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def format_time(epoch: int) -> str:
    """Zscaler's `time` format, e.g. "Tue Oct 20 09:14:03 2026". Built by hand because
    strftime's day and month names depend on the machine's locale."""
    t = time.gmtime(epoch)
    return (
        f"{DAYS[t.tm_wday]} {MONTHS[t.tm_mon - 1]} {t.tm_mday:02d} "
        f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d} {t.tm_year}"
    )


def to_event(req: Request, recordid: int) -> dict[str, str]:
    epoch = int(req.ts)
    supercat, subcat, urlclass = req.category
    values = {
        "time": format_time(epoch),
        "host": req.host,
        "serverip": req.serverip,
        "action": req.action,
        "recordid": recordid,
        "reason": req.reason,
        "threatseverity": req.threatseverity,
        "tz": TIMEZONE,
        "sha256": req.sha256,
        "filename": req.filename,
        "upload_filename": req.upload_filename,
        "filetype": req.filetype,
        "devicehostname": req.user.device,
        "reqsize": req.reqsize,
        "reqmethod": req.method,
        "respsize": req.respsize,
        "respcode": req.status,
        "proto": req.proto,
        "rulelabel": req.rulelabel,
        "cltip": req.user.ip,
        "threatname": req.threatname,
        "b64url": base64.b64encode(f"{req.host}{req.path}".encode()).decode(),
        "useragent": req.useragent or req.user.useragent,
        "login": req.user.login,
        "appclass": req.appclass,
        "appname": req.appname,
        "contenttype": req.contenttype,
        "dept": req.user.dept,
        "dstip_country": req.country,
        "epochtime": epoch,
        "location": req.user.location,
        "malwarecategory": req.malwarecategory,
        "malwareclass": req.malwareclass,
        "refererhost": req.referer,
        "riskscore": req.riskscore,
        "ruletype": req.ruletype,
        "urlsubcat": subcat,
        "urlsupercat": supercat,
        "urlclass": urlclass,
    }
    return {field: NONE if values[field] is None else str(values[field]) for field in FIELDS}


def to_line(event: dict[str, str]) -> str:
    # Compact separators and \u escapes for non-ASCII, matching real NSS output.
    envelope = {"version": "v12", "sourcetype": "zscalernss-web", "event": event}
    return json.dumps(envelope, separators=(",", ":"))
