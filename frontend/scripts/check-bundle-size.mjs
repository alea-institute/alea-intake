#!/usr/bin/env node
/**
 * Bundle size gate — fails the build if the main chunk exceeds the
 * budget set by D-35 (<200KB gzipped).
 */
import { readdirSync, readFileSync } from 'fs'
import { join } from 'path'
import { gzipSync } from 'zlib'

const DIST = 'dist/assets'
const MAX_MAIN_GZIP_KB = 200

function findMainChunk() {
  let files
  try {
    files = readdirSync(DIST)
  } catch (err) {
    console.error(`Could not read ${DIST}: ${err.message}`)
    console.error('Run `npm run build` before the bundle-size check.')
    process.exit(1)
  }
  // Main chunk is the entry JS (not a named vendor chunk).
  return files.find(
    (f) => f.startsWith('index-') && f.endsWith('.js') && !f.includes('vendor')
  )
}

const main = findMainChunk()
if (!main) {
  console.error('No main chunk found in', DIST)
  process.exit(1)
}

const content = readFileSync(join(DIST, main))
const gzipped = gzipSync(content)
const kbRaw = content.length / 1024
const kbGzip = gzipped.length / 1024

console.log(`Main chunk: ${main}`)
console.log(`  Raw:     ${kbRaw.toFixed(2)} KB`)
console.log(`  Gzipped: ${kbGzip.toFixed(2)} KB`)
console.log(`  Budget:  ${MAX_MAIN_GZIP_KB} KB gzipped`)

if (kbGzip > MAX_MAIN_GZIP_KB) {
  const over = (kbGzip - MAX_MAIN_GZIP_KB).toFixed(2)
  console.error(`Bundle exceeds budget by ${over} KB gzipped`)
  process.exit(1)
}

console.log('Bundle within budget')
process.exit(0)
