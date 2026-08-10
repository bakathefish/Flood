# NDMA Sachet: an alert feed, and what the captured responses show

Every observation below is scoped to a retained response and names the poll it
came from. Two of those were reconnaissance polls, at **2026-08-07T08:24:50Z**
and **2026-08-09T18:38:10Z**; the rest are scheduled-path polls, the first at
**2026-08-10T07:40:04Z**. The archive keeps growing past them, and
`data/sachet/polls.jsonl` records every poll made since the manifest began: its
first row is a reconstruction of the rows that predate it, not a record of the
attempts that fetched them, so the manifest is complete forward from that point
and makes no claim before it. A figure here is therefore a dated measurement
rather than a running total. Where something is an inference from those responses
rather than a reading of them, it says so.

## Why this source and not another

Of the ground-truth routes this project has actually reached, each arrives through
a satellite product, and each carries the revisit gap into its own dates. That is
an observation about the routes tried here, not a claim that no non-satellite route
exists:

- **Copernicus GFM** is derived from Sentinel-1 acquisitions, so a footprint is
  dated by an overpass.
- **NDEM/NRSC sheets** are independent of GFM in processing chain and partly in
  sensor, which makes them a real check on *extent*, but an NDEM acquisition
  timestamp is likewise the day of an acquisition. If water arrived on 14 Aug and
  the first acquisition in hand is 16 Aug, an onset read off that sheet is late
  by the gap between them.
- **CWC flood forecasting** publishes no level-forecast station in Punjab, so
  there is no CWC level series here to date an onset against. The CWC station
  reported in Punjab is an inflow-forecast station at Ranjit Sagar Dam, which
  reports what enters a reservoir rather than a river level downstream. An earlier
  level site at Bamiyal on the Ravi was reported defunct (SANDRP, 2019), and that
  secondary report is the weakest link in this bullet. The dated primary evidence
  is the Commission's own state-wise table, "as on January 2018" (`data.gov.in`
  resource `0ff82e77`, held here as `data/cwc_ff_stations_2018.csv`): of the 22
  states and union territories that table lists, Punjab is not one.

A Sachet alert carries the issuing agency's own timestamp instead. Every alert captured so far is a CAP message stamped by a state
disaster authority, the CWC or an IMD office, checkable against the archive at
any time. That a Punjab flood alert here would therefore
be datable independently of revisit is an **inference** from those responses rather
than a property of the feed established by them, and the archive is what would test
it.

## What the endpoint is

```
POST https://sachet.ndma.gov.in/cap_public_website/FetchAllAlertDetails
Content-Type: application/json      body: {}
User-Agent: a browser string (required)
```

Keyless, CORS-open, returns a bare JSON list. Fields per alert: `identifier`,
`disaster_type`, `severity`, `severity_level`, `severity_color`,
`effective_start_time`, `effective_end_time`, `area_description`, `area_covered`,
`centroid`, `alert_source`, `sender_org_id`, `warning_message`, `actual_lang`,
`disseminated`, `type`, `alert_id_sdma_autoinc`.

The 2026-08-07 response carried **70 alerts, 34 of them flood type** (33 `Flood`,
1 `Flash Flood`) from **19 distinct senders**; 68 survived deduplication into the
archive. The 2026-08-09 response added **56 alerts from 16 distinct senders**, six of
which had not appeared on 08-07.

## What the two responses show about history, and what they cannot

Every date parameter tried (`fromDate`, `startDate`, `start_date`, `date`,
`from`/`to`) was **silently ignored** and returned the identical current set. No
archive endpoint responds: `FetchAllSenderDetails`, `FetchSenderDetails`,
`FetchAllAgency`, `FetchStateDetails`, `FetchAllStates`, `getStates`,
`FetchAllDisasterType`, `FetchAllAlertDetailsCount` all 404.

**Consequence: no backfill route is known**, so history exists only if it is kept
from now on. That is why `pipeline/fetch_sachet.py` runs on the 6-hourly monitor
cadence, and why a missed run is a window nobody can recover.

What the two responses do NOT establish is how wide the served window is. All 68
identifiers present at 2026-08-07T08:24:50Z were absent at 2026-08-09T18:38:10Z.
That is the whole of the observation. Two polls 58 hours apart cannot measure a
retention period, and no retention bound is asserted anywhere in this file or in
the fetcher.

## Punjab does reach this feed (settled 2026-08-09)

The 2026-08-09 response contained a row whose `alert_source` was **"Punjab
SDMA"** and whose `sender_org_id` was **"36"**, identifier
`1786259146152036`. Its Gurmukhi `warning_message` named Barnala, Bathinda,
Faridkot, Firozpur, Hoshiarpur, Mansa, Moga, Shahid Bhagat Singh Nagar and Tarn
Taran. `sender_org_id 36` was not among the 2026-08-07 set
`{6,7,9,10,12,13,16,17,18,20,21,22,23,24,27,28,29,30,38}`.

Two things this row does and does not settle:

- It **refutes** the reading that Punjab does not publish to Sachet at all. That
  reading is closed. Punjab SDMA published again in the **2026-08-10T07:40:04Z**
  response (Moderate Rain, ALERT, Patiala and Sangrur) and again in the
  **2026-08-10T09:24:24Z** response (Moderate Rain, ALERT, Bathinda, Mansa and
  Sangrur), so the sender is not a one-off. Both of those are rain advisories
  too, not flood observations, and each names only the districts quoted here.
- It does **not** confirm the other reading. That Punjab SDMA was registered all
  along and merely had nothing to publish on 2026-08-07 is a claim about the
  *reason* for an absence, and a single later row cannot establish a reason.
- The row was a **WATCH-level advisory, not a flood observation**. It says nothing
  about whether Punjab was flooding on 2026-08-09.

Punjab SDMA was one of six senders new to the 08-09 response; the other five were
Tripura, Gujarat, Puducherry, Mizoram and Chhattisgarh SDMA. A sender appearing
for the first time in a later response is therefore not by itself unusual.

### The 2026-08-07 absence, kept because it is true of that response

The 2026-08-07 response contained **no Punjab SDMA row and zero rows naming
Punjab**, among these senders:

| sender | n | | sender | n |
|---|---|---|---|---|
| Assam SDMA | 12 | | Jharkhand SDMA | 2 |
| Uttar Pradesh SDMA | 10 | | **Haryana SDMA** | **2** |
| CWC | 9 | | Telangana SDMA | 2 |
| Rajasthan SDMA | 5 | | Andaman and Nicobar SDMA | 2 |
| Uttarakhand SDMA | 5 | | Dadra and Nagar Haveli and Daman and Diu SDMA | 1 |
| Kerala SDMA | 4 | | IMD Ahmedabad | 1 |
| IMD Raipur | 3 | | IMD Mumbai | 1 |
| Madhya Pradesh SDMA | 3 | | IMD New Delhi | 1 |
| West Bengal SDMA | 3 | | IMD Chennai | 1 |
| Bihar SDMA | 3 | | | |

That observation stands as a dated fact about that response. What was deleted
from this note is not the observation but the conclusion once drawn from it: that
Punjab might not publish here at all. Deleting a true dated observation because a
later one superseded the conclusion drawn from it would damage the record rather
than correct it.

None of the enumeration routes tried responded, and the served HTML carried no
state list: the site is a Next.js SPA, and the eight names listed above all
returned 404. That is a statement about the routes tried and the HTML inspected,
not about what the site does or does not expose. What follows is only that the
roster of registered senders could not be read directly by these means, so the
evidence about any sender remains which responses carried it.

## Why the archive is worth running

- **When Punjab flood alerts appear**, the project gains dates set by the issuing
  agency rather than by an overpass, which is the one thing no other source here
  offers and the only basis on which a forecast claim could be tested
  prospectively.
- **If Punjab flood alerts never appear across a monsoon**, the archive is the
  evidence for that, and it can be stated with dates rather than as an
  impression.

Either way the archive is the instrument, it cannot be started retroactively, and
it is worthless only if it is not running.

## What the capture records about its own running

`data/sachet/polls.jsonl` is a manifest, committed beside the archive. What each
poll writes depends on how far it gets, and that is the design rather than an
omission:

- a `started` row before the network call, always, because it is the only row a
  poll can guarantee to leave;
- an `observed` row carrying every returned hash, **only if the fetch returned**,
  written before the archive is touched. A failed fetch never writes one, so its
  absence is the record that nothing came back;
- a terminal `result` row whose `outcome` is `ok`, `empty` or `failed`, for any
  poll that reaches its own end. A poll killed by a step timeout does not, which
  is why the `started` row is written first.

So an unchanged poll, an empty window and a failed request are three
distinguishable records rather than the same silence, and a poll that leaves only
a `started` row is a recorded gap the next run repairs.

`data/sachet/.lock` serialises the read-modify-write. It is broken only when its
heartbeat is older than 30 minutes, never because it was created long ago, and it
is not PID-based: `pipeline/fetch_footprint_cache.py` had a liveness check that
read a live foreign-owned process as dead, and that is the incident class this
avoids.

## What the capture deliberately does not do

`pipeline/fetch_sachet.py` stores **every alert from every state, verbatim**. It
does not filter to Punjab, does not label, and does not interpret. Two reasons:

1. A capture that asserts nothing cannot be wrong. Deciding what counts as a
   Punjab flood event is a claim, and a claim has to be argued and recorded
   before it is coded in.
2. A label definition settled later must not be limited by what a filter written
   today happened to keep. `punjab_view()` is a read-time lens over a complete
   archive, so tightening or loosening it costs no evidence.

The lens is deliberately loose (bare name matching, so it would also take a
same-named town in another state, or Pakistan's Punjab if that ever appeared).
That is pinned by a test rather than left as a surprise, and it is safe *because*
the archive underneath is complete. The 2026-08-10 poll produced the first
observed instance: a Haryana SDMA row whose text names Patiala and Sangrur was
taken by the lens. Read at write time that would have been a misfiled Punjab
alert; read at query time it is a row a reader can inspect and reject.

A failed poll raises rather than writing an empty capture. Recording a transient
HTTP failure as "no alerts today" would fabricate a quiet day, which is the same
class of error as recording an unimaged district-day as dry.

## Cost

Measured immediately after the 2026-08-10T07:40:04Z poll, the archive held 186
rows in 170 KB, which is ~935 bytes per row. At the per-response volumes seen so
far that projects to roughly 10 MB of append-only JSONL across a monsoon; the
projection is an extrapolation from the polls made up to that measurement, not a
measured rate, and the figures above are a dated observation rather than a
running total. Committed rather than git-ignored, because it is
evidence and there is no way to re-obtain it.
