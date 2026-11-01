# Sample logs

Synthetic **Zscaler NSS web logs** for a fictional company, Acme, in the format Zscaler streams to
SIEMs (one JSON object per line, Elastic's v12 `zscalernss-web` template). Each file has an
**answer key** listing exactly which lines are planted attacks.

| File | Lines | What's in it | Use it to… |
|---|---|---|---|
| `acme-web-day.ndjson.gz` | 18,654 | 40 employees, one day, **all 8 attacks** + benign look-alikes (1 MB gzipped, 20.8 MB raw) | see the full analysis |
| `acme-web-small.ndjson` | 1,934 | 5 employees, 3 attacks (phishing, malware download, exfiltration) | try a quick upload |
| `acme-web-clean.ndjson` | 4,608 | 12 employees, **no attacks**, only normal traffic + look-alikes | check false alarms |
| `not-zscaler.log` | 40 | An Apache access log | see the "not a Zscaler web log" error |
| `*.ground_truth.json` | | The answer key for each Zscaler file | compare detections with reality |

The small file has too few user-hours for Isolation Forest (it needs at least 200), so on it only
the rule-based and statistical detectors run.

## Planted attacks (`acme-web-day`)

All times UTC on Tue 20 Oct 2026.

| Attack | When | Who | Lines | What it looks like |
|---|---|---|---|---|
| Generated domains (DGA) | 03:05–03:07 | carla.evans | 60 | One laptop tries ~60 random domain names; most don't resolve |
| C2 beaconing | 03:12–23:59 | carla.evans | 1,247 | The same laptop calls the domain that answered, every ~60 s |
| Compromised account | 03:24–03:46 | wei.moreau | 40 | Known login on an unknown Linux PC: mailbox searches, CRM exports |
| Phishing | 10:44–10:45 | wei.patel | 4 | Look-alike login page from an email link; the form is submitted |
| Malware download | 11:21 | umar.baker | 3 | `Invoice_8812.exe` blocked twice as a trojan |
| Scanning | 14:32–14:34 | vera.tanaka | 520 | Path brute-force of a partner portal, mostly 404s, `python-requests` |
| Policy probing | 16:22–16:34 | vera.tanaka | 22 | Repeated anonymizer / VPN attempts, all blocked |
| Data exfiltration | 23:01–23:19 | yusuf.zhang | 15 | Large uploads of payroll and customer files to a personal file-sharing site |

## Benign look-alikes (in every file)

Normal traffic that *resembles* an attack, so detection is measured on telling them apart:

| Look-alike | Resembles | Why it's fine |
|---|---|---|
| Security-agent heartbeat (every ~30 min, all devices, all night) | C2 beaconing | Every device, to the company's security vendor |
| Browser update check (hourly) | Beaconing | Software updates, every device |
| IT automation (`python-requests` at 02:00, `curl` mid-morning) | Scanning, bots | IT admin on company tools; every call succeeds |
| 190 MB video upload (Sales, mid-afternoon) | Exfiltration | The company's own drive, during work hours |

## Format

One line, pretty-printed (fields trimmed):

```json
{"version": "v12", "sourcetype": "zscalernss-web", "event": {
  "time": "Tue Oct 20 10:44:49 2026", "tz": "GMT", "epochtime": "1792493089",
  "login": "wei.patel@acme.example", "dept": "HR", "devicehostname": "ACME-LT-0032",
  "host": "officesuite-login.example", "b64url": "b2ZmaWNlc3VpdGUtbG9naW4uZXhhbXBsZS9zaWduaW4=",
  "reqmethod": "GET", "respcode": "200", "action": "Allowed", "urlsubcat": "Phishing",
  "riskscore": "88", "recordid": "7000000000000005985", "...": "..."}}
```

Like real NSS output: every value is a string, missing values are `"None"`, the URL is base64
(`b64url` = `host/path`), and time appears twice (`time` + `tz`, and `epochtime`).

## Answer key

```json
{
  "generator": {"seed": 42, "users": 40, "days": 1, "start": "2026-10-20", "attacks": ["..."]},
  "attacks": [{"name": "phishing", "description": "...", "users": ["wei.patel@acme.example"],
               "first_seen": "2026-10-20T10:44:49Z", "last_seen": "2026-10-20T10:45:17Z",
               "line_count": 4, "recordids": ["7000000000000005985", "..."]}],
  "benign_lookalikes": ["...same shape..."]
}
```

## Safety

Everything is fictional: hostnames use the reserved `.example` domain, server IPs come from the
documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24), client IPs are private
`10.x` addresses, and the employees are made up.

## Regenerating

The generator is a seeded behaviour simulation (standard-library Python only), so the same
options always produce byte-identical files.

```bash
make samples                       # rebuild every file above (options in build_samples.py)
python samples/generate.py --help  # custom files: --users, --days, --seed, --attacks
```

`not-zscaler.log` is hand-made and isn't regenerated.
