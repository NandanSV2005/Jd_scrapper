"""
Test 2: Scrapling DynamicFetcher for JS-heavy Naukri pages
"""
from scrapling.fetchers import DynamicFetcher


def test_naukri():
    print("=" * 60)
    print("TEST: DynamicFetcher - Full JS Rendering")
    print("=" * 60)

    try:
        # DynamicFetcher uses Playwright for full JS rendering
        page = DynamicFetcher.fetch(
            'https://www.naukri.com/ai-jobs',
            headless=True,
            network_idle=True,
        )

        if not page:
            print("[FAIL] Page empty")
            return

        body = page.text if hasattr(page, 'text') else ''
        print(f"[OK] Page fetched! Body: {len(body)} chars")
        
        title = page.css('title::text')
        print(f"  Title: {title[0] if title else 'N/A'}")

        # Check if page has job content
        if 'captcha' in body.lower() or 'verify' in body.lower():
            print("[FAIL] CAPTCHA detected!")
            return

        # Debug: count all links
        all_links = page.css('a[href]')
        print(f"  Total links on page: {len(all_links)}")

        # Show link patterns
        from collections import Counter
        patterns = Counter()
        for link in all_links:
            h = link.attrib.get('href', '')
            if '/job-listings' in h:
                patterns['job-listings'] += 1
            elif '/ai-jobs' in h or h.endswith('-jobs'):
                patterns['filter-jobs'] += 1
            elif 'company' in h.lower():
                patterns['company'] += 1
            elif len(h) > 5 and h.startswith('/'):
                patterns['other'] += 1
        
        print(f"  Link breakdown:")
        for k, v in patterns.most_common():
            print(f"    {k}: {v}")

        # Try different card selectors
        for sel in ['.jobTuple', 'div[class*="jobTuple"]', '.job-tuple', 
                    'section[class*="job"]', 'li[class*="job"]',
                    'div[class*="srp"]', 'div[class*="list"]']:
            els = page.css(sel)
            if els:
                print(f"  Selector '{sel}': {len(els)} matches")
        
        # Show first 50 link texts and URLs to understand the structure
        print(f"\n  Sample links (first 20):")
        count = 0
        for link in all_links:
            if count >= 20:
                break
            href = link.attrib.get('href', '')
            text = (link.text_content() or '')[:60].strip()
            if href and not href.startswith('#') and not href.startswith('javascript'):
                print(f"    [{text}] -> {href[:90]}")
                count += 1

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_naukri()
