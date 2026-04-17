import os, re, xml.etree.ElementTree as ET

d = r'W:\AIPPT cli\ppt-master\projects\debugtxt_runner_3_ppt169_20260416\svg_output'
files = sorted([f for f in os.listdir(d) if f.endswith('.svg')])
print(f'Total SVG files: {len(files)}')

for f in files:
    path = os.path.join(d, f)
    with open(path, 'r', encoding='utf-8') as fh:
        content = fh.read()
    
    issues = []
    
    try:
        ET.parse(path)
    except ET.ParseError as e:
        issues.append(f'XML error: {e}')
    
    for banned in ['<mask', '<foreignObject', 'textPath', '<animate', '<script', '@font-face', '<iframe', 'rgba(']:
        if banned in content:
            issues.append(f'Banned: {banned}')
    
    style_tags = re.findall(r'<style[^>]*>.*?</style>', content, re.DOTALL)
    if style_tags:
        issues.append('Has style tag')
    
    class_attrs = re.findall(r'\bclass="[^"]*"', content)
    if class_attrs:
        issues.append(f'Has class: {class_attrs[:2]}')
    
    has_icon = 'data-icon=' in content
    icon_refs = re.findall(r'data-icon="([^"]+)"', content)
    non_chunk = [i for i in icon_refs if not i.startswith('chunk/')]
    if non_chunk:
        issues.append(f'Non-chunk: {non_chunk}')
    
    status = 'ISSUES: ' + '; '.join(issues) if issues else ('OK' + (f' ({len(icon_refs)} icons)' if has_icon else ' (no icons)'))
    print(f'  {f}: {status}')

# Check notes
notes_path = r'W:\AIPPT cli\ppt-master\projects\debugtxt_runner_3_ppt169_20260416\notes\total.md'
if os.path.exists(notes_path):
    with open(notes_path, 'r', encoding='utf-8') as fh:
        notes = fh.read()
    headings = re.findall(r'^# (.+)$', notes, re.MULTILINE)
    print(f'Notes headings: {len(headings)}')
    expected = ['slide_01_cover','slide_02_content_01','slide_03_content_02','slide_04_content_03','slide_05_content_04','slide_06_content_05','slide_07_content_06','slide_08_content_07','slide_09_content_08','slide_10_content_09','slide_11_content_10','slide_12_content_11','slide_13_content_12','slide_14_content_13','slide_15_content_14','slide_16_content_15','slide_17_content_16','slide_18_content_17','slide_19_content_18','slide_20_content_19','slide_21_content_20','slide_22_content_21','slide_23_content_22','slide_24_content_23','slide_25_content_24','slide_26_content_25','slide_27_content_26','slide_28_content_27','slide_29_content_28','slide_30_content_29','slide_31_content_30','slide_32_ending']
    for i, (h, e) in enumerate(zip(headings, expected)):
        if h != e:
            print(f'  MISMATCH #{i+1}: got "{h}" expected "{e}"')
    if headings == expected:
        print('  All headings match!')
else:
    print('Notes file missing!')
