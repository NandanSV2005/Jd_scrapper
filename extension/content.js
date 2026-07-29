/**
 * Job Scraper Pro - Content Script
 * Extracts company names, job roles, and descriptions from any page.
 * Detects page type (listing vs individual job) and uses appropriate strategies.
 * v2.0 - Fixes: company name extraction, job description extraction,
 * page type detection, transparent logging, no silent placeholders.
 */

// ─── Constants ──────────────────────────────────────────────────────────────

const COMPANY_SUFFIXES = [
  'inc', 'ltd', 'limited', 'pvt', 'private', 'corp', 'corporation',
  'llc', 'llp', 'plc', 'gmbh', 'ag', 'sa', 'bv', 'nv', 'pty',
  'technologies', 'tech', 'solutions', 'services', 'consulting',
  'group', 'holdings', 'enterprises', 'systems', 'software',
  'digital', 'global', 'international', 'industries', 'labs',
  'ventures', 'partners', 'associates', 'analytics', 'data', 'infotech',
];

const EXCLUDE_WORDS = new Set([
  'home', 'about', 'contact', 'search', 'login', 'sign', 'register',
  'jobs', 'careers', 'apply', 'submit', 'next', 'previous', 'page',
  'loading', 'error', 'menu', 'navigation', 'footer', 'header',
  'skip', 'share', 'save', 'cancel', 'delete', 'edit', 'filter',
  'sort', 'view', 'list', 'grid', 'back', 'more', 'less', 'all',
  'submit', 'reset', 'send', 'close', 'open', 'help', 'faq', 'features',
  'products', 'services', 'solutions', 'pricing', 'blog', 'contact us',
]);

// Site-specific selectors for individual job posting pages
const SITE_SELECTORS = {
  'indeed.com': {
    company: [
      '[data-testid="inlineHeader-companyName"]',
      '.jobsearch-JobInfoHeader-companyName',
      '.icl-u-lg-mr--sm',
      '[data-tn-component="companyHeader"]',
    ],
    role: [
      '.jobsearch-JobInfoHeader-title',
      'h1[class**="title"]',
      '[data-testid="jobsearch-JobInfoHeader-title"]',
      '.jobsearch-JobInfoHeader-title > span',
    ],
    description: [
      '#jobDescriptionText',
      '.jobsearch-jobDescriptionText',
      '#jobDescriptionText > div',
      '[id*="jobDescription"]',
      '.jobsearch-JobComponent-description',
    ],
    isJobPage: [
      '#jobDescriptionText',
      '.jobsearch-JobInfoHeader',
      '[data-testid="jobsearch-JobInfoHeader"]',
    ],
  },
  'linkedin.com': {
    company: [
      '.job-details-jobs-unified-top-card__company-name',
      '.topcard__flavor--bullet',
      '.job-details-preferences-and-skills__company-name',
      'a[href*="/company/"]',
      '.topcard__org-name-link',
    ],
    role: [
      '.job-details-jobs-unified-top-card__job-title',
      '.topcard__title',
      'h1[class*="title"]',
      '.job-title',
    ],
    description: [
      '.job-details-jobs-unified-top-card__description-container',
      '.job-details__job-description',
      '.show-more-less-html__markup',
      'article.description',
      '#job-details',
    ],
    isJobPage: [
      '.job-details-jobs-unified-top-card',
      '.job-view-layout',
      '.jobs-details',
    ],
  },
  'naukri.com': {
    company: [
      '.jd-header-title-company',
      'a[class*="company"]',
      '.companyInfo .companyName',
      '[class*="company-name"]',
      '.job-header-corp .company-name',
      '.job-company-wrapper a',
    ],
    role: [
      '.jd-header-title',
      'h1[class*="title"]',
      '.job-header-corp h1',
      '[class*="job-title"] h1',
      'h1.job-title',
      '.job-details-jobs-unified-top-card__job-title',
    ],
    description: [
      '.job-details-description',
      '.jd-desc',
      'div[class*="description"]',
      '.job-description',
      '.details-section',
      '.job-description-section',
    ],
    highlights: [
      '.job-highlights',
      '.job-summary',
      '[class*="highlight"]',
      '.job-header-brief',
    ],
    skills: [
      '.key-skill',
      '.skill',
      '[class*="skill"] a',
      '.tags-container a',
      '.skill-tag',
      '.jd-skills a',
    ],
    location: [
      '.location',
      '.loc',
      '[class*="location"]',
      '.job-location',
      '[class*="place"]',
    ],
    experience: [
      '.experience',
      '.exp',
      '[class*="exp"]',
      '.work-exp',
      '.job-experience',
    ],
    education: [
      '.education',
      '.edu',
      '[class*="education"]',
      '.eligibility',
    ],
    jobDetails: [
      '.other-details',
      '.job-other-details',
      '.job-detail',
      '[class*="detail"]',
      'table td',
    ],
    isJobPage: [
      '.job-details-description',
      '.jd-header-title',
      '.job-header-corp',
      '.job-details-jobs-unified-top-card',
    ],
  },
};

// ─── Messaging ──────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'scrape') {
    try {
      const result = scrapePage(request.options || {});
      sendResponse(result);
    } catch (err) {
      sendResponse({
        error: err.message,
        data: [],
        pageType: 'error',
        extractionLog: [`CRITICAL ERROR: ${err.message}`]
      });
    }
  }  // Close the if block
  // Keep channel open for async response
  return true;
});

// ─── Main ───────────────────────────────────────────────────────────────────

function scrapePage(options = {}) {
  const { dedup = true, deepMode = true, cssSelectors = {} } = options;
  const log = [];
  const seenFingerprints = new Set();
  const items = [];
  const url = window.location.href;
  const hostname = window.location.hostname;

  function logger(msg) {
    console.log('[Job Scraper]', msg);
    log.push(msg);
  }

  logger(`=== Job Scraper Pro v2.0 ===`);
  logger(`URL: ${url}`);
  logger(`Hostname: ${hostname}`);

  // ── Step 1: Detect page type ──────────────────────────────────────────
  const pageType = detectPageType(hostname, logger);
  logger(`Page type: ${pageType.type} (${pageType.reason})`);

  // ── Step 2: If individual job page on known site, use site-specific extraction ──
  if (pageType.type === 'job' && pageType.site) {
    logger(`→ Site-specific extraction for "${pageType.site}"`);
    const siteItems = extractFromJobPage(pageType.site, logger);
    for (const item of siteItems) {
      if (validateItem(item, dedup, seenFingerprints, logger)) {
        items.push(item);
      }
    }
    logger(`Site-specific: ${siteItems.length} items extracted`);

    if (items.length > 0) {
      logger(`✓ TOTAL: ${items.length} entries with real data`);
      return buildResult(items, log, pageType, logger);
    }
  }

  // ── Step 3: JSON-LD (ONLY JobPosting/Organization — skip ItemList) ────
  if (deepMode) {
    logger('Strategy 1/5: JSON-LD structured data...');
    const jsonldRaw = extractJSONLD(logger);
    const before = items.length;
    for (const item of jsonldRaw) {
      if (validateItem(item, dedup, seenFingerprints, logger)) {
        items.push(item);
      }
    }
    const added = items.length - before;
    logger(`  JSON-LD: ${jsonldRaw.length} candidates → ${added} new`);
  }

  // ── Step 4: CSS Selectors ──────────────────────────────────────────────
  logger('Strategy 2/5: CSS Selectors...');
  const before2 = items.length;
  const selRaw = extractViaSelectors(cssSelectors, seenFingerprints, logger);
  for (const item of selRaw) {
    if (validateItem(item, dedup, seenFingerprints, logger)) {
      items.push(item);
    }
  }
  logger(`  Selectors: ${selRaw.length} candidates → ${items.length - before2} new`);

  // ── Step 5: Tables ─────────────────────────────────────────────────────
  if (deepMode || items.length === 0) {
    logger('Strategy 3/5: HTML Tables...');
    const before3 = items.length;
    const tableRaw = extractFromTables(seenFingerprints, logger);
    for (const item of tableRaw) {
      if (validateItem(item, dedup, seenFingerprints, logger)) {
        items.push(item);
      }
    }
    logger(`  Tables: ${tableRaw.length} candidates → ${items.length - before3} new`);
  }

  // ── Step 6: Card/list patterns ─────────────────────────────────────────
  if (deepMode || items.length === 0) {
    logger('Strategy 4/5: Card/List patterns...');
    const before4 = items.length;
    const cardRaw = extractFromCards(cssSelectors, seenFingerprints, logger);
    for (const item of cardRaw) {
      if (validateItem(item, dedup, seenFingerprints, logger)) {
        items.push(item);
      }
    }
    logger(`  Cards: ${cardRaw.length} candidates → ${items.length - before4} new`);
  }

  // ── Step 7: Text patterns (last resort) ───────────────────────────────
  if (items.length === 0) {
    logger('Strategy 5/5: Text patterns (last resort)...');
    const before5 = items.length;
    const textRaw = extractFromTextPatterns(seenFingerprints, logger);
    for (const item of textRaw) {
      if (validateItem(item, dedup, seenFingerprints, logger)) {
        items.push(item);
      }
    }
    logger(`  Text: ${textRaw.length} candidates → ${items.length - before5} new`);
  }

  if (items.length === 0) {
    logger('✗ NO DATA EXTRACTED — none of the 5 strategies found results');
  } else {
    logger(`✓ TOTAL: ${items.length} entries`);
  }

  return buildResult(items, log, pageType, logger);
}

// ─── Build result object ────────────────────────────────────────────────────

function buildResult(items, log, pageType, logger) {
  const result = {
    data: items,
    count: items.length,
    pageType: pageType.type,
    extractionLog: log,
  };

  // If it's a listing page, ALSO extract job links for batch scraping
  if (pageType.type === 'listing') {
    // Extract job links from the listing cards
    const links = extractJobLinks();
    result.jobLinks = links;
    result.jobLinksCount = links.length;

    logger(`Extracted ${links.length} job link(s) from listing page for batch processing`);

    // No warning anymore — listing pages are the primary workflow now!
    // We'll handle batch scraping in the popup
    if (links.length > 0) {
      result.pageType = 'listing-with-links';
    }
  }

  return result;
}

// ─── Page Type Detection ────────────────────────────────────────────────────

function detectPageType(hostname, logger) {
  const site = Object.keys(SITE_SELECTORS).find(s => hostname.includes(s));

  if (site) {
    const selectors = SITE_SELECTORS[site];

    // Check if this is an individual job posting page
    for (const sel of selectors.isJobPage) {
      const el = document.querySelector(sel);
      if (el) {
        // Also verify there's a description container
        const hasDesc = selectors.description.some(d => document.querySelector(d));
        if (hasDesc) {
          return { type: 'job', site, reason: `Individual job page: found "${sel}" + description` };
        }
        return { type: 'job', site, reason: `Individual job page: found "${sel}"` };
      }
    }

    // Check for listing page indicators
    const listingChecks = [
      { label: 'search result cards', check: document.querySelectorAll('.job_seen_beacon, .jobsearch-SerpJobCard, .base-card, .job-card-container, div[class*="jobTuple"], .job-tuple, .srp-jobtuple-wrapper, [class*="srp-"], div[class*="listings"]').length > 3 },
      { label: 'pagination', check: !!document.querySelector('[class*="pagination"], [aria-label*="pagination"]') },
      { label: 'search header', check: !!document.querySelector('[data-testid*="search"], [class*="search-header"], .jobsearch-ResultsList, [class*="search-result"], [class*="srp-"]') },
    ];

    // Naukri-specific listing detection (more relaxed)
    if (hostname.includes('naukri.com')) {
      const naukriListingSignals = [
        document.querySelectorAll('div[class*="jobTuple"], .job-tuple').length >= 2,
        document.querySelectorAll('a[href*="/job-listings"]').length >= 2,
        document.querySelectorAll('a[href*="/ai-jobs"], a[href*="-jobs"]').length >= 3,
        !!document.querySelector('[class*="search-result"], [class*="srp"]'),
      ].filter(Boolean).length;
      if (naukriListingSignals >= 2) {
        return { type: 'listing', site, reason: `Naukri listing page: ${naukriListingSignals}/4 signals` };
      }
    }

    const matches = listingChecks.filter(c => c.check);
    if (matches.length >= 2) {
      return { type: 'listing', site, reason: `Listing page: ${matches.map(m => m.label).join(', ')}` };
    }
  }

  // Generic listing detection (unknown sites)
  const genericListingSignals = [
    document.querySelectorAll('article').length > 5,
    document.querySelectorAll('li > a[href*="job"], li > a[href*="career"]').length > 5,
    document.querySelectorAll('[class*="pagination"]').length > 0,
    document.querySelectorAll('[class*="result"], [class*="listing"]').length > 5,
  ].filter(Boolean).length;

  if (genericListingSignals >= 2) {
    return { type: 'listing', site: null, reason: 'Generic listing patterns detected' };
  }

  return { type: 'unknown', site, reason: 'Could not determine page type' };
}

// ─── Validation ────────────────────────────────────────────────────────────

function validateItem(item, dedup, seenFingerprints, logger) {
  if (!item) {
    logger('  ✗ REJECTED: null item');
    return false;
  }

  const company = (item.company || '').trim();

  // Reject obvious placeholders from failed extraction
  if (!company || company.length < 2 || company.startsWith('[COMPANY_')) {
    logger(`  ✗ REJECTED: no valid company name "${item.company}"`);
    return false;
  }

  if (EXCLUDE_WORDS.has(company.toLowerCase())) {
    logger(`  ✗ REJECTED: "${company}" is an excluded word`);
    return false;
  }

  if (dedup) {
    const fp = ((item.description || '') + company + (item.role || ''))
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim()
      .substring(0, 120);
    if (seenFingerprints.has(fp)) {
      logger(`  • Duplicate skipped: "${company}"`);
      return false;
    }
    seenFingerprints.add(fp);
  }

  return true;
}

function looksLikeCompany(text) {
  if (!text || typeof text !== 'string') return false;
  const t = text.trim();
  if (t.length < 2) return false;
  const tl = t.toLowerCase();

  // Known company suffixes
  if (COMPANY_SUFFIXES.some(s => tl.includes(s))) return true;

  // 2+ capitalized words
  const caps = (t.match(/[A-Z][a-z]+/g) || []).length;
  if (caps >= 2) return true;

  // Single capitalized word
  if (caps === 1 && t.length >= 3 && t.length <= 40) {
    return !EXCLUDE_WORDS.has(tl);
  }

  // All-caps acronym (TCS, IBM, HCL, WIPRO, INFOSYS...)
  if (/^[A-Z]{2,6}$/.test(t)) return true;

  return false;
}

// ═════════════════════════════════════════════════════════════════════════════
// SITE-SPECIFIC: Individual Job Page
// ═════════════════════════════════════════════════════════════════════════════

function extractFromJobPage(site, logger) {
  const selectors = SITE_SELECTORS[site];
  const items = [];

  // ── Helper: extract text from first matching selector ─────────────
  function findText(selectorList) {
    if (!selectorList) return '';
    for (const sel of selectorList) {
      const el = document.querySelector(sel);
      if (el) {
        const text = el.textContent.trim();
        if (text && text.length > 0) return text;
      }
    }
    return '';
  }

  // ── Helper: extract array of items from multiple matching elements ──
  function findAllTexts(selectorList) {
    if (!selectorList) return [];
    const results = [];
    const seen = new Set();
    for (const sel of selectorList) {
      document.querySelectorAll(sel).forEach(el => {
        const text = el.textContent.trim();
        if (text && text.length > 0 && !seen.has(text)) {
          seen.add(text);
          results.push(text);
        }
      });
      if (results.length > 0) break;
    }
    return results;
  }

  // ── Extract Company Name ─────────────────────────────────────────────
  let company = findText(selectors.company);
  if (company) {
    logger(`  Company: "${company}"`);
  } else {
    logger(`  ✗ COMPANY NAME NOT FOUND`);
  }

  // ── Extract Job Role ─────────────────────────────────────────────────
  let role = findText(selectors.role);
  if (!role) {
    const h1 = document.querySelector('h1');
    if (h1) {
      role = h1.textContent.trim();
      logger(`  Role fallback <h1>: "${role.substring(0, 80)}..."`);
    }
  } else {
    logger(`  Role: "${role.substring(0, 80)}..."`);
  }

  // ── Extract Job Description (preserve structure) ───────────────────
  let description = '';
  for (const sel of (selectors.description || [])) {
    const el = document.querySelector(sel);
    if (el) {
      description = (el.innerText || el.textContent || '').trim();
      logger(`  Description selector "${sel}": ${description.length} chars`);
      if (description && description.length > 20) break;
    }
  }
  if (!description) {
    logger(`  ✗ JOB DESCRIPTION NOT FOUND`);
  }

  // ── Extract Job Highlights / Summary ───────────────────────────────
  let highlights = findText(selectors.highlights);
  if (highlights) logger(`  Highlights: ${highlights.substring(0, 100)}...`);

  // ── Extract Key Skills ─────────────────────────────────────────────
  const skills = findAllTexts(selectors.skills);
  if (skills.length > 0) logger(`  Skills: ${skills.join(', ').substring(0, 120)}...`);

  // ── Extract Location ───────────────────────────────────────────────
  let location = findText(selectors.location);
  if (location) logger(`  Location: "${location}"`);

  // ── Extract Experience ─────────────────────────────────────────────
  let experience = findText(selectors.experience);
  if (experience) logger(`  Experience: "${experience}"`);

  // ── Extract Education ──────────────────────────────────────────────
  let education = findText(selectors.education);
  if (education) logger(`  Education: "${education.substring(0, 80)}..."`);

  // ── Extract Job Details (role type, industry, dept, employment) ───
  let employmentType = '', department = '', industry = '';
  const detailsText = findText(selectors.jobDetails);
  if (detailsText) {
    // Parse structured detail text for known labels
    const lines = detailsText.split(/\n|•|▪/).map(l => l.trim()).filter(l => l);
    for (const line of lines) {
      const lower = line.toLowerCase();
      if (/employment\s*type|employment type/i.test(line)) {
        employmentType = line.replace(/employment\s*type\s*:?\s*/i, '').trim();
      } else if (/industry\s*type|industry/i.test(line) && !line.includes('employment')) {
        industry = line.replace(/industry\s*(type)?\s*:?\s*/i, '').trim();
      } else if (/department|dept/i.test(line)) {
        department = line.replace(/department\s*:?\s*/i, '').trim();
      }
    }
  }
  if (employmentType) logger(`  Employment: "${employmentType}"`);
  if (department) logger(`  Department: "${department}"`);
  if (industry) logger(`  Industry: "${industry}"`);

  // ── Extract Bullet Points from Description ─────────────────────────
  // Keep original line breaks for proper bullet formatting
  const bullets = description ? extractBullets(description) : [];
  logger(`  Description: ${bullets.length} bullet points`);

  // Only add if we got something useful
  if (company || role) {
    items.push({
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
      source: `${site}-job-page`,
    });
    logger(`  → Entry: ${company} | ${role} | ${bullets.length} bullets | ${skills.length} skills`);
  }

  return items;
}

// ═════════════════════════════════════════════════════════════════════════════
// STRATEGY 1: JSON-LD
// ═════════════════════════════════════════════════════════════════════════════

function extractJSONLD(logger) {
  const items = [];
  const scripts = document.querySelectorAll('script[type="application/ld+json"]');

  if (scripts.length === 0) {
    logger('  No JSON-LD scripts found');
    return items;
  }

  logger(`  Found ${scripts.length} JSON-LD script(s)`);

  for (const script of scripts) {
    try {
      let data = JSON.parse(script.textContent);
      if (!Array.isArray(data)) data = [data];

      for (const item of data) {
        const type = item['@type'] || '';

        // ONLY process JobPosting and Organization — skip everything else
        if (type.includes('JobPosting')) {
          const org = item.hiringOrganization || {};
          const company = typeof org === 'string' ? org : (org.name || '');
          const role = item.title || '';
          const desc = item.description || item.responsibilities || '';

          if (company && role) {
            logger(`  ✓ JobPosting: "${company}" — "${role}"`);
            items.push({
              company: company.trim(),
              role: role.trim(),
              description: (desc || '').trim(),
              descriptionBullets: desc ? extractBullets(desc) : [],
              source: 'jsonld-job',
            });
          } else {
            logger(`  JobPosting SKIPPED (missing company or role)`);
          }

        } else if (['Organization', 'Corporation', 'Company', 'LocalBusiness'].includes(type)) {
          const name = item.name || '';
          if (name) {
            logger(`  Organization: "${name}"`);
            items.push({
              company: name.trim(),
              role: 'Company Profile',
              description: item.description || '',
              descriptionBullets: item.description ? extractBullets(item.description) : [],
              source: 'jsonld-org',
            });
          }
        } else {
          // Explicitly skip ItemList, WebSite, BreadcrumbList, SearchAction, etc.
          logger(`  SKIPPED JSON-LD type: "${type}" (not a job posting or organization)`);
        }
      }
    } catch (e) {
      logger(`  JSON-LD parse error: ${e.message}`);
    }
  }

  return items;
}

// ═════════════════════════════════════════════════════════════════════════════
// STRATEGY 2: CSS Selectors
// ═════════════════════════════════════════════════════════════════════════════

function extractViaSelectors(cssSelectors, seen, logger) {
  const items = [];

  // User-provided custom selectors
  if (cssSelectors.company && cssSelectors.company.length > 0) {
    logger(`  Custom selectors: company="${cssSelectors.company}"`);
    const companyEls = document.querySelectorAll(cssSelectors.company);
    const roleEls = cssSelectors.role ? document.querySelectorAll(cssSelectors.role) : [];
    const descEls = cssSelectors.description ? document.querySelectorAll(cssSelectors.description) : [];

    logger(`  Found ${companyEls.length} company, ${roleEls.length} role, ${descEls.length} desc elements`);

    if (companyEls.length === 0) {
      logger('  ✗ Custom company selector matched nothing!');
      return items;
    }

    const count = Math.max(companyEls.length, roleEls.length);
    for (let i = 0; i < count; i++) {
      const company = companyEls[i] ? companyEls[i].textContent.trim() : '';
      const role = roleEls[i] ? roleEls[i].textContent.trim() : '';
      const desc = descEls[i] ? descEls[i].textContent.trim() : '';

      if (company && company.length > 1) {
        items.push({
          company,
          role: role || '[ROLE_NOT_FOUND]',
          description: desc || '',
          descriptionBullets: desc ? extractBullets(desc) : [],
          source: 'custom-css',
        });
      }
    }
    return items;
  }

  // Auto-detect selectors
  logger('  Auto-detecting company links via common patterns...');
  const commonSelectors = [
    'a[href*="/company/"]', 'a[href*="/companies/"]',
    '[class*="company-name"]', '[class*="companyName"]',
    '[class*="org-name"]', '[class*="orgName"]',
    '[data-company]', '[data-company-name]',
    '.employer', '.employer-name',
  ];

  for (const sel of commonSelectors) {
    const els = document.querySelectorAll(sel);
    if (els.length >= 2) {
      logger(`  Found ${els.length} elements matching "${sel}"`);
      for (const el of els) {
        const text = el.textContent.trim();
        if (text && looksLikeCompany(text)) {
          const parent = el.closest('li, div, article, tr') || el.parentElement;
          const nearbyTitle = findJobTitleNearby(parent, el);
          items.push({
            company: text,
            role: nearbyTitle || '[ROLE_NOT_FOUND]',
            description: '',
            descriptionBullets: [],
            source: 'auto-css',
          });
        }
      }
      if (items.length > 0) {
        logger(`  Auto-selectors: ${items.length} entries found`);
        break;
      }
    } else {
      logger(`  "${sel}": only ${els.length} match(es) — need ≥2`);
    }
  }
  return items;
}

function findJobTitleNearby(parent, excludeEl) {
  if (!parent) return '';
  const selectors = [
    'h2', 'h3', 'h4', 'a[class*="title"]', 'a[class*="job"]',
    '[class*="job-title"]', '[class*="jobTitle"]', '[class*="position"]',
    '[class*="role"]', '[class*="designation"]',
  ];
  for (const sel of selectors) {
    const el = parent.querySelector(sel);
    if (el && el !== excludeEl) {
      const text = el.textContent.trim();
      if (text && text.length > 1 && text.length < 200 && !looksLikeCompany(text)) {
        return text;
      }
    }
  }
  const links = parent.querySelectorAll('a');
  for (const link of links) {
    if (link !== excludeEl) {
      const text = link.textContent.trim();
      if (text && text.length > 2 && text.length < 150 && !looksLikeCompany(text)) {
        return text;
      }
    }
  }
  return '';
}

// ═════════════════════════════════════════════════════════════════════════════
// STRATEGY 3: Tables
// ═════════════════════════════════════════════════════════════════════════════

function extractFromTables(seen, logger) {
  const items = [];
  const tables = document.querySelectorAll('table');
  if (tables.length === 0) {
    logger('  No tables found');
    return items;
  }

  logger(`  Found ${tables.length} table(s)`);

  for (const table of tables) {
    const rows = table.querySelectorAll('tr');
    if (rows.length < 2) {
      logger('  Table with <2 rows, skipping');
      continue;
    }

    const headerCells = rows[0].querySelectorAll('th, td');
    const headers = Array.from(headerCells).map(th => th.textContent.trim().toLowerCase());

    let companyIdx = -1, roleIdx = -1, descIdx = -1;
    headers.forEach((h, i) => {
      if (/company|organization|firm|employer|name/.test(h)) companyIdx = i;
      if (/job|title|position|role|designation/.test(h)) roleIdx = i;
      if (/description|details|info|about/.test(h)) descIdx = i;
    });

    if (companyIdx === -1 && rows.length > 1) {
      const cells = rows[1].querySelectorAll('td');
      cells.forEach((cell, i) => {
        if (looksLikeCompany(cell.textContent.trim())) companyIdx = i;
      });
    }

    logger(`  Table columns — company:${companyIdx} role:${roleIdx} desc:${descIdx}`);

    for (let r = 1; r < rows.length; r++) {
      const cells = rows[r].querySelectorAll('td');
      if (cells.length === 0) continue;

      let company = '', role = '', desc = '';
      if (companyIdx >= 0 && companyIdx < cells.length) {
        company = cells[companyIdx].textContent.trim();
      } else if (cells.length > 0) {
        const first = cells[0].textContent.trim();
        if (looksLikeCompany(first)) company = first;
      }
      if (roleIdx >= 0 && roleIdx < cells.length) role = cells[roleIdx].textContent.trim();
      if (descIdx >= 0 && descIdx < cells.length) desc = cells[descIdx].textContent.trim();

      if (company) {
        items.push({
          company,
          role: role || '[ROLE_NOT_FOUND]',
          description: desc || '',
          descriptionBullets: desc ? extractBullets(desc) : [],
          source: 'table',
        });
      }
    }
  }
  return items;
}

// ═════════════════════════════════════════════════════════════════════════════
// STRATEGY 4: Cards / Listings
// ═════════════════════════════════════════════════════════════════════════════

function extractFromCards(cssSelectors, seen, logger) {
  const items = [];

  const cardSelectors = [
    'article',
    'div[class*="card"]',
    'div[class*="list-item"]',
    'div[class*="result"]',
    'li[class*="list"]',
    'div[class*="company"]',
    'div[class*="job"]',
    'div[class*="listing"]',
    'section[class*="card"]',
    'div[data-company]',
    'li[class*="job"]',
  ];

  let cards = [];
  for (const sel of cardSelectors) {
    const found = document.querySelectorAll(sel);
    if (found.length > 1 && found.length < 200) {
      cards = found;
      logger(`  Using "${sel}" — ${cards.length} card(s) found`);
      break;
    }
  }

  if (cards.length === 0) {
    logger('  No card containers found');
    return items;
  }

  for (const card of cards) {
    try {
      let company = '', role = '', desc = '';

      // Custom selectors within each card
      if (cssSelectors.company) {
        const el = card.querySelector(cssSelectors.company);
        if (el) company = el.textContent.trim();
      }
      if (cssSelectors.role) {
        const el = card.querySelector(cssSelectors.role);
        if (el) role = el.textContent.trim();
      }
      if (cssSelectors.description) {
        const el = card.querySelector(cssSelectors.description);
        if (el) desc = el.textContent.trim();
      }

      if (company && role) {
        items.push({
          company,
          role,
          description: desc || '',
          descriptionBullets: desc ? extractBullets(desc) : [],
          source: 'card',
        });
        continue;
      }

      // Auto-detect within card
      const allLinks = card.querySelectorAll('a, strong, h2, h3, h4');
      const texts = Array.from(allLinks)
        .map(el => el.textContent.trim())
        .filter(t => t.length > 1);

      for (const t of texts) {
        if (!company && looksLikeCompany(t)) {
          company = t;
        } else if (!role && !looksLikeCompany(t) && t.length < 200) {
          role = t;
        }
      }

      if (!company) {
        const firstLink = card.querySelector('a');
        if (firstLink) {
          const t = firstLink.textContent.trim();
          if (t.length > 1 && !EXCLUDE_WORDS.has(t.toLowerCase())) company = t;
        }
      }

      const descEl = card.querySelector('p, div[class*="desc"], div[class*="summary"]');
      if (descEl) desc = descEl.textContent.trim();

      if (company && company.length > 1 && !EXCLUDE_WORDS.has(company.toLowerCase())) {
        items.push({
          company,
          role: role || '[ROLE_NOT_FOUND]',
          description: desc || '',
          descriptionBullets: desc ? extractBullets(desc) : [],
          source: 'card',
        });
      }
    } catch (e) {
      logger(`  Card error: ${e.message}`);
    }
  }
  return items;
}

// ═════════════════════════════════════════════════════════════════════════════
// STRATEGY 5: Text Patterns
// ═════════════════════════════════════════════════════════════════════════════

function extractFromTextPatterns(seen, logger) {
  const items = [];
  const bodyText = document.body.innerText.substring(0, 50000);

  const pattern = new RegExp(
    `([A-Z][A-Za-z0-9\\s&.-]{1,40}?)(${COMPANY_SUFFIXES.join('|')})`,
    'gi'
  );

  let match;
  const foundCompanies = new Set();
  let count = 0;

  while ((match = pattern.exec(bodyText)) !== null) {
    const company = match[0].trim();
    if (company.length > 2 && !EXCLUDE_WORDS.has(company.toLowerCase())) {
      const contextStart = Math.max(0, match.index - 100);
      const contextEnd = Math.min(bodyText.length, match.index + 200);
      const context = bodyText.substring(contextStart, contextEnd);

      const titleMatch = context.match(
        /(?:hiring|looking for|seeking|position|role|job)[:\s]+([A-Z][A-Za-z\s/]+?)(?:\n|\.|,)/i
      );
      const role = titleMatch ? titleMatch[1].trim() : '[ROLE_NOT_FOUND]';

      if (!foundCompanies.has(company)) {
        foundCompanies.add(company);
        count++;
        items.push({
          company,
          role,
          description: '',
          descriptionBullets: [],
          source: 'text-pattern',
        });
      }
    }
  }

  logger(`  Found ${count} unique company name(s) via text patterns`);
  return items;
}

// ═════════════════════════════════════════════════════════════════════════════
// BULK MODE: Extract Job Links from Listing Page
// ═════════════════════════════════════════════════════════════════════════════

function extractJobLinks() {
  const links = [];
  const hostname = window.location.hostname;
  const seenUrls = new Set();

  function addLink(url, company, role) {
    if (!url || seenUrls.has(url)) return;
    seenUrls.add(url);
    // Ensure absolute URL
    if (url.startsWith('/')) {
      url = window.location.origin + url;
    }
    links.push({ url: url, company: company || '', role: role || '' });
  }

  // ══════════════════════════════════════════════════════════════════════
  // METHOD A: Site-specific selectors
  // ══════════════════════════════════════════════════════════════════════

  if (hostname.includes('indeed.com')) {
    // Indeed: each job card has a link with data-jk or href containing jk=
    document.querySelectorAll('.job_seen_beacon, .jobsearch-SerpJobCard, [data-testid="job-card"]').forEach(card => {
      const linkEl = card.querySelector('a[data-jk], a[id^="job_"]');
      const href = card.querySelector('a[href*="jk="]');
      const url = linkEl ? linkEl.href : (href ? href.href : '');
      const company = (card.querySelector('[data-testid="company-name"], .companyName, .css-1ioi40n, .css-1rrizms') || {}).textContent || '';
      const role = (card.querySelector('a[data-jk] span, .jobTitle, [id^="job_"] span, h2 span') || {}).textContent || '';
      if (url) addLink(url, company.trim(), role.trim());
    });
  } else if (hostname.includes('linkedin.com')) {
    // LinkedIn: base cards
    document.querySelectorAll('.base-card, .job-card-container, .job-search-card').forEach(card => {
      const linkEl = card.querySelector('.base-card__full-link, .job-card-container__link, a[href*="/jobs/view/"]');
      const url = linkEl ? linkEl.href : '';
      const company = (card.querySelector('.base-card__subtitle, .job-card-container__company-name, .artdeco-entity-lockup__caption, [class*="company"]') || {}).textContent || '';
      const role = (card.querySelector('.base-card__title, .job-card-container__link, .job-search-card__title, [class*="title"]') || {}).textContent || '';
      if (url) addLink(url, company.trim(), role.trim());
    });
  } else if (hostname.includes('naukri.com')) {
    // Naukri: try multiple card container selectors
    const naukriCardSelectors = [
      'div[class*="jobTuple"]', '.job-tuple', 'section[class*="job"]',
      'div[class*="srp-job"]', '.job-card-container', '.job-list-card',
      'article[data-*]', 'li[class*="job"]', 'article'
    ];
    let naukriCards = [];
    for (const sel of naukriCardSelectors) {
      const found = document.querySelectorAll(sel);
      if (found.length >= 2 && found.length < 300) {
        naukriCards = found;
        break;
      }
    }

    if (naukriCards.length > 0) {
      naukriCards.forEach(card => {
        // Try all possible job link patterns
        const linkEl = card.querySelector(
          'a[href*="/job-listings"], a[href*="job-details"], a[href*="-job-"], ' +
          'a[href*="jobs"], a[class*="title"], a.title, ' +
          'a[href*="/ai-jobs"], a[href*="/software"], a[href*="/engineer"]'
        );
        const url = linkEl ? linkEl.href : '';
        // Try all possible company name patterns
        const companyEl = card.querySelector(
          '.company-name, .comp-name, .comp-dtls, .subTitle, ' +
          '[class*="company"], [class*="org"], [class*="employer"]'
        );
        const company = companyEl ? companyEl.textContent.trim() : '';
        // Try all possible role/title patterns
        const roleEl = linkEl || card.querySelector(
          '.title, a.title, [class*="title"] a, h2, h3, ' +
          'a[class*="title"], [class*="job-title"]'
        );
        const role = roleEl ? roleEl.textContent.trim() : '';
        if (url) addLink(url, company.trim(), role.trim());
      });
    }
  } else {
    // Generic: look for job-like links inside card-like containers
    const cardSelectors = ['article', 'li[class*="job"]', 'div[class*="job-card"]', 'div[class*="result"]', 'div[class*="listing"]', 'div[class*="card"]', 'div[class*="tuple"]', 'section[class*="result"]'];
    for (const sel of cardSelectors) {
      const cards = document.querySelectorAll(sel);
      for (const card of cards) {
        const a = card.querySelector('a[href]');
        if (a && (/job|career|position|vacancy/i.test(a.href) || /job|career|position|vacancy/i.test(a.textContent))) {
          const company = (card.querySelector('[class*="company"], [class*="org"], [class*="employer"]') || {}).textContent || '';
          const role = a.textContent || '';
          addLink(a.href, company.trim(), role.trim());
        }
      }
      if (links.length > 0) break;
    }
  }

  // ══════════════════════════════════════════════════════════════════════
  // METHOD B: Global link scan — find ALL job-like links on the page
  // ══════════════════════════════════════════════════════════════════════
  if (links.length === 0) {
    // Scan every single <a> tag on the page for job-like URL patterns
    const allLinks = document.querySelectorAll('a[href]');
    const jobUrlPatterns = [/\/job/i, /\/career/i, /\/vacancy/i, /\-job\-/, /\/position/, /\/listing/i, /\/opening/i];
    const seenHrefs = new Set();

    for (const a of allLinks) {
      const href = a.href;
      if (!href || seenHrefs.has(href)) continue;
      seenHrefs.add(href);

      // Check if URL looks like a job listing
      const isJobLink = jobUrlPatterns.some(p => p.test(href));
      if (isJobLink) {
        const text = a.textContent.trim();
        if (text && text.length > 2 && text.length < 200) {
          // Try to find company name from parent elements
          let company = '';
          let parent = a.parentElement;
          for (let i = 0; i < 5 && parent; i++) {
            // Look for company-like text in siblings and nearby elements
            const nearby = parent.querySelectorAll('[class*="company"], [class*="org"], [class*="employer"], [class*="comp"]');
            for (const el of nearby) {
              const t = el.textContent.trim();
              if (t && t.length > 1 && t.length < 100 && !text.includes(t)) {
                company = t;
                break;
              }
            }
            if (company) break;
            parent = parent.parentElement;
          }
          addLink(href, company.trim(), text);
        }
      }
    }
  }

  // ══════════════════════════════════════════════════════════════════════
  // METHOD C: Try looking for Naukri-specific structured data fallback
  // ══════════════════════════════════════════════════════════════════════
  if (links.length === 0 && hostname.includes('naukri.com')) {
    // On Naukri, job cards may use data attributes
    document.querySelectorAll('[data-job-id], [data-company-id], [id*="job_"]').forEach(el => {
      // Find the nearest job link
      const link = el.querySelector('a[href]') || el.closest('a[href]');
      if (link && link.href && !seenUrls.has(link.href) && /job|career/i.test(link.href)) {
        const company = (el.querySelector('[class*="company"], [class*="comp"], [class*="org"]') || {}).textContent || '';
        const role = link.textContent.trim();
        addLink(link.href, company.trim(), role);
      }
    });
  }

  // ══════════════════════════════════════════════════════════════════════
  // METHOD D: Last resort — JSON-LD (already processed in scrapePage,
  // but page might have ItemList with job URLs we can use)
  // ══════════════════════════════════════════════════════════════════════
  if (links.length === 0) {
    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (const script of scripts) {
      try {
        let data = JSON.parse(script.textContent);
        if (!Array.isArray(data)) data = [data];
        for (const item of data) {
          if (item['@type'] === 'ItemList' && item.itemListElement) {
            for (const element of item.itemListElement) {
              const url = element.url || (element.item && element.item.url);
              if (url) {
                const name = element.name || (element.item && element.item.name) || '';
                addLink(url, '', name);
              }
            }
          }
        }
      } catch(e) {}
      if (links.length > 0) break;
    }
  }

  return links;
}

// ═════════════════════════════════════════════════════════════════════════════
// Bullet Point Extraction
// ═════════════════════════════════════════════════════════════════════════════

function extractBullets(text) {
  if (!text || text.length < 20) return [];

  // Strip HTML tags first
  const cleaned = text.replace(/<[^>]*>/g, '\n');
  // Split on bullet chars, newlines, or numbered lists
  const lines = cleaned.split(/[•·●◆◇▪▸▹►▻‣⁃⦿✦✧\-]\s*|[\n\r]+|(?:\d+[.)])\s*/);
  return lines
    .map(l => l.replace(/\s+/g, ' ').trim())
    .filter(l => l.length > 10)
    .slice(0, 50);
}
