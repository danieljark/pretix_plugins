/* SPDX-License-Identifier: AGPL-3.0-or-later – Copyright (C) 2026 Club Céronne im ETV Hamburg e.V. */
/* Céronne Saalplan: zeichnet den Plan als SVG und hält ihn mit den Kontrollkästchen synchron.
   Shop: Kontrollkästchen sind die Formularfelder (seat_<produkt> = Platz-ID) – ohne JavaScript geht die Liste.
   Backend (Belegung): Kontrollkästchen „gesperrt“ – Klick sperrt bzw. gibt frei.
   Gutschein-Formular (gutschein.js): Optionsfelder, ein Platz; Auswahl wird als Ereignis „cs-auswahl“ gemeldet.
   Die Buchungsregeln entsprechen regeln.py und werden vor der Kasse auf dem Server noch einmal geprüft. */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';

  function el(name, attrs, parent) {
    var e = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(e);
    return e;
  }

  function abstand(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }

  /* ---------- Regeln (wie regeln.py) ---------- */

  function nachbarn(plaetze) {
    var tische = {}, nb = {};
    plaetze.forEach(function (p) { (tische[p.t] = tische[p.t] || []).push(p); });
    Object.keys(tische).forEach(function (t) {
      var l = tische[t], min = Infinity;
      for (var i = 0; i < l.length; i++) for (var j = i + 1; j < l.length; j++) min = Math.min(min, abstand(l[i], l[j]));
      var grenze = min * 1.5;
      l.forEach(function (a) {
        nb[a.g] = l.filter(function (b) { return b !== a && abstand(a, b) <= grenze; }).map(function (b) { return b.g; });
      });
    });
    return nb;
  }

  function pruefen(plaetze, pos, nb, belegt, auswahl, regeln) {
    var ids = Object.keys(auswahl);
    if (!ids.length) return null;
    var besetzt = function (g) { return belegt[g] || auswahl[g]; };
    var beruehrt = {}, frei = {};
    ids.forEach(function (g) { beruehrt[pos[g].t] = true; });
    plaetze.forEach(function (p) { if (!besetzt(p.g)) frei[p.t] = (frei[p.t] || 0) + 1; });
    var tische = Object.keys(beruehrt).sort(), i, t;
    if (regeln.tischmodus === 'nur_tische') {
      for (i = 0; i < tische.length; i++) {
        t = tische[i];
        if (frei[t]) return 'Bei dieser Veranstaltung können nur ganze Tische gebucht werden – bitte alle freien Plätze an Tisch ' + t + ' wählen.';
      }
    }
    if (regeln.restplatz) {
      for (i = 0; i < tische.length; i++) {
        t = tische[i];
        if (frei[t] === 1) return 'An Tisch ' + t + ' bliebe genau ein Platz frei. Bitte einen Platz mehr oder weniger wählen.';
      }
    }
    if (regeln.luecken) {
      for (i = 0; i < plaetze.length; i++) {
        var s = plaetze[i];
        if (besetzt(s.g)) continue;
        var n = nb[s.g] || [];
        for (var a = 0; a < n.length; a++) {
          for (var b = a + 1; b < n.length; b++) {
            if (!besetzt(n[a]) || !besetzt(n[b]) || !(auswahl[n[a]] || auswahl[n[b]])) continue;
            var va = [pos[n[a]].x - s.x, pos[n[a]].y - s.y], vb = [pos[n[b]].x - s.x, pos[n[b]].y - s.y];
            if (va[0] * vb[0] + va[1] * vb[1] < 0) return 'Bitte keinen einzelnen Platz zwischen zwei belegten Plätzen frei lassen (Tisch ' + s.t + ').';
          }
        }
      }
    }
    return null;
  }

  /* ---------- Zeichnen ---------- */

  function zeichneFlaechen(svg, flaechen) {
    var deko = el('g', { 'aria-hidden': 'true' }, svg);
    var schilder = {};
    flaechen.forEach(function (a) {
      // Drehung wie im pretix-Saalplan-Editor: um den Ankerpunkt (bei Rechtecken die linke obere Ecke)
      var x = a.position.x, y = a.position.y, form = null;
      var stil = { fill: a.color || 'none', stroke: a.border_color || 'none', 'stroke-width': 2, class: 'cs-flaeche-form' };
      if (a.shape === 'rectangle') {
        stil.x = x; stil.y = y; stil.width = a.rectangle.width; stil.height = a.rectangle.height;
        form = el('rect', stil, deko);
      } else if (a.shape === 'circle') {
        stil.cx = x; stil.cy = y; stil.r = a.circle.radius;
        form = el('circle', stil, deko);
      } else if (a.shape === 'ellipse') {
        stil.cx = x; stil.cy = y; stil.rx = a.ellipse.radius.x; stil.ry = a.ellipse.radius.y;
        form = el('ellipse', stil, deko);
      } else if (a.shape === 'polygon' && a.polygon) {
        stil.points = a.polygon.points.map(function (p) { return (x + p.x) + ',' + (y + p.y); }).join(' ');
        form = el('polygon', stil, deko);
      }
      var drehung = a.rotation ? 'rotate(' + a.rotation + ' ' + x + ' ' + y + ')' : null;
      if (form && drehung) form.setAttribute('transform', drehung);
      var text = a.text && a.text.text ? a.text.text.trim() : '';
      if (text) {
        var t = el('text', {
          x: x + (a.text.position ? a.text.position.x : 0),
          y: y + (a.text.position ? a.text.position.y : 0),
          fill: a.text.color || '#333',
          'font-size': a.text.size || 16,
          'text-anchor': 'middle',
          'dominant-baseline': 'middle',
          class: 'cs-text'
        }, deko);
        t.textContent = text;
        if (drehung) t.setAttribute('transform', drehung);
      }
      if (form && text) schilder[text] = form;
    });
    return schilder;
  }

  function sichtbarerBereich(d) {
    var r = d.radius, minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    function erw(x1, y1, x2, y2) {
      minX = Math.min(minX, x1); minY = Math.min(minY, y1); maxX = Math.max(maxX, x2); maxY = Math.max(maxY, y2);
    }
    d.plaetze.forEach(function (p) { erw(p.x - r, p.y - r, p.x + r, p.y + r); });
    d.flaechen.forEach(function (a) {
      var x = a.position.x, y = a.position.y;
      if (a.shape === 'rectangle') {
        var w = a.rectangle.width, h = a.rectangle.height;
        if (a.rotation) { var m = Math.max(w, h); erw(x - m, y - m, x + m, y + m); } else erw(x, y, x + w, y + h);
      } else if (a.shape === 'circle') erw(x - a.circle.radius, y - a.circle.radius, x + a.circle.radius, y + a.circle.radius);
      else if (a.shape === 'ellipse') erw(x - a.ellipse.radius.x, y - a.ellipse.radius.y, x + a.ellipse.radius.x, y + a.ellipse.radius.y);
      else erw(x, y, x, y);
    });
    var rand = 20;
    return [minX - rand, minY - rand, maxX - minX + 2 * rand, maxY - minY + 2 * rand];
  }

  /* ---------- Start ---------- */

  function init(wurzel) {
    var datenEl = wurzel.querySelector('script[type="application/json"]');
    var flaeche = wurzel.querySelector('.cs-flaeche');
    if (!datenEl || !flaeche || wurzel.classList.contains('cs-js')) return;
    wurzel.classList.add('cs-js');
    var d = JSON.parse(datenEl.textContent);
    var gutscheinModus = d.modus === 'gutschein';
    var admin = d.modus === 'admin' || gutscheinModus;
    var regeln = d.regeln || {};
    var r = d.radius;

    var farbe = {}, preis = {};
    d.kategorien.forEach(function (k) { farbe[k.name] = k.farbe; preis[k.name] = k.preis; });

    // Je Platz ein Kontrollkästchen; bei Produkten mit Varianten gibt es für die Liste ohne JavaScript eines je
    // Variante – mit JavaScript zählt nur das erste, die Variante wird in der Auswahlliste gewählt.
    var varianten = d.varianten || {};
    var kaestchen = {};
    wurzel.querySelectorAll('input[data-guid]').forEach(function (c) {
      if (kaestchen[c.dataset.guid]) {
        c.disabled = true;
        if (c.closest('label')) c.closest('label').hidden = true;
      } else kaestchen[c.dataset.guid] = c;
    });

    var pos = {}, belegt = {}, tischPlaetze = {};
    d.plaetze.forEach(function (p) {
      pos[p.g] = p;
      if (!admin && !kaestchen[p.g]) belegt[p.g] = true;
      (tischPlaetze[p.t] = tischPlaetze[p.t] || []).push(p);
    });
    var nb = nachbarn(d.plaetze);

    var titelEl = wurzel.querySelector('[id$="titel"]'), hilfeEl = wurzel.querySelector('[id$="hilfe"]');
    var svg = el('svg', { viewBox: sichtbarerBereich(d).join(' '), role: 'group', class: 'cs-svg' }, flaeche);
    if (titelEl) svg.setAttribute('aria-labelledby', titelEl.id);
    if (hilfeEl) svg.setAttribute('aria-describedby', hilfeEl.id);
    var schilder = zeichneFlaechen(svg, d.flaechen);

    // Plätze
    var sitze = [], sitzVon = {};
    var gruppe = el('g', {}, svg);
    var dynamisch = null;
    function kasten(p) {
      // Kontrollkästchen für einen Platz, der erst nachträglich frei geworden ist
      if (!kaestchen[p.g]) {
        if (!dynamisch) { dynamisch = document.createElement('div'); dynamisch.hidden = true; wurzel.appendChild(dynamisch); }
        var k = document.createElement('input');
        var vs = varianten[p.i];
        k.type = 'checkbox'; k.name = 'seat_' + p.i + (vs ? '_' + vs[0].id : ''); k.value = p.g; k.dataset.guid = p.g;
        k.addEventListener('change', aktualisiere);
        dynamisch.appendChild(k);
        kaestchen[p.g] = k;
      }
      return kaestchen[p.g];
    }

    function zustand(c, frei) {
      var p = c._p;
      c._frei = frei;
      c.classList.toggle('cs-sitz--frei', frei);
      c.classList.toggle('cs-sitz--belegt', !frei);
      c.setAttribute('fill', frei ? (farbe[p.k] || '#999') : '#c4c4c4');
      if (c._kreuz) c._kreuz.setAttribute('visibility', frei ? 'hidden' : 'visible');
      if (frei) {
        c.setAttribute('role', 'checkbox');
        c.removeAttribute('aria-hidden');
        if (c.getAttribute('tabindex') !== '0') c.setAttribute('tabindex', '-1');
        if (!admin) { var k = kasten(p); k.disabled = false; if (k.closest('label')) k.closest('label').hidden = false; }
      } else {
        ['role', 'aria-checked', 'tabindex'].forEach(function (a) { c.removeAttribute(a); });
        c.setAttribute('aria-hidden', 'true');
        c.classList.remove('cs-sitz--gewaehlt');
        var kk = kaestchen[p.g];
        if (kk) { kk.checked = false; kk.disabled = true; if (kk.closest('label')) kk.closest('label').hidden = true; }
      }
      if (!admin) belegt[p.g] = !frei;
    }

    d.plaetze.forEach(function (p) {
      var waehlbar = !!kaestchen[p.g];
      var live = !admin && !!p.i;
      var fill = '#c4c4c4', klasse = 'cs-sitz';
      if (admin && p.s === 'verkauft') { fill = '#2e7d32'; klasse += ' cs-sitz--verkauft'; }
      else if (admin && p.s === 'gutschein' && !waehlbar) { fill = '#e65100'; klasse += ' cs-sitz--gutschein'; }
      else if (waehlbar) { fill = farbe[p.k] || '#999'; klasse += ' cs-sitz--frei'; }
      else klasse += ' cs-sitz--belegt';
      var c = el('circle', { cx: p.x, cy: p.y, r: r - 1, class: klasse, fill: fill, 'data-guid': p.g }, gruppe);
      if (!waehlbar && !live) {
        if (admin && p.s === 'verkauft') {
          var tt = el('title', {}, c);
          tt.textContent = p.l + ' – ' + p.o + (p.n ? ' – ' + p.n : '') + (p.bezahlt ? '' : ' (offen)');
          return;
        }
        if (admin && p.s === 'gutschein') {
          var tg = el('title', {}, c);
          tg.textContent = p.l + ' – reserviert für Gutschein ' + p.o;
          return;
        }
        c.setAttribute('aria-hidden', 'true');
        el('path', { d: 'M' + (p.x - r / 2) + ' ' + (p.y - r / 2) + 'l' + r + ' ' + r + 'm0 ' + (-r) + 'l' + (-r) + ' ' + r, class: 'cs-kreuz', 'aria-hidden': 'true' }, gruppe);
        return;
      }
      c.setAttribute('role', 'checkbox');
      c.setAttribute('tabindex', '-1');
      c.setAttribute('aria-checked', 'false');
      var name = admin ? p.l + ', ' + p.k : p.l + ', ' + p.k + (preis[p.k] ? ', ' + preis[p.k] : '');
      c.setAttribute('aria-label', admin && !gutscheinModus ? name + ' – gesperrt' : name);
      var titel = el('title', {}, c);
      titel.textContent = name;
      c._p = p;
      if (live) {
        c._kreuz = el('path', { d: 'M' + (p.x - r / 2) + ' ' + (p.y - r / 2) + 'l' + r + ' ' + r + 'm0 ' + (-r) + 'l' + (-r) + ' ' + r, class: 'cs-kreuz', 'aria-hidden': 'true' }, gruppe);
        zustand(c, waehlbar);
      } else c._frei = true;
      sitze.push(c);
      sitzVon[p.g] = c;
    });
    var ersterFreier = sitze.filter(function (c) { return c._frei; })[0];
    if (ersterFreier) ersterFreier.setAttribute('tabindex', '0');

    var liste = wurzel.querySelector('.cs-auswahl__liste');
    var leer = wurzel.querySelector('.cs-auswahl__leer');
    var absenden = wurzel.querySelector('.cs-absenden');
    var meldung = wurzel.querySelector('.cs-meldung');

    function auswahl() {
      var a = {};
      Object.keys(kaestchen).forEach(function (g) { if (kaestchen[g].checked && !kaestchen[g].disabled) a[g] = true; });
      return a;
    }

    function aktualisiere() {
      var a = auswahl();
      sitze.forEach(function (c) {
        if (!c._frei) return;
        var an = !!a[c._p.g];
        c.setAttribute('aria-checked', an ? 'true' : 'false');
        c.classList.toggle(admin && !gutscheinModus ? 'cs-sitz--blockiert' : 'cs-sitz--gewaehlt', an);
      });
      wurzel.dispatchEvent(new CustomEvent('cs-auswahl', { detail: Object.keys(a).map(function (g) { return pos[g]; }) }));
      if (admin) return;
      liste.textContent = '';
      var ids = Object.keys(a);
      var produkte = d.produkte || {};
      ids.forEach(function (g) {
        var p = pos[g];
        var vs = varianten[p.i];
        var info = produkte[p.i] || {};
        var k = kaestchen[g];
        // Posten wie auf dem Ticket: Produkt, Platz, ggf. Variante mit Beschreibung, Preis (mit Gutschein: alt/neu)
        var li = document.createElement('li');
        li.className = 'cs-posten';
        var titel = document.createElement('strong');
        titel.textContent = info.name || p.k;
        li.appendChild(titel);
        var platz = document.createElement('div');
        platz.textContent = p.l.replace(/, /g, ' – ');
        li.appendChild(platz);
        var beschreibung = document.createElement('div');
        beschreibung.className = 'cs-posten__text';
        var preisZeile = document.createElement('div');
        preisZeile.className = 'cs-posten__preis';
        function zeigePreis(x) {
          beschreibung.textContent = x.beschreibung || '';
          beschreibung.hidden = !x.beschreibung;
          preisZeile.textContent = x.preis_neu
            ? 'Ursprünglicher Preis: ' + x.preis + ' · Neuer Preis: ' + x.preis_neu
            : 'Preis: ' + (x.preis || '');
        }
        if (vs) {
          // Variante je Platz (z. B. Standard/Ermäßigt) – bestimmt den Feldnamen seat_<produkt>_<variante>
          var wahl = document.createElement('select');
          wahl.className = 'form-control cs-variante';
          wahl.setAttribute('aria-label', 'Ticketart für ' + p.l);
          var gewaehlt = vs[0];
          vs.forEach(function (v) {
            var o = document.createElement('option');
            o.value = v.id;
            o.textContent = v.name + ' – ' + (v.preis_neu || v.preis);
            if (k.name === 'seat_' + p.i + '_' + v.id) { o.selected = true; gewaehlt = v; }
            wahl.appendChild(o);
          });
          wahl.addEventListener('change', function () {
            k.name = 'seat_' + p.i + '_' + wahl.value;
            zeigePreis(vs.filter(function (v) { return String(v.id) === wahl.value; })[0]);
          });
          li.appendChild(wahl);
          zeigePreis(gewaehlt);
        } else zeigePreis(info);
        li.appendChild(beschreibung);
        li.appendChild(preisZeile);
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'btn btn-link cs-entfernen';
        b.textContent = 'Entfernen';
        b.setAttribute('aria-label', p.l + ' entfernen');
        b.addEventListener('click', function () {
          (regeln.tischmodus === 'nur_tische' ? tischPlaetze[p.t] : [p]).forEach(function (q) {
            if (kaestchen[q.g]) kaestchen[q.g].checked = false;
          });
          aktualisiere();
          if (sitzVon[g]) sitzVon[g].focus();
        });
        li.appendChild(b);
        liste.appendChild(li);
      });
      leer.hidden = ids.length > 0;
      var fehler = pruefen(d.plaetze, pos, nb, belegt, a, regeln);
      meldung.hidden = !fehler;
      meldung.textContent = fehler || '';
      if (absenden) absenden.disabled = ids.length === 0 || !!fehler;
    }

    function freieAmTisch(t) {
      return (tischPlaetze[t] || []).filter(function (p) { return sitzVon[p.g] && sitzVon[p.g]._frei; });
    }

    function tischUmschalten(t) {
      var frei = freieAmTisch(t);
      if (!frei.length) return;
      var alleAn = frei.every(function (p) { return kasten(p).checked; });
      frei.forEach(function (p) { kasten(p).checked = !alleAn; });
      aktualisiere();
    }

    function umschalten(c) {
      if (!admin && regeln.tischmodus === 'nur_tische') return tischUmschalten(c._p.t);
      var k = admin ? kaestchen[c._p.g] : kasten(c._p);
      k.checked = k.type === 'radio' ? true : !k.checked;
      aktualisiere();
    }

    function fokus(c) {
      sitze.forEach(function (s) { if (s._frei) s.setAttribute('tabindex', '-1'); });
      c.setAttribute('tabindex', '0');
      sichtbarMachen(c._p);
      c.focus({ preventScroll: true });
    }

    // Pfeiltasten: nächster freier Platz in der jeweiligen Richtung
    function naechster(c, dx, dy) {
      var best = null, bestWert = Infinity;
      sitze.forEach(function (s) {
        if (s === c || !s._frei) return;
        var vx = s._p.x - c._p.x, vy = s._p.y - c._p.y;
        var vor = vx * dx + vy * dy;
        if (vor <= 0) return;
        var wert = vor + 3 * Math.abs(vx * dy - vy * dx);
        if (wert < bestWert) { bestWert = wert; best = s; }
      });
      return best;
    }

    var gezogen = false, letzterZeiger = 'mouse', sichtbarMachen = function () {};
    gruppe.addEventListener('click', function (e) {
      if (gezogen) { gezogen = false; return; }
      var c = e.target.closest('.cs-sitz--frei');
      if (!c) return;
      // Auf dem Handy sind die Plätze in der Gesamtansicht zu klein zum Treffen: erst heranzoomen
      if (letzterZeiger === 'touch' && r * pixelJeEinheit() < 9) {
        var p = planPunkt(e.clientX, e.clientY);
        zoomUm(3, p[0], p[1]);
        return;
      }
      fokus(c); umschalten(c);
    });
    gruppe.addEventListener('keydown', function (e) {
      var c = e.target.closest('.cs-sitz--frei');
      if (!c) return;
      var richtung = { ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowDown: [0, 1], ArrowUp: [0, -1] }[e.key];
      if (richtung) {
        var n = naechster(c, richtung[0], richtung[1]);
        if (n) fokus(n);
        e.preventDefault();
      } else if (e.key === ' ' || e.key === 'Enter') {
        umschalten(c);
        e.preventDefault();
      } else if ((e.key === 't' || e.key === 'T') && !admin && regeln.tischmodus !== 'einzeln') {
        tischUmschalten(c._p.t);
        e.preventDefault();
      }
    });
    Object.keys(kaestchen).forEach(function (g) { kaestchen[g].addEventListener('change', aktualisiere); });

    // Tischschilder anklickbar (Maus); Tastatur: Taste T am Platz oder Knopf in der Liste
    if (!admin && regeln.tischmodus !== 'einzeln') {
      var deko = svg.querySelector('g[aria-hidden]');
      Object.keys(tischPlaetze).forEach(function (t) {
        var s = schilder[t];
        if (!s || !freieAmTisch(t).length) return;
        s.classList.add('cs-schild');
        s.addEventListener('click', function () { if (gezogen) { gezogen = false; return; } tischUmschalten(t); });
      });
      // Schilder liegen in der Deko-Gruppe; Klicks auf den Text sollen das Schild treffen
      if (deko) deko.style.pointerEvents = 'auto';
      wurzel.querySelectorAll('.cs-tisch-knopf').forEach(function (b) {
        b.addEventListener('click', function () { tischUmschalten(b.dataset.tisch); });
      });
    }

    // Plätze vorschlagen: N nebeneinanderliegende freie Plätze, die alle Regeln einhalten
    var vorschlagen = document.getElementById('cs-vorschlagen');
    if (vorschlagen) {
      vorschlagen.addEventListener('click', function () {
        var n = parseInt(document.getElementById('cs-anzahl').value, 10) || 1;
        var basis = auswahl(), gefunden = null;
        Object.keys(tischPlaetze).some(function (t) {
          var frei = freieAmTisch(t).filter(function (p) { return !basis[p.g]; });
          if (frei.length < n) return false;
          // Reihen am Tisch = zusammenhängende Nachbarn, entlang der Reihe sortiert
          var gesehen = {}, reihen = [];
          frei.forEach(function (p) {
            if (gesehen[p.g]) return;
            var reihe = [], stapel = [p.g];
            while (stapel.length) {
              var g = stapel.pop();
              if (gesehen[g]) continue;
              gesehen[g] = true; reihe.push(pos[g]);
              (nb[g] || []).forEach(function (h) { if (!gesehen[h] && sitzVon[h] && sitzVon[h]._frei && !basis[h]) stapel.push(h); });
            }
            reihe.sort(function (a, b) { return (a.x + a.y) - (b.x + b.y); });
            reihen.push(reihe);
          });
          var kandidaten = [];
          reihen.forEach(function (reihe) {
            for (var i = 0; i + n <= reihe.length; i++) kandidaten.push(reihe.slice(i, i + n));
          });
          if (!kandidaten.length) {
            // mehr Personen als eine Tischseite: Tischseiten zusammennehmen
            kandidaten.push(reihen.reduce(function (a, b) { return a.concat(b); }, []).slice(0, n));
          }
          return kandidaten.some(function (k) {
            var a = Object.assign({}, basis);
            k.forEach(function (p) { a[p.g] = true; });
            if (pruefen(d.plaetze, pos, nb, belegt, a, regeln)) return false;
            gefunden = k;
            return true;
          });
        });
        if (gefunden) {
          gefunden.forEach(function (p) { kasten(p).checked = true; });
          aktualisiere();
          fokus(sitzVon[gefunden[0].g]);
        } else {
          meldung.hidden = false;
          meldung.textContent = 'Es gibt keine ' + n + ' passenden freien Plätze nebeneinander. Bitte wähle selbst im Plan.';
        }
      });
    }

    // Ansicht: Der ganze Saal passt immer in den Rahmen. Zoomen per Knopf, Strg/⌘ + Mausrad oder zwei Fingern
    // (Trackpad, Handy), gezoomt lässt sich der Plan per Ziehen verschieben. Gezoomt wird über die viewBox –
    // weder der Rahmen noch die Seite scrollen seitlich.
    var basis = sichtbarerBereich(d), ansicht = basis.slice();
    function setzeAnsicht(v) {
      var w = Math.min(basis[2], Math.max(basis[2] / 12, v[2]));
      var h = w * basis[3] / basis[2];
      var x = Math.min(basis[0] + basis[2] - w, Math.max(basis[0], v[0]));
      var y = Math.min(basis[1] + basis[3] - h, Math.max(basis[1], v[1]));
      ansicht = [x, y, w, h];
      svg.setAttribute('viewBox', ansicht.join(' '));
      flaeche.classList.toggle('cs-gezoomt', w < basis[2] - 0.5);
    }
    function zoomUm(f, px, py) {
      var w = Math.min(basis[2], Math.max(basis[2] / 12, ansicht[2] / f)), k = w / ansicht[2];
      setzeAnsicht([px - (px - ansicht[0]) * k, py - (py - ansicht[1]) * k, w, ansicht[3] * k]);
    }
    function planPunkt(cx, cy) {
      var pt = svg.createSVGPoint(); pt.x = cx; pt.y = cy;
      var q = pt.matrixTransform(svg.getScreenCTM().inverse());
      return [q.x, q.y];
    }
    function pixelJeEinheit() { return svg.getScreenCTM().a; }
    function hoeheAnpassen() {
      var anteil = wurzel.classList.contains('cs-gutschein') ? 0.6 : 0.78;
      var h = Math.min(window.innerHeight * anteil, flaeche.clientWidth * basis[3] / basis[2]);
      flaeche.style.height = Math.max(220, Math.round(h)) + 'px';
    }
    hoeheAnpassen();
    window.addEventListener('resize', hoeheAnpassen);
    setzeAnsicht(basis);
    sichtbarMachen = function (p) {
      if (p.x < ansicht[0] || p.x > ansicht[0] + ansicht[2] || p.y < ansicht[1] || p.y > ansicht[1] + ansicht[3]) {
        setzeAnsicht([p.x - ansicht[2] / 2, p.y - ansicht[3] / 2, ansicht[2], ansicht[3]]);
      }
    };
    wurzel.querySelectorAll('.cs-zoom').forEach(function (b) {
      b.addEventListener('click', function () {
        var z = parseFloat(b.dataset.zoom);
        if (z) zoomUm(z, ansicht[0] + ansicht[2] / 2, ansicht[1] + ansicht[3] / 2);
        else setzeAnsicht(basis);
      });
    });
    svg.addEventListener('wheel', function (e) {
      if (!e.ctrlKey && !e.metaKey) return; // normales Scrollen bleibt Scrollen der Seite
      e.preventDefault();
      var p = planPunkt(e.clientX, e.clientY);
      zoomUm(Math.exp(-e.deltaY * 0.0025), p[0], p[1]);
    }, { passive: false });
    var zeiger = {}, geste = null;
    function gesteStarten() {
      var ids = Object.keys(zeiger);
      if (ids.length === 1) {
        var a = zeiger[ids[0]];
        geste = { x: a[0], y: a[1], v: ansicht.slice(), proPixel: 1 / pixelJeEinheit() };
      } else if (ids.length === 2) {
        var p1 = zeiger[ids[0]], p2 = zeiger[ids[1]];
        geste = { abstand: Math.hypot(p1[0] - p2[0], p1[1] - p2[1]) || 1, v: ansicht.slice(),
                  mitte: planPunkt((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2) };
      } else geste = null;
    }
    svg.addEventListener('pointerdown', function (e) {
      letzterZeiger = e.pointerType;
      zeiger[e.pointerId] = [e.clientX, e.clientY];
      gezogen = false;
      gesteStarten();
    });
    svg.addEventListener('pointermove', function (e) {
      if (!zeiger[e.pointerId] || !geste) return;
      zeiger[e.pointerId] = [e.clientX, e.clientY];
      var ids = Object.keys(zeiger);
      if (ids.length === 2 && geste.abstand) {
        var p1 = zeiger[ids[0]], p2 = zeiger[ids[1]];
        ansicht = geste.v.slice();
        zoomUm(Math.hypot(p1[0] - p2[0], p1[1] - p2[1]) / geste.abstand, geste.mitte[0], geste.mitte[1]);
        gezogen = true;
      } else if (ids.length === 1 && geste.proPixel) {
        var dx = e.clientX - geste.x, dy = e.clientY - geste.y;
        if (!gezogen && Math.hypot(dx, dy) < 6) return;
        if (!flaeche.classList.contains('cs-gezoomt')) return;
        gezogen = true;
        setzeAnsicht([geste.v[0] - dx * geste.proPixel, geste.v[1] - dy * geste.proPixel, geste.v[2], geste.v[3]]);
      }
    });
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (t) {
      svg.addEventListener(t, function (e) { delete zeiger[e.pointerId]; gesteStarten(); });
    });

    aktualisiere();

    // Live: im Hintergrund alle paar Sekunden nur den Platzstatus holen und die Plätze umfärben – kein Neuladen
    if (!admin && d.status_url) {
      var laeuft = false;
      var zahl = wurzel.querySelector('.cs-frei-zahl');
      var abfragen = function () {
        if (document.hidden || laeuft) return;
        laeuft = true;
        fetch(d.status_url, { credentials: 'same-origin', cache: 'no-store' })
          .then(function (antwort) { return antwort.json(); })
          .then(function (j) {
            var frei = {}, verloren = [], geaendert = false;
            j.frei.forEach(function (g) { frei[g] = true; });
            sitze.forEach(function (c) {
              var jetzt = !!frei[c._p.g];
              if (jetzt === c._frei) return;
              geaendert = true;
              if (!jetzt && kaestchen[c._p.g] && kaestchen[c._p.g].checked) verloren.push(c._p.l);
              zustand(c, jetzt);
            });
            if (zahl) zahl.textContent = String(sitze.filter(function (c) { return c._frei; }).length);
            if (geaendert) aktualisiere();
            if (verloren.length) {
              meldung.hidden = false;
              meldung.textContent = verloren.join(', ') + (verloren.length === 1 ? ' wurde' : ' wurden') +
                ' gerade von jemand anderem gebucht und ist nicht mehr verfügbar.';
            }
          })
          .catch(function () { /* Netzwerkfehler: beim nächsten Mal erneut versuchen */ })
          .then(function () { laeuft = false; });
      };
      setInterval(abfragen, 4000);
      document.addEventListener('visibilitychange', abfragen);
    }
  }

  window.CeronneSaalplan = { init: init };
  function alle() { document.querySelectorAll('.cs-saalplan').forEach(init); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', alle);
  else alle();
})();
