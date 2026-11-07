GREG THE GROUPER ASSETS

The original eight poses and four additional component variants are in public/mascot/. See CLAUDE-HANDOFF.txt for usage, appropriate placements and exact paths; asset-map.json provides a machine-readable index.

New variants: oops, winner, shuffle, head. The first three have transparent 512px PNGs, animated web SVGs, cream GIFs and transparent animated WebPs. Head is a still portrait supplied at 32, 48, 64, 128, 256 and 512px plus WebP and a static SVG wrapper. public/share.jpg is the 1200x630 Greg social card (JPEG quality 85, about 95 KB, so link previews load quickly).

Greg's name comes from Good Guy Greg. Artwork was created with the built-in image generation tool against the supplied character reference; exact prompts are in generation-prompts.json and high-resolution originals are in source/.

Preview: /mascot/preview.html on the development site. It includes the new variants, native small-size portraits, the social card, dark backgrounds and all original poses.

The existing React entry point is src/components/mascot/Grouper.tsx. All twelve pose names are supported; head is always still. Use animated={false} for other stills. The original poses have already been integrated in several pages; new variants are ready for page-level integration.

SVGs embed generated raster artwork and animation, so they are not resolution-independent vector drawings. The SVG animations respect system reduced-motion preferences. Raw GIF/WebP files cannot do so by themselves. All full-body animations loop over 4.8 seconds. Shuffle visibly moves two separate card packets; other motion details are documented in the handoff.

Rebuild the original eight poses:
  node design/mascot/build-assets.cjs
Rebuild the favicons, app icons (including Android's maskable ones) and header logo:
  python design/mascot/build-icons.py
Rebuild the additional variants, portraits and social card:
  node design/mascot/build-variants.cjs

These packaging scripts require sharp, Playwright and an installed Chromium, with no generation or API calls. MASCOT_NODE_MODULES can point to an existing package folder; MASCOT_CHROMIUM can point to an existing Chromium executable. The scripts default to the Codex bundled packages when available. Runtime dependencies were not added to the application.
