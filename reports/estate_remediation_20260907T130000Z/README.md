# Nine-site estate remediation — 2026-09-07

Companion to `reports/measurement_retirement_20260907T110425Z/`. Tags: **OBSERVED**,
**CHANGED**, **VERIFIED**, **UNRESOLVED**.

## Estate topology — OBSERVED (and it mattered)

Eight of the nine sites are on Hostinger (`193.203.185.149`). **`ambimat.com` is not** —
it resolves to `166.62.28.103` (GoDaddy, `sg2plzcpnl506044.prod.sin2.secureserver.net`,
docroot `/home/xemtd1m9scay/public_html`). The Hostinger box also carries a
`~/domains/ambimat.com/public_html` WordPress install; it is **stale and not production**.
Diagnosis started there and its `products` post type, rewrite rules and `url_to_postid()`
all disagreed with the live site — which is how the split was caught, before anything was
written to the wrong install.

`ambimechanicals.ambimat.com` also exists on the Hostinger box. Retired, out of scope, untouched.

## Defects fixed

| # | Site | Defect | Root cause | Status |
| --- | --- | --- | --- | --- |
| 1 | orders | all sitemap routes 404 while serving valid XML | shop page is the front page → `WC_Query` clears `is_home` → `WP::handle_404()` 404s the sitemap query before the renderer runs | **CHANGED, VERIFIED** |
| 2 | orders | cart/checkout/my-account/share-cart listed in the sitemap while `noindex` + robots-disallowed | WP core lists every published page | **CHANGED, VERIFIED** |
| 3 | orders | `/brand/…` had no canonical while its sibling `/product-category/…` did | WooCommerce canonicalises `product_cat`, not the newer `product_brand` | **CHANGED, VERIFIED** |
| 4 | ambimat | every product page's breadcrumb linked to `/products/` → 404 | 2026-08-30 permalink migration added a rewrite slug; the crumb builds its href from the slug, but `has_archive` is still false | **CHANGED, VERIFIED** |
| 5 | ai | dev-only comment containing a literal `<title>` shipped above the real title | build note never stripped from prerendered output | **CHANGED, VERIFIED** |
| 6 | monitor | 15 working AddToAny links reported broken | `_status_only()` fell back to GET on 405/5xx only; addtoany answers HEAD 403 / GET 302 | **CHANGED, VERIFIED** |
| 7 | monitor | third-party bot-blocks reported as broken links | external 401/403/429 treated as failures | **CHANGED, VERIFIED** |

Details and rollback: `ambimat-site/reports/orders_sitemap_404_20260907T120417Z/` and
`ambimat-site/reports/ambimat_products_crumb_404_20260907T114739Z/`.

## Estate audit — OBSERVED

709 sitemap URLs across all nine sites fetched and parsed. Checked per URL: HTTP status,
redirect chain, title presence/contamination, canonical presence, canonical host,
canonical/URL agreement, meta robots, H1 count, and sitemap/robots consistency.

Result after the fixes: **every one of the 709 returns 200**, none redirects, none is
`noindex`-while-in-a-sitemap, none has a wrong-host or missing canonical, none has a
contaminated or empty title, and every page has exactly one H1. JSON-LD parses on every
site that emits it.

## Classification of external-link failures — OBSERVED

Re-checked from the Mac with a full browser UA:

| URL | crawler | browser | verdict |
| --- | --- | --- | --- |
| `cisa.gov` | 403 | **200** | monitor false positive (UA block) |
| `gsma.com`, `centralbank.ae`, `alliedmarketresearch.com`, `slack.com/signup`, `jhu.edu`, `wvu.edu`, `iso.org`, `entrust.com`, `cloudflare.com` | 403 | 403 | expected external blocking — refuses non-browser clients |
| `nxp.com/kr/products/…/single-dual` | 404 | **404** | **TRUE dead outbound link** |
| addtoany.com share links (×15) | HEAD 403 | GET 302 | monitor false positive — now correct |

## Final nine-site run — VERIFIED

`report_latest.json` generated **2026-09-07T18:32:43+05:30**:

```
sites_total 9  sites_reported 9  sites_unreachable 0
pages_crawled 902  broken_pages 0  broken_links 0  partial false
```

SEO tracker, generated **2026-09-07 18:04:12 +0530**, 9 domains — **Orders 15 pages
(was 0 for the entire life of the job)**.

## UNRESOLVED — owner decisions only

1. **`ambimat.com` has no `/products/` landing page.** The breadcrumb no longer lies about
   it. Whether to create one (Products index using the existing `Template Products`) is a
   content decision — what it says, which categories, indexable or not.
2. **One dead outbound link.** `https://www.nxp.com/kr/products/identification-and-security/security-controller-ics/single-dual`
   returns a real 404 to browsers, linked from
   `https://ambimat.com/products/nxps-development-kits-with-secure-element-pdm-1-0-plugin-sim-package-from-nxp/`.
   Choosing the correct replacement NXP page is a content decision.
