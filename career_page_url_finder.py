import csv
import asyncio
import os
import argparse
from playwright.async_api import async_playwright
import re
import time
from datetime import datetime

# ======== SIGNIFICANTLY EXPANDED URL PATTERNS ========
URL_PATTERNS = [
    # Standard paths
    "/careers", "/jobs", "/join-us", "/work-with-us", "/join", 
    "/job-openings", "/vacancies", "/positions", "/employment",
    "/career", "/work", "/hiring", "/apply", "/job-opportunities",
    
    # Opportunities variations
    "/opportunities", "/career-opportunities", "/open-opportunities",
    "/current-opportunities", "/job-opportunities",
    
    # Openings variations
    "/open-positions", "/openings", "/current-openings", "/job-openings",
    
    # Company section paths
    "/company/careers", "/company/jobs", "/company/join-us", "/company/work-with-us",
    "/company/opportunities", "/company/openings", "/company/positions",
    
    # About section paths
    "/about/careers", "/about/jobs", "/about/join-us", "/about/work-with-us", 
    "/about/opportunities", "/about-us/careers", "/about-us/jobs",
    
    # Team section paths
    "/team/join", "/team/careers", "/team/jobs", "/join-the-team", 
    "/our-team/careers", "/our-team/jobs",
    
    # Life section paths
    "/life/careers", "/life/jobs", "/life", "/life-at-company",
    
    # HR section paths
    "/hr/careers", "/hr/jobs", "/hr/opportunities", "/recruitment",
    
    # Hyphenated variations
    "/career-opportunities", "/job-opportunities", "/job-openings",
    
    # Regional variations
    "/us/careers", "/usa/careers", "/en/careers", "/global/careers",
    "/careers/india", "/jobs/india", "/careers/remote"
]

# ======== SUBDOMAIN CHECKS ========
SUBDOMAIN_PATTERNS = [
    "careers", "jobs", "work", "employment", "hiring", "joinus", 
    "apply", "talent", "hr", "recruitment", "join",
    "opportunities", "team"
]

# ======== THIRD-PARTY JOB BOARDS ========
THIRD_PARTY_PATTERNS = [
    r"jobs\.lever\.co/([^/]+)",
    r"([^/]+)\.lever\.co",
    r"boards\.greenhouse\.io/([^/]+)",
    r"jobs\.greenhouse\.io/([^/]+)",
    r"jobs\.ashbyhq\.com/([^/]+)",
    r"([^/]+)\.bamboohr\.com/jobs",
    r"workday\.([^/]+)\.com/careers",
    r"([^/]+)\.workday\.com/careers",
    r"([^/]+)\.recruitee\.com",
    r"([^/]+)\.applytojob\.com",
    r"([^/]+)\.breezy\.hr",
    r"([^/]+)\.comeet\.com/jobs",
    r"([^/]+)\.teamtailor\.com",
    r"([^/]+)\.rippling-ats\.com",
    r"linkedin\.com/company/([^/]+)/jobs",
    r"indeed\.com/cmp/([^/]+)/jobs",
    r"smartrecruiters\.com/([^/]+)"
]

# ======== EXPANDED LINK TEXT PATTERNS ========
LINK_TEXTS = [
    # Basic terms
    r"career", r"job", r"employment", r"position", r"vacanc", 
    r"opening", r"opportunit", 
    
    # Phrases
    r"join(\s+the)?\s+team", r"join\s+us", r"work\s+(with|for)\s+us", 
    r"we.?re\s+hiring", r"we\s+are\s+hiring",
    r"apply\s+(now|today)", r"work\s+at", r"work\s+for", 
    
    # Action-oriented
    r"explore\s+(job|career)", r"find\s+a\s+(job|career)",
    r"become\s+part\s+of", r"apply\s+for", r"current\s+(opening|position|vacanc)",
    
    # Career-specific
    r"career\s+path", r"job\s+search", r"join\s+our\s+talent",
    r"life\s+at", r"work\s+life"
]

async def check_subdomain_urls(base_url, company_name):
    """Try common career subdomains"""
    parsed_url = re.match(r'https?://(?:www\.)?([^/]+)', base_url)
    if not parsed_url:
        return None
    
    domain = parsed_url.group(1)
    base_domain = '.'.join(domain.split('.')[-2:]) # Gets e.g. "company.com" from "www.company.com"
    
    subdomain_urls = []
    for pattern in SUBDOMAIN_PATTERNS:
        subdomain_urls.append(f"https://{pattern}.{base_domain}")
    
    print(f"  → Checking {len(subdomain_urls)} possible career subdomains...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        for url in subdomain_urls:
            try:
                print(f"  → Trying subdomain: {url}")
                response = await page.goto(url, timeout=8000)
                
                if response and response.status < 400:
                    content = await page.content()
                    if re.search(r"(career|job|position|opening|opportunit|vacanc)", content, re.I):
                        print(f"  ✅ Found career subdomain: {url}")
                        await browser.close()
                        return url
            except Exception as e:
                continue
                
        await browser.close()
    return None

async def find_career_page(page, base_url, company_name):
    """Find the careers page through multiple strategies"""
    print(f"\n🔎 Analyzing {company_name} ({base_url})")
    
    # STRATEGY 0: Check for common career subdomains
    subdomain_url = await check_subdomain_urls(base_url, company_name)
    if subdomain_url:
        return subdomain_url
    
    # STRATEGY 1: Go to homepage and look for navigation menus
    try:
        print(f"  → Visiting homepage and checking navigation")
        await page.goto(base_url, timeout=20000)
        await page.wait_for_load_state("networkidle", timeout=10000)
        
        # First check for third-party job boards in any links
        all_links = await page.get_by_role("link").all()
        for link in all_links:
            try:
                href = await link.get_attribute("href")
                if href:
                    # Check for known job board URLs
                    for pattern in THIRD_PARTY_PATTERNS:
                        if re.search(pattern, href, re.I):
                            print(f"  ✅ Found third-party job board: {href}")
                            return href
            except:
                continue
        
        # Check main navigation elements
        for nav_text in ["company", "about", "about us", "team", "life", "work"]:
            print(f"  → Looking for '{nav_text}' navigation section")
            company_nav = page.get_by_role("link").filter(has_text=re.compile(f"^{nav_text}$", re.I))
            
            if await company_nav.count() > 0:
                print(f"  → Found '{nav_text}' navigation, checking for career links")
                await company_nav.first.hover()
                await page.wait_for_timeout(1000)  # Wait for potential dropdown
                
                # Look for career links in any revealed dropdown
                for career_text in LINK_TEXTS:
                    career_link = page.get_by_role("link").filter(has_text=re.compile(career_text, re.I))
                    if await career_link.count() > 0:
                        href = await career_link.first.get_attribute("href")
                        if href:
                            # Handle relative URLs
                            if href.startswith("/"):
                                href = base_url.rstrip("/") + href
                            elif not href.startswith(("http://", "https://")):
                                href = base_url.rstrip("/") + "/" + href
                            print(f"  ✅ Found career link via navigation menu: {href}")
                            return href
        
        # STRATEGY 2: Look for footer links directly
        print(f"  → Checking footer links")
        footer = page.locator("footer")
        if await footer.count() > 0:
            print(f"  → Footer found, scanning for career links")
            for career_text in LINK_TEXTS:
                footer_career = footer.get_by_role("link").filter(has_text=re.compile(career_text, re.I))
                if await footer_career.count() > 0:
                    href = await footer_career.first.get_attribute("href")
                    if href:
                        # Handle relative URLs
                        if href.startswith("/"):
                            href = base_url.rstrip("/") + href
                        elif not href.startswith(("http://", "https://")):
                            href = base_url.rstrip("/") + "/" + href
                        print(f"  ✅ Found career link in footer: {href}")
                        return href
        
        # STRATEGY 3: Search for any career link on the page
        print(f"  → Scanning entire page for career-related links")
        for career_text in LINK_TEXTS:
            career_link = page.get_by_role("link").filter(has_text=re.compile(career_text, re.I))
            if await career_link.count() > 0:
                href = await career_link.first.get_attribute("href")
                if href:
                    # Handle relative URLs
                    if href.startswith("/"):
                        href = base_url.rstrip("/") + href
                    elif not href.startswith(("http://", "https://")):
                        href = base_url.rstrip("/") + "/" + href
                    print(f"  ✅ Found career link on page: {href}")
                    return href
    except Exception as e:
        print(f"  ⚠️ Error checking homepage navigation: {e}")
    
    # STRATEGY 4: Try direct URL patterns
    print(f"  → Trying {len(URL_PATTERNS)} direct URL patterns")
    for pattern in URL_PATTERNS:
        try:
            test_url = base_url.rstrip('/') + pattern
            print(f"  → Testing URL: {test_url}")
            response = await page.goto(test_url, timeout=10000)
            
            # Check if page exists (no 404)
            if response and response.status < 400:
                # Quick check if this looks like a careers page
                content = await page.content()
                if re.search(r"(career|job|position|opening|opportunit|work with us|employ|vacanc)", content, re.I):
                    print(f"  ✅ Found working careers URL: {test_url}")
                    return test_url
        except Exception as e:
            pass
    
    # STRATEGY 5: Google search as last resort
    try:
        print(f"  → Trying Google search fallback")
        search_queries = [
            f"{company_name} careers",
            f"{company_name} jobs",
            f"{company_name} hiring",
            f"{company_name} join team",
            f"{company_name} careers page"
        ]
        
        for query in search_queries:
            try:
                await page.goto(f"https://www.google.com/search?q={query}", timeout=15000)
                await page.wait_for_load_state("networkidle", timeout=10000)
                
                # Look for results with career/job in the title
                results = page.locator("h3").filter(has_text=re.compile(r"(career|job|position|opening|join|work)", re.I))
                if await results.count() > 0:
                    # Click first result
                    print(f"  → Found potential result in Google search: '{await results.first.text_content()}', clicking")
                    await results.first.click()
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    
                    # Check if it looks like a career page
                    current_url = page.url
                    content = await page.content()
                    if re.search(r"(career|job|position|opening|opportunit|vacanc)", content, re.I):
                        print(f"  ✅ Found career page via Google: {current_url}")
                        return current_url
            except Exception as e:
                print(f"  → Search for '{query}' failed: {str(e)[:50]}...")
    except Exception as e:
        print(f"  ⚠️ Error with Google search fallback: {e}")
    
    print(f"  ❌ Could not find career page for {company_name}")
    return None

def append_to_csv(filename, row_dict, fieldnames):
    """Append a single row to CSV file, creating it if needed"""
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        # Write header if file doesn't exist
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(row_dict)
    
    print(f"💾 Saved result to {filename}")

async def process_companies(input_csv, output_csv):
    """Process all companies and find their career pages"""
    fieldnames = ['company', 'website', 'career_url', 'timestamp']
    
    # Create the output file if it doesn't exist
    if not os.path.exists(output_csv):
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
    
    # Read existing processed companies with non-null career URLs
    processed_companies = set()
    if os.path.exists(output_csv):
        with open(output_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Only consider companies with non-empty career_url as processed
                if row.get('career_url'):
                    processed_companies.add(row.get('company'))
    
    print(f"📋 Found {len(processed_companies)} already processed companies with career URLs")
    
    # Read input companies
    companies = []
    with open(input_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        print(f"📋 Loading companies from {input_csv}")
        for row in reader:
            company_name = row.get('company', row.get('name', ''))
            # Skip companies that already have career URLs
            if company_name not in processed_companies:
                companies.append(row)
    
    print(f"🔄 Processing {len(companies)} companies that need career URLs...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        # Process each company
        for index, company in enumerate(companies):
            company_name = company.get('company', company.get('name', ''))
            website = company.get('website', company.get('url', ''))
            
            if not website.startswith(('http://', 'https://')):
                website = 'https://' + website
            
            print(f"\n📊 Processing company {index+1}/{len(companies)}: {company_name}")
            
            page = await context.new_page()
            try:
                career_url = await find_career_page(page, website, company_name)
                
                # Create result and save immediately
                result = {
                    'company': company_name,
                    'website': website,
                    'career_url': career_url or '',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Append this result to the CSV
                append_to_csv(output_csv, result, fieldnames)
                
                print(f"✅ Completed {company_name}: {'Found career URL' if career_url else 'No career URL found'}")
                
            except Exception as e:
                print(f"❌ Error processing {company_name}: {e}")
                result = {
                    'company': company_name,
                    'website': website,
                    'career_url': '',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                # Save failure immediately too
                append_to_csv(output_csv, result, fieldnames)
            finally:
                await page.close()
                # Add delay to avoid rate limiting
                await asyncio.sleep(2)
        
        await context.close()
        await browser.close()
    
    print(f"\n✅ All done! Results saved to {output_csv}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Find career pages for companies')
    parser.add_argument('input_csv', type=str, help='CSV file with companies')
    parser.add_argument('output_csv', type=str, help='CSV file to save results')
    args = parser.parse_args()
    
    asyncio.run(process_companies(args.input_csv, args.output_csv))