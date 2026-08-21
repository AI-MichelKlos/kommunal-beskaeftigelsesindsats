from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
HTML = BASE / 'index.html'
SCRIPT = '<script src="assets/personal-view.js"></script>\n'
MARKER = '<script data-goatcounter="https://kommune.goatcounter.com/count"'
OLD_EMAIL = 'mk@danskeakasser.dk'
NEW_EMAIL = 'michel@klos.dk'


def main():
    text = HTML.read_text(encoding='utf-8')
    if SCRIPT.strip() not in text:
        if MARKER not in text:
            raise RuntimeError('Kunne ikke finde GoatCounter-markør')
        text = text.replace(MARKER, SCRIPT + MARKER, 1)
    text = text.replace(OLD_EMAIL, NEW_EMAIL)
    HTML.write_text(text, encoding='utf-8')
    print('OK: personlig visning og kontaktmail er opdateret i Kommuneindsigt')


if __name__ == '__main__':
    main()
