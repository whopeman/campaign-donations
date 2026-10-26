/*
  tools/build-map.mjs
  Project : Campaign Donations
  Date    : 2026-10-26
  Purpose : Turn the US Census Bureau cartographic boundary files (public
            domain), as packaged and pre-projected (Albers USA, with Alaska
            and Hawaii inset) by the us-atlas package (ISC), into one SVG path
            per state. Output: data/us-states-paths.json, keyed by state FIPS
            code. The page generator adds the links and labels.
  Usage   : npm install; npm run build:map
  Change log:
    2026-10-26  0.1.0  Initial version.
*/
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { geoPath } from 'd3-geo';
import { feature, mesh } from 'topojson-client';

const require = createRequire(import.meta.url);
const atlasPath = require.resolve('us-atlas/states-albers-10m.json');
const us = JSON.parse(await readFile(atlasPath, 'utf8'));

const path = geoPath(); // data is already projected to a 975 x 610 canvas
const states = {};
for (const f of feature(us, us.objects.states).features) {
  const [cx, cy] = path.centroid(f);
  states[f.id] = {
    name: f.properties.name,
    d: path(f),
    cx: Math.round(cx * 10) / 10,
    cy: Math.round(cy * 10) / 10,
  };
}
const out = {
  source: 'US Census Bureau cartographic boundary files, 1:10,000,000, via us-atlas 3.0.1 (states-albers-10m)',
  sourceUrl: 'https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html',
  viewBox: '0 0 975 610',
  borders: path(mesh(us, us.objects.states, (a, b) => a !== b)),
  states,
};
await mkdir('data', { recursive: true });
await writeFile('data/us-states-paths.json', JSON.stringify(out));
console.log(`wrote ${Object.keys(states).length} states to data/us-states-paths.json`);
