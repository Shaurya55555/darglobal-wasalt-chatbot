/**
 * Scraper used to build the files in /data.
 *
 * Both sites sit behind bot protection (Cloudflare on wasalt.sa, Imperva on darglobal.co.uk),
 * so plain HTTP clients get 403 or an empty page. The pages render server-side though, so the
 * scraper runs INSIDE a real browser session on the target origin: open the site normally,
 * then paste this into the DevTools console (or drive it with browser automation).
 *
 * It only reads public pages, one request at a time, and returns clean text per page.
 * Usage:   await scrape(['/en/about', '/en/faq'])   ->  { path: { title, text } }
 * Then turn the text into the section files under /data (markdown, "## heading" per chunk).
 */
async function scrape(paths) {
  const out = {};
  for (const p of paths) {
    try {
      const html = await fetch(p).then((r) => r.text());
      const doc = new DOMParser().parseFromString(html, "text/html");
      doc.querySelectorAll("script,style,noscript,svg,nav,header,footer").forEach((e) => e.remove());
      const text = (doc.body.innerText || doc.body.textContent).replace(/\s+/g, " ").trim();
      out[p] = { title: doc.title, text };
    } catch (e) {
      out[p] = { error: String(e) };
    }
    await new Promise((r) => setTimeout(r, 400)); // be polite
  }
  return out;
}

/** Wasalt listing pages: split the page text into listing cards and keep price, type, size, district. */
function parseWasaltListings(text, max = 8) {
  const i = text.indexOf(" results");
  return text
    .slice(i + 8)
    .split(/WhatsAppCall|View Details/)
    .map((s) => s.replace(/Featured Plus|Featured|New|Upcoming/g, "").trim())
    .filter((s) => s.length > 8 && !/^Auction/.test(s))
    .slice(0, max);
}

// Pages scraped: wasalt.sa  /en/{villas|apartments|properties|lands}-for-{sale|rent}-in-<city>, /en/corporate
//                darglobal.co.uk /en/{about,projects,why-invest,faq,hospitality,tokenization,one-of-one,
//                                     investor,press,press/<slug>,landing-page/aida,partners/<brand>}
