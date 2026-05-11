# Figma 65CM Default Capture Notes

Source Figma file: `65CMrCi7opIqi80NPrKFxu`

Requested nodes: `151:33`, `151:534`, `151:1062`, `151:1394`, `151:98`, `151:755`, `151:1900`, `151:179`, `151:1239`, `151:432`, `151:1182`, `151:267`, `151:327`, `151:1751`, `151:1469`, `151:1028`, `151:649`, `151:1595`, `151:489`, `151:976`, `151:1092`, `151:1538`, `151:879`, `151:1131`, `151:1319`, `151:1630`, `151:1681`, `151:1787`, `151:1833`.

Captured locally:
- `assets/screenshots/*.png`: 29 native 1920x1080 Figma screenshots.
- `assets/contact_sheet.png`: visual audit sheet for all requested frames.
- `assets/figma_assets/*.png`: downloaded representative reusable Figma assets from design-context asset constants.

Figma MCP evidence:
- `whoami` verified Figma access as `7142698286@featherstoneacademy.org.uk`.
- `get_screenshot` succeeded for all 29 frames.
- `use_figma` compact aggregate extraction found the dominant colors, fonts, image counts, text samples, and node type counts across all frames.
- `get_variable_defs` on representative pages exposed named color/font variables: `Color 1 #ffffff`, `Color 2 #000000`, `Color 4 #ff6400`, `Color 8 #f2f2f2`, `Color 9 #007a73`, `Color 10 #2b01be`, plus Metropolis Caption/Body/Header styles.
- `get_metadata` was captured for representative strategic and financial-document pages to verify concrete Figma coordinates.
- `get_design_context` was captured for representative strategic, table/chart, team, and financial-document pages; one cover-page context timed out, but cover geometry was recoverable from screenshot plus `use_figma` extraction.

Limitations:
- Figma asset URLs are short-lived. Reusable assets were downloaded into `assets/figma_assets/` and final cookbook rules reference local asset names rather than URLs.
- Some design-context output was too large for full transcript preservation. The cookbook uses stable evidence from downloaded screenshots, local assets, compact extraction, variable definitions, and representative metadata.
- The reference is brand-specific. The cookbook preserves the design grammar but instructs generated PPTs to replace Pfizer/Merck literal branding with source-relevant labels unless the source explicitly asks for those brands.
