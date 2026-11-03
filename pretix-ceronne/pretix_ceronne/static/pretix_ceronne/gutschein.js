/* SPDX-License-Identifier: AGPL-3.0-or-later – Copyright (C) 2026 Club Céronne im ETV Hamburg e.V. */
/* Céronne Saalplan im Gutschein-Formular: Knopf „Platz im Saalplan wählen“ neben dem pretix-Feld
   „Bestimmter Sitzplatz“ (Einzelgutschein) bzw. „Bestimmte Sitzplätze“ (mehrere Gutscheine, eine ID pro Zeile).
   Ein so gebundener Platz bleibt reserviert, bis der Gutschein eingelöst, gelöscht oder abgelaufen ist (pretix-Kern). */
(function () {
  'use strict';
  var skript = document.currentScript;
  var datenUrl = skript && skript.dataset.datenUrl;

  function knopf(text) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn btn-default';
    b.textContent = text;
    return b;
  }

  function einrichten(feld, nr) {
    var mehrere = feld.tagName === 'TEXTAREA';
    var oeffnen = knopf(mehrere ? 'Plätze im Saalplan wählen' : 'Platz im Saalplan wählen');
    oeffnen.setAttribute('aria-expanded', 'false');
    var anzeige = document.createElement('p');
    anzeige.className = 'help-block cs-gewaehlt';
    anzeige.setAttribute('aria-live', 'polite');
    var bereich = document.createElement('div');
    bereich.hidden = true;
    feld.insertAdjacentElement('afterend', bereich);
    feld.insertAdjacentElement('afterend', anzeige);
    feld.insertAdjacentElement('afterend', oeffnen);

    var geladen = false;
    oeffnen.addEventListener('click', function () {
      bereich.hidden = !bereich.hidden;
      oeffnen.setAttribute('aria-expanded', bereich.hidden ? 'false' : 'true');
      if (geladen || bereich.hidden) return;
      geladen = true;
      bereich.textContent = 'Saalplan wird geladen …';
      fetch(datenUrl, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
        var aktuell = feld.value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
        d.modus = 'gutschein';
        bereich.textContent = '';
        var wurzel = document.createElement('div');
        wurzel.className = 'cs-saalplan cs-gutschein';
        var hilfe = document.createElement('p');
        hilfe.id = 'cs-g' + nr + '-hilfe';
        hilfe.textContent = mehrere
          ? 'Freie Plätze anklicken (ein Gutschein je Platz). Orange = schon für einen anderen Gutschein reserviert, grün = verkauft.'
          : 'Freien Platz anklicken. Orange = schon für einen anderen Gutschein reserviert, grün = verkauft.';
        wurzel.appendChild(hilfe);
        var werkzeuge = document.createElement('div');
        werkzeuge.className = 'cs-werkzeuge';
        [['+', '1.5', 'Plan vergrößern'], ['−', '0.6667', 'Plan verkleinern'], ['Ganzer Saal', '0', '']].forEach(function (z) {
          var b = knopf(z[0]);
          b.classList.add('cs-zoom');
          b.dataset.zoom = z[1];
          if (z[2]) b.setAttribute('aria-label', z[2]);
          werkzeuge.appendChild(b);
        });
        wurzel.appendChild(werkzeuge);
        var zh = document.createElement('p');
        zh.className = 'cs-zoom-hinweis';
        zh.textContent = 'Zoomen mit + und −, Strg/⌘ + Mausrad oder zwei Fingern; vergrößert lässt sich der Plan verschieben.';
        wurzel.appendChild(zh);
        var flaeche = document.createElement('div');
        flaeche.className = 'cs-flaeche';
        wurzel.appendChild(flaeche);
        var json = document.createElement('script');
        json.type = 'application/json';
        json.textContent = JSON.stringify(d);
        wurzel.appendChild(json);
        // Auswahlfelder: freie Plätze und die bereits in diesem Gutschein eingetragenen
        var felder = document.createElement('div');
        felder.hidden = true;
        d.plaetze.forEach(function (p) {
          if (p.s !== 'frei' && aktuell.indexOf(p.g) < 0) return;
          var i = document.createElement('input');
          i.type = mehrere ? 'checkbox' : 'radio';
          i.name = 'cs-gutschein-platz-' + nr;
          i.dataset.guid = p.g;
          i.checked = aktuell.indexOf(p.g) >= 0;
          i.tabIndex = -1;
          felder.appendChild(i);
        });
        wurzel.appendChild(felder);
        wurzel.addEventListener('cs-auswahl', function (e) {
          var plaetze = e.detail;
          if (!plaetze.length && !aktuell.length) return;
          feld.value = plaetze.map(function (p) { return p.g; }).join(mehrere ? '\n' : '');
          feld.dispatchEvent(new Event('change', { bubbles: true }));
          aktuell = plaetze.map(function (p) { return p.g; });
          anzeige.textContent = plaetze.length
            ? 'Gewählt: ' + plaetze.map(function (p) { return p.l + ' (' + p.k + ')'; }).join('; ')
            : '';
        });
        bereich.appendChild(wurzel);
        window.CeronneSaalplan.init(wurzel);
      }).catch(function () {
        bereich.textContent = 'Der Saalplan konnte nicht geladen werden.';
      });
    });
  }

  function start() {
    if (!datenUrl || !window.CeronneSaalplan) return;
    document.querySelectorAll('[data-seat-guid-field]').forEach(einrichten);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
