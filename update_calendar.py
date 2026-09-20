#!/usr/bin/env python3
"""Fetch the Holidu iCal feed and regenerate the static calendar block in index.html.
Runs on a schedule via GitHub Actions. Keeps the page's design 100% unchanged —
only the <div class="calendar-grid">...</div> content is regenerated.
"""
import re
import sys
import datetime
import urllib.request

ICAL_URL = "https://api.host.holidu.com/ical/znwtcfz3eg_9bazegiyyq.ics"
INDEX_PATH = "index.html"
MONTHS_AHEAD = 12

MONTHS_ES = ["", "enero","febrero","marzo","abril","mayo","junio","julio","agosto",
             "septiembre","octubre","noviembre","diciembre"]
MONTHS_EN = ["", "January","February","March","April","May","June","July","August",
             "September","October","November","December"]
WD_ES = ["L","M","X","J","V","S","D"]


def fetch_ical(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_events(ics_text):
    events = []
    cur = {}
    for raw_line in ics_text.splitlines():
        line = raw_line.strip()
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line.startswith("DTSTART"):
            val = line.split(":")[-1].strip()
            cur["start"] = datetime.datetime.strptime(val, "%Y%m%d").date()
        elif line.startswith("DTEND"):
            val = line.split(":")[-1].strip()
            cur["end"] = datetime.datetime.strptime(val, "%Y%m%d").date()
        elif line == "END:VEVENT":
            if "start" in cur and "end" in cur:
                events.append((cur["start"], cur["end"]))
    return events


def unavailable_days(events):
    days = set()
    for start, end in events:
        d = start
        while d < end:
            days.add(d)
            d += datetime.timedelta(days=1)
    return days


def month_block(year, month, unavailable, today):
    first = datetime.date(year, month, 1)
    start_wd = first.weekday()
    next_first = datetime.date(year + 1, 1, 1) if month == 12 else datetime.date(year, month + 1, 1)
    days_in_month = (next_first - first).days

    cells = ['<span class="cal-day empty"></span>' for _ in range(start_wd)]
    for day in range(1, days_in_month + 1):
        d = datetime.date(year, month, day)
        classes = ["cal-day"]
        if d in unavailable:
            classes.append("unavail")
        if d == today:
            classes.append("today")
        cells.append(f'<span class="{" ".join(classes)}">{day}</span>')

    label_es = f"{MONTHS_ES[month]} {year}"
    label_en = f"{MONTHS_EN[month]} {year}"
    dow_header = "".join(f'<span class="cal-dow">{w}</span>' for w in WD_ES)

    return (
        '      <div class="cal-month">\n'
        f'        <div class="cal-month-title" data-lang="es" class="active">{label_es}</div>\n'
        f'        <div class="cal-month-title" data-lang="en">{label_en}</div>\n'
        f'        <div class="cal-dows">{dow_header}</div>\n'
        f'        <div class="cal-days">{"".join(cells)}</div>\n'
        '      </div>'
    )


def build_calendar_html(unavailable, today):
    blocks = []
    y, m = today.year, today.month
    for _ in range(MONTHS_AHEAD):
        blocks.append(month_block(y, m, unavailable, today))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return "\n".join(blocks)


def main():
    today = datetime.date.today()
    try:
        ics_text = fetch_ical(ICAL_URL)
    except Exception as exc:
        print(f"ERROR fetching iCal: {exc}", file=sys.stderr)
        sys.exit(1)

    events = parse_events(ics_text)
    unavailable = unavailable_days(events)
    new_calendar_html = build_calendar_html(unavailable, today)

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    pattern = re.compile(
        r'(<div class="calendar-grid">\n).*?(\n\s*</div>\n\s*</div>\n\s*<p class="form-note")',
        re.DOTALL
    )
    new_html, count = pattern.subn(
        lambda m_: m_.group(1) + new_calendar_html + m_.group(2), html
    )
    if count == 0:
        print("ERROR: calendar-grid block not found in index.html", file=sys.stderr)
        sys.exit(1)

    # Update the "as of" note dates (ES + EN) to today's date
    today_es = f"{today.day} {MONTHS_ES[today.month][:3]} {today.year}"
    today_en = today.strftime("%d %b %Y")
    new_html = re.sub(
        r'(Calendario actualizado a fecha de )\d{1,2} \w+ \d{4}',
        lambda m_: m_.group(1) + today_es, new_html
    )
    new_html = re.sub(
        r'(Calendar updated as of )\d{1,2} \w+ \d{4}',
        lambda m_: m_.group(1) + today_en, new_html
    )

    if new_html != html:
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            f.write(new_html)
        print(f"Calendar updated: {len(unavailable)} unavailable days, {len(events)} events.")
    else:
        print("No changes to calendar.")


if __name__ == "__main__":
    main()
