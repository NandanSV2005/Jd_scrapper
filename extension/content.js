/**
 * Job Scraper Pro - Content Script v3.0
 * Runs on listing pages to extract job links AND on individual job pages to extract full details.
 * Naukri-optimized with robust fallback selectors.
 */

// ─── Site-Specific Selectors (most specific first, fallback last) ────────

const SITE = {
  'naukri': {
    // ── Listing page: detect if we're on a search results page ──
    isListing: () => {
      const signals = [
        document.querySelectorAll('a[href*="/job-listings"]').length >= 2,
        document.querySelectorAll('a[href*="-jobs-careers-"]').length >= 2,
        document.querySelectorAll('div[class*="cust-job-tuple"], div[class*="sjw__tuple"], div[class*="jobTuple"]').length >= 2,
        document.querySelectorAll('div[class*="srp-"], div[class*="search-result"]').length >= 2,
        document.querySelector('[class*="pagination"], [aria-label*="pagination"]') !== null,
        window.location.pathname.includes('/jobs/') || window.location.search.includes('k='),
      ];
      return signals.filter(Boolean).length >= 2;
    },

    // ── Individual job page detection ──
    isJobPage: () => {
      const signals = [
        window.location.pathname.includes('/job-listings'),
        window.location.pathname.includes('/job-details'),
        !!document.querySelector('[class*="jd-header"], [class*="styles_jd-header"], [class*="job-header"]'),
        !!document.querySelector('h1') && !!document.querySelector('[class*="description"]'),
      ];
      return signals.filter(Boolean).length >= 2;
    },

    // ── Extract job URLs from listing page ──
    extractJobLinks: () => {
      const links = [];
      const seen = new Set();

      // PRIMARY: Direct a[href*="job-listings"] scan
      document.querySelectorAll('a[href*="/job-listings"]').forEach(a => {
        const href = a.href || a.getAttribute('href') || '';
        if (!href || seen.has(href)) return;
        seen.add(href);

        // Find company name by looking up the DOM tree
        let company = '';
        const card = a.closest('div[class*="cust-job-tuple"], div[class*="sjw__tuple"], div[class*="jobTuple"], div[class*="card"], article, li');
        if (card) {
          const companyEl = card.querySelector('a[href*="-jobs-careers-"], [class*="company"], [class*="comp-name"], [class*="org"]');
          if (companyEl) company = companyEl.textContent.trim();
        }
        // Fallback: try to find company from nearby text
        if (!company) {
          let parent = a.parentElement;
          for (let i = 0; i < 5 && parent; i++) {
            const text = parent.textContent || '';
            const match = text.match(/(?:at|with|via)\s+([A-Z][A-Za-z0-9\s.&-]{2,40}?)(?:\s+[A-Z]|$|•|·|\d)/);
            if (match) { company = match[1].trim(); break; }
            parent = parent.parentElement;
          }
        }

        const role = (a.textContent || '').trim();
        const finalUrl = href.startsWith('/') ? window.location.origin + href : href;
        links.push({ url: finalUrl, company, role });
      });

      // SECONDARY: Find job links inside card containers (fallback)
      if (links.length === 0) {
        const cards = document.querySelectorAll(
          'div[class*="cust-job-tuple"], div[class*="sjw__tuple"], div[class*="jobTuple"], ' +
          'section[class*="job"], article[class*="job"]'
        );
        cards.forEach(card => {
          const linkEl = card.querySelector('a[href*="/job-listings"], a[href*="-job-"], a[class*="title"]');
          if (!linkEl) return;
          const href = linkEl.href || '';
          if (!href || seen.has(href)) return;
          seen.add(href);

          const companyEl = card.querySelector('a[href*="-jobs-careers-"], [class*="company"], [class*="comp-name"]');
          const company = companyEl ? companyEl.textContent.trim() : '';
          const role = (linkEl.textContent || '').trim();
          const finalUrl = href.startsWith('/') ? window.location.origin + href : href;
          links.push({ url: finalUrl, company, role });
        });
      }

      return links;
    },

    // ── Extract details from an individual job page ──
    extractJobPage: () => {
      const log = [];

      // Helper: find first matching text
      const find = (selectors) => {
        for (const sel of selectors) {
          try {
            const el = document.querySelector(sel);
            if (el) {
              const text = el.textContent.trim();
              if (text && text.length > 0) return text;
            }
          } catch (e) { /* invalid selector, skip */ }
        }
        return '';
      };

      // Helper: find ALL matching texts
      const findAll = (selectors) => {
        const results = [];
        const seen = new Set();
        for (const sel of selectors) {
          try {
            document.querySelectorAll(sel).forEach(el => {
              const text = el.textContent.trim();
              if (text && text.length > 0 && !seen.has(text) && text.length < 100) {
                seen.add(text);
                results.push(text);
              }
            });
          } catch (e) { /* skip */ }
        }
        return results;
      };

      // ── Company Name ──
      let company = find([
        'a[href*="-jobs-careers-"]',        // Naukri company careers link
        'a[class*="company"]',               // Generic company link
        'a[class*="comp-name"]',             // Company name class
        '[class*="company-name"]',           // Generic
        '[class*="companyName"]',            // Generic
        '[class*="org-name"]',               // Organization name
        '[class*="orgName"]',                // Generic
        'h4[class*="company"]',              // Naukri-style header
        '[data-company-name]',               // Data attribute
        '.jd-header-title-company',          // Naukri specific
        '[class*="subTitle"]',              // Naukri subtitle
      ]);
      log.push(company ? `Company: "${company.substring(0, 60)}"` : 'Company: NOT FOUND');

      // ── Job Role (Title) ──
      let role = find([
        'h1[class*="title"]',                // H1 with title class
        'h1[class*="header"]',               // H1 with header class
        'h1.jd-header-title',                // Naukri specific
        'h1[class*="jd-header"]',            // Naukri specific
        'h1',                                // Fallback to any H1
        '[class*="job-title"] h1',           // Generic
        '.job-title',                        // Generic
        '[class*="designation"]',            // Some sites
      ]);
      log.push(role ? `Role: "${role.substring(0, 80)}"` : 'Role: NOT FOUND');

      // ── Job Description (the full text!) ──
      // Strategy A: Try the EXACT CSS-module container FIRST (user-confirmed via Inspect).
      // It contains ONLY the clean job description with proper <ul>/<li> structure —
      // no company reviews, salaries, benefits, or similar-jobs junk.
      // If found, use it UNCONDITIONALLY and skip the messy fallback entirely.
      const exactSelectors = [
        'div[class*="JDC__dang-inner-html"]', // Naukri CSS-module exact description container
        'div[class*="dang-inner-html"]',       // Naukri broader pattern
      ];
      let description = '';
      let usedExactContainer = false;
      for (const sel of exactSelectors) {
        try {
          const el = document.querySelector(sel);
          if (el) {
            // innerText (not textContent) preserves line breaks between <li> items,
            // so extractBullets() can split them into proper bullet points.
            const text = el.innerText.trim();
            if (text && text.length > 30) {
              description = text;
              usedExactContainer = true;
              break;
            }
          }
        } catch (e) { /* invalid selector, skip */ }
      }
      log.push(usedExactContainer
        ? `  ✓ Exact description container found: ${description.length} chars (no fallback needed)`
        : '  Exact description container: NOT FOUND — using fallback chain');

      // Strategy B: Only run the fallback chain if the exact container was NOT found
      if (!usedExactContainer) {
        // Try remaining CSS selectors for targeted extraction
        let cssDescription = find([
          '.job-details-description',           // Naukri class
          'div[class*="jd-desc"]',              // Naukri description
          'div[class*="description"]',          // Generic
          'section[id*="description"]',         // Section ID
          'div[id*="description"]',             // Div ID
          'div[class*="job-desc"]',             // Generic
          'div[class*="details-section"]',      // Naukri details
          'div[class*="job-detail"]',           // Generic
          'section[class*="description"]',      // Generic section
          '.styles_jd-header-description',      // Naukri styled
          '[class*="detail-section"]',           // Generic
          'div[class*="text-container"]',        // Generic
          '[class*="jd-section"]',              // Naukri sections
          'div[class*="styles_jd"]',            // Naukri CSS-modules pattern
        ]);
        log.push(cssDescription ? `  CSS description: ${cssDescription.length} chars` : '  CSS description: none');

        // ALWAYS run page-text fallback as a safety net (may include junk, smart-trimmed below)
        let fallbackDescription = '';
        log.push('  Running page-text fallback...');

        // Try <main>/<article> area first
        const mainArea = document.querySelector('main, article, [role="main"], .content, #content, .container');
        if (mainArea) {
          const clone = mainArea.cloneNode(true);
          clone.querySelectorAll('header, footer, nav, script, style, ' +
            '[class*="header"], [class*="footer"], [class*="navi"], ' +
            '[class*="sidebar"], [class*="aside"], [class*="banner"], ' +
            '[class*="ad-"], [class*="advertise"], [class*="recommend"]'
          ).forEach(el => el.remove());
          fallbackDescription = clone.innerText.trim();
          if (fallbackDescription.length >= 30) {
            log.push(`  Fallback (main): ${fallbackDescription.length} chars`);
          }
        }

        // Try <body> with more aggressive stripping
        if (!fallbackDescription || fallbackDescription.length < 100) {
          const bodyClone = document.body.cloneNode(true);
          bodyClone.querySelectorAll('header, footer, nav, script, style, ' +
            '[class*="header"], [class*="footer"], [class*="navi"], ' +
            '[class*="sidebar"], [class*="aside"], [class*="banner"], ' +
            '[class*="ad-"], [class*="advertise"], [class*="recommend"], ' +
            '[class*="pagination"], [class*="breadcrumb"], ' +
            '[class*="widget"], [class*="chat"], [class*="footer-"]'
          ).forEach(el => el.remove());
          fallbackDescription = bodyClone.innerText.trim();
          if (fallbackDescription.length >= 30) {
            log.push(`  Fallback (body): ${fallbackDescription.length} chars`);
          }
        }

        // Pick the LONGEST of the two fallback sources
        if (cssDescription.length > 50 && cssDescription.length >= fallbackDescription.length * 0.8) {
          description = cssDescription;
          log.push(`  → Using CSS description (${cssDescription.length} chars)`);
        } else if (fallbackDescription.length >= 30) {
          description = fallbackDescription;
          log.push(`  → Using page-text fallback (${fallbackDescription.length} chars)`);

          // Apply smart trimming to remove junk (company info, reviews, salaries, etc.)
          const trimmed = smartTrimDescription(description);
          if (trimmed.length >= 30) {
            log.push(`  Smart-trimmed from ${description.length} to ${trimmed.length} chars`);
            description = trimmed;
          } else {
            log.push('  Smart-trim skipped (no markers found, text unchanged)');
          }
        } else {
          description = cssDescription || fallbackDescription;
          log.push(`  → Using minimal text (${description.length} chars)`);
        }
      }

      log.push(`Final description: ${description.length} chars`);

      // ── Key Skills ──
      const skills = findAll([
        'a[class*="skill"]',                 // Skill tags links
        'span[class*="skill"]',              // Skill tags spans
        '.key-skill a',                       // Naukri key skills
        '.skill-tag',                         // Generic
        '[class*="skill"] a',                // Generic
        '.jd-skills a',                       // Naukri skills
        '.tags-container a',                 // Generic tags
        'a[href*="/skills/"]',               // Skill URLs
      ]);
      log.push(skills.length > 0 ? `Skills: ${skills.length} found` : 'Skills: 0 found');

      // ── Location ──
      let location = find([
        '[class*="location"]',               // Generic
        '[class*="loc"]',                     // Abbreviated
        '[class*="place"]',                   // Some sites use "place"
        '.job-location',                      // Generic
      ]);
      log.push(location ? `Location: "${location}"` : 'Location: NOT FOUND');

      // ── Experience ──
      let experience = find([
        '[class*="exp"]',                     // Abbreviated
        '[class*="experience"]',              // Full word
        '.work-exp',                          // Naukri
        '.job-experience',                    // Generic
      ]);
      log.push(experience ? `Experience: "${experience}"` : 'Experience: NOT FOUND');

      // ── Education ──
      let education = find([
        '[class*="education"]',              // Generic
        '[class*="edu"]',                     // Abbreviated
        '.eligibility',                       // Some sites
      ]);
      if (education) log.push(`Education: "${education.substring(0, 80)}"`);

      // ── Employment Type, Department, Industry ──
      // Scan the full page text for these details
      const bodyText = document.body.innerText.substring(0, 20000);
      let employmentType = '', department = '', industry = '';

      // Match patterns like "Employment Type: Full Time" or "Industry Type: IT Services"
      const empMatch = bodyText.match(/(?:Employment|Job)\s*Type\s*:?\s*([A-Za-z\s,/&-]+?)(?:\n|•|·|\||$)/i);
      if (empMatch) employmentType = empMatch[1].trim();

      const deptMatch = bodyText.match(/Department\s*:?\s*([A-Za-z\s,&/-]+?)(?:\n|•|·|\||$)/i);
      if (deptMatch) department = deptMatch[1].trim();

      const indMatch = bodyText.match(/Industry\s*(?:Type)?\s*:?\s*([A-Za-z\s,&/-]+?)(?:\n|•|·|\||$)/i);
      if (indMatch) industry = indMatch[1].trim();

      // ── Job Highlights ──
      let highlights = find([
        '[class*="highlight"]',
        '[class*="summary"]',
        '.job-summary',
      ]);

      // ── Bullet Points from Description ──
      const bullets = extractBullets(description);
      log.push(`Bullet points: ${bullets.length}`);

      console.log('[Job Scraper] Job page extraction complete:', log.join(' | '));

      return {
        company: company || '[COMPANY_NOT_FOUND]',
        role: role || '[ROLE_NOT_FOUND]',
        description: description || '',
        descriptionBullets: bullets,
        highlights: highlights || '',
        skills: skills,
        location: location || '',
        experience: experience || '',
        education: education || '',
        employmentType: employmentType || '',
        department: department || '',
        industry: industry || '',
        source: 'naukri-job-page',
        extractionLog: log,
      };
    },
  },

  // ── Generic fallback (works for Indeed, LinkedIn, etc.) ──
  'generic': {
    isListing: () => {
      const links = document.querySelectorAll('a[href*="/job"], a[href*="/career"], a[href*="/position"], a[href*="/vacancy"]');
      return links.length >= 3;
    },

    isJobPage: () => {
      const hasJobTitle = !!document.querySelector('h1, h2[class*="title"]');
      const hasDescription = !!document.querySelector('[class*="description"], [class*="job-detail"], #jobDescriptionText');
      return hasJobTitle && hasDescription;
    },

    extractJobLinks: () => {
      const links = [];
      const seen = new Set();
      const cards = document.querySelectorAll('article, div[class*="card"], div[class*="result"], li[class*="job"]');

      cards.forEach(card => {
        const a = card.querySelector('a[href*="/job"], a[href*="/career"], a[href*="/position"]');
        if (!a) return;
        const href = a.href || '';
        if (!href || seen.has(href)) return;
        seen.add(href);

        const company = (card.querySelector('[class*="company"], [class*="org"], [class*="employer"]') || {}).textContent || '';
        const role = (a.textContent || '').trim();
        links.push({ url: href, company: company.trim(), role });
      });

      // Fallback: scan all links
      if (links.length === 0) {
        document.querySelectorAll('a[href*="/job"], a[href*="/career"], a[href*="/position"], a[href*="/vacancy"]').forEach(a => {
          const href = a.href || '';
          if (!href || seen.has(href)) return;
          seen.add(href);
          const text = (a.textContent || '').trim();
          if (text && text.length > 2 && text.length < 200) {
            links.push({ url: href, company: '', role: text });
          }
        });
      }

      return links;
    },

    extractJobPage: () => {
      // Generic extraction using common job site patterns
      const find = (sels) => {
        for (const s of sels) {
          try {
            const el = document.querySelector(s);
            if (el) {
              const t = el.textContent.trim();
              if (t) return t;
            }
          } catch(e) {}
        }
        return '';
      };

      return {
        company: find(['[class*="company"]', '[class*="org"]', 'a[href*="/company/"]']),
        role: find(['h1', 'h1[class*="title"]', '[class*="job-title"] h1']),
        description: find(['#jobDescriptionText', '[class*="description"]', '[class*="job-detail"]']),
        descriptionBullets: [],
        highlights: '',
        skills: [],
        location: find(['[class*="location"]', '[class*="loc"]']),
        experience: find(['[class*="exp"]', '[class*="experience"]']),
        education: '',
        employmentType: '',
        department: '',
        industry: '',
        source: 'generic-job-page',
        extractionLog: [],
      };
    },
  },
};

// ─── Smart Description Trimmer (cuts junk before/after the actual JD) ──────

function smartTrimDescription(text) {
  if (!text || text.length < 50) return text;

  // Start markers - find the EARLIEST one that appears
  const startMarkers = [
    'Job description',
    'Job Description',
    'We are looking for',
    "You'll make an impact by",
    'Your key responsibilities',
    "What you'll do",
    'About the role',
    'About this role',
    'Job Description:',
    'Job description:',
  ];

  // End markers - find the EARLIEST one that appears AFTER the start
  const endMarkers = [
    '\nRole:',
    '\nRole :',
    '\nIndustry Type:',
    '\nIndustry :',
    '\nCompany Info',
    '\nKey highlights',
    '\nCompany reviews',
    '\nAbout Company',
    '\nBeware of imposters',
    '\nroles you might be interested in',
    '\nSimilar Jobs',
    '\nSimilar jobs',
    '\nHome Jobs',
    '\nEmployee reviews',
    '\nSalary & Benefits',
    '\nPerks and Benefits',
    '\nCompany website',
    '\nFollow',
    '\nKickstart your',
    '\nReport this',
  ];

  // Find start
  let startIdx = -1;
  let usedStartMarker = '';
  for (const marker of startMarkers) {
    const idx = text.indexOf(marker);
    if (idx >= 0) {
      if (startIdx === -1 || idx < startIdx) {
        startIdx = idx;
        usedStartMarker = marker;
      }
    }
  }

  if (startIdx >= 0) {
    // Cut from the start marker
    text = text.substring(startIdx);
    // Remove the marker text itself (it's just a section header)
    if (text.startsWith(usedStartMarker)) {
      text = text.substring(usedStartMarker.length).trim();
    }
  }

  // Find end
  let endIdx = text.length;
  for (const marker of endMarkers) {
    const idx = text.indexOf(marker);
    if (idx >= 0 && idx < endIdx) {
      endIdx = idx;
    }
  }

  text = text.substring(0, endIdx).trim();

  // If we trimmed nothing meaningful, return original
  if (text.length < 30) return '';
  return text;
}

// ─── Bullet Point Extraction ────────────────────────────────────────────────

function extractBullets(text) {
  if (!text || text.length < 20) return [];

  // Strip HTML
  const cleaned = text.replace(/<[^>]*>/g, '\n');

  // Split by common delimiters: bullet chars, newlines, numbered lists
  const lines = cleaned.split(/[•·●◆◇▪▸▹►▻‣⁃⦿✦✧■✓–—]|\n+|(?:\d+[.)])\s*/);

  return lines
    .map(l => l.replace(/\s+/g, ' ').trim())
    .filter(l => l.length > 15)           // Filter too-short lines
    .filter(l => !/^(and|or|the|a|an|to|for|in|of|with|by|at|is|are|was|were)$/i.test(l))
    .slice(0, 100);                        // Max 100 bullets
}

// ─── Messaging Handler ──────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'scrape') {
    try {
      const result = scrapeCurrentPage(request.options || {});

      // If description is too short, wait 3s and retry (JS may still be rendering)
      if (result.data && result.data.length > 0) {
        const item = result.data[0];
        if (item && (!item.description || item.description.length < 100)) {
          setTimeout(() => {
            const retryResult = scrapeCurrentPage(request.options || {});
            if (retryResult.data && retryResult.data.length > 0) {
              const retryItem = retryResult.data[0];
              if (retryItem && retryItem.description && retryItem.description.length > (item.description || '').length) {
                // Retry got better data, update extraction log
                retryResult.extractionLog.unshift('[Retry after 3s — got more content]');
                sendResponse(retryResult);
                return;
              }
            }
            // Retry didn't help, send original result
            result.extractionLog.push('[Retry after 3s — no improvement]');
            sendResponse(result);
          }, 3000);
          return true; // Keep channel open for async retry
        }
      }

      sendResponse(result);
    } catch (err) {
      sendResponse({
        error: err.message,
        data: [],
        pageType: 'error',
        extractionLog: [`CRITICAL ERROR: ${err.message}`],
        jobLinks: [],
      });
    }
  }
  // Keep channel open for async response
  return true;
});

// ─── Main Scrape Function ──────────────────────────────────────────────────

function scrapeCurrentPage(options = {}) {
  const url = window.location.href;
  const hostname = window.location.hostname;
  const log = [];

  function l(msg) {
    console.log('[Job Scraper]', msg);
    log.push(msg);
  }

  l(`=== Job Scraper Pro v3.0 ===`);
  l(`URL: ${url}`);

  // ── Detect Site ──
  let site = 'generic';
  if (hostname.includes('naukri.com')) site = 'naukri';
  else if (hostname.includes('indeed.com')) site = 'generic'; // Still works with generic
  else if (hostname.includes('linkedin.com')) site = 'generic';
  l(`Site: ${site}`);

  // ── Detect Page Type ──
  const s = SITE[site];
  const isJob = s.isJobPage();
  const isListing = s.isListing();

  let pageType;
  if (isJob) pageType = 'job';
  else if (isListing) pageType = 'listing';
  else pageType = 'unknown';
  l(`Page type: ${pageType}`);

  // ── If Job Page → Extract Full Details ──
  if (pageType === 'job') {
    const data = s.extractJobPage();
    if (data.extractionLog) data.extractionLog.forEach(msg => l(msg));

    const hasRealData = data.company && !data.company.startsWith('[COMPANY_') && data.company !== '';
    const hasRole = data.role && !data.role.startsWith('[ROLE_') && data.role !== '';
    const hasDesc = data.description && data.description.length > 20;

    if (hasRealData || hasRole) {
      l(`✓ SUCCESS: ${data.company} — ${data.role.substring(0, 60)}`);
      if (hasDesc) l(`  Description: ${data.description.length} chars, ${data.descriptionBullets.length} bullets`);
      if (data.skills.length > 0) l(`  Skills: ${data.skills.length}`);

      return {
        data: [data],
        count: 1,
        pageType: 'job',
        jobLinks: [],
        extractionLog: log,
      };
    }

    l('✗ Failed to extract job data from this page');
    return { data: [], count: 0, pageType: 'job', jobLinks: [], extractionLog: log };
  }

  // ── If Listing Page → Extract Job Links for Batch ──
  if (pageType === 'listing') {
    const jobLinks = s.extractJobLinks();
    l(`Found ${jobLinks.length} job link(s)`);

    if (jobLinks.length > 0) {
      // Show first few links
      jobLinks.slice(0, 3).forEach((jl, i) => {
        l(`  [${i + 1}] ${jl.company || '?'} — ${jl.role.substring(0, 60)}`);
      });
      return {
        data: [],
        count: 0,
        pageType: 'listing-with-links',
        jobLinks: jobLinks,
        jobLinksCount: jobLinks.length,
        extractionLog: log,
      };
    }

    l('✗ No job links found on listing page');
    return { data: [], count: 0, pageType: 'listing', jobLinks: [], extractionLog: log };
  }

  // ── Unknown → Try generic extraction ──
  l('Unknown page type — attempting generic extraction...');
  return {
    data: [],
    count: 0,
    pageType: 'unknown',
    jobLinks: [],
    extractionLog: log,
  };
}
