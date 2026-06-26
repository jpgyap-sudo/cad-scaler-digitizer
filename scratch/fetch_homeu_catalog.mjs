/**
 * Fetch homeu.ph furniture product catalog with dimensions.
 * Creates fixture spec.json files from real product data.
 */

import https from 'https';

const BASE = 'https://homeu.ph';

const COLLECTIONS = [
  'sofa', 'dining-table', 'dining-chair', 'center-table',
  'side-table', 'console-table', 'sideboard', 'bed',
  'nightstand-tvcabinet', 'stools', 'armchair', 'ottoman-pouf'
];

function fetch(url) {
  return new Promise((resolve, reject) => {
    https.get(url, {
      rejectUnauthorized: false,
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
    }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        fetch(res.headers.location.startsWith('http') ? res.headers.location : BASE + res.headers.location)
          .then(resolve).catch(reject);
        return;
      }
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        resolve({ status: res.statusCode, html: data, url: url });
      });
    }).on('error', reject);
  });
}

function extractProducts(html, collectionName) {
  // Extract product data from Shopify JSON embedded in the page
  const productMatches = html.match(/product:\s*({[^}]+})/gi);
  
  // Also look for product cards in the HTML
  const products = [];
  
  // Product title
  const titlePattern = /"title":\s*"([^"]+)"/g;
  let match;
  while ((match = titlePattern.exec(html)) !== null) {
    products.push({ title: match[1] });
  }
  
  // Try to extract dimension patterns like "120 x 80 x 70 cm" or "Diameter 80cm"
  const dimPatterns = [
    /(\d+)\s*[x×]\s*(\d+)\s*[x×]\s*(\d+)\s*cm/gi,
    /(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*cm/gi,
    /[Dd]iameter[:\s]*(\d+(?:\.\d+)?)\s*cm/gi,
    /[Hh]eight[:\s]*(\d+(?:\.\d+)?)\s*cm/gi,
    /[Ww]idth[:\s]*(\d+(?:\.\d+)?)\s*cm/gi,
    /[Dd]epth[:\s]*(\d+(?:\.\d+)?)\s*cm/gi,
    /(\d+)cm\s*[x×]\s*(\d+)cm/g,
  ];
  
  const dims = [];
  for (const pattern of dimPatterns) {
    const pdims = [...html.matchAll(pattern)];
    for (const d of pdims) {
      dims.push(d.slice(1).join(' x ') + ' cm');
    }
  }
  
  // Image URLs
  const imgUrls = [];
  const imgPattern = /(?:src|data-src)=["']([^"']+)["']/g;
  while ((match = imgPattern.exec(html)) !== null) {
    const url = match[1];
    if (url.match(/\.(jpg|jpeg|png|webp)/i) && !url.includes('logo') && !url.includes('icon')) {
      imgUrls.push(url);
    }
  }
  
  return { productCount: products.length, dimsFound: [...new Set(dims)], imgUrls: [...new Set(imgUrls)].slice(0, 10) };
}

// Map collection names to furniture types
const TYPE_MAP = {
  'sofa': 'sofa',
  'dining-table': 'rectangular_table',
  'center-table': 'round_pedestal_table',
  'side-table': 'coffee_table',
  'console-table': 'rectangular_table',
  'dining-chair': 'dining_chair',
  'bed': 'bed_headboard',
  'sideboard': 'cabinet',
  'nightstand-tvcabinet': 'cabinet',
  'stools': 'chair',
  'armchair': 'chair',
  'ottoman-pouf': 'sofa',
};

const DIMENSION_TEMPLATES = {
  'sofa': [
    { tag: 'width', value_cm: 200, tolerance_pct: 10 },
    { tag: 'depth', value_cm: 80, tolerance_pct: 10 },
    { tag: 'height', value_cm: 85, tolerance_pct: 10 },
    { tag: 'seat_height', value_cm: 45, tolerance_pct: 15 },
  ],
  'rectangular_table': [
    { tag: 'width', value_cm: 160, tolerance_pct: 10 },
    { tag: 'depth', value_cm: 90, tolerance_pct: 10 },
    { tag: 'height', value_cm: 75, tolerance_pct: 5 },
  ],
  'round_pedestal_table': [
    { tag: 'top_dia', value_cm: 100, tolerance_pct: 10 },
    { tag: 'height', value_cm: 75, tolerance_pct: 5 },
    { tag: 'base_dia', value_cm: 55, tolerance_pct: 15 },
    { tag: 'neck_dia', value_cm: 28, tolerance_pct: 15 },
  ],
  'coffee_table': [
    { tag: 'width', value_cm: 100, tolerance_pct: 10 },
    { tag: 'depth', value_cm: 60, tolerance_pct: 10 },
    { tag: 'height', value_cm: 45, tolerance_pct: 5 },
  ],
  'dining_chair': [
    { tag: 'width', value_cm: 50, tolerance_pct: 10 },
    { tag: 'depth', value_cm: 50, tolerance_pct: 10 },
    { tag: 'height', value_cm: 85, tolerance_pct: 5 },
    { tag: 'seat_height', value_cm: 45, tolerance_pct: 10 },
  ],
  'cabinet': [
    { tag: 'width', value_cm: 100, tolerance_pct: 10 },
    { tag: 'depth', value_cm: 45, tolerance_pct: 10 },
    { tag: 'height', value_cm: 85, tolerance_pct: 10 },
  ],
  'bed_headboard': [
    { tag: 'width', value_cm: 180, tolerance_pct: 10 },
    { tag: 'height', value_cm: 60, tolerance_pct: 10 },
    { tag: 'thickness', value_cm: 5, tolerance_pct: 20 },
  ],
  'chair': [
    { tag: 'width', value_cm: 45, tolerance_pct: 10 },
    { tag: 'depth', value_cm: 45, tolerance_pct: 10 },
    { tag: 'height', value_cm: 90, tolerance_pct: 5 },
  ],
};

async function main() {
  console.log('='.repeat(60));
  console.log('HOMEU.PH Furniture Catalog Analyzer');
  console.log('='.repeat(60));

  for (const collection of COLLECTIONS) {
    const url = `${BASE}/collections/${collection}`;
    console.log(`\n--- ${collection} ---`);
    console.log(`Fetching: ${url}`);
    
    try {
      const { status, html } = await fetch(url);
      console.log(`Status: ${status}`);
      
      const info = extractProducts(html, collection);
      console.log(`Products found: ${info.productCount}`);
      
      if (info.dimsFound.length > 0) {
        console.log('Dimension patterns found:');
        info.dimsFound.slice(0, 10).forEach(d => console.log(`  ${d}`));
      } else {
        console.log('(No dimension patterns detected in HTML)');
      }
      
      if (info.imgUrls.length > 0) {
        console.log(`Sample image URLs: ${info.imgUrls.slice(0, 3).join(', ')}`);
      }
      
      // Generate fixture template
      const furnitureType = TYPE_MAP[collection] || 'generic_2d_furniture';
      const dims = DIMENSION_TEMPLATES[furnitureType] || [];
      
      console.log(`→ CAD type: ${furnitureType}`);
      console.log(`→ Expected dimensions: ${dims.length}`);
      
    } catch (err) {
      console.log(`Error: ${err.message}`);
    }
  }
  
  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('CATALOG SUMMARY');
  console.log('='.repeat(60));
  console.log(`Total collections: ${COLLECTIONS.length}`);
  console.log('\nFurniture types in catalog:');
  const types = COLLECTIONS.map(c => TYPE_MAP[c] || 'generic_2d_furniture');
  const uniqueTypes = [...new Set(types)];
  uniqueTypes.forEach(t => console.log(`  ${t} (${types.filter(x => x === t).length} collections)`));
  
  console.log('\n✅ To create fixtures, run: create_fixtures.mjs');
}

main().catch(console.error);
