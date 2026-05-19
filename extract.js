const fs = require('fs');

const content = fs.readFileSync('WKUCampusGuide/server/storage.ts', 'utf8');

const restaurants = [];
const menus = [];

// Extract restaurants manually
// Look for lines like: id: 'r1', name: '학생식당', nameEn: 'Student Cafeteria', category: 'restaurant', location: '...', locationEn: '...', hours: '...', mapLat: '...', mapLng: '...', imageUrl: cafeteriaInterior, status: 'open', crowdingLevel: 3,

let rMatch;
const rRegex = /id:\s*'([^']+)',\s*name:\s*'([^']+)',\s*nameEn:\s*'([^']+)',\s*category:\s*'([^']+)',\s*location:\s*'([^']+)',\s*locationEn:\s*'([^']+)',\s*hours:\s*'([^']+)',\s*mapLat:\s*'([^']+)',\s*mapLng:\s*'([^']+)',\s*imageUrl:\s*([^,]+),/g;

while ((rMatch = rRegex.exec(content)) !== null) {
  restaurants.push({
    id: rMatch[1],
    name_ko: rMatch[2],
    name_en: rMatch[3],
    category: rMatch[4],
    location: rMatch[5],
    hours: rMatch[7],
    coverImage: rMatch[10].trim(),
  });
}

// Extract menus manually
// Look for: { restaurantId: 'r1', name: '돼지고기김치찌개', nameEn: 'Pork Kimchi Stew', price: 6000, imageUrl: porkKimchiStewImage, hasPork: true, isSpicy: true, isVegetarian: false, dayOfWeek: null }

let mMatch;
const mRegex = /restaurantId:\s*'([^']+)',\s*name:\s*'([^']+)',\s*nameEn:\s*'([^']+)',\s*price:\s*(\d+),\s*imageUrl:\s*([^,]+),/g;

while ((mMatch = mRegex.exec(content)) !== null) {
  menus.push({
    restaurantId: mMatch[1],
    name_ko: mMatch[2],
    name_en: mMatch[3],
    price: mMatch[4],
    image: mMatch[5].trim().replace(/['"]/g, ''),
  });
}

// Convert image variables to paths
const imgVars = {};
const imgRegex = /const\s+([a-zA-Z0-9_]+)\s*=\s*'([^']+)';/g;
let imgMatch;
while ((imgMatch = imgRegex.exec(content)) !== null) {
  imgVars[imgMatch[1]] = imgMatch[2];
}

// Assemble final data structure
const finalData = [];
let nextId = 1;

for (const r of restaurants) {
  let cat = r.category === 'cafe' ? 'Cafe' : 'Restaurant';
  
  const rMenus = menus.filter(m => m.restaurantId === r.id).map(m => {
    let img = m.image;
    if (imgVars[img]) img = imgVars[img];
    
    // Convert /attached_assets to ./WKUCampusGuide/attached_assets
    if (img && img.startsWith('/attached_assets')) {
      img = './WKUCampusGuide' + img;
    }

    return {
      name: m.name_ko,
      desc: { ko: "", en: m.name_en },
      price: m.price + "원",
      image: img || ""
    };
  });

  let cover = r.coverImage;
  if (imgVars[cover]) cover = imgVars[cover];
  if (cover && cover.startsWith('/attached_assets')) {
    cover = './WKUCampusGuide' + cover;
  }

  // Adjust locationType
  // All these are in-campus
  let locType = "in-campus";

  finalData.push({
    id: nextId++,
    name_ko: r.name_ko,
    name_en: r.name_en,
    category: cat,
    reviewCount: Math.floor(Math.random() * 200) + 50,
    hearts: Math.floor(Math.random() * 500) + 100,
    locationType: locType,
    emoji: cat === 'Cafe' ? '☕' : '🍱',
    coverImage: cover || "",
    address: r.location,
    hours: r.hours,
    breakTime: "",
    mapNaver: "",
    mapGoogle: "",
    menu: rMenus,
    reviews: []
  });
}

fs.writeFileSync('extracted_data.json', JSON.stringify(finalData, null, 2));
console.log('Extraction complete. Wrote extracted_data.json');
