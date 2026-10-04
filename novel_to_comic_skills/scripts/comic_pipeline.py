#!/usr/bin/env python3
"""Deterministic gates and artifact accounting; no model/API calls are made here."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from comic_sources import SourceError, extract, sha_file

SCHEMA_VERSION = 1
REVIEW_CHECKS = {
    'coverage': ['all_source_read', 'events_preserved', 'arcs_preserved', 'ending_preserved'],
    'continuity': ['causality', 'timeline', 'identity', 'states', 'knowledge_and_reveals'],
    'comic': ['drawable_panels', 'dialogue_and_speakers', 'reading_order', 'pacing', 'text_density'],
}
PANEL_CHECKS = ['identity', 'continuity', 'composition', 'drawing_quality', 'no_unwanted_text']
REFERENCE_CHECKS = ['identity', 'distinctiveness', 'angles_and_expressions', 'source_faithfulness']
LAYOUT_CHECKS = ['text_accuracy', 'reading_order', 'speaker_assignment', 'face_visibility']


class GateError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def inside(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise GateError('Artifact path escapes the project directory.')
    return target


def project_load(root):
    project = load_json(Path(root) / 'project.json')
    if project.get('schema_version') != SCHEMA_VERSION:
        raise GateError('Unsupported project schema; preserve project and migrate explicitly.')
    return project


def save(root, project):
    project['updated_at'] = now()
    atomic_json(Path(root) / 'project.json', project)


def index_hash(source):
    return digest({'files': source['files'], 'units': source['units'], 'chapters': [
        {key: chapter[key] for key in ('id', 'title', 'unit_ids', 'has_body')}
        for chapter in source['chapters']]})


def source_errors(project):
    source = project['source']
    errors = []
    if index_hash(source) != project['source_index_hash']:
        errors.append('Source index changed; re-ingest rather than editing extracted source facts.')
    for item in source['files']:
        path = Path(item['path'])
        if not path.is_file() or sha_file(path) != item['sha256']:
            errors.append('Source missing or changed: ' + str(path))
    if not source['confirmed']:
        errors.append('Source completeness has not been checked.')
    errors.extend('Unresolved extraction issue: ' + item['id'] for item in source['issues'] if not item['resolved'])
    return errors


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def page_rows(page):
    """Return narrative row order; single-panel rows occupy the full width."""
    columns = page.get('columns', 1)
    if type(columns) is not int or columns not in (1, 2):
        raise GateError('Page columns must be 1 or 2.')
    pids = page.get('panel_ids')
    if not isinstance(pids, list) or not pids or any(not nonempty(pid) for pid in pids):
        raise GateError('Page needs a nonempty panel_ids array.')
    if 'rows' not in page:
        return [pids[start:start + columns] for start in range(0, len(pids), columns)]
    rows = page['rows']
    if (not isinstance(rows, list) or not rows or
            any(not isinstance(row, list) or len(row) not in (1, 2) or
                any(not nonempty(pid) for pid in row) for row in rows)):
        raise GateError('Page rows must contain one or two panel IDs per row.')
    if [pid for row in rows for pid in row] != pids:
        raise GateError('Page rows must match panel_ids exactly in reading order.')
    return rows


def script_errors(project):
    """Structural checks cannot establish fidelity, art quality, or review truthfulness."""
    errors = source_errors(project)
    source, script = project['source'], project['script']
    for chapter in source['chapters']:
        if chapter['has_body'] and (not chapter['read'] or not nonempty(chapter['read_note'])):
            errors.append('Unread chapter: ' + chapter['id'])
    for field in ('outline', 'ending'):
        if not nonempty(script.get(field)):
            errors.append('Missing full-book ' + field)
    style = script.get('style', {})
    for key in ('genre', 'look', 'palette', 'selection_reason'):
        if not nonempty(style.get(key)):
            errors.append('Style missing: ' + key)
    if style.get('format') not in ('pages', 'strip') or style.get('reading_direction') not in ('ltr', 'rtl'):
        errors.append('Style format/reading direction invalid.')
    lists = ['characters', 'settings', 'events', 'scenes', 'panels', 'pages']
    registries = {}
    for key in lists:
        items = script.get(key, [])
        if not isinstance(items, list):
            errors.append('Script ' + key + ' must be an array.')
            items = []
        identifiers = [item.get('id') for item in items if isinstance(item, dict)]
        if len(identifiers) != len(items) or any(not nonempty(i) for i in identifiers) or len(set(identifiers)) != len(identifiers):
            errors.append('Missing or duplicate IDs in ' + key)
        registries[key] = {item.get('id'): item for item in items if isinstance(item, dict)}
    units = {item['id']: item for item in source['units']}
    chapters = {item['id']: item for item in source['chapters']}
    covered, chapter_panels, used_events = set(), set(), set()
    for character in registries['characters'].values():
        if not nonempty(character.get('name')):
            errors.append('Character missing name.')
        if character.get('importance') not in ('major', 'supporting', 'minor'):
            errors.append('Character importance invalid: ' + str(character.get('id')))
        for key in ('goal', 'motivation', 'voice', 'arc'):
            if not nonempty(character.get('narrative', {}).get(key)):
                errors.append('Character narrative missing ' + key + ': ' + str(character.get('id')))
        for key in ('face_shape', 'eyes', 'brows', 'nose_mouth', 'body', 'posture', 'hair', 'age'):
            if not nonempty(character.get('visual', {}).get(key)):
                errors.append('Character visual missing ' + key + ': ' + str(character.get('id')))
        if not isinstance(character.get('source_facts'), list) or not isinstance(character.get('design_notes'), list):
            errors.append('Separate source_facts and design_notes arrays are required.')
        for fact in character.get('source_facts', []):
            if not nonempty(fact.get('text')) or not fact.get('source_unit_ids') or any(u not in units for u in fact['source_unit_ids']):
                errors.append('Character source fact has no valid evidence.')
    for event in registries['events'].values():
        if not nonempty(event.get('description')) or not event.get('source_unit_ids') or any(u not in units for u in event['source_unit_ids']):
            errors.append('Event has no valid source evidence: ' + str(event.get('id')))
    for scene in registries['scenes'].values():
        if scene.get('chapter_id') not in chapters or scene.get('setting_id') not in registries['settings']:
            errors.append('Scene chapter/setting invalid: ' + str(scene.get('id')))
    previous_states = {}
    for panel in script.get('panels', []):
        pid = str(panel.get('id'))
        chapter = panel.get('chapter_id')
        scene = registries['scenes'].get(panel.get('scene_id'))
        if chapter not in chapters or not chapters.get(chapter, {}).get('has_body'):
            errors.append('Panel belongs to absent/empty chapter: ' + pid)
        if scene is None or scene.get('chapter_id') != chapter:
            errors.append('Panel scene invalid: ' + pid)
        chapter_panels.add(chapter)
        for key in ('action', 'shot', 'space', 'expression'):
            if not nonempty(panel.get(key)):
                errors.append('Panel missing ' + key + ': ' + pid)
        if 'visual_plan' in panel and not isinstance(panel['visual_plan'], dict):
            errors.append('Panel visual_plan must be an object: ' + pid)
        source_ids = panel.get('source_unit_ids', [])
        if not source_ids or any(u not in units for u in source_ids):
            errors.append('Panel source evidence invalid: ' + pid)
        covered.update(u for u in source_ids if u in units)
        for event_id in panel.get('event_ids', []):
            event = registries['events'].get(event_id)
            if event is None or not set(event['source_unit_ids']).issubset(source_ids):
                errors.append('Panel event evidence invalid: ' + pid)
            used_events.add(event_id)
        cast = panel.get('cast', [])
        if len(cast) != len(set(cast)) or any(c not in registries['characters'] for c in cast):
            errors.append('Panel cast invalid: ' + pid)
        for character in cast:
            before = panel.get('state_before', {}).get(character)
            after = panel.get('state_after', {}).get(character)
            if not isinstance(before, dict) or not before or not isinstance(after, dict) or not after:
                errors.append('Panel needs explicit before/after states: ' + pid)
                continue
            previous = previous_states.get(character, {})
            changed = [key for key in previous.keys() & before.keys() if previous[key] != before[key]]
            if changed:
                transitions = panel.get('state_transitions', [])
                justified = set()
                for transition in transitions:
                    if transition.get('character_id') == character and nonempty(transition.get('reason')) and transition.get('source_unit_ids') and all(u in units for u in transition['source_unit_ids']):
                        justified.update(transition.get('fields', []))
                if not set(changed).issubset(justified):
                    errors.append('Unexplained between-panel state change: ' + pid + '/' + character)
            previous_states[character] = after
        for dialogue in panel.get('dialogue', []):
            if dialogue.get('kind') not in ('speech', 'thought', 'caption', 'sfx') or not nonempty(dialogue.get('text')):
                errors.append('Invalid dialogue: ' + pid)
            if dialogue.get('kind') in ('speech', 'thought') and dialogue.get('speaker') not in cast:
                errors.append('Dialogue speaker not in cast: ' + pid)
    for disposition in script.get('source_dispositions', []):
        uid = disposition.get('unit_id')
        if uid not in units or disposition.get('kind') not in ('context', 'repetition', 'paratext') or not nonempty(disposition.get('reason')):
            errors.append('Invalid source disposition.')
        elif disposition['kind'] == 'context' and (not disposition.get('panel_ids') or any(p not in registries['panels'] for p in disposition['panel_ids'])):
            errors.append('Visual context requires real panel references.')
        else:
            covered.add(uid)
    for unit in units.values():
        if unit['kind'] == 'body' and unit['id'] not in covered:
            errors.append('Unmapped original text: ' + unit['id'])
    for chapter in chapters.values():
        if chapter['has_body'] and chapter['id'] not in chapter_panels:
            errors.append('Chapter has no full panel script: ' + chapter['id'])
    for eid in registries['events']:
        if eid not in used_events:
            errors.append('Event has no panel: ' + eid)
    page_panels = []
    for page in script.get('pages', []):
        pids = page.get('panel_ids', [])
        if not pids or any(p not in registries['panels'] for p in pids):
            errors.append('Page references missing panels.')
        if page.get('chapter_id') not in chapters or any(registries['panels'].get(p, {}).get('chapter_id') != page.get('chapter_id') for p in pids):
            errors.append('Page crosses/omits its chapter.')
        try:
            page_rows(page)
        except GateError as error:
            errors.append(str(error))
        page_panels.extend(pids)
    if page_panels != [p['id'] for p in script.get('panels', [])]:
        errors.append('Pages must cover all panels exactly once in script reading order.')
    if not registries['panels'] or not registries['pages']:
        errors.append('Complete drawable panels and page plan required.')
    return errors


def validate_qa(report, required):
    if not isinstance(report, dict) or not nonempty(report.get('evidence')):
        raise GateError('QA requires actual visual/read evidence, not an unexplained pass.')
    checks = report.get('checks', {})
    if any(checks.get(key) is not True for key in required):
        raise GateError('QA not passed: ' + ', '.join(k for k in required if checks.get(k) is not True))


def assert_script_lock(project):
    errors = script_errors(project)
    lock = project.get('script_lock')
    if not lock or lock.get('script_hash') != digest(project['script']) or lock.get('source_index_hash') != project['source_index_hash']:
        errors.append('Full-script lock missing or stale; no drawing is allowed.')
    if lock and lock.get('reviews_hash') != digest(project['reviews']):
        errors.append('Review records changed after script lock.')
    if errors:
        raise GateError('\n'.join(errors))


def design_hash(project, character_ids):
    characters = {c['id']: c for c in project['script']['characters']}
    return digest({'style': project['script']['style'], 'characters': [characters[c] for c in sorted(character_ids)]})


def valid_reference(root, project, reference):
    try:
        validate_qa(reference['qa'], REFERENCE_CHECKS)
        path = inside(root, reference['path'])
        return (reference['design_hash'] == design_hash(project, reference['character_ids']) and path.is_file()
                and sha_file(path) == reference['sha256'])
    except (KeyError, GateError):
        return False


def select_references(root, project, panel):
    selected = []
    for character in panel['cast']:
        choices = [r for r in project['art']['references'] if character in r['character_ids'] and valid_reference(root, project, r)]
        if not choices:
            raise GateError('No valid visually reviewed reference for character: ' + character)
        ref = choices[-1]
        if ref not in selected:
            selected.append(ref)
    return selected


def render_hash(project, panel, references):
    # Dialogue-only edits reflow pages without discarding unchanged paintings.
    visual = {key: panel.get(key) for key in ('id', 'scene_id', 'cast', 'action', 'shot', 'space', 'expression', 'state_before', 'state_after')}
    if 'visual_plan' in panel:
        visual['visual_plan'] = panel['visual_plan']
    scenes = {s['id']: s for s in project['script']['scenes']}
    settings = {s['id']: s for s in project['script']['settings']}
    scene = scenes[panel['scene_id']]
    return digest({'visual': visual, 'scene': scene, 'setting': settings[scene['setting_id']],
                   'style': project['script']['style'], 'refs': [(r['id'], r['sha256'], r['design_hash']) for r in references]})


def accepted_panel(root, project, panel):
    try:
        references = select_references(root, project, panel)
        fingerprint = render_hash(project, panel, references)
        attempts = project['art']['panels'].get(panel['id'], [])
        for attempt in reversed(attempts):
            if attempt['status'] == 'accepted' and attempt['render_hash'] == fingerprint:
                validate_qa(attempt['qa'], PANEL_CHECKS)
                path = inside(root, attempt['path'])
                prompt = inside(root, attempt['prompt_path'])
                if path.is_file() and sha_file(path) == attempt['sha256'] and prompt.is_file() and sha_file(prompt) == attempt['prompt_sha256']:
                    return attempt
    except (KeyError, GateError):
        pass
    return None


def copy_image(root, original, category):
    from PIL import Image
    original = Path(original).resolve()
    with Image.open(original) as image:
        image.verify()
    filename = uuid.uuid4().hex[:12] + original.suffix.lower()
    relative = str(Path('art') / category / filename).replace('\\', '/')
    target = inside(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, target)
    return relative, sha_file(target)


def script_markdown(project):
    script = project['script']
    chapters = {c['id']: c for c in project['source']['chapters']}
    names = {c['id']: c['name'] for c in script['characters']}
    parts = ['# ' + project['title'] + ' · 通篇漫画剧本', '', '剧本指纹：' + digest(script), '',
             '## 全书结构', script['outline'], '', '## 原文收尾', script['ending'], '']
    previous = None
    for panel in script['panels']:
        if panel['chapter_id'] != previous:
            parts += ['## ' + chapters[panel['chapter_id']]['title'], '']
            previous = panel['chapter_id']
        parts += ['### ' + panel['id'], '原文：' + ', '.join(panel['source_unit_ids']),
                  '镜头：' + panel['shot'], '空间：' + panel['space'], '动作：' + panel['action'],
                  '表情：' + panel['expression'], '人物状态：' + json.dumps(
                      {'before': panel['state_before'], 'after': panel['state_after']}, ensure_ascii=False)]
        for dialogue in panel.get('dialogue', []):
            parts.append(dialogue['kind'] + ' / ' + names.get(dialogue.get('speaker'), '旁白') + '：' + dialogue['text'])
        parts.append('')
    return '\n'.join(parts) + '\n'


def run(args):
    root = Path(args.project).resolve()
    command = args.command
    if command == 'init':
        if root.exists() and any(root.iterdir()):
            raise GateError('Project directory must be new/empty; use status for existing projects.')
        source = extract(args.source)
        template = load_json(Path(__file__).resolve().parents[1] / 'assets' / 'script-template.json')
        root.mkdir(parents=True, exist_ok=True)
        project = {'schema_version': SCHEMA_VERSION, 'title': args.title or Path(args.source[0]).stem,
                   'created_at': now(), 'source': source, 'source_index_hash': index_hash(source),
                   'script': template, 'reviews': [], 'script_lock': None,
                   'art': {'references': [], 'panels': {}}, 'layout': None, 'exports': None, 'final_review': None}
        for chapter in source['chapters']:
            text = '\n'.join(u['text'] for u in source['units'] if u['chapter_id'] == chapter['id'])
            target = inside(root, 'source/' + chapter['id'] + '.txt')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text + '\n', encoding='utf-8')
        save(root, project)
        return {'project': str(root), 'chapters': len(source['chapters']), 'issues': source['issues']}
    project = project_load(root)
    if command == 'chapter':
        return [u for u in project['source']['units'] if not args.chapter or u['chapter_id'] == args.chapter]
    if command == 'resolve-issue':
        issue = next((i for i in project['source']['issues'] if i['id'] == args.id), None)
        if not issue or not nonempty(args.evidence):
            raise GateError('Issue ID and concrete verification evidence required.')
        issue.update(resolved=True, evidence=args.evidence)
    elif command == 'confirm-source':
        if any(not i['resolved'] for i in project['source']['issues']) or not nonempty(args.note):
            raise GateError('Resolve every extraction issue and record completeness evidence first.')
        project['source'].update(confirmed=True, confirmation_note=args.note)
        if args.scope:
            project['source']['scope_note'] = args.scope
    elif command == 'mark-read':
        chapter = next((c for c in project['source']['chapters'] if c['id'] == args.chapter), None)
        if chapter is None or not nonempty(args.note):
            raise GateError('Existing chapter ID and actual reading note required.')
        chapter.update(read=True, read_note=args.note)
    elif command == 'set-script':
        script = load_json(args.file)
        if not isinstance(script, dict):
            raise GateError('Script must be a JSON object.')
        if digest(script) != digest(project['script']):
            project['script_lock'] = None
        project['script'] = script
    elif command == 'check-script':
        errors = script_errors(project)
        return {'script_hash': digest(project['script']), 'errors': errors[:100], 'error_count': len(errors),
                'semantic_review_required': True}
    elif command == 'review':
        errors = script_errors(project)
        if errors:
            raise GateError('\n'.join(errors))
        report = load_json(args.file)
        if report.get('script_hash') != digest(project['script']):
            raise GateError('Review must explicitly bind the current script_hash.')
        validate_qa(report, REVIEW_CHECKS[args.kind])
        body_chapters = {c['id'] for c in project['source']['chapters'] if c['has_body']}
        if set(report.get('reviewed_chapter_ids', [])) != body_chapters:
            raise GateError('Review must cover every chapter with body text.')
        if any(not i.get('resolved') for i in report.get('issues', []) if i.get('severity') in ('critical', 'major')):
            raise GateError('Resolve important review findings before passing.')
        project['reviews'].append({**report, 'kind': args.kind, 'recorded_at': now()})
        project['script_lock'] = None
    elif command == 'lock-script':
        errors = script_errors(project)
        fingerprint = digest(project['script'])
        for kind in REVIEW_CHECKS:
            if not any(r['kind'] == kind and r['script_hash'] == fingerprint for r in project['reviews']):
                errors.append('Missing current full-book review: ' + kind)
        if errors:
            raise GateError('\n'.join(errors))
        project['script_lock'] = {'script_hash': fingerprint, 'source_index_hash': project['source_index_hash'],
                                  'reviews_hash': digest(project['reviews']), 'locked_at': now()}
        (root / 'full-script.md').write_text(script_markdown(project), encoding='utf-8')
    elif command == 'assert-art':
        assert_script_lock(project)
        return {'allowed': True, 'script_hash': project['script_lock']['script_hash']}
    elif command == 'register-reference':
        assert_script_lock(project)
        ids = args.characters or []
        known = {c['id'] for c in project['script']['characters']}
        if not ids or any(c not in known for c in ids):
            raise GateError('Reference must identify existing characters.')
        report = load_json(args.qa)
        validate_qa(report, REFERENCE_CHECKS)
        path, sha = copy_image(root, args.file, 'references')
        project['art']['references'].append({'id': 'ref' + uuid.uuid4().hex[:12], 'character_ids': ids,
                    'design_hash': design_hash(project, ids), 'path': path, 'sha256': sha, 'qa': report, 'at': now()})
    elif command == 'begin-panel':
        assert_script_lock(project)
        panel = next((p for p in project['script']['panels'] if p['id'] == args.panel), None)
        if panel is None:
            raise GateError('Panel ID missing.')
        accepted = accepted_panel(root, project, panel)
        if accepted:
            return {'already_accepted': True, 'path': str(inside(root, accepted['path']))}
        references = select_references(root, project, panel)
        fingerprint = render_hash(project, panel, references)
        attempts = project['art']['panels'].setdefault(panel['id'], [])
        relevant = [a for a in attempts if a['render_hash'] == fingerprint]
        if any(a['status'] == 'pending' for a in relevant):
            raise GateError('Unfinished attempt exists; finish/fail it before another image call.')
        if len(relevant) >= 3:
            raise GateError('Three attempts exhausted for these visual inputs; intervention is required.')
        prompt = Path(args.prompt).read_text(encoding='utf-8-sig')
        if not nonempty(prompt):
            raise GateError('Persist a real drawing prompt before calling image generation.')
        number = len(attempts) + 1
        prompt_path = f'prompts/{panel["id"]}-{number:03d}.txt'
        target = inside(root, prompt_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(prompt, encoding='utf-8')
        attempt = {'number': number, 'status': 'pending', 'render_hash': fingerprint,
                   'created_script_hash': digest(project['script']), 'prompt_path': prompt_path,
                   'prompt_sha256': sha_file(target), 'reference_ids': [r['id'] for r in references], 'at': now()}
        attempts.append(attempt)
        save(root, project)
        return {'attempt': number, 'prompt': str(target),
                'referenced_image_paths': [str(inside(root, r['path'])) for r in references]}
    elif command in ('finish-panel', 'fail-panel'):
        assert_script_lock(project)
        attempts = project['art']['panels'].get(args.panel, [])
        attempt = next((a for a in attempts if a['number'] == args.attempt), None)
        if not attempt or attempt['status'] != 'pending':
            raise GateError('Pending panel attempt required.')
        panel = next(p for p in project['script']['panels'] if p['id'] == args.panel)
        if attempt['render_hash'] != render_hash(project, panel, select_references(root, project, panel)):
            raise GateError('Attempt inputs changed during generation; preserve output and review against current inputs.')
        if command == 'fail-panel':
            if not nonempty(args.reason):
                raise GateError('Failure reason required.')
            attempt.update(status='failed', failure=args.reason)
        else:
            report = load_json(args.qa)
            try:
                validate_qa(report, PANEL_CHECKS)
            except GateError:
                attempt.update(status='rejected', qa=report)
                save(root, project)
                raise
            path, sha = copy_image(root, args.file, 'panels')
            attempt.update(status='accepted', path=path, sha256=sha, qa=report)
    elif command in ('compose', 'review-layout', 'export', 'verify-export', 'complete'):
        assert_script_lock(project)
        from comic_layout import layout_fingerprint, compose, export, verify_exports
        fingerprint = layout_fingerprint(root, project)
        if command == 'compose':
            project['layout'] = compose(root, project, args.font)
            project['exports'], project['final_review'] = None, None
        else:
            layout = project.get('layout')
            if not layout or layout['input_hash'] != fingerprint:
                raise GateError('Composed pages missing or stale.')
            for page in layout['pages']:
                path = inside(root, page['path'])
                if not path.is_file() or sha_file(path) != page['sha256']:
                    raise GateError('Composed page missing or changed.')
            if command == 'review-layout':
                report = load_json(args.file)
                validate_qa(report, LAYOUT_CHECKS)
                if report.get('input_hash') != fingerprint or set(report.get('reviewed_page_ids', [])) != {p['id'] for p in layout['pages']}:
                    raise GateError('Visual layout review must bind current hash and every composed page.')
                layout['qa'] = report
            else:
                if not layout.get('qa'):
                    raise GateError('View and review every composed page before export.')
                validate_qa(layout['qa'], LAYOUT_CHECKS)
                if command == 'export':
                    project['exports'] = export(root, project)
                    project['final_review'] = None
                else:
                    verification = verify_exports(root, project)
                    if command == 'verify-export':
                        return verification
                    report = load_json(args.file)
                    validate_qa(report, ['source_scope', 'story_complete', 'visual_consistency', 'exports_opened'])
                    if report.get('input_hash') != fingerprint:
                        raise GateError('Final review must bind current deliverable inputs.')
                    project['final_review'] = {**report, 'verification': verification, 'at': now()}
    elif command == 'status':
        try:
            assert_script_lock(project)
            locked, blockers = True, []
        except GateError as error:
            locked, blockers = False, str(error).splitlines()
        panels = project['script'].get('panels', [])
        accepted = [p['id'] for p in panels if accepted_panel(root, project, p)]
        complete = False
        if locked and project.get('final_review'):
            try:
                validate_qa(project['final_review'], ['source_scope', 'story_complete', 'visual_consistency', 'exports_opened'])
                from comic_layout import layout_fingerprint, verify_exports
                if project['final_review']['input_hash'] == layout_fingerprint(root, project):
                    verify_exports(root, project)
                    complete = True
            except (GateError, OSError, ValueError):
                pass
        return {'complete': complete, 'source_scope': project['source']['scope_note'],
                'chapters_with_body': sum(c['has_body'] for c in project['source']['chapters']),
                'chapters_read': sum(c['has_body'] and c['read'] for c in project['source']['chapters']),
                'script_hash': digest(project['script']), 'script_locked': locked,
                'panels_planned': len(panels), 'panels_accepted': len(accepted),
                'next_panel': next((p['id'] for p in panels if p['id'] not in accepted), None),
                'blockers': blockers[:40], 'blocker_count': len(blockers), 'exports': project.get('exports')}
    else:
        raise GateError('Unknown command.')
    save(root, project)
    return {'ok': True, 'command': command, 'script_hash': digest(project['script'])}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    subs = p.add_subparsers(dest='command', required=True)
    for name in ('init', 'chapter', 'resolve-issue', 'confirm-source', 'mark-read', 'set-script',
                 'check-script', 'review', 'lock-script', 'assert-art', 'register-reference',
                 'begin-panel', 'finish-panel', 'fail-panel', 'compose', 'review-layout',
                 'export', 'verify-export', 'complete', 'status'):
        sub = subs.add_parser(name)
        sub.add_argument('--project', required=True)
        if name == 'init':
            sub.add_argument('--source', nargs='+', required=True)
            sub.add_argument('--title')
        if name in ('chapter', 'mark-read'):
            sub.add_argument('--chapter', required=name == 'mark-read')
        if name == 'resolve-issue':
            sub.add_argument('--id', required=True)
            sub.add_argument('--evidence', required=True)
        if name in ('confirm-source', 'mark-read'):
            sub.add_argument('--note', required=True)
        if name == 'confirm-source':
            sub.add_argument('--scope')
        if name in ('set-script', 'review', 'register-reference', 'finish-panel', 'review-layout', 'complete'):
            sub.add_argument('--file', required=True)
        if name == 'review':
            sub.add_argument('--kind', choices=REVIEW_CHECKS, required=True)
        if name == 'register-reference':
            sub.add_argument('--characters', nargs='+', required=True)
        if name in ('register-reference', 'finish-panel'):
            sub.add_argument('--qa', required=True)
        if name in ('begin-panel', 'finish-panel', 'fail-panel'):
            sub.add_argument('--panel', required=True)
        if name in ('finish-panel', 'fail-panel'):
            sub.add_argument('--attempt', type=int, required=True)
        if name == 'begin-panel':
            sub.add_argument('--prompt', required=True)
        if name == 'fail-panel':
            sub.add_argument('--reason', required=True)
        if name == 'compose':
            sub.add_argument('--font')
    return p


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        result = run(parser().parse_args())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if isinstance(result, dict) and result.get('errors'):
            sys.exit(2)
    except (GateError, SourceError, OSError, ValueError, KeyError, TypeError, ImportError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
