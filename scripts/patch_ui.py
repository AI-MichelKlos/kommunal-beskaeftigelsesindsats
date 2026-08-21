from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
HTML = BASE / 'index.html'
SCRIPT = '<script src="assets/personal-view.js"></script>\n'
MARKER = '<script data-goatcounter="https://kommune.goatcounter.com/count"'


def main():
    text = HTML.read_text(encoding='utf-8')
    if SCRIPT.strip() not in text:
        if MARKER not in text:
            raise RuntimeError('Kunne ikke finde GoatCounter-markør')
        text = text.replace(MARKER, SCRIPT + MARKER, 1)
    HTML.write_text(text, encoding='utf-8')
    print('OK: personlig visning er koblet på Kommuneindsigt')


if __name__ == '__main__':
    main()
