"""
ENRICHED AICTE COLLEGE SCRAPER — v3
=====================================
Key fixes from debug:
  - Field mapping corrected (API has no website field)
  - Bing tracking URLs decoded properly
  - Website discovery is now primary source (not fallback)

Fields from API:
  [0] AICTE_ID
  [1] College_Name
  [2] Address
  [3] District
  [4] Institution_Type
  [5] Women_College (Y/N)
  [6] Minority (Y/N)
  [7] University_ID

Install:
  pip install requests pandas openpyxl beautifulsoup4 playwright
  playwright install chromium
"""

import os
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote, parse_qs
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID  = os.getenv("GOOGLE_CSE_ID",  "")

REQUEST_TIMEOUT = 10
PW_TIMEOUT      = 15_000
SLEEP_BETWEEN   = 2
TEST_LIMIT = None   # was 20      # set to None to run all


# ==============================
# STEP 1 — FETCH AICTE DATA
# ==============================

def fetch_aicte_data():
    url = "https://facilities.aicte-india.org/dashboard/pages/php/approvedinstituteserver.php"
    params = {
        "method": "fetchdata",
        "year": "2025-2026",
        "program": "Engineering and Technology",
        "level": "1",
        "institutiontype": "1",
        "Women": "1",
        "Minority": "1",
        "state": "Andhra Pradesh ",
        "course": "1"
    }
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "x-requested-with": "XMLHttpRequest",
        "user-agent": "Mozilla/5.0"
    }
    response = requests.get(url, params=params, headers=headers, timeout=15)
    data = response.json()
    print(f"Total records fetched from AICTE: {len(data)}")

    colleges = []
    for row in data:
        try:
            colleges.append({
                "AICTE_ID":        row[0],
                "College_Name":    row[1],
                "Address":         row[2],
                "District":        row[3],
                "Institution_Type": row[4],
                "Women_College":   row[5],   # Y/N
                "Minority":        row[6],   # Y/N
                "University_ID":   row[7]
            })
        except Exception:
            continue

    return pd.DataFrame(colleges)


# ==============================
# STEP 2 — WEBSITE DISCOVERY
# ==============================

def decode_bing_url(href):
    """Bing wraps real URLs in tracking redirects. Decode them."""
    if not href:
        return None
    # Format: bing.com/ck/a?...&u=a1<base64url>...
    if "bing.com/ck/a" in href:
        try:
            # extract the 'u' param
            qs = parse_qs(urlparse(href).query)
            u = qs.get("u", [None])[0]
            if u and u.startswith("a1"):
                import base64
                # strip leading "a1" and decode
                decoded = base64.urlsafe_b64decode(u[2:] + "==").decode("utf-8", errors="ignore")
                if decoded.startswith("http"):
                    return decoded
        except Exception:
            pass
    return href  # return as-is if not a tracking URL


def search_bing(college_name):
    """Search Bing and decode tracking URLs to get real URLs."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(
            "https://www.bing.com/search",
            params={"q": f"{college_name} official website"},
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        soup = BeautifulSoup(r.text, "html.parser")
        results = soup.select("li.b_algo h2 a")

        decoded_urls = []
        for a in results:
            real_url = decode_bing_url(a.get("href", ""))
            if real_url and real_url.startswith("http"):
                decoded_urls.append(real_url)

        # Prefer .ac.in / .edu.in
        for u in decoded_urls:
            if ".ac.in" in u or ".edu.in" in u:
                return u

        # Otherwise return first result
        if decoded_urls:
            return decoded_urls[0]

    except Exception as e:
        print(f"   [Bing error] {e}")
    return None


def search_google_cse(college_name):
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return None
    try:
        params = {
            "key": GOOGLE_API_KEY,
            "cx":  GOOGLE_CSE_ID,
            "q":   f"{college_name} official website",
            "num": 3
        }
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params, timeout=REQUEST_TIMEOUT
        )
        items = r.json().get("items", [])
        for item in items:
            link = item.get("link", "")
            if ".ac.in" in link or ".edu" in link:
                return link
        if items:
            return items[0].get("link")
    except Exception:
        pass
    return None


def discover_website(college_name):
    # Try Google CSE first if configured
    url = search_google_cse(college_name)
    if url:
        print(f"   [Google CSE] {url}")
        return url
    # Bing fallback
    url = search_bing(college_name)
    if url:
        print(f"   [Bing] {url}")
        return url
    print("   [Search] No website found")
    return None


# ==============================
# STEP 3 — URL VALIDATION
# ==============================

def is_valid_url(val):
    if val is None:
        return False
    if isinstance(val, float):
        return False
    val = str(val).strip()
    if val.lower() in {"nan", "none", "n", "na", "0", "", "#", "-", "null", "y"}:
        return False
    parsed = urlparse(val)
    return bool(parsed.scheme and parsed.netloc)


def clean_url(val):
    if not is_valid_url(val):
        return None
    url = str(val).strip()
    if not url.startswith("http"):
        url = "http://" + url
    return url


# ==============================
# STEP 4 — PLAYWRIGHT SCRAPING
# ==============================

def make_browser(pw):
    return pw.chromium.launch(headless=True)


def get_page_html(url, browser):
    if not is_valid_url(url):
        return None
    try:
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        page.goto(str(url), timeout=PW_TIMEOUT, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        html = page.content()
        page.close()
        return html
    except PWTimeout:
        print(f"   [Timeout] {url}")
    except Exception as e:
        print(f"   [Page error] {type(e).__name__}")
    try:
        page.close()
    except:
        pass
    return None


def get_subpages(base_url, soup):
    keywords = ["contact", "about", "placement", "admission", "tpo", "principal"]
    pages = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if any(k in href for k in keywords):
            full = urljoin(base_url, a["href"])
            if urlparse(full).netloc == urlparse(base_url).netloc:
                pages.append(full)
    return list(set(pages))[:5]


# ==============================
# STEP 5 — EXTRACT DETAILS
# ==============================

def extract_from_soup(soup):
    result = {
        "Principal_Email": None,
        "Placement_Email": None,
        "Admission_Email": None,
        "Phone":           None,
        "Social_Links":    []
    }

    # Emails: mailto: links first
    emails = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip().lower()
            if email and "@" in email:
                emails.append(email)

    # Regex fallback on text
    text = soup.get_text(" ")
    regex_emails = re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text)
    emails += [e.lower() for e in regex_emails]
    emails = list(dict.fromkeys(emails))

    for email in emails:
        if "principal" in email and not result["Principal_Email"]:
            result["Principal_Email"] = email
        elif ("placement" in email or "tpo" in email) and not result["Placement_Email"]:
            result["Placement_Email"] = email
        elif "admission" in email and not result["Admission_Email"]:
            result["Admission_Email"] = email

    if emails and not result["Principal_Email"]:
        result["Principal_Email"] = emails[0]

    # Indian phone numbers
    phones = re.findall(r"(?:\+91[\s\-]?)?[6-9]\d{9}|0\d{2,4}[\s\-]?\d{6,8}", text)
    if phones:
        result["Phone"] = phones[0].strip()

    # Social links
    social_domains = ["facebook.com", "linkedin.com", "twitter.com", "instagram.com", "youtube.com"]
    socials = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(s in href for s in social_domains):
            socials.append(href)
    result["Social_Links"] = list(set(socials))

    return result


def merge(collected, new_data):
    for key in collected:
        if key == "Social_Links":
            collected[key] = list(set(collected[key] + new_data.get(key, [])))
        elif not collected[key] and new_data.get(key):
            collected[key] = new_data[key]
    return collected


def scrape_college(website, browser):
    collected = {
        "Principal_Email": None,
        "Placement_Email": None,
        "Admission_Email": None,
        "Phone":           None,
        "Social_Links":    []
    }

    if not website:
        return collected

    html = get_page_html(website, browser)
    if not html:
        return collected

    soup = BeautifulSoup(html, "html.parser")
    collected = merge(collected, extract_from_soup(soup))

    for page_url in get_subpages(website, soup):
        sub_html = get_page_html(page_url, browser)
        if sub_html:
            sub_soup = BeautifulSoup(sub_html, "html.parser")
            collected = merge(collected, extract_from_soup(sub_soup))

    return collected


# ==============================
# STEP 6 — TIER
# ==============================

def classify_tier(college_name):
    name = college_name.lower()
    if any(k in name for k in ["iit", "nit", "iiit", "iiser"]):
        return "Tier 1"
    elif any(k in name for k in ["university", "autonomous", "deemed", "gitam", "klef", "rgukt"]):
        return "Tier 2"
    else:
        return "Tier 3"


# ==============================
# MAIN
# ==============================

def main():
    df = fetch_aicte_data()

    if TEST_LIMIT:
        df = df.head(TEST_LIMIT)
        print(f"TEST MODE: processing first {TEST_LIMIT} colleges\n")

    enriched_rows = []

    with sync_playwright() as pw:
        browser = make_browser(pw)

        for i, row in df.iterrows():
            print(f"[{i+1}/{len(df)}] {row['College_Name']}")

            # API has no website — always search
            website = discover_website(row["College_Name"])
            website = clean_url(website)
            print(f"   Website: {website or 'NOT FOUND'}")

            # Restart browser if crashed
            try:
                browser.contexts
            except Exception:
                print("   [Browser] Restarting...")
                try: browser.close()
                except: pass
                browser = make_browser(pw)

            extra = scrape_college(website, browser)

            enriched_rows.append({
                **row.to_dict(),
                "Website":         website,
                "Principal_Email": extra["Principal_Email"],
                "Placement_Email": extra["Placement_Email"],
                "Admission_Email": extra["Admission_Email"],
                "Phone":           extra["Phone"],
                "Social_Links":    ", ".join(extra["Social_Links"]) if extra["Social_Links"] else None,
                "Tier":            classify_tier(row["College_Name"])
            })

            time.sleep(SLEEP_BETWEEN)

        browser.close()

    final_df = pd.DataFrame(enriched_rows)
    output_file = "ENRICHED_COLLEGES_v3.xlsx"
    final_df.to_excel(output_file, index=False)

    print(f"\nDone! Saved: {output_file}")
    print(f"Total processed  : {len(final_df)}")
    print(f"Websites found   : {final_df['Website'].notna().sum()}")
    print(f"Emails found     : {final_df['Principal_Email'].notna().sum()}")
    print(f"Phones found     : {final_df['Phone'].notna().sum()}")


if __name__ == "__main__":
    main()