#!/usr/bin/env node

const args = process.argv.slice(2);

function hasFlag(name) {
  return args.includes(`--${name}`);
}

function readArg(name, fallback) {
  const index = args.indexOf(`--${name}`);
  if (index === -1) return fallback;
  const value = args[index + 1];
  if (!value || value.startsWith("--")) throw new Error(`--${name} requires a value`);
  return value;
}

function usage() {
  return `Usage: node scripts/query-inaturalist.mjs --lat <number> --lng <number> [options]

Options:
  --radius <km>           Search radius (default: 50, max: 200)
  --days <number>         Lookback window (default: 30, max: 3650)
  --taxon <name>          Scientific or common taxon name
  --quality <grade>       research, needs_id, or casual (default: research)
  --limit <number>        Results to return (default: 10, max: 200)
  --animals-only          Restrict results to Animalia
  --photos                Require attached photos
  --photo-license <codes> Filter photo licenses (for example: cc0,cc-by)
  --sounds                Require attached sounds
  --sound-license <codes> Filter sound licenses (for example: cc0,cc-by)
  --user-agent <value>    Descriptive caller identity
  --help                  Show this message`;
}

if (hasFlag("help")) {
  console.log(usage());
  process.exit(0);
}

const lat = Number(readArg("lat"));
const lng = Number(readArg("lng"));
const radius = Number(readArg("radius", "50"));
const days = Number(readArg("days", "30"));
const limit = Number(readArg("limit", "10"));
const quality = readArg("quality", "research");
const taxon = readArg("taxon");
const photoLicense = readArg("photo-license");
const soundLicense = readArg("sound-license");
const userAgent = readArg(
  "user-agent",
  "eprs-inaturalist-skill/1.0 (read-only attributed media discovery)",
);

if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
  throw new Error("--lat must be a number from -90 to 90");
}
if (!Number.isFinite(lng) || lng < -180 || lng > 180) {
  throw new Error("--lng must be a number from -180 to 180");
}
if (!Number.isFinite(radius) || radius <= 0 || radius > 200) {
  throw new Error("--radius must be greater than 0 and no more than 200 km");
}
if (!Number.isInteger(days) || days < 1 || days > 3650) {
  throw new Error("--days must be an integer from 1 to 3650");
}
if (!Number.isInteger(limit) || limit < 1 || limit > 200) {
  throw new Error("--limit must be an integer from 1 to 200");
}
if (!new Set(["research", "needs_id", "casual"]).has(quality)) {
  throw new Error("--quality must be research, needs_id, or casual");
}
if (photoLicense && !hasFlag("photos")) {
  throw new Error("--photo-license requires --photos");
}
if (soundLicense && !hasFlag("sounds")) {
  throw new Error("--sound-license requires --sounds");
}

const d1 = new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
const params = new URLSearchParams({
  lat: String(lat),
  lng: String(lng),
  radius: String(radius),
  d1,
  quality_grade: quality,
  captive: "false",
  order_by: "observed_on",
  order: "desc",
  per_page: String(limit),
});
if (taxon) params.set("taxon_name", taxon);
if (hasFlag("animals-only")) params.set("taxon_id", "1");
if (hasFlag("photos")) params.set("photos", "true");
if (photoLicense) params.set("photo_license", photoLicense);
if (hasFlag("sounds")) params.set("sounds", "true");
if (soundLicense) params.set("sound_license", soundLicense);

const url = `https://api.inaturalist.org/v1/observations?${params}`;
const response = await fetch(url, {
  headers: {"User-Agent": userAgent, Accept: "application/json"},
});
if (!response.ok) {
  throw new Error(`${response.status} ${response.statusText} for ${url}`);
}

const payload = await response.json();
if (!payload || !Array.isArray(payload.results)) {
  throw new Error("iNaturalist returned an invalid observation payload");
}

const observations = payload.results.map((observation) => ({
  id: observation.id,
  observedOn: observation.observed_on,
  url: observation.uri || `https://www.inaturalist.org/observations/${observation.id}`,
  qualityGrade: observation.quality_grade,
  photos: (observation.photos ?? [])
    .filter((photo) => !photo.hidden)
    .map((photo) => ({
      id: photo.id,
      previewUrl: photo.url,
      licenseCode: photo.license_code,
      attribution: photo.attribution,
      originalDimensions: photo.original_dimensions,
    })),
  sounds: (observation.sounds ?? [])
    .filter((sound) => !sound.hidden)
    .map((sound) => ({
      id: sound.id,
      url: sound.file_url,
      contentType: sound.file_content_type,
      licenseCode: sound.license_code,
      attribution: sound.attribution,
    })),
  taxon: observation.taxon
    ? {
        id: observation.taxon.id,
        scientificName: observation.taxon.name,
        commonName: observation.taxon.preferred_common_name,
        iconicTaxonName: observation.taxon.iconic_taxon_name,
        ancestorIds: observation.taxon.ancestor_ids,
        introduced: observation.taxon.introduced,
        endemic: observation.taxon.endemic,
        threatened: observation.taxon.threatened,
        observationsCount: observation.taxon.observations_count,
      }
    : undefined,
}));

console.log(JSON.stringify({
  query: {
    lat,
    lng,
    radiusKm: radius,
    days,
    taxon,
    quality,
    photos: hasFlag("photos"),
    photoLicense,
    sounds: hasFlag("sounds"),
    soundLicense,
  },
  totalResults: payload.total_results ?? 0,
  observations,
}, null, 2));
