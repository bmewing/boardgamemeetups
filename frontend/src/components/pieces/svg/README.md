# Piece drawings

Each file here is one game piece people can pick, named after the piece (`race_car.svg` is
the `race_car` piece). Edit them in any vector editor; the app reads them as they are.

## The rules

- **Canvas:** `viewBox="0 0 100 100"`. Keep the drawing a little inside the edges: the app
  adds a thick outline around the body.
- **Three groups**, found by their id (or, in Inkscape, the layer's name):
  - `body`: the piece itself, as filled shapes. The app fills it with the person's color and
    draws one outline around the whole silhouette, so don't draw an outline yourself.
  - `details`: filled marks on top, like eyes, pips and wheel hubs. Drawn in the olive ink.
  - `lines`: lines on top, like stitching or a cube's edges. Drawn as olive strokes, 5 wide.
- **Colors, stroke widths and styles in the file are ignored.** Use any colors you like while
  drawing; the app brings its own.
- **Allowed shapes:** paths, circles, ellipses, rectangles, lines, polylines and polygons.
  Nested groups inside the three are fine.
- **Not allowed:** transforms (flatten them), text (convert it to a path), images, masks and
  clones. A shape outside the three groups is an error too.

Holes in a shape work with `fill-rule="evenodd"`, the way Inkscape usually saves them.

`npm test` checks every file against these rules and says what's wrong. If a file is broken,
the site draws that piece as a plain meeple instead of failing.

## Adding a piece

1. Add the name to `Piece` in `backend/app/pieces.py`, then run `bash functions/sync_backend.sh`
   from the repo root and `npm run gen:api` from `frontend/`.
2. Add `<name>.svg` here.
3. In `../shapes.ts`, give it a label in `PIECE_LABELS` and put it in one of `PIECE_GROUPS`.

Removing or renaming a piece someone has picked needs a migration that moves their rows off it
first; the backend can't load a user whose piece no longer exists.
