import https from 'https';

function fetch(url, redirects = 0) {
  if (redirects > 5) { console.log('Too many redirects'); return; }
  
  https.get(url, {
    rejectUnauthorized: false,
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
  }, (res) => {
    // Follow redirect
    if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
      console.log(`Redirect ${res.statusCode} → ${res.headers.location}`);
      fetch(res.headers.location, redirects + 1);
      return;
    }
    
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
      console.log('Status:', res.statusCode);
      const titleMatch = data.match(/<title>([^<]+)<\/title>/i);
      console.log('Title:', titleMatch ? titleMatch[1] : 'N/A');
      
      // Extract ALL image URLs
      const imgPattern = /src=["']([^"']+\.(?:jpg|jpeg|png|webp|avif))["']/gi;
      let match;
      const imgs = [];
      while ((match = imgPattern.exec(data)) !== null) {
        imgs.push(match[1]);
      }
      console.log('Total images:', imgs.length);
      
      // Product patterns
      const productPattern = /"product"/gi;
      const prods = data.match(productPattern);
      console.log('"product" mentions:', prods ? prods.length : 0);
      
      // Extract product links
      const linkPattern = /href=["']([^"']+)["']/gi;
      const links = [];
      while ((match = linkPattern.exec(data)) !== null) {
        const href = match[1];
        if (href.includes('collections') || href.includes('products') || href.includes('catalog')) {
          links.push(href);
        }
      }
      console.log('\nProduct/Collection links:');
      [...new Set(links)].slice(0, 30).forEach(l => console.log(`  ${l}`));
      
      // Show page structure
      const sections = data.match(/<h[1-6][^>]*>[^<]+<\/h[1-6]>/gi);
      if (sections) {
        console.log('\nPage headings:');
        sections.slice(0, 20).forEach(s => console.log(`  ${s.replace(/<[^>]+>/g, '')}`));
      }
    });
  }).on('error', e => console.log('Error:', e.message));
}

fetch('https://homeu.ph/');
