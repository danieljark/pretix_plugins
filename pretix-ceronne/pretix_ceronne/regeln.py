# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Club Céronne im ETV Hamburg e.V.
"""Buchungsregeln für den Saalplan. Dieselbe Logik steckt in saalplan.js (sofortige Rückmeldung im Shop);
hier wird sie vor der Kasse noch einmal geprüft, damit sie sich nicht umgehen lässt.

Ein „Tisch“ ist eine Reihe des Saalplans (z. B. A1 mit 6 Plätzen). Nachbarn sind Plätze desselben Tisches im
Abstand des 1,5-fachen kleinsten Platzabstands an diesem Tisch – also die Plätze links und rechts, nicht gegenüber.
"""
import math

TISCHMODI = (
    ('einzeln', 'Nur einzelne Plätze'),
    ('beides', 'Einzelne Plätze und ganze Tische'),
    ('nur_tische', 'Nur ganze Tische'),
)


def einstellungen(event):
    return {
        'tischmodus': event.settings.get('ceronne_tischmodus', default='beides'),
        'luecken': event.settings.get('ceronne_luecken', as_type=bool, default=True),
        'restplatz': event.settings.get('ceronne_restplatz', as_type=bool, default=False),
    }


def nachbarn(sitze):
    """sitze: Liste von Dicts mit g (ID), x, y, t (Tisch). Ergebnis: {ID: [Nachbar-IDs]}"""
    tische = {}
    for s in sitze:
        tische.setdefault(s['t'], []).append(s)
    ergebnis = {}
    for liste in tische.values():
        abstand = min(
            (math.dist((a['x'], a['y']), (b['x'], b['y'])) for i, a in enumerate(liste) for b in liste[i + 1:]),
            default=0,
        )
        grenze = abstand * 1.5
        for a in liste:
            ergebnis[a['g']] = [
                b['g'] for b in liste
                if b is not a and math.dist((a['x'], a['y']), (b['x'], b['y'])) <= grenze
            ]
    return ergebnis


def pruefen(sitze, belegt, auswahl, regeln):
    """Gibt eine Fehlermeldung zurück oder None. belegt: von anderen belegt oder nicht buchbar; auswahl: eigene."""
    if not auswahl:
        return None
    pos = {s['g']: s for s in sitze}
    tisch_von = {s['g']: s['t'] for s in sitze}
    besetzt = set(belegt) | set(auswahl)
    beruehrt = {tisch_von[g] for g in auswahl if g in tisch_von}

    frei_danach = {}
    for s in sitze:
        if s['g'] not in besetzt:
            frei_danach[s['t']] = frei_danach.get(s['t'], 0) + 1

    if regeln['tischmodus'] == 'nur_tische':
        for t in sorted(beruehrt):
            if frei_danach.get(t, 0):
                return f'Bei dieser Veranstaltung können nur ganze Tische gebucht werden – bitte alle freien Plätze an Tisch {t} wählen.'

    if regeln['restplatz']:
        for t in sorted(beruehrt):
            if frei_danach.get(t, 0) == 1:
                return f'An Tisch {t} bliebe genau ein Platz frei. Bitte einen Platz mehr oder weniger wählen.'

    if regeln['luecken']:
        nb = nachbarn(sitze)
        for s in sitze:
            g = s['g']
            if g in besetzt:
                continue
            n = nb.get(g, [])
            for i, a in enumerate(n):
                for b in n[i + 1:]:
                    if a not in besetzt or b not in besetzt or not ({a, b} & set(auswahl)):
                        continue
                    va = (pos[a]['x'] - s['x'], pos[a]['y'] - s['y'])
                    vb = (pos[b]['x'] - s['x'], pos[b]['y'] - s['y'])
                    if va[0] * vb[0] + va[1] * vb[1] < 0:
                        return f'Bitte keinen einzelnen Platz zwischen zwei belegten Plätzen frei lassen (Tisch {s["t"]}).'
    return None
