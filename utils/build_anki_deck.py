"""Generate Anki decks from practical_test_*.html question banks."""

import hashlib
import json
import re
import sys
from pathlib import Path

import genanki

ROOT = Path(__file__).parent.parent

MODEL_ID = 1607392319

_FRONT = """\
<div class="scenario">{{Scenario}}</div>
<div class="situation">{{Situation}}</div>
<hr>
<div class="question">{{Question}}</div>
<ol type="A">
<li>{{OptionA}}</li>
<li>{{OptionB}}</li>
<li>{{OptionC}}</li>
<li>{{OptionD}}</li>
</ol>"""

_BACK = """\
{{FrontSide}}
<hr id=answer>
<b>Answer: {{Correct}}</b><br><br>
{{Explanation}}"""

_CSS = """\
.card { font-family: sans-serif; font-size: 16px; }
.scenario { color: #888; font-size: 13px; text-transform: uppercase; margin-bottom: 8px; }
.situation { border-left: 3px solid #888; padding: 8px 12px; margin-bottom: 12px; }
.question { font-weight: bold; margin-bottom: 8px; }
ol { margin: 0; padding-left: 24px; }
li { margin-bottom: 6px; }
#answer { margin: 16px 0 8px; }"""

_MODEL = genanki.Model(
    MODEL_ID,
    'Claude Certified Architect MCQ',
    fields=[
        {'name': 'Scenario'},
        {'name': 'Situation'},
        {'name': 'Question'},
        {'name': 'OptionA'},
        {'name': 'OptionB'},
        {'name': 'OptionC'},
        {'name': 'OptionD'},
        {'name': 'Correct'},
        {'name': 'Explanation'},
    ],
    templates=[{'name': 'MCQ', 'qfmt': _FRONT, 'afmt': _BACK}],
    css=_CSS,
)

def _deck_id(lang: str) -> int:
    return int(hashlib.sha256(f'cca-deck:{lang}'.encode()).hexdigest()[:8], 16)


def _validate_question(q: dict, index: int) -> None:
    for field in ('question', 'correct', 'explanation', 'options'):
        if not q.get(field):
            raise ValueError(f'question {index}: missing field "{field}"')
    letters = {o['letter'] for o in q['options']}
    for letter in ('A', 'B', 'C', 'D'):
        if letter not in letters:
            raise ValueError(f'question {index}: missing option "{letter}"')


def _compute_source_hashes(html_files: list[Path]) -> dict[str, str]:
    return {
        path.stem.removeprefix('practical_test_'): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in html_files
    }


def extract_questions(html_path: Path) -> list[dict]:
    """Returns the QUESTIONS list parsed from a practical_test_*.html file."""
    content = html_path.read_text(encoding='utf-8')
    match = re.search(r'const QUESTIONS = (\[.*?\]);', content, re.DOTALL)
    if not match:
        raise ValueError(f'No QUESTIONS array found in {html_path}')
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        raise ValueError(f'{html_path}: {e}') from e


def build_deck(lang: str, questions: list[dict]) -> genanki.Deck:
    """Returns a populated genanki.Deck for the given language and questions."""
    deck = genanki.Deck(
        _deck_id(lang),
        f'Claude Certified Architect :: {lang}',
        description=(
            'Multiple-choice questions from the Claude Certified Architect '
            'practical tests. Source: practical_test_*.html.'
        ),
    )
    for i, q in enumerate(questions):
        _validate_question(q, i)
        opts = {o['letter']: o['text'] for o in q['options']}
        scenario_tag = re.sub(
            r'\W+', '-', (q.get('scenario') or 'misc').lower()
        ).strip('-')
        deck.add_note(genanki.Note(
            model=_MODEL,
            fields=[
                q.get('scenario') or '',
                q.get('situation') or '',
                q.get('question') or '',
                opts.get('A') or '',
                opts.get('B') or '',
                opts.get('C') or '',
                opts.get('D') or '',
                q.get('correct') or '',
                q.get('explanation') or '',
            ],
            tags=[lang, scenario_tag],
            sort_field=2,
        ))
    return deck


def main() -> None:
    """Generates Anki decks for all practical_test_*.html files at ROOT."""
    out_dir = ROOT / 'anki'
    out_dir.mkdir(exist_ok=True)
    html_files = sorted(ROOT.glob('practical_test_*.html'))
    if not html_files:
        print('No practical_test_*.html files found', file=sys.stderr)
        sys.exit(1)
    hash_file = out_dir / '.source-hash'
    new_hashes = _compute_source_hashes(html_files)
    try:
        old_hashes = json.loads(hash_file.read_text()) if hash_file.exists() else {}
    except ValueError:
        old_hashes = {}
    to_build = [
        ROOT / f'practical_test_{lang}.html'
        for lang, h in new_hashes.items()
        if h != old_hashes.get(lang)
    ]
    if not to_build:
        print('Source HTML unchanged, skipping generation.')
        return
    for html_path in to_build:
        lang = html_path.stem.removeprefix('practical_test_')
        questions = extract_questions(html_path)
        deck = build_deck(lang, questions)
        out_path = out_dir / f'practical_test_{lang}.apkg'
        genanki.Package(deck).write_to_file(out_path, timestamp=MODEL_ID)
        print(f'Processing {html_path.name} ({lang})')
        print(f'  → {out_path.name} ({len(questions)} cards)')
    hash_file.write_text(json.dumps(new_hashes) + '\n')


if __name__ == '__main__':
    main()
