// Package Greg's additional illustrations without changing the original eight poses.
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
const runtimeRequire = createRequire(path.join(runtime, 'greg-runtime.cjs'))
const sharp = runtimeRequire('sharp')
const { chromium } = runtimeRequire('playwright')
const source = path.join(__dirname, 'source')
const out = path.resolve(__dirname, '../../public/mascot')
const poses = ['oops', 'winner', 'shuffle']

const motion = `
.greg-body { transform-origin:120px 210px; animation:greg-float 4.8s ease-in-out infinite; }
@keyframes greg-float { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-3px); } }
[data-pose="oops"] .greg-body { animation:greg-oops 4.8s ease-in-out infinite; }
@keyframes greg-oops { 0%,30%,100% { transform:rotate(0deg); } 55%,70% { transform:rotate(2deg); } }
[data-pose="shuffle"] .greg-body { animation:greg-focus 2.4s ease-in-out infinite; }
@keyframes greg-focus { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-1px); } }
.greg-card-left { transform-origin:120px 126px; animation:greg-riffle-left 2.4s ease-in-out infinite; }
.greg-card-right { transform-origin:120px 126px; animation:greg-riffle-right 2.4s ease-in-out infinite; }
@keyframes greg-riffle-left { 0%,100% { transform:translate(-8px,0) rotate(-18deg); } 25% { transform:translate(-3px,-4px) rotate(-9deg); } 45%,60% { transform:translate(6px,0) rotate(0deg); } 75% { transform:translate(-2px,1px) rotate(-8deg); } }
@keyframes greg-riffle-right { 0%,100% { transform:translate(8px,0) rotate(18deg); } 25% { transform:translate(3px,-4px) rotate(9deg); } 45%,60% { transform:translate(-6px,0) rotate(0deg); } 75% { transform:translate(2px,1px) rotate(8deg); } }
.greg-spark { transform-box:fill-box; transform-origin:center; animation:greg-spark 2.4s ease-in-out infinite; }
.greg-spark.second { animation-delay:-1.2s; }
@keyframes greg-spark { 0%,100% { opacity:.25; transform:scale(.7); } 50% { opacity:1; transform:scale(1); } }
@media(prefers-reduced-motion:reduce) { .greg-stage * { animation:none!important; } .greg-spark { display:none; } .greg-card-left { transform:translate(-8px,0) rotate(-18deg); } .greg-card-right { transform:translate(8px,0) rotate(18deg); } }
`

async function main() {
  await fs.mkdir(path.join(out, 'layers'), { recursive: true })
  await fs.mkdir(path.join(out, 'anim'), { recursive: true })
  const images = {}
  for (const name of [...poses, 'card-stack', 'head']) {
    const file = path.join(source, `${name}.png`)
    if (!(await sharp(file).metadata()).hasAlpha)
      throw new Error(`${name} must have transparent alpha`)
    const buffer = await sharp(file)
      .resize(512, 512)
      .webp({ quality: 90, alphaQuality: 100 })
      .toBuffer()
    images[name] = `data:image/webp;base64,${buffer.toString('base64')}`
    await fs.writeFile(path.join(out, 'layers', `${name}.webp`), buffer)
  }
  // Head art has no animation and is supplied at native inline/avatar sizes.
  for (const size of [32, 48, 64, 128, 256, 512]) {
    const name = size === 512 ? 'grouper-head.png' : `grouper-head-${size}.png`
    await sharp(path.join(source, 'head.png')).resize(size, size).png().toFile(path.join(out, name))
  }
  await sharp(path.join(source, 'head.png'))
    .resize(512, 512)
    .webp({ quality: 90 })
    .toFile(path.join(out, 'grouper-head.webp'))
  await fs.writeFile(
    path.join(out, 'grouper-head.svg'),
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" width="512" height="512" role="img" aria-label="Greg the grouper"><image href="${images.head}" width="240" height="240"/></svg>`,
  )
  await sharp(path.join(source, 'social.png'))
    .resize(1200, 630, { fit: 'contain', background: '#ffeedb' })
    // A JPEG keeps link previews fast: about 95 KB against roughly 900 KB as a PNG.
    .jpeg({ quality: 85, progressive: true, mozjpeg: true })
    .toFile(path.join(out, '../share.jpg'))

  const scenes = {}
  for (const pose of poses) {
    let extras = ''
    if (pose === 'shuffle')
      extras = `<g class="greg-card-left"><image href="${images['card-stack']}" x="78" y="78" width="64" height="64"/></g><g class="greg-card-right"><image href="${images['card-stack']}" x="114" y="78" width="64" height="64"/></g>`
    if (pose === 'winner')
      extras =
        '<path class="greg-spark" d="M210 36l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" fill="#d4ac56"/><path class="greg-spark second" d="M194 65l1.5 3.5 3.5 1.5-3.5 1.5-1.5 3.5-1.5-3.5-3.5-1.5 3.5-1.5z" fill="#dd7373"/>'
    scenes[pose] =
      `<svg xmlns="http://www.w3.org/2000/svg" class="greg-stage" data-pose="${pose}" viewBox="0 0 240 240" width="512" height="512" role="img" aria-label="Greg the grouper: ${pose}"><style>${motion}</style><g class="greg-body"><image href="${images[pose]}" width="240" height="240"/>${extras}</g></svg>`
    await fs.writeFile(path.join(out, `grouper-${pose}.svg`), scenes[pose])
  }
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.MASCOT_CHROMIUM ? { executablePath: process.env.MASCOT_CHROMIUM } : {}),
  })
  try {
    const page = await browser.newPage({
      viewport: { width: 1536, height: 512 },
      deviceScaleFactor: 1,
    })
    await page.setContent(
      `<html><head><style>html,body{margin:0;background:transparent}body{display:grid;grid-template-columns:repeat(3,512px)}svg{display:block;width:100%;height:auto}</style></head><body>${poses.map((p) => scenes[p]).join('')}</body></html>`,
    )
    await page.evaluate(async () => {
      await Promise.all(
        [...document.querySelectorAll('svg image')].map((el) => {
          const img = new Image()
          img.src = el.getAttribute('href')
          return img.decode()
        }),
      )
      document.getAnimations().forEach((a) => {
        a.pause()
        a.currentTime = 0
      })
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    })
    const still = await page.screenshot({ omitBackground: true })
    for (let i = 0; i < poses.length; i++)
      await sharp(still)
        .extract({ left: i * 512, top: 0, width: 512, height: 512 })
        .png()
        .toFile(path.join(out, `grouper-${poses[i]}.png`))
    await page.addStyleTag({ content: 'body{grid-template-columns:repeat(3,256px)}' })
    await page.setViewportSize({ width: 768, height: 256 })
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
              .extract({ left: i * 256, top: 0, width: 256, height: 256 })
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
        .webp({ quality: 82, loop: 0, delay: Array(48).fill(100) })
        .toFile(path.join(out, 'anim', `grouper-${poses[i]}.webp`))
      await sharp(raw, input)
        .flatten({ background: '#ffeedb' })
        .gif({ loop: 0, delay: Array(48).fill(100), effort: 7 })
        .toFile(path.join(out, 'anim', `grouper-${poses[i]}.gif`))
      console.log(`Packaged ${poses[i]}: PNG, SVG, GIF and WebP`)
    }
    console.log('Packaged head portrait sizes and the 1200x630 social image')
  } finally {
    await browser.close()
  }
}
main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
