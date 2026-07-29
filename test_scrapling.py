"""
Test: Scrapling vs Naukri.com
Tests if Scrapling can:
1. Bypass Naukri's anti-bot protection (Akamai/Cloudflare)
2. Extract job links from listing page
3. Extract details from individual job pages
"""

from scrapling.fetchers import StealthyFetcher


def test_naukri_listing():
    print("=" * 60)
    print("TEST 1: Fetch Naukri AI Jobs Listing Page")
    print("=" * 60)

    try:
        StealthyFetcher.adaptive = True
        page = StealthyFetcher.fetch(
            'https://www.naukri.com/ai-jobs',
            headless=True,
            network_idle=True,
        )

        if not page:
            print("[FAIL] Failed to fetch page - got empty response")
            return None, None

        body_html = page.text if hasattr(page, 'text') else (page.body.decode() if hasattr(page, 'body') else str(page))
        print(f"[OK] Page fetched successfully! ({len(body_html)} chars)")
        title_el = page.css('title::text')
        print(f"  Title: {title_el[0] if title_el else 'N/A'}")
        print(f"  URL: {page.url if hasattr(page, 'url') else 'N/A'}")

        # Check for anti-bot indicators
        body_lower = body_html.lower()
        if 'captcha' in body_lower or 'verify you are human' in body_lower or 'blocked' in body_lower:
            print("[FAIL] Anti-bot protection detected (CAPTCHA/blocked page)")
            return None, None

        print("[OK] Anti-bot: BYPASSED!")
        return page, body_html

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None, None


def extract_job_links(page):
    """Extract job links from a Naukri listing page."""
    print("\n--- Extracting Job Links ---")
    
    links = []
    seen_urls = set()
    
    # Try finding job cards with various selectors
    card_selectors = [
        'div[class*="jobTuple"]',
        '.job-tuple',
        'article',
        'div[class*="card"]',
    ]
    
    cards = []
    for sel in card_selectors:
        found = page.css(sel)
        if found and len(found) >= 2:
            cards = found
            print(f"  [OK] Found {len(cards)} cards with selector: '{sel}'")
            break

    if not cards:
        print("  [FAIL] No job cards found")
        print(f"  Debug: Page has {len(page.css('a[href]'))} total links")
        return []

    for card in cards:
        try:
            for link in card.css('a[href]'):
                href = link.attrib.get('href', '')
                if href and '/job-listings' in href and href not in seen_urls:
                    seen_urls.add(href)
                    company_el = card.css('[class*="company"], [class*="org"]')
                    company = company_el[0].text_content().strip() if company_el else ''
                    title = link.text_content().strip() if link.text_content() else ''
                    links.append({
                        'url': href if href.startswith('http') else f'https://www.naukri.com{href}',
                        'company': company[:80],
                        'title': title[:120],
                    })
                    break
        except Exception:
            continue

    print(f"  [OK] Extracted {len(links)} job links")
    for i, job in enumerate(links[:5], 1):
        print(f"    {i}. [{job['company']}] {job['title']}")
    return links


def test_job_page(url):
    """Test fetching an individual Naukri job page."""
    print(f"\n--- TEST 2: Individual Job Page ---")
    print(f"  URL: {url[:100]}")
    
    try:
        StealthyFetcher.adaptive = True
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
        
        if not page:
            print("  [FAIL] Could not fetch job page")
            return None

        print(f"  [OK] Job page fetched!")
        title_el = page.css('title::text')
        print(f"  Title: {title_el[0] if title_el else 'N/A'}")
        
        # Company name
        company = ""
        for sel in ['.jd-header-title-company', 'a[class*="company"]', '[class*="company-name"]']:
            el = page.css(sel)
            if el:
                company = el[0].text_content().strip()[:100]
                print(f"  [OK] Company: {company}")
                break
        if not company:
            print("  [FAIL] Company not found")

        # Job role
        role = ""
        for sel in ['.jd-header-title', 'h1[class*="title"]', 'h1']:
            el = page.css(sel)
            if el:
                role = el[0].text_content().strip()[:120]
                print(f"  [OK] Role: {role}")
                break
        if not role:
            print("  [FAIL] Role not found")

        # Description
        desc = ""
        for sel in ['.job-details-description', '.jd-desc', 'div[class*="description"]']:
            el = page.css(sel)
            if el:
                desc = el[0].text_content().strip()
                print(f"  [OK] Description: {len(desc)} chars")
                break
        if not desc:
            print("  [FAIL] Description not found")

        # Skills
        skills = []
        for sel in ['.key-skill', '.skill', '[class*="skill"]']:
            els = page.css(sel)
            if els:
                skills = [e.text_content().strip() for e in els[:15] if e.text_content()]
                if skills:
                    print(f"  [OK] Skills ({len(skills)}): {', '.join(skills[:6])}")
                    break

        return {
            'company': company or '[MISSING]',
            'role': role or '[MISSING]',
            'desc_len': len(desc) if desc else 0,
            'skills': skills,
        }

    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


if __name__ == "__main__":
    page, body = test_naukri_listing()
    
    if page:
        links = extract_job_links(page)
        
        if links:
            # Test one individual job page
            job_page = test_job_page(links[0]['url'])
    
    print("\n" + "=" * 60)
    print("RESULT SUMMARY")
    print("=" * 60)
    if page:
        print("[PASS] Naukri listing page: FETCHABLE (anti-bot bypassed)")
    else:
        print("[FAIL] Naukri listing page: Could not fetch")
