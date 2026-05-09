# Figma MCP Evidence: 145 Designs Colorblock Modern

Source file: `65CMrCi7opIqi80NPrKFxu`

Requested node set: 35 frames under `145:*`.

All requested screenshots were captured at `1920 x 1080` and saved under `figma/65CMrCi7opIqi80NPrKFxu/screenshots/145_designs/`. The contact sheet is `figma/65CMrCi7opIqi80NPrKFxu/contact_sheet_145_designs.png`.

## Variable and Style Evidence

Representative `get_variable_defs` calls returned these resolved tokens:

- `Color 1`: `#000000`
- `Color 2`: `#ffffff`
- `Color 3`: `#465e3a`
- `Color 4`: `#eab855`
- `Color 5`: `#8ba7bf`
- `Color 6`: `#d96b2c`
- `Title`: Plus Jakarta Sans Light, `240`, weight `300`, line-height `1`, letter spacing `0`.
- `Subtitle`: Plus Jakarta Sans Light, `96`, weight `300`, line-height `1`, letter spacing `0`.
- `Headline`: Plus Jakarta Sans Regular, `72`, weight `400`, line-height `1`, letter spacing `0`.
- `Subheadline 1`: Plus Jakarta Sans Light, `80`, weight `300`, line-height `1`, letter spacing `1`.
- `Subheadline 2`: Plus Jakarta Sans Medium, `48`, weight `500`, line-height `1`, letter spacing `10`.
- `Paragraph 1`: Plus Jakarta Sans Regular, `35`, weight `400`, line-height `1.1`, letter spacing `1`.
- `Paragraph 2`: Plus Jakarta Sans Regular, `22`, weight `400`, line-height `1`, letter spacing `0`.

Scaled to PPT Master `1280 x 720`:

- `Title`: `160`
- `Subtitle`: `64`
- `Headline`: `48`
- `Subheadline 1`: `53`
- `Subheadline 2`: `32`, tracking about `3.2`
- `Paragraph 1`: `23`, tracking about `0.23`
- `Paragraph 2`: `15`

## Geometry Evidence

### `145:1024` cover split image slab

Figma-native metadata:

- Frame `1920 x 1080`.
- Title at `x=50`, `y=50`, `w=805`, `h=384`.
- Subheadline at `x=50`, `y=986`, `w=382`, `h=48`.
- Image at `x=908.44`, `y=50.33`, `w=708.52`, `h=979.67`.
- Yellow decorative slab at `x=1482.02`, `y=50`, `w=382.30`, `h=980`.

PPT Master scaled geometry:

- Title at `x=33`, `y=33`, `w=537`.
- Subheadline at `x=33`, `y=657`, `w=255`.
- Image at `x=606`, `y=34`, `w=472`, `h=653`.
- Yellow slab at `x=988`, `y=33`, `w=255`, `h=653`.

Design context confirmed dark green root fill, white Plus Jakarta Light title, image object-cover, and yellow `#eab855` rail.

### `145:1053` agenda

Figma-native metadata:

- Yellow background.
- Small image at `x=56`, `y=728`, `w=403`, `h=302`.
- `AGENDA` at `x=56`, `y=33`, size `72`.
- Seven agenda rows: number column `x=930`, `w=169`; label column `x=1131`, `w=696`; y positions `33.5`, `161.5`, `289.5`, `417.5`, `545.5`, `673.5`, `801.5`.

PPT Master scaled geometry:

- Image `x=38`, `y=485`, `w=269`, `h=202`.
- Title `x=38`, `y=22`, size `48`.
- Number column `x=620`, `w=113`.
- Label column `x=754`, `w=464`.
- Row step about `85`.

Design context confirmed Plus Jakarta Light `80` for agenda numbers and item labels.

### `145:1114` three metric colorblock columns

Figma-native metadata:

- Title at `x=50.5`, `y=50.73`, `w=1818.77`, size `96`.
- Three metric labels at `x=103.21`, `690.06`, `1325.53`, `y=420`, size `96`.
- Body blocks at same x positions, `y=733.50`, `w=420.55`, paragraph size `35`.
- Orange, green, and blue block fields begin near `y=362` and extend beyond the bottom edge.

PPT Master scaled geometry:

- Title `x=34`, `y=34`, size `64`.
- Metric x positions about `69`, `460`, `884`; metric baseline around `280`, size `64`.
- Body blocks x about `69`, `460`, `884`; y about `489`; width about `280`; size `23`.

Design context confirmed yellow root, orange `#d96b2c`, green `#465e3a`, and blue `#8ba7bf` columns.

### `145:1174` budget or bar metric columns

Figma-native metadata:

- Title at `x=50.73`, `y=50.73`, size `96`.
- Five vertical blocks, each `w=364.05`, with staggered heights: `186.91`, `672.11`, `401.52`, `600.58`, `479.27`.
- Label text uses Plus Jakarta Sans Medium `48` with letter spacing `10`.
- Year labels use paragraph style at bottom.

PPT Master scaled geometry:

- Title `x=34`, `y=34`, size `64`.
- Bar width about `243`.
- Bar x positions about `269`, `511`, `753`, `995`, `1237`; last can crop intentionally if used as an off-canvas rhythm.
- Use actual chart data to set heights; preserve staggered colorblock look.

### `145:1215` phone showcase

Figma-native metadata:

- Green root with blue inset slab `x=56.39`, `y=50`, `w=1808.42`, `h=980`.
- Central phone frame group at `x=452.67`, `y=50`, `w=1015.87`, `h=980`.
- Left label at `x=53`, `y=413`, `w=481`; left body at `x=53`, `y=501`, `w=481`.
- Right label at `x=1387`, `y=780`, `w=478`; right body at `x=1387`, `y=868`, `w=478`.

PPT Master scaled geometry:

- Inset slab `x=38`, `y=33`, `w=1206`, `h=653`.
- Phone stage `x=302`, `y=33`, `w=677`, `h=653`.
- Left label `x=35`, `y=275`, `w=321`; right label `x=925`, `y=520`, `w=319`.

Design context confirmed device images are remote Figma MCP assets; generated SVG must use project-local images or drawn device frames instead.

### `145:1255` team roster

Figma-native metadata:

- Orange root.
- Title `x=50`, `y=50`, `w=1834`, size `96`.
- Blue team band `x=49.90`, `y=406.34`, `w=1833.97`, `h=623.66`.
- Four image slots from x about `50`, `502`, `959`, `1420`, y `406`, height `296`.
- Name labels use Plus Jakarta Medium `48`, uppercase, letter spacing `10`.
- Role/title labels use Paragraph 1.

PPT Master scaled geometry:

- Title `x=33`, `y=33`, size `64`.
- Blue band `x=33`, `y=271`, `w=1223`, `h=416`.
- Image slots `w=301..309`, `h=198`, y `271`.
- Name labels start around y `482`, size `32`, tracking `3.2`.

### `145:1314` closing

Figma-native metadata:

- Dark green root.
- `Thank you.` at `x=50`, `y=790`, `w=1820`, size `240`.
- Image at `x=1043.21`, `y=50.33`, `w=821.10`, `h=615.83`.

PPT Master scaled geometry:

- Closing title `x=33`, `y=527`, `w=1213`, size `160`.
- Image `x=696`, `y=34`, `w=547`, `h=411`.

## Additional Representative Patterns

### `145:1246` quote poster

- Orange root with blue inset panel `x=56.39`, `y=50`, `w=1808.42`, `h=980`.
- Quote text `x=90.77`, `y=69.22`, `w=1156.23`, size `96`.
- Outline quote-mark vector near top right.
- Author line right-aligned near lower right, Medium `48`, uppercase, tracking `10`.

### `145:1238` laptop showcase

- Green root with blue inset panel.
- Laptop group starts at `x=55.79`, `y=50`, fills the inset; device image strongly crops off the right.
- Left title `x=98.68`, `y=83.48`, size `80`.
- Left body `x=98.68`, bottom-aligned around `y=571`, width `605`, size `35`.

### `145:1087` icon text grid

- Blue root.
- Title at `x=56`, `y=50`, size `72`, uppercase.
- Left story paragraph at `x=56`, `y=324`, `w=640`, size `35`.
- Four outline glyphs plus small body copy blocks in the right two columns.
- Small body copy uses Paragraph 2, size `22`, line-height `1`.

## Capture Notes

- Screenshot evidence is local and durable.
- Figma MCP image URLs in design context are short-lived and are not suitable for final SVG.
- The final cookbook rewrites all remote images and vector assets into PPT-safe local image slots or simple SVG primitives.
