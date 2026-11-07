"""Build the browser, home-screen and installed-app icons from Greg's head.

Run from frontend/:  python design/mascot/build-icons.py   (needs Pillow)

- favicon.svg / favicon.ico / favicon.png: Greg's head on a transparent background.
- apple-touch-icon.png: the head on cream, since iOS fills transparency with black.
- icon-192.png / icon-512.png: the head on transparent, for "any" purpose.
- icon-maskable-192.png / icon-maskable-512.png: the head on cream inside Android's
  safe zone, so launchers can crop it to a circle, squircle or square without clipping.
- logo.svg: the hexagon Greg used as the site header logo.
"""

import base64
import io
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source"
PUBLIC = HERE.parent.parent / "public"
CREAM = (255, 238, 219, 255)  # #ffeedb, the site's background and theme colour


def trimmed(path: Path) -> Image.Image:
    """The art cropped to its visible pixels and centred on a square canvas."""
    art = Image.open(path).convert("RGBA")
    art = art.crop(art.getbbox())
    side = max(art.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(art, ((side - art.width) // 2, (side - art.height) // 2))
    return square


def placed(art: Image.Image, size: int, scale: float, background=(0, 0, 0, 0)) -> Image.Image:
    """`art` shrunk to `scale` of a `size` square and centred on `background`."""
    canvas = Image.new("RGBA", (size, size), background)
    inner = round(size * scale)
    shrunk = art.resize((inner, inner), Image.LANCZOS)
    canvas.alpha_composite(shrunk, ((size - inner) // 2, (size - inner) // 2))
    return canvas


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def svg_wrapper(image: Image.Image) -> str:
    data = base64.b64encode(png_bytes(image)).decode()
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
        f'<image width="128" height="128" href="data:image/png;base64,{data}"/></svg>'
    )


def main() -> None:
    head = trimmed(SOURCE / "head.png")

    (PUBLIC / "favicon.svg").write_text(svg_wrapper(placed(head, 128, 1.0)))
    placed(head, 48, 1.0).save(PUBLIC / "favicon.png", optimize=True)
    placed(head, 256, 1.0).save(PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

    # iOS rounds the corners itself; keep a little room so the fins aren't clipped.
    placed(head, 180, 0.84, CREAM).convert("RGB").save(PUBLIC / "apple-touch-icon.png", optimize=True)

    for size in (192, 512):
        placed(head, size, 1.0).save(PUBLIC / f"icon-{size}.png", optimize=True)
        # Android's safe zone is the centre circle, 80% of the width across. The head's
        # farthest visible pixel sits 49% of its width from the centre, so at 80% scale
        # every fin and the chin stay inside that circle.
        placed(head, size, 0.80, CREAM).save(PUBLIC / f"icon-maskable-{size}.png", optimize=True)

    hexagon = Image.open(SOURCE / "favicon.png").convert("RGBA")
    (PUBLIC / "logo.svg").write_text(svg_wrapper(hexagon.resize((128, 128), Image.LANCZOS)))


if __name__ == "__main__":
    main()
