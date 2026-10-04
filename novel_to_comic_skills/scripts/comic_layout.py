"""Page assembly/lettering and offline exports; illustration pixels are not redrawn."""
from __future__ import annotations

import html
import json
import math
import os
import zipfile
from pathlib import Path

LAYOUT_VERSION = 2
PAPER_COLOR = '#faf9f5'
INK_COLOR = '#2e3035'


def core():
    # Avoid a second __main__ module when invoked through the CLI.
    import sys
    main = sys.modules.get('__main__')
    if hasattr(main, 'GateError') and hasattr(main, 'accepted_panel'):
        return main
    import comic_pipeline
    return comic_pipeline


def layout_fingerprint(root, project):
    c = core()
    images = []
    for panel in project['script']['panels']:
        attempt = c.accepted_panel(root, project, panel)
        if not attempt:
            raise c.GateError('Missing, stale, or unreviewed illustration: ' + panel['id'])
        images.append((panel['id'], attempt['sha256']))
    return c.digest({'layout_version': LAYOUT_VERSION,
                     'title': project['title'], 'source_scope': project['source']['scope_note'],
                     'script': project['script'], 'images': images})


def find_font(explicit=None):
    candidates = [explicit] if explicit else []
    candidates += [os.environ.get('COMIC_FONT'), 'C:/Windows/Fonts/simhei.ttf',
                   '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
                   '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise core().GateError('CJK font missing. Supply --font with a font covering the dialogue language.')


def wrap_text(text, font, width):
    """Measured Unicode wrapping, keeping source characters and explicit newlines."""
    lines = []
    for paragraph in text.split('\n'):
        current = ''
        for character in paragraph:
            if font.getlength(character) > width:
                raise core().GateError('Lettering cell narrower than one glyph; increase page width.')
            if current and font.getlength(current + character) > width:
                lines.append(current)
                current = ''
            current += character
        lines.append(current)
    return lines


def panel_tile(root, project, panel, width, font_path, font_size):
    from PIL import Image, ImageDraw, ImageFont
    c = core()
    attempt = c.accepted_panel(root, project, panel)
    path = c.inside(root, attempt['path'])
    font = ImageFont.truetype(font_path, font_size)
    names = {item['id']: item['name'] for item in project['script']['characters']}
    blocks = []
    line_height = math.ceil(font_size * 1.4)
    padding = max(14, font_size // 2)
    stroke = max(1, round(width / 768))
    for dialogue in panel.get('dialogue', []):
        prefix = ''
        if dialogue['kind'] in ('speech', 'thought'):
            prefix = names[dialogue['speaker']] + (' · 内心' if dialogue['kind'] == 'thought' else '') + '：'
        text = prefix + dialogue['text']
        lines = wrap_text(text, font, width - padding * 4)
        blocks.append((dialogue, lines, line_height * len(lines) + padding * 2))
    with Image.open(path) as image:
        image = image.convert('RGB')
        picture_height = max(1, round(image.height * width / image.width))
        image = image.resize((width, picture_height), Image.Resampling.LANCZOS)
        band_height = sum(height + padding for _, _, height in blocks) + (padding if blocks else 0)
        tile = Image.new('RGB', (width, picture_height + band_height), PAPER_COLOR)
        tile.paste(image, (0, 0))
    draw = ImageDraw.Draw(tile)
    draw.rectangle((0, 0, width - 1, picture_height - 1), outline=INK_COLOR, width=stroke)
    y = picture_height + padding
    for dialogue, lines, height in blocks:
        bounds = (padding, y, width - padding - 1, y + height)
        if dialogue['kind'] == 'speech':
            # Separate text band protects faces. Explicit speaker labels keep dense exchanges unambiguous.
            anchor = dialogue.get('anchor', [0.5, 0.8])
            x = max(padding * 2, min(width - padding * 2, int(width * float(anchor[0]))))
            draw.polygon([(x - padding // 2, y), (x, max(5, picture_height - padding)),
                          (x + padding // 2, y)], fill='white', outline=INK_COLOR)
            draw.rounded_rectangle(bounds, radius=padding, fill='white', outline=INK_COLOR, width=stroke)
        elif dialogue['kind'] == 'thought':
            draw.rounded_rectangle(bounds, radius=padding * 2, fill='#f5f4f0', outline='#747069', width=stroke)
        else:
            draw.rectangle(bounds, fill='#eeece6', outline='#89867e', width=stroke)
        for number, line in enumerate(lines):
            draw.text((padding * 2, y + padding + number * line_height), line, font=font, fill='#25262a', anchor='lt')
        y += height + padding
    return tile


def compose(root, project, explicit_font=None):
    from PIL import Image, ImageDraw, ImageFont
    c = core()
    fingerprint = layout_fingerprint(root, project)
    style = project['script']['style']
    width = int(style.get('width', 1536))
    size = int(style.get('font_size', 46))
    if width < 600 or width > 6000 or size < 16 or size > width // 8:
        raise c.GateError('Page width/font size invalid for readable layout.')
    font_path = find_font(explicit_font or style.get('font_path'))
    # Check cmap for all emitted characters, including speaker labels, before rendering.
    try:
        from reportlab.pdfbase.ttfonts import TTFont
        font = TTFont('comic-font-coverage', font_path, subfontIndex=0)
        cmap = font.face.charToGlyph
        texts = [project['title']] + [x['title'] for x in project['source']['chapters']]
        texts += [x['name'] for x in project['script']['characters']]
        texts += [d['text'] for p in project['script']['panels'] for d in p.get('dialogue', [])]
        missing = {ch for text in texts for ch in text if not ch.isspace() and ord(ch) not in cmap}
        if missing:
            raise c.GateError('Chosen font lacks glyphs: ' + ''.join(sorted(missing))[:80])
    except ImportError as error:
        raise c.GateError('Font coverage verification requires reportlab in the layout runtime.') from error
    panels = {p['id']: p for p in project['script']['panels']}
    chapters = {c['id']: c for c in project['source']['chapters']}
    margin, gutter = max(28, width // 28), max(18, width // 55)
    title_size = max(16, round(size * 0.85))
    title_font = ImageFont.truetype(font_path, title_size)
    rendered, order = [], 0
    for page in project['script']['pages']:
        rows = []
        for ids in c.page_rows(page):
            columns = len(ids)
            cell_width = (width - 2 * margin - (columns - 1) * gutter) // columns
            tiles = [panel_tile(root, project, panels[pid], cell_width, font_path, size) for pid in ids]
            rows.append((ids, tiles, max(t.height for t in tiles)))
        max_height = int(style.get('max_segment_height', 6000))
        header = margin + title_size * 2 + gutter
        segments, current, current_height = [], [], header + margin
        for row in rows:
            if row[2] + header + margin > max_height:
                raise c.GateError('A row is too tall; re-plan layout/panel ratio without deleting dialogue.')
            if current and current_height + row[2] + gutter > max_height:
                segments.append(current)
                current, current_height = [], header + margin
            current_height += row[2] + (gutter if current else 0)
            current.append(row)
        if current:
            segments.append(current)
        for segment_number, segment in enumerate(segments, 1):
            order += 1
            height = header + margin + sum(row[2] for row in segment) + gutter * (len(segment) - 1)
            if style['format'] == 'pages':
                height = max(height, int(style.get('height', 2176)))
            canvas = Image.new('RGB', (width, height), PAPER_COLOR)
            draw = ImageDraw.Draw(canvas)
            title = chapters[page['chapter_id']]['title']
            # Header wraps too; titles are never clipped.
            title_lines = wrap_text(title, title_font, width - 2 * margin)
            if len(title_lines) > 2:
                raise c.GateError('Chapter title exceeds header; use a wider page or smaller header font.')
            for i, line in enumerate(title_lines):
                draw.text((margin, margin + i * title_size), line, font=title_font, fill='#5b5c60', anchor='lt')
            y, included = header, []
            for ids, tiles, row_height in segment:
                indexes = list(range(len(tiles)))
                if style['reading_direction'] == 'rtl':
                    indexes.reverse()
                for position, index in enumerate(indexes):
                    canvas.paste(tiles[index], (margin + position * (tiles[index].width + gutter), y))
                included.extend(ids)
                y += row_height + gutter
            identifier = page['id'] + (f'-s{segment_number:03d}' if len(segments) > 1 else '')
            suffix = c.digest({'input': fingerprint, 'font': c.sha_file(font_path), 'id': identifier})[:12]
            relative = f'pages/{order:06d}-{identifier}-{suffix}.png'
            path = c.inside(root, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                canvas.save(path, 'PNG')
            rendered.append({'id': identifier, 'order': order, 'chapter_id': page['chapter_id'],
                             'panel_ids': included, 'path': relative, 'sha256': c.sha_file(path),
                             'width': width, 'height': height})
    return {'input_hash': fingerprint, 'font_path': font_path, 'font_sha256': c.sha_file(font_path),
            'pages': rendered, 'qa': None}


def export(root, project):
    c = core()
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    root = Path(root)
    layout = project['layout']
    fingerprint = layout['input_hash']
    destination = root / 'exports' / fingerprint[:12]
    destination.mkdir(parents=True, exist_ok=True)
    title = project['title']
    pages = layout['pages']
    # file:// compatible: manifest is embedded; no fetch, server, CDN or third-party script.
    cards = ''.join('<figure data-chapter="' + html.escape(page['chapter_id'], quote=True) + '">'
                    '<img loading="lazy" src="../../' + html.escape(page['path'], quote=True) +
                    '" alt="第' + str(page['order']) + '页"><figcaption>' + str(page['order']) +
                    ' / ' + str(len(pages)) + '</figcaption></figure>' for page in pages)
    used = {p['chapter_id'] for p in pages}
    options = '<option value="">全部章节</option>' + ''.join(
        '<option value="' + html.escape(ch['id'], quote=True) + '">' + html.escape(ch['title']) + '</option>'
        for ch in project['source']['chapters'] if ch['id'] in used)
    reader = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    reader += '<title>' + html.escape(title) + '</title><style>body{margin:0;background:#202329;color:#eee;font:16px system-ui}'
    reader += 'header{position:sticky;top:0;background:#202329;padding:12px;z-index:1}h1{font-size:18px;margin:0 0 8px}'
    reader += 'main{max-width:1000px;margin:auto}figure{margin:16px 0}img{display:block;width:100%;height:auto}'
    reader += 'figcaption{text-align:center;padding:8px}select,button{font:inherit;margin-right:8px}a{color:#a9d6ff}</style>'
    reader += '<header><h1>' + html.escape(title) + '</h1><select id="chapter">' + options + '</select>'
    reader += '<button id="zoom">放大 / 适合屏幕</button><a href="comic.pdf">PDF</a> · <a href="comic.cbz">CBZ</a></header>'
    reader += '<main>' + cards + '</main><script>document.getElementById("chapter").onchange=function(){'
    reader += 'document.querySelectorAll("figure").forEach(f=>f.hidden=!!this.value&&f.dataset.chapter!==this.value);scrollTo(0,0)};'
    reader += 'document.getElementById("zoom").onclick=()=>{const m=document.querySelector("main");m.style.maxWidth=m.style.maxWidth?"":"none"};'
    reader += '</script></html>'
    reader_path = destination / 'reader.html'
    reader_path.write_text(reader, encoding='utf-8')
    pdf_path = destination / 'comic.pdf'
    pdf = canvas.Canvas(str(pdf_path))
    pdf.setTitle(title)
    for page in pages:
        w, h = page['width'] / 2, page['height'] / 2
        pdf.setPageSize((w, h))
        pdf.drawImage(ImageReader(str(c.inside(root, page['path']))), 0, 0, width=w, height=h)
        pdf.showPage()
    pdf.save()
    cbz_path = destination / 'comic.cbz'
    with zipfile.ZipFile(cbz_path, 'w', compression=zipfile.ZIP_STORED) as archive:
        for page in pages:
            archive.write(c.inside(root, page['path']), f'{page["order"]:06d}.png')
        info = '<ComicInfo><Title>' + html.escape(title) + '</Title><PageCount>' + str(len(pages)) + '</PageCount></ComicInfo>'
        archive.writestr('ComicInfo.xml', info)
    records = []
    for kind, path in [('reader', reader_path), ('pdf', pdf_path), ('cbz', cbz_path)]:
        records.append({'kind': kind, 'path': path.relative_to(root).as_posix(), 'sha256': c.sha_file(path)})
    return {'input_hash': fingerprint, 'page_count': len(pages), 'files': records}


def verify_exports(root, project):
    c = core()
    from pypdf import PdfReader
    from PIL import Image
    exports, layout = project.get('exports'), project.get('layout')
    fingerprint = layout_fingerprint(root, project)
    if not exports or not layout or exports['input_hash'] != fingerprint or layout['input_hash'] != fingerprint:
        raise c.GateError('Exports missing/stale.')
    if not layout.get('qa') or layout['qa'].get('input_hash') != fingerprint:
        raise c.GateError('Current page review missing.')
    c.validate_qa(layout['qa'], c.LAYOUT_CHECKS)
    ordered = []
    for page in layout['pages']:
        path = c.inside(root, page['path'])
        if not path.is_file() or c.sha_file(path) != page['sha256']:
            raise c.GateError('Final page missing/changed.')
        with Image.open(path) as image:
            if image.size != (page['width'], page['height']):
                raise c.GateError('Final page dimensions changed.')
            image.verify()
        ordered.extend(page['panel_ids'])
    if ordered != [p['id'] for p in project['script']['panels']]:
        raise c.GateError('Final page manifest omits/reorders/duplicates panels.')
    files = {f['kind']: f for f in exports['files']}
    if set(files) != {'reader', 'pdf', 'cbz'}:
        raise c.GateError('Reader/PDF/CBZ all required.')
    for item in files.values():
        path = c.inside(root, item['path'])
        if not path.is_file() or c.sha_file(path) != item['sha256']:
            raise c.GateError('Export missing/changed: ' + item['kind'])
    reader = c.inside(root, files['reader']['path']).read_text(encoding='utf-8')
    if any('../../' + html.escape(p['path'], quote=True) not in reader for p in layout['pages']):
        raise c.GateError('Offline reader misses a page.')
    pdf_pages = len(PdfReader(c.inside(root, files['pdf']['path'])).pages)
    if pdf_pages != len(layout['pages']):
        raise c.GateError('PDF page count mismatch.')
    with zipfile.ZipFile(c.inside(root, files['cbz']['path'])) as archive:
        names = [n for n in archive.namelist() if n.endswith('.png')]
        expected = [f'{p["order"]:06d}.png' for p in layout['pages']]
        if names != expected or archive.testzip() is not None:
            raise c.GateError('CBZ page order/integrity mismatch.')
        for name, page in zip(names, layout['pages']):
            if hashlib_bytes(archive.read(name)) != page['sha256']:
                raise c.GateError('CBZ image differs from the reviewed page.')
    return {'ok': True, 'page_count': pdf_pages, 'formats': ['png', 'reader', 'pdf', 'cbz']}


def hashlib_bytes(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()
