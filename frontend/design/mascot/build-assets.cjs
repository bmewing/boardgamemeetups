// Encode the generated artwork and render its web motion to portable image formats.
// Requires sharp and playwright. Set MASCOT_NODE_MODULES to use your own installation.
const fs = require('node:fs/promises')
const path = require('node:path')
const os = require('node:os')
const { createRequire } = require('node:module')
const runtime =
  process.env.MASCOT_NODE_MODULES ||
  path.join(
    os.homedir(),
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',
  )
const runtimeRequire = createRequire(path.join(runtime, 'mascot-runtime.cjs'))
const sharp = runtimeRequire('sharp')
const { chromium } = runtimeRequire('playwright')
const out = path.resolve(__dirname, '../../public/mascot')
const poses = ['idle', 'toss', 'twirl', 'wave', 'think', 'snooze', 'cheer', 'deal']

const motion = `
.grp-body { transform-origin: 120px 210px; animation: grp-float 4.8s ease-in-out infinite; }
@keyframes grp-float { 0%,100% { transform: translateY(0) rotate(0deg); } 50% { transform: translateY(-4px) rotate(-1deg); } }
[data-pose="wave"] .grp-body { animation: grp-wave 4.8s ease-in-out infinite; }
@keyframes grp-wave { 0%,45%,100% { transform: rotate(0deg); } 12%,30% { transform: rotate(-4deg); } 21%,39% { transform: rotate(2deg); } }
[data-pose="think"] .grp-body { animation: grp-ponder 4.8s ease-in-out infinite; }
@keyframes grp-ponder { 0%,100% { transform: rotate(0deg); } 50% { transform: rotate(-2deg) translateY(-2px); } }
[data-pose="snooze"] .grp-body { animation: grp-breathe 4.8s ease-in-out infinite; }
@keyframes grp-breathe { 0%,100% { transform: scale(1); } 50% { transform: scale(1.015,1.025); } }
[data-pose="cheer"] .grp-body { animation: grp-hop 2.4s ease-in-out infinite; }
@keyframes grp-hop { 0%,65%,100% { transform: translateY(0); } 15% { transform: translateY(2px) scale(1.01,.99); } 35% { transform: translateY(-10px); } }
.grp-die-flight { animation: grp-toss 2.4s infinite; }
.grp-die-spin { transform-box: fill-box; transform-origin: center; animation: grp-spin 2.4s infinite; }
@keyframes grp-toss { 0%,12%,86%,100% { transform: translate(0,0); } 20% { transform: translate(0,3px); animation-timing-function:ease-out; } 50% { transform: translate(-6px,-56px); animation-timing-function:ease-in; } 80% { transform:translate(0,0); } }
@keyframes grp-spin { 0%,20% { transform:rotate(0deg); } 80%,100% { transform:rotate(360deg); } }
.grp-meeple { transform-box:fill-box; transform-origin:center; animation:grp-twirl 2.4s linear infinite; }
@keyframes grp-twirl { 0%,100% { transform:scaleX(1); } 25%,75% { transform:scaleX(.16) translateY(-3px); } 50% { transform:scaleX(-1); } }
.grp-bubble { animation:grp-bubble 4.8s ease-in-out infinite; }
.grp-bubble.b2 { animation-delay:-1.6s; } .grp-bubble.b3 { animation-delay:-3.2s; }
@keyframes grp-bubble { 0%,100% { opacity:0; transform:translate(0,0); } 25% { opacity:.8; } 80% { opacity:0; transform:translate(5px,-20px); } }
.grp-z { fill:#514b23; font:bold 17px Georgia,serif; animation:grp-bubble 4.8s ease-in-out infinite; }
.grp-z.z2 { animation-delay:-2.4s; }
.grp-confetti { transform-box:fill-box; transform-origin:center; animation:grp-confetti 2.4s ease-out infinite; animation-delay:var(--delay); }
@keyframes grp-confetti { 0% { opacity:0; transform:translateY(8px) rotate(-15deg); } 25% { opacity:1; } 100% { opacity:0; transform:translateY(-17px) rotate(75deg); } }
@media(prefers-reduced-motion:reduce) { .grp-stage * { animation:none!important; } .grp-bubble,.grp-z,.grp-confetti { display:none; } }
`

async function main() {
  await fs.mkdir(path.join(out, 'anim'), { recursive: true })
  await fs.mkdir(path.join(out, 'layers'), { recursive: true })
  const images = {}
  for (const name of [...poses, 'die', 'meeple', 'favicon']) {
    const source = path.join(__dirname, 'source', `${name}.png`)
    const meta = await sharp(source).metadata()
    if (!meta.hasAlpha) throw new Error(`${name}: generated source is missing transparency`)
    const encoded = await sharp(source)
      .resize(512, 512)
      .webp({ quality: 90, alphaQuality: 100 })
      .toBuffer()
    images[name] = `data:image/webp;base64,${encoded.toString('base64')}`
    if (name !== 'favicon') await fs.writeFile(path.join(out, 'layers', `${name}.webp`), encoded)
  }
  const scenes = {}
  for (const pose of poses) {
    let extras = ''
    if (pose === 'toss')
      extras = `<g class="grp-die-flight"><image class="grp-die-spin" href="${images.die}" x="166" y="67" width="48" height="48"/></g>`
    if (pose === 'twirl')
      extras = `<image class="grp-meeple" href="${images.meeple}" x="177" y="59" width="42" height="42"/>`
    if (pose === 'think')
      extras = [0, 1, 2]
        .map(
          (n) =>
            `<circle class="grp-bubble b${n + 1}" cx="${182 + n * 7}" cy="${57 - n * 11}" r="${3 + n}" fill="#ffeedb" stroke="#1d7874" stroke-width="1.5"/>`,
        )
        .join('')
    if (pose === 'snooze')
      extras =
        '<text class="grp-z" x="180" y="60">z</text><text class="grp-z z2" x="195" y="43">z</text>'
    if (pose === 'cheer')
      extras = [
        [33, 49],
        [199, 64],
        [48, 103],
        [190, 117],
        [69, 28],
        [167, 31],
        [210, 92],
      ]
        .map(
          ([x, y], i) =>
            `<rect class="grp-confetti" x="${x}" y="${y}" width="4" height="8" rx="1" fill="${['#dd7373', '#1d7874', '#514b23'][i % 3]}" style="--delay:-${i * 0.3}s"/>`,
        )
        .join('')
    scenes[pose] =
      `<svg xmlns="http://www.w3.org/2000/svg" class="grp-stage" data-pose="${pose}" viewBox="0 0 240 240" width="512" height="512" role="img" aria-label="Grouper: ${pose}"><style>${motion}</style><g class="grp-body"><image href="${images[pose]}" width="240" height="240"/>${extras}</g></svg>`
    await fs.writeFile(path.join(out, `grouper-${pose}.svg`), scenes[pose])
  }
  // Favicons, app icons and the header logo come from design/mascot/build-icons.py.

  const browser = await chromium.launch({
    headless: true,
    ...(process.env.MASCOT_CHROMIUM ? { executablePath: process.env.MASCOT_CHROMIUM } : {}),
  })
  try {
    const page = await browser.newPage({
      viewport: { width: 2048, height: 1024 },
      deviceScaleFactor: 1,
    })
    await page.setContent(
      `<html><head><style>html,body{margin:0;background:transparent}body{display:grid;grid-template-columns:repeat(4,512px)}svg{width:100%;height:auto;display:block}</style></head><body>${poses.map((p) => scenes[p]).join('')}</body></html>`,
    )
    await page.evaluate(async () => {
      await Promise.all([...document.images].map((img) => img.decode()))
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
      document.getAnimations().forEach((a) => {
        a.pause()
        a.currentTime = 0
      })
    })
    // SVG images are decoded asynchronously; wait for the document's load as well.
    await page.waitForLoadState('load')
    const stills = await page.screenshot({ omitBackground: true })
    for (let i = 0; i < poses.length; i++)
      await sharp(stills)
        .extract({ left: (i % 4) * 512, top: Math.floor(i / 4) * 512, width: 512, height: 512 })
        .png()
        .toFile(path.join(out, `grouper-${poses[i]}.png`))
    await page.addStyleTag({ content: 'body{grid-template-columns:repeat(4,256px)}' })
    await page.setViewportSize({ width: 1024, height: 512 })
    const frames = poses.map(() => [])
    for (let frame = 0; frame < 48; frame++) {
      await page.evaluate(
        (time) =>
          document.getAnimations().forEach((a) => {
            a.currentTime = time
          }),
        frame * 100,
      )
      const sheet = await page.screenshot({ omitBackground: true })
      await Promise.all(
        poses.map(async (_, i) =>
          frames[i].push(
            await sharp(sheet)
              .extract({
                left: (i % 4) * 256,
                top: Math.floor(i / 4) * 256,
                width: 256,
                height: 256,
              })
              .png()
              .toBuffer(),
          ),
        ),
      )
    }
    for (let i = 0; i < poses.length; i++) {
      const raw = await sharp({
        create: {
          width: 256,
          height: 256 * 48,
          channels: 4,
          background: { r: 0, g: 0, b: 0, alpha: 0 },
        },
      })
        .composite(frames[i].map((input, n) => ({ input, left: 0, top: n * 256 })))
        .raw()
        .toBuffer()
      const input = { raw: { width: 256, height: 256 * 48, channels: 4, pageHeight: 256 } }
      await sharp(raw, input)
        .webp({ quality: 82, loop: 0, delay: Array(48).fill(100), effort: 4 })
        .toFile(path.join(out, 'anim', `grouper-${poses[i]}.webp`))
      await sharp(raw, input)
        .flatten({ background: '#ffeedb' })
        .gif({ loop: 0, delay: Array(48).fill(100), effort: 7 })
        .toFile(path.join(out, 'anim', `grouper-${poses[i]}.gif`))
      console.log(`Exported ${poses[i]}: still PNG, animated SVG, GIF and WebP`)
    }
  } finally {
    await browser.close()
  }
}
main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
