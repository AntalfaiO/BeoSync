import os
import re
import sys
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from bs4 import BeautifulSoup
from ics import Calendar, Event
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("MY_EMAIL")
PASSWORD = os.environ.get("MY_PASSWORD")

LOGIN_URL = "https://wi.kmarcell.com/index.php?i=1"
SCHEDULE_URL = "https://wi.kmarcell.com/beosztasom.php"

TIMEZONE_OFFSET = "+02:00"
OUTPUT_FILENAME = "beosztasom.ics"


def run_sync():
    print("🤖 Automatizált felhős folyamat indítása...")

    if not EMAIL or not PASSWORD:
        print("❌ Hiba: Nem találhatók a bejelentkezési adatok a környezeti változókban.")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = context.new_page()
        page.set_default_timeout(20000)

        try:
            print("🔑 Bejelentkezés...")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.wait_for_selector("input", timeout=10000)

            email_field = page.locator('input[type="text"], input[type="email"], input[name="user"], input[name="username"]').first
            password_field = page.locator('input[type="password"]').first

            email_field.fill(EMAIL)
            password_field.fill(PASSWORD)

            with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                password_field.press("Enter")

            print("📅 Beosztási oldal megnyitása...")
            page.goto(SCHEDULE_URL, wait_until="domcontentloaded")
            page.wait_for_selector("div#content-in center table", timeout=10000)

            html_content = page.content()
            browser.close()

        except Exception as e:
            print(f"❌ Hiba történt a letöltéskor: {e}")
            browser.close()
            sys.exit(1)

    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.select_one("div#content-in center table") or soup.find("table")

    if not table:
        print("❌ Hiba: Nem található táblázat.")
        sys.exit(1)

    calendar = Calendar()
    rows = table.find_all("tr")

    current_date_str = None
    added_events = 0

    for row in rows:
        cols = row.find_all(["td", "th"])
        col_texts = [c.get_text(strip=True) for c in cols]

        if not col_texts or "Datum" in col_texts[0] or "Dátum" in col_texts[0]:
            continue

        first_col = col_texts[0]
        date_match = re.search(r"(\d{4})\.\s*(\d{2})\.\s*(\d{2})\.", first_col)

        if date_match:
            current_date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            group_text = col_texts[1] if len(col_texts) > 1 else ""
            shift_text = col_texts[2] if len(col_texts) > 2 else ""
        else:
            group_text = col_texts[0] if len(col_texts) > 0 else ""
            shift_text = col_texts[1] if len(col_texts) > 1 else ""

        if "Pihenőnap" in shift_text or not shift_text or shift_text == "-":
            continue

        time_matches = re.findall(r"(\d{1,2}:\d{2})(?::\d{2})?\s*-\s*(\d{1,2}:\d{2})(?::\d{2})?", shift_text)

        for match in time_matches:
            start_time = match[0].zfill(5)
            end_time = match[1].zfill(5)

            if current_date_str:
                start_iso = f"{current_date_str}T{start_time}:00{TIMEZONE_OFFSET}"
                end_iso = f"{current_date_str}T{end_time}:00{TIMEZONE_OFFSET}"

                try:
                    event = Event()
                    event.name = f"Műszak: {group_text}" if group_text and group_text != "-" else "Beosztás"
                    event.begin = start_iso
                    event.end = end_iso
                    calendar.events.add(event)

                    added_events += 1
                except Exception:
                    continue

    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(calendar.serialize_iter())

    print(f"✨ Mentve: {OUTPUT_FILENAME} ({added_events} műszak)")


if __name__ == "__main__":
    run_sync()
