// The generated sheet contains eight views of one extruded wooden meeple, in a 4x2 grid.
// Start at the three-quarter view so stills and reduced-motion mode show its depth.
const motion = `
.grp-meeple-frames { transform:translate(-256px,0); animation:grp-meeple-turn 1.2s steps(1,end) infinite; }
@keyframes grp-meeple-turn {
  0%,100% { transform:translate(-256px,0); }
  12.5% { transform:translate(-512px,0); }
  25% { transform:translate(-768px,0); }
  37.5% { transform:translate(0,-256px); }
  50% { transform:translate(-256px,-256px); }
  62.5% { transform:translate(-512px,-256px); }
  75% { transform:translate(-768px,-256px); }
  87.5% { transform:translate(0,0); }
}
@media(prefers-reduced-motion:reduce) { .grp-meeple-frames { animation:none!important; } }
`

function markup(sheet) {
  return `<svg class="grp-meeple-turntable" x="177" y="59" width="42" height="42" viewBox="0 0 256 256" overflow="hidden"><image class="grp-meeple-frames" href="${sheet}" width="1024" height="512"/></svg>`
}

async function packageSheet(sharp, fs, path, sourceDir, outputDir) {
  const sheet = await sharp(path.join(sourceDir, 'meeple-turntable.png'))
    .resize(1024, 512, { fit: 'fill' })
    .webp({ quality: 90, alphaQuality: 100 })
    .toBuffer()
  await fs.writeFile(path.join(outputDir, 'layers', 'meeple-turntable.webp'), sheet)
  await sharp(sheet)
    .extract({ left: 256, top: 0, width: 256, height: 256 })
    .webp({ quality: 90, alphaQuality: 100 })
    .toFile(path.join(outputDir, 'layers', 'meeple.webp'))
  return `data:image/webp;base64,${sheet.toString('base64')}`
}

module.exports = { motion, markup, packageSheet }
