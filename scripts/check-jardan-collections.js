/** Check Jardan collection URLs for dining table products. */
async function check(url, label){
  try {
    const r = await fetch(url, {signal: AbortSignal.timeout(10000)});
    const text = await r.text();
    console.log(label + ": HTTP " + r.status + " (" + text.length + " bytes)");
    if(r.ok){
      const products = [...new Set(text.match(/\/products\/([a-z0-9-]+?)(?:["'\/])/g))];
      console.log("  Products found: " + products.length);
      products.slice(0,5).forEach(p => console.log("  " + p));
    }
  } catch(e) { console.log(label + ": " + e.message); }
}

Promise.all([
  check("https://www.jardan.com.au/collections/dining-tables", "/collections/dining-tables"),
  check("https://www.jardan.com.au/collections/tables", "/collections/tables"),
  check("https://www.jardan.com.au/collections/furniture", "/collections/furniture"),
  check("https://www.jardan.com.au/collections/all", "/collections/all"),
  check("https://www.jardan.com.au/collections", "/collections"),
]).then(() => process.exit(0));
