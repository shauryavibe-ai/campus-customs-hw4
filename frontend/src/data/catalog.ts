// Builds the website's product records from the JSON exports in hw 4/outputs,
// following the rules in outputs/harness.md.
import rawCatalogue from '../../../outputs/catalogue.json'
import rawInventory from '../../../outputs/inventory.json'

export type Category =
  | 'T-Shirts'
  | 'Crewnecks'
  | 'Hoodies'
  | 'Quarter-Zips'
  | 'Jackets & Fleece'
  | 'Long Sleeves'

export type Collection =
  | 'Residential Colleges'
  | 'Athletics'
  | 'Graduate & Professional Schools'
  | 'Yale Family'
  | 'Classic Yale'

export type ColorFamily = 'Navy' | 'Gray' | 'Cream / White' | 'Pink'

export type Size = 'XS' | 'S' | 'M' | 'L' | 'XL' | 'XXL'
export type StockStatus = 'in_stock' | 'low_stock' | 'sold_out'

export interface SizeStock {
  size: Size
  qty: number
  status: StockStatus
}

export interface Product {
  id: string
  name: string
  category: Category
  garmentType: string
  collection: Collection
  price: number
  description: string | null
  shortDescription: string
  colors: string[]
  colorFamily: ColorFamily | null
  tags: string[]
  image: string
  sizes: SizeStock[]
  totalStock: number
  sizesAvailable: number
  badge: 'Sold out' | 'Low stock' | 'Limited sizes' | null
  isPlaceholder: boolean
}

export const CATEGORIES: Category[] = [
  'T-Shirts',
  'Crewnecks',
  'Hoodies',
  'Quarter-Zips',
  'Jackets & Fleece',
  'Long Sleeves',
]

export const COLLECTIONS: Collection[] = [
  'Residential Colleges',
  'Athletics',
  'Graduate & Professional Schools',
  'Yale Family',
  'Classic Yale',
]

export const COLOR_FAMILIES: ColorFamily[] = ['Navy', 'Gray', 'Cream / White', 'Pink']
export const SIZES: Size[] = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
export const LOW_STOCK_MAX = 5

const images = import.meta.glob<string>('../../../data/products/*.jpg', {
  eager: true,
  query: '?url',
  import: 'default',
})

function imageFor(path: string): string {
  return images[`../../../data/${path}`] ?? ''
}

function categoryOf(garmentType: string): Category {
  const g = garmentType.toLowerCase()
  if (g.includes('jacket')) return 'Jackets & Fleece'
  if (g.includes('quarter-zip')) return 'Quarter-Zips'
  if (g.includes('hood')) return 'Hoodies'
  if (g.includes('crewneck') || g.includes('mockneck')) return 'Crewnecks'
  if (g.includes('long-sleeve')) return 'Long Sleeves'
  return 'T-Shirts'
}

const RESIDENTIAL_COLLEGES = [
  'benjamin-franklin', 'berkeley', 'branford', 'davenport', 'grace-hopper',
  'jonathan-edwards', 'morse', 'pierson', 'saybrook', 'timothy-dwight', 'trumbull',
]
const RELATIVES = ['mom', 'dad', 'grandma', 'grandpa', 'aunt', 'uncle', 'brother', 'cousin']
const SPORTS = [
  'baseball', 'basketball', 'football', 'hockey', 'soccer', 'tennis', 'track', 'diving',
  'fencing', 'lacrosse', 'sailing', 'squash', 'volleyball', 'golf', 'swimming',
  'field-hockey', 'crew-left', 'sports',
]

function collectionOf(id: string): Collection {
  if (RESIDENTIAL_COLLEGES.some((c) => id.includes(c))) return 'Residential Colleges'
  if (['school', 'divinity', 'law'].some((s) => id.includes(s))) return 'Graduate & Professional Schools'
  if (RELATIVES.some((r) => id.includes(`yale-${r}-`))) return 'Yale Family'
  if (SPORTS.some((s) => id.includes(s))) return 'Athletics'
  return 'Classic Yale'
}

function colorFamilyOf(baseColor: string | undefined): ColorFamily | null {
  if (!baseColor) return null
  if (baseColor.includes('navy')) return 'Navy'
  if (['cream', 'ivory', 'white'].includes(baseColor)) return 'Cream / White'
  if (baseColor.includes('coral') || baseColor.includes('pink')) return 'Pink'
  return 'Gray'
}

const NAME_FIXES: [RegExp, string][] = [
  [/^Ua Mens Tech L S 2 0$/, "UA Men's Tech Long Sleeve 2.0"],
  [/^Squash Left Chest Tennis$/, 'Squash Left Chest Crewneck'],
  [/\b1 4 Zip\b/g, '¼-Zip'],
  [/\bT Shirt\b/g, 'T-Shirt'],
  [/\bTri Blend\b/g, 'Tri-Blend'],
  [/\bSchool Of\b/g, 'School of'],
  [/\bCreqneck\b/g, 'Crewneck'],
  [/\bTrack Field\b/g, 'Track & Field'],
  [/\bTrack And Field\b/g, 'Track & Field'],
  [/\bVs\b/g, 'vs.'],
  [/^Ua /, 'UA '],
  [/ 1$/, ''],
]

function cleanName(name: string): string {
  return NAME_FIXES.reduce((n, [pattern, replacement]) => n.replace(pattern, replacement), name)
}

const SHORT_DESCRIPTION_MAX = 110

function shortDescriptionOf(description: string | null, collection: Collection): string {
  if (!description) return `A Campus Customs pick from our ${collection} collection.`
  if (description.length <= SHORT_DESCRIPTION_MAX) return description
  const cut = description.slice(0, SHORT_DESCRIPTION_MAX)
  return `${cut.slice(0, cut.lastIndexOf(' ')).replace(/[\s,;:]+$/, '')}…`
}

function statusOf(qty: number): StockStatus {
  if (qty === 0) return 'sold_out'
  if (qty <= LOW_STOCK_MAX) return 'low_stock'
  return 'in_stock'
}

const stockById = new Map<string, Map<string, number>>()
for (const row of rawInventory) {
  if (!stockById.has(row.product_id)) stockById.set(row.product_id, new Map())
  stockById.get(row.product_id)!.set(row.size, row.quantity)
}

export const PRODUCTS: Product[] = rawCatalogue.map((p) => {
  const stock = stockById.get(p.product_id)
  const sizes: SizeStock[] = SIZES.map((size) => {
    const qty = stock?.get(size) ?? 0
    return { size, qty, status: statusOf(qty) }
  })
  const available = sizes.filter((s) => s.qty > 0)
  const isPlaceholder = p.colors.length === 0

  const collection = collectionOf(p.product_id)
  const description = isPlaceholder ? null : p.description

  let badge: Product['badge'] = null
  if (available.length === 0) badge = 'Sold out'
  else if (available.every((s) => s.status === 'low_stock')) badge = 'Low stock'
  else if (available.length <= 2) badge = 'Limited sizes'

  return {
    id: p.product_id,
    name: cleanName(p.name),
    category: categoryOf(p.garment_type),
    garmentType: p.garment_type,
    collection,
    price: p.price,
    description,
    shortDescription: shortDescriptionOf(description, collection),
    colors: p.colors,
    colorFamily: colorFamilyOf(p.colors[0]),
    tags: p.search_tags,
    image: imageFor(p.image_file_path),
    sizes,
    totalStock: sizes.reduce((sum, s) => sum + s.qty, 0),
    sizesAvailable: available.length,
    badge,
    isPlaceholder,
  }
})

export function getProduct(id: string): Product | undefined {
  return PRODUCTS.find((p) => p.id === id)
}

// "Handsome Dan" is Yale's bulldog mascot, but no product is tagged with the name.
const SYNONYMS: Record<string, string> = { 'handsome dan': 'bulldog' }

export function matchesSearch(product: Product, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const term = SYNONYMS[q] ?? q
  const haystack = [
    product.name,
    product.category,
    product.collection,
    product.description ?? '',
    ...product.colors,
    ...product.tags,
  ]
    .join(' ')
    .toLowerCase()
  return haystack.includes(term)
}

export function formatPrice(price: number): string {
  return `$${price.toFixed(2)}`
}
