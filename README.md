# 📊 Campuspe DataScrapping Project — Enriched College Scraper

## 📌 Overview

This project uses a Python script (`v3.py`) to build a **complete contact database** of engineering colleges in Andhra Pradesh.

It fetches college data from the **AICTE government database**, finds official websites, extracts contact details, and saves everything into an Excel file.

---

## 🚀 What Does `v3.py` Do?

The script performs the following:

- Fetches college data from AICTE
- Finds official college websites
- Visits websites using a real browser
- Extracts contact details (emails, phone numbers, social links)
- Classifies colleges into tiers
- Saves final data into Excel

📁 Output file: `ENRICHED_COLLEGES_v3.xlsx`

---

## ⚙️ Complete Workflow

### Step 1 — Fetch College Data (AICTE)

- Connects to AICTE API
- Filters:
  - Program: Engineering & Technology
  - State: Andhra Pradesh
  - Year: 2025–2026
  - Level: UG

Extracted fields:
- AICTE ID
- College Name
- Address
- District
- Institution Type
- Women/Minority status
- University ID

---

### Step 2 — Find Official Website

Since AICTE doesn’t provide websites:

- Uses:
  - Google Custom Search (optional)
  - Bing (fallback)

Search format:

✔ Prefers:
- `.ac.in`
- `.edu.in`

#### 🔍 Bing URL Decoding

Bing returns encoded URLs → script:
- Extracts Base64 data
- Decodes it
- Retrieves real website

---

### Step 3 — Validate & Clean URLs

Rejects:
- Empty values
- `nan`, `none`, `null`, `-`
- Invalid formats

Fixes:
- Adds `http://` if missing

---

### Step 4 — Visit Website (Playwright)

Uses **Playwright** to simulate a real browser.

Process:
- Opens homepage
- Waits for JavaScript to load
- Finds relevant pages:
  - contact
  - about
  - placement
  - admission
  - tpo
  - principal
- Visits up to 5 pages

✔ Handles crashes automatically

---

### Step 5 — Extract Contact Details

#### Method A — Mailto Links (Most Reliable)
- Extracts emails from:


#### Method B — Regex (Pattern Matching)

Finds:
- Emails → `text@text.com`
- Phone numbers → Indian formats

---

### 📧 Email Classification

| Type | Keyword |
|------|--------|
| Principal | "principal" |
| Placement | "placement", "tpo" |
| Admission | "admission" |
| General | fallback |

---

### 🌐 Social Media Extraction

Detects links for:
- Facebook
- LinkedIn
- Twitter
- Instagram
- YouTube

---

### Step 6 — Tier Classification

| Tier | Criteria |
|------|---------|
| Tier 1 | IIT, NIT, IIIT, IISER |
| Tier 2 | University, Autonomous, Deemed |
| Tier 3 | Others |

---

## 📦 Final Output

Saved as:

### Columns:

- College Name
- District
- Address
- Website
- Principal Email
- Placement Email
- Admission Email
- Phone
- Social Links
- Tier

---

## 🔄 Full Process Flow

1. Fetch AICTE data  
2. Search website  
3. Decode Bing URLs  
4. Validate URL  
5. Open in browser  
6. Find contact pages  
7. Visit subpages  
8. Extract emails  
9. Extract phone numbers  
10. Classify emails  
11. Extract social links  
12. Assign tier  
13. Save to Excel  

---

## 🧰 Libraries Used

| Library | Purpose |
|--------|--------|
| `requests` | API calls |
| `pandas` | Data handling + Excel |
| `BeautifulSoup` | HTML parsing |
| `Playwright` | Browser automation |
| `re (regex)` | Pattern matching |
| `openpyxl` | Excel writing |

---

## 📍 Data Source

- AICTE Government Database  
- JNTUA  
- JNTUK  

---

## ✅ Summary

This script automates the entire pipeline of:

👉 Data collection → Website discovery → Contact extraction → Classification → Excel output  

---

## 💡 Use Case

Perfect for:
- Outreach campaigns  
- College contact databases  
- Market research  
- Lead generation  

---
