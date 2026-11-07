// Render selected existing animated SVGs to matching PNG, GIF and WebP exports.
// Example: node design/mascot/render-poses.cjs oops twirl
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
const runtimeRequire = createRequire(path.join(runtime, 'greg-render-runtime.cjs'))
const sharp = runtimeRequire('sharp')
const { chromium } = runtimeRequire('playwright')
const out = path.resolve(__dirname, '../../public/mascot')

async function renderPoses(poses) {
  if (!poses.length || poses.some((p) => !/^[a-z]+$/.test(p)))
    throw new Error('Pass the pose names to render.')
  const scenes = await Promise.all(
    poses.map((p) => fs.readFile(path.join(out, `grouper-${p}.svg`), 'utf8')),
  )
  const count = poses.length
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.MASCOT_CHROMIUM ? { executablePath: process.env.MASCOT_CHROMIUM } : {}),
  })
  try {
    const page = await browser.newPage({
      viewport: { width: count * 512, height: 512 },
      deviceScaleFactor: 1,
    })
    await page.setContent(
      `<html><head><style>html,body{margin:0;background:transparent}body{display:grid;grid-template-columns:repeat(${count},512px)}body>svg{display:block;width:100%;height:auto}</style></head><body>${scenes.join('')}</body></html>`,
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
    for (let i = 0; i < count; i++)
      await sharp(still)
        .extract({ left: i * 512, top: 0, width: 512, height: 512 })
        .png()
        .toFile(path.join(out, `grouper-${poses[i]}.png`))
    await page.addStyleTag({ content: `body{grid-template-columns:repeat(${count},256px)}` })
    await page.setViewportSize({ width: count * 256, height: 256 })
    const frames = poses.map(() => [])
    for (let frame = 0; frame < 96; frame++) {
      await page.evaluate(
        (time) =>
          document.getAnimations().forEach((a) => {
            a.currentTime = time
          }),
        frame * 50,
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
    for (let i = 0; i < count; i++) {
      const raw = await sharp({
        create: {
          width: 256,
          height: 256 * 96,
          channels: 4,
          background: { r: 0, g: 0, b: 0, alpha: 0 },
        },
      })
        .composite(frames[i].map((input, n) => ({ input, left: 0, top: n * 256 })))
        .raw()
        .toBuffer()
      const input = { raw: { width: 256, height: 256 * 96, channels: 4, pageHeight: 256 } }
      await sharp(raw, input)
        .webp({ quality: 82, loop: 0, delay: Array(96).fill(50) })
        .toFile(path.join(out, 'anim', `grouper-${poses[i]}.webp`))
      await sharp(raw, input)
        .flatten({ background: '#ffeedb' })
        .gif({ loop: 0, delay: Array(96).fill(50), effort: 7 })
        .toFile(path.join(out, 'anim', `grouper-${poses[i]}.gif`))
      console.log(`Rendered ${poses[i]}: PNG, GIF and WebP, 4.8 seconds`)
    }
  } finally {
    await browser.close()
  }
}
if (require.main === module)
  renderPoses(process.argv.slice(2)).catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
module.exports = { renderPoses }
