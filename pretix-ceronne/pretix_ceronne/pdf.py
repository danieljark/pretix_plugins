# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Club Céronne im ETV Hamburg e.V.
"""PDFs für vor Ort: Saalliste (Tisch für Tisch mit Namen) und Saalplan in Schwarz-Weiß (belegt = grau)."""
from io import BytesIO

from django.utils.formats import date_format
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

STATUS_TEXT = {
    'verkauft': '',
    'gutschein': 'Gutschein',
    'warenkorb': 'im Warenkorb',
    'blockiert': 'gesperrt',
    'gesperrt': 'nicht buchbar',
    'frei': 'frei',
}
BELEGT = ('verkauft', 'gutschein', 'warenkorb', 'blockiert', 'gesperrt')


def _tische(daten):
    tische = {}
    for p in daten['plaetze']:
        tische.setdefault(p['t'], []).append(p)
    for plaetze in tische.values():
        plaetze.sort(key=lambda p: (0, int(p['nr'])) if str(p.get('nr', '')).isdigit() else (1, str(p.get('nr', ''))))
    return tische


def _kopf(c, event, titel, breite, hoehe):
    c.setFont('Helvetica-Bold', 14)
    c.drawString(15 * mm, hoehe - 15 * mm, f'{event.name} – {titel}')
    c.setFont('Helvetica', 9)
    c.drawString(15 * mm, hoehe - 20 * mm, date_format(event.date_from, 'DATETIME_FORMAT'))
    return hoehe - 28 * mm


def saalliste(event, daten):
    """Tisch für Tisch: Platz, Name, Bestellung, Kategorie, Status. Freie Plätze sind als „frei“ aufgeführt."""
    puffer = BytesIO()
    breite, hoehe = A4
    c = canvas.Canvas(puffer, pagesize=A4, pageCompression=1)
    c.setTitle(f'Saalliste {event.name}')
    spalten = [15 * mm, 30 * mm, 100 * mm, 130 * mm, 160 * mm]
    y = _kopf(c, event, 'Saalliste', breite, hoehe)
    seite = 1

    def neue_seite():
        nonlocal y, seite
        c.setFont('Helvetica', 8)
        c.drawRightString(breite - 15 * mm, 10 * mm, f'Seite {seite}')
        c.showPage()
        seite += 1
        y = _kopf(c, event, 'Saalliste', breite, hoehe)

    for tisch, plaetze in _tische(daten).items():
        if y < 30 * mm + 5 * mm * min(len(plaetze), 6):
            neue_seite()
        c.setFont('Helvetica-Bold', 11)
        verkauft = sum(1 for p in plaetze if p['s'] == 'verkauft')
        c.drawString(spalten[0], y, f'Tisch {tisch}')
        c.setFont('Helvetica', 9)
        c.drawRightString(breite - 15 * mm, y, f'{verkauft} von {len(plaetze)} verkauft')
        y -= 2 * mm
        c.setLineWidth(0.6)
        c.line(spalten[0], y, breite - 15 * mm, y)
        y -= 4.5 * mm
        for p in plaetze:
            if y < 20 * mm:
                neue_seite()
            c.setFont('Helvetica', 9.5)
            c.drawString(spalten[0], y, f'Platz {p.get("nr", "")}')
            name = p.get('n') or ''
            c.setFont('Helvetica-Bold' if p['s'] == 'verkauft' else 'Helvetica', 9.5)
            c.drawString(spalten[1], y, name[:42])
            c.setFont('Helvetica', 9.5)
            c.drawString(spalten[2], y, p.get('o') or '')
            c.drawString(spalten[3], y, p['k'][:16])
            status = STATUS_TEXT.get(p['s'], p['s'])
            if p['s'] == 'verkauft' and not p.get('bezahlt'):
                status = 'offen'
            c.drawString(spalten[4], y, status)
            # Abhak-Kästchen für den Einlass
            if p['s'] == 'verkauft':
                c.rect(breite - 20 * mm, y - 0.5 * mm, 3.5 * mm, 3.5 * mm)
            y -= 5 * mm
        y -= 4 * mm
    c.setFont('Helvetica', 8)
    c.drawRightString(breite - 15 * mm, 10 * mm, f'Seite {seite}')
    c.save()
    return puffer.getvalue()


def saalplan(event, daten, format_name='A4'):
    """Plan in Schwarz-Weiß: freie Plätze weiß mit schwarzem Rand, belegte grau gefüllt; danach Liste der freien Plätze."""
    groesse = landscape(A3) if format_name == 'A3' else A4
    breite, hoehe = groesse
    puffer = BytesIO()
    c = canvas.Canvas(puffer, pagesize=groesse, pageCompression=1)
    c.setTitle(f'Saalplan {event.name}')
    oben = _kopf(c, event, 'Saalplan (grau = belegt)', breite, hoehe)

    r = daten['radius']
    xs, ys = [], []
    for p in daten['plaetze']:
        xs += [p['x'] - r, p['x'] + r]
        ys += [p['y'] - r, p['y'] + r]
    for a in daten['flaechen']:
        x, y = a['position']['x'], a['position']['y']
        if a['shape'] == 'rectangle':
            w, h = a['rectangle']['width'], a['rectangle']['height']
            m = max(w, h) if a.get('rotation') else 0
            xs += [x - m, x + w + m]
            ys += [y - m, y + h + m]
        elif a['shape'] == 'circle':
            xs += [x - a['circle']['radius'], x + a['circle']['radius']]
            ys += [y - a['circle']['radius'], y + a['circle']['radius']]
        else:
            xs.append(x)
            ys.append(y)
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    rand = 12 * mm
    legende = 22 * mm
    massstab = min((breite - 2 * rand) / (max_x - min_x), (oben - legende - 10 * mm) / (max_y - min_y))

    def pos(x, y):
        return rand + (x - min_x) * massstab, oben - 4 * mm - (y - min_y) * massstab

    # Flächen: nur Umriss und Beschriftung, keine Farbe
    for a in daten['flaechen']:
        x, y = a['position']['x'], a['position']['y']
        c.saveState()
        px, py = pos(x, y)
        c.translate(px, py)
        if a.get('rotation'):
            c.rotate(-a['rotation'])
        c.setStrokeGray(0.35)
        c.setLineWidth(0.8)
        c.setFillGray(0.96)
        if a['shape'] == 'rectangle':
            w, h = a['rectangle']['width'] * massstab, a['rectangle']['height'] * massstab
            c.rect(0, -h, w, h, stroke=1, fill=1)
        elif a['shape'] == 'circle':
            c.circle(0, 0, a['circle']['radius'] * massstab, stroke=1, fill=1)
        text = (a.get('text') or {}).get('text', '').strip()
        if text:
            tp = a['text'].get('position') or {'x': 0, 'y': 0}
            groesse_text = max(5, min(18, (a['text'].get('size') or 16) * massstab))
            c.setFillGray(0)
            c.setFont('Helvetica', groesse_text)
            c.drawCentredString(tp['x'] * massstab, -tp['y'] * massstab - groesse_text / 3, text)
        c.restoreState()

    # Plätze
    rs = (r - 1) * massstab
    for p in daten['plaetze']:
        px, py = pos(p['x'], p['y'])
        c.setLineWidth(0.7)
        c.setStrokeGray(0)
        if p['s'] in BELEGT:
            c.setFillGray(0.55)
            c.circle(px, py, rs, stroke=1, fill=1)
        else:
            c.setFillGray(1)
            c.circle(px, py, rs, stroke=1, fill=1)
            if rs > 4:
                c.setFillGray(0)
                c.setFont('Helvetica', rs * 1.1)
                c.drawCentredString(px, py - rs * 0.38, str(p.get('nr', '')))

    # Legende
    frei = [p for p in daten['plaetze'] if p['s'] == 'frei']
    preise = {k['name']: k.get('preis') for k in daten['kategorien']}
    ly = 14 * mm
    c.setStrokeGray(0)
    c.setFillGray(1)
    c.circle(rand + 2 * mm, ly + 1.2 * mm, 1.8 * mm, stroke=1, fill=1)
    c.setFillGray(0.55)
    c.circle(rand + 32 * mm, ly + 1.2 * mm, 1.8 * mm, stroke=1, fill=1)
    c.setFillGray(0)
    c.setFont('Helvetica', 9)
    c.drawString(rand + 5 * mm, ly, 'frei')
    c.drawString(rand + 35 * mm, ly, 'belegt / reserviert / gesperrt')
    zaehl = {}
    for p in frei:
        zaehl[p['k']] = zaehl.get(p['k'], 0) + 1
    c.drawString(rand, ly - 5 * mm, f'{len(frei)} Plätze frei: ' + ', '.join(
        f'{k} {n}' + (f' ({preise[k]})' if preise.get(k) else '') for k, n in zaehl.items()
    ))
    c.showPage()

    # Seite 2: freie Plätze je Tisch – zum Abhaken beim Verkauf
    y = _kopf(c, event, 'Freie Plätze zum Verkauf vor Ort', breite, hoehe)
    for tisch, plaetze in _tische(daten).items():
        freie = [p for p in plaetze if p['s'] == 'frei']
        if not freie:
            continue
        if y < 20 * mm:
            c.showPage()
            y = _kopf(c, event, 'Freie Plätze zum Verkauf vor Ort', breite, hoehe)
        c.setFont('Helvetica-Bold', 10)
        c.drawString(15 * mm, y, f'Tisch {tisch}')
        c.setFont('Helvetica', 10)
        x = 40 * mm
        for p in freie:
            c.rect(x, y - 0.6 * mm, 3.5 * mm, 3.5 * mm)
            c.drawString(x + 5 * mm, y, f'Platz {p.get("nr", "")} · {p["k"]}')
            x += 38 * mm
            if x > breite - 40 * mm:
                x = 40 * mm
                y -= 6 * mm
        y -= 8 * mm
    c.save()
    return puffer.getvalue()
