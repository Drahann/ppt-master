# MCP Design Context Samples

These notes preserve representative Figma MCP outputs for cookbook authoring. The raw `get_design_context` responses are too large to store wholesale in this chat, so this file records the implementation-relevant code patterns, geometry, typography, asset constants, and metadata that should inform the cookbook.

Source file: `65CMrCi7opIqi80NPrKFxu`

## What Figma MCP Returned

Tools used:
- `get_screenshot`: native 1920 x 1080 PNG screenshots for all 11 frames.
- `get_variable_defs`: variables for light, lime, dark, dashboard, and dense risk pages.
- `get_metadata`: XML-like structure with node IDs, layer names, positions, and sizes.
- `get_design_context`: React/Tailwind-style generated code with exact geometry classes, asset constants, node IDs, and style summaries.
- `use_figma`: custom compact extraction attempt. Full local POST export was not possible because the Figma plugin runtime in this environment did not expose `fetch`.

## Representative Code Patterns

### Lime agenda page, node `131:305`

Key returned details:
- Full-bleed lime background: `bg-[var(--color-3,#c7ef4e)]`.
- Display title: `Neuton:Light`, `200px`, dark green `#003310`, positioned at `left-[100px]`.
- Agenda list starts around the right half: `left-[calc(58.33%-2px)] top-[calc(25%+58px)]`.
- Repeated agenda text uses `Open Sans Regular`, `36px`, tight negative tracking.
- Thin separators are line image assets returned as `imgLine2`; top chrome line returned as `imgLine7`.

Representative excerpt:

```tsx
const imgLine2 = "figma-mcp-asset-url";
const imgLine7 = "figma-mcp-asset-url";

<div className="bg-[var(--color-3,#c7ef4e)] relative size-full" data-node-id="131:305">
  <div className="absolute ... left-[100px] ... text-[200px] text-[color:var(--color-2,#003310)] tracking-[-4.4px]">
    <p className="leading-none">Agenda</p>
  </div>
  <div className="absolute content-stretch flex flex-col gap-[26px] items-start left-[calc(58.33%-2px)] top-[calc(25%+58px)]">
    <div className="font-['Open_Sans:Regular'] text-[36px] tracking-[-0.792px]">
      <p className="leading-[1.2]">Project Overview & Objectives</p>
    </div>
  </div>
</div>
```

### White dashboard/status page, node `131:401`

Key returned details:
- White background.
- Title: `Neuton Light`, `80px`, at `x=100 y=214`.
- Status pills: `146 x 43`, rounded `40px`, `Open Sans Regular 18px`.
- Complete pill uses dark green fill `#003310` with lime text.
- In-progress pills use lime fill `#c7ef4e` with black text.
- Not-started pill uses black fill with white text.
- Timeline bar at bottom: lime base `1720 x 32`, dark green progress overlay `1283 x 32`.
- Bottom labels use uppercase `Open Sans SemiBold 20px`.

Representative excerpt:

```tsx
<div className="bg-white relative size-full" data-node-id="131:401">
  <div className="absolute bg-[var(--color-3,#c7ef4e)] h-[32px] left-[100px] top-[calc(87.5%+29px)] w-[1720px]" />
  <div className="absolute bg-[var(--color-2,#003310)] h-[32px] left-[100px] top-[calc(87.5%+29px)] w-[1283px]" />
  <div className="absolute bg-[var(--color-2,#003310)] flex items-center justify-center rounded-[40px] w-[146px]">
    <div className="font-['Open_Sans:Regular'] text-[18px] text-[color:var(--color-3,#c7ef4e)]">Complete</div>
  </div>
</div>
```

### Dark risk/mitigation page, node `131:474`

Key returned details:
- Background is variable `White` but resolved to black in this file; cookbook should treat this as a dark page.
- Title: white `Neuton Light`, `80px`, at `x=100 y=192`.
- Dense row group starts at `x=100 y=344`, width about `1717`, height about `636`.
- Four repeated issue/mitigation rows, each roughly `1713 x 114`, vertical gap `60`.
- Left issue column width `724`; right mitigation column width `667`; gap about `322`.
- Issue headings use lime `#c7ef4e`, `Open Sans Regular`, `36px`.
- Body uses white, `Open Sans Regular`, `24px`, line-height `130%`.
- Lime arrow assets are returned as `imgArrow1`; top rules returned as line assets.

Representative excerpt:

```tsx
const imgArrow1 = "figma-mcp-asset-url";

<div className="bg-[var(--white,black)] relative size-full" data-node-id="131:474">
  <div className="absolute ... left-[100px] text-[80px] text-[color:var(--color,white)] tracking-[-1.6px]">
    <p className="leading-[1.1]">Issues and Mitigation Strategies</p>
  </div>
  <div className="absolute flex flex-col gap-[60px] left-[100px] top-[calc(25%+74px)]">
    <div className="flex gap-[322px] items-end">
      <div className="flex flex-col gap-[25px] w-[724px]">
        <p className="text-[36px] text-[color:var(--color-3,#c7ef4e)]">Supply Chain Disruption</p>
        <p className="text-[24px] text-[color:var(--color,white)]">Risk text...</p>
      </div>
      <p className="text-[24px] text-[color:var(--color,white)] w-[667px]">Mitigation text...</p>
    </div>
  </div>
</div>
```

## Representative Metadata Geometry

### Objectives metrics, node `131:352`

Important metadata:
- Three lime metric rectangles:
  - `x=81 y=663 w=565 h=301`
  - `x=669 y=663 w=565 h=301`
  - `x=1253 y=663 w=565 h=301`
- Title: `x=100 y=214 w=1717 h=88`.
- Top chrome: project name `x=100 y=46`, page number `x=1793 y=46`, rule `x=100 y=100 w=1717`.
- Three content columns begin around `x=101`, `x=684`, `x=1268`, each `~550px` wide.
- Column vertical rhythm: text block, `100px` gap, label + huge metric.

### Current status, node `131:401`

Important metadata:
- Title: `x=100 y=214 w=569 h=88`.
- Pill column at `x=700`, each pill `146 x 43`.
- Body text column at `x=878`, width `939`.
- Timeline/progress bar at `x=100 y=974`, base width `1720`, progress width `1283`, height `32`.

### Risks, node `131:474`

Important metadata:
- Title: `x=100 y=192 w=1137 h=88`.
- Row group: `x=100 y=344 w=1717 h=636`.
- Repeated rows:
  - left block width `724`
  - right block starts around `x=1046/1050`, width `667`
  - arrow vectors at `x=907`, width `152`.

## Variable Definitions Observed

Combined across sampled nodes:

```json
{
  "Color 2": "#003310",
  "Color 3": "#c7ef4e",
  "Color 4": "#7a7a7a",
  "Color": "#ffffff",
  "White": "#000000",
  "Title": "Neuton Light, 80, weight 300, lineHeight 110%, letterSpacing -2%",
  "Header": "Neuton Light, 200, weight 300, lineHeight 100%, letterSpacing -2.2%",
  "Body Large": "Open Sans Regular, 36, weight 400, lineHeight 120%, letterSpacing -2.2%",
  "Body Medium": "Open Sans Regular, 24, weight 400, lineHeight 130%, letterSpacing 0",
  "Body Small": "Open Sans Regular, 18, weight 400, lineHeight 130%, letterSpacing 0",
  "PADDING_TOP_BOTTOM": 128,
  "PADDING_LEFT_RIGHT": 168
}
```

Note: The variable named `White` resolves to `#000000` in sampled nodes. Cookbook should avoid relying on variable names alone; use resolved colors and semantic roles.

## Implications For Cookbook

- Store both screenshot evidence and MCP-derived geometry/code evidence.
- Use `get_design_context` for exact layout clues, but convert React/Tailwind examples into SVG/PPT grammar instead of treating them as implementation code.
- Use `get_metadata` to define geometry recipes because it is concise and stable.
- Use `get_variable_defs` for token names but verify resolved values visually.
- Do not preserve short-lived MCP asset URLs as source assets; download screenshots and restate line/arrow geometry in SVG-safe terms.
