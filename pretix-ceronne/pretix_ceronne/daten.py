# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Club Céronne im ETV Hamburg e.V.
from django.db.models import F, Q
from django.urls import reverse
from django.utils.timezone import now

from pretix.base.models import Order, OrderPosition, Voucher
from pretix.base.templatetags.money import money_filter

from .regeln import einstellungen

SITZ_RADIUS = 10  # Standardgröße im pretix-Saalplanformat


def _buchbar(item, voucher):
    if not item or not item.active:
        return False
    if item.require_voucher and not voucher:
        return False
    if item.has_variations and not any(v.active for v in item.variations.all()):
        return False
    return item.is_available()


def _preise(voucher, item, variation, preis, currency):
    """Preis und – falls ein Gutschein den Preis ändert – neuer Preis, jeweils formatiert."""
    neu = None
    if voucher is not None and voucher.applies_to(item, variation):
        neu = voucher.calculate_price(preis)
    return {
        'preis': money_filter(preis, currency),
        'preis_neu': money_filter(neu, currency) if neu is not None and neu != preis else None,
    }


def varianten(item, currency, voucher=None):
    """Aktive Varianten eines Produkts (z. B. Standard/Ermäßigt) mit Preis; leer bei Produkten ohne Varianten."""
    if not item or not item.has_variations:
        return []
    return [
        dict(
            id=v.pk,
            name=str(v.value),
            beschreibung=str(v.description).strip() if v.description else '',
            **_preise(voucher, item, v, v.default_price if v.default_price is not None else item.default_price, currency),
        )
        for v in item.variations.all() if v.active
    ]


def tischname(zone, reihe, mehrere_zonen):
    return f'{zone} {reihe}' if mehrere_zonen else reihe


def gutschein_plaetze(event):
    """Plätze, die ein gültiger, noch nicht eingelöster Gutschein festhält: {Platz-ID: Gutschein}."""
    return {
        v.seat.seat_guid: v for v in Voucher.objects.filter(
            event=event, seat__isnull=False, subevent__isnull=True, redeemed__lt=F('max_usages'),
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=now())).select_related('seat')
    }


def saalplan_daten(event, request=None, voucher=None, admin=False, mit_namen=True):
    """Alles, was der Plan zum Zeichnen braucht: Flächen, Plätze mit Status, Kategorien mit Preis, Regeln.

    Status im Shop: frei / belegt / gesperrt (nicht buchbar).
    Im Backend zusätzlich: verkauft (mit Bestellung), gutschein (durch Gutschein reserviert), warenkorb, blockiert.
    Löst jemand einen Gutschein mit festem Platz ein, ist im Shop nur dieser Platz frei.
    """
    plan = event.seating_plan
    layout = plan.layout_data
    mehrere_zonen = len(layout.get('zones', [])) > 1
    kanal = getattr(getattr(request, 'sales_channel', None), 'identifier', 'web')
    frei = set(event.free_seats(ignore_voucher=voucher, sales_channel=kanal).values_list('seat_guid', flat=True))
    sitze = {s.seat_guid: s for s in event.seats.filter(subevent__isnull=True)}
    # Produkte einmal laden und je Produkt nur einmal prüfen (sonst einige hundert Abfragen pro Seitenaufruf)
    produkte = event.items.prefetch_related('variations').in_bulk({s.product_id for s in sitze.values() if s.product_id})
    buchbar_cache = {}

    gutschein_platz = voucher.seat.seat_guid if voucher is not None and voucher.seat_id else None
    if gutschein_platz:
        frei &= {gutschein_platz}

    verkauft, reserviert = {}, {}
    if admin:
        for g, v in gutschein_plaetze(event).items():
            reserviert[g] = {
                'o': v.code,
                'n': v.comment or v.tag or '',
                'u': reverse('control:event.voucher', kwargs={
                    'organizer': event.organizer.slug, 'event': event.slug, 'voucher': v.pk,
                }),
            }
        for op in OrderPosition.objects.filter(
            order__event=event, seat__isnull=False, subevent__isnull=True,
            order__status__in=[Order.STATUS_PENDING, Order.STATUS_PAID], canceled=False,
        ).select_related('order', 'order__invoice_address', 'seat', 'variation'):
            verkauft[op.seat.seat_guid] = {
                'o': op.order.code,
                'n': op.attendee_name or (op.order.invoice_address.name if hasattr(op.order, 'invoice_address') else '') or op.order.email or '',
                'u': reverse('control:event.order', kwargs={
                    'organizer': event.organizer.slug, 'event': event.slug, 'code': op.order.code,
                }),
                'bezahlt': op.order.status == Order.STATUS_PAID,
                'v': str(op.variation.value) if op.variation else '',
                # Varianten mit Beschreibung (z. B. Ermäßigt) brauchen am Einlass einen Nachweis
                'nachweis': bool(op.variation and op.variation.description and str(op.variation.description).strip()),
            }

    farben = {k['name']: k.get('color') or '#999999' for k in layout.get('categories', [])}
    kategorien = {}
    produkt_varianten = {}
    produkt_infos = {}
    plaetze = []
    for raw in plan.iter_all_seats():
        sitz = sitze.get(raw.guid)
        item = produkte.get(sitz.product_id) if sitz else None
        if item is None:
            buchbar = False
        elif admin:
            buchbar = True
        else:
            if item.pk not in buchbar_cache:
                buchbar_cache[item.pk] = _buchbar(item, voucher)
            buchbar = buchbar_cache[item.pk]
        if raw.guid in verkauft:
            status = 'verkauft'
        elif raw.guid in reserviert:
            status = 'gutschein'
        elif admin and sitz and sitz.blocked:
            status = 'blockiert'
        elif buchbar and raw.guid in frei:
            status = 'frei'
        elif buchbar:
            status = 'warenkorb' if admin else 'belegt'
        else:
            status = 'gesperrt'
        if buchbar and item.pk not in produkt_varianten:
            produkt_varianten[item.pk] = varianten(item, event.currency, voucher)
            produkt_infos[str(item.pk)] = dict(name=str(item.name), **_preise(voucher, item, None, item.default_price, event.currency))
        if raw.category not in kategorien:
            vs = produkt_varianten.get(item.pk) if buchbar else None
            if not buchbar:
                preis = None
            elif vs:
                preis = ' / '.join(f'{v["name"]} {v["preis"]}' for v in vs)
            else:
                preis = money_filter(item.default_price, event.currency)
            kategorien[raw.category] = {
                'name': raw.category,
                'farbe': farben.get(raw.category, '#999999'),
                'preis': preis,
            }
        p = {
            'g': raw.guid,
            'x': round(raw.x, 2),
            'y': round(raw.y, 2),
            'k': raw.category,
            's': status,
            'i': item.pk if buchbar else None,
            'l': str(sitz) if sitz else raw.guid,
            't': tischname(raw.zone, raw.row, mehrere_zonen),
            'nr': raw.number,
        }
        if raw.guid in verkauft:
            p.update(verkauft[raw.guid] if mit_namen else {'o': verkauft[raw.guid]['o']})
        elif raw.guid in reserviert:
            p.update(reserviert[raw.guid])
        plaetze.append(p)

    flaechen = []
    for z in layout.get('zones', []):
        zx, zy = z.get('position', {}).get('x', 0), z.get('position', {}).get('y', 0)
        for a in z.get('areas', []):
            a = dict(a)
            a['position'] = {'x': zx + a['position']['x'], 'y': zy + a['position']['y']}
            flaechen.append(a)

    return {
        'groesse': layout.get('size', {'width': 1000, 'height': 1000}),
        'radius': SITZ_RADIUS,
        'flaechen': flaechen,
        'plaetze': plaetze,
        'kategorien': list(kategorien.values()),
        'varianten': {str(k): v for k, v in produkt_varianten.items() if v},
        'produkte': produkt_infos,
        # Gutschein mit festem Platz: keine Lücken-/Tischregeln, der Platz ist vorgegeben
        'regeln': {'tischmodus': 'einzeln', 'luecken': False, 'restplatz': False, 'vorschlag': False} if gutschein_platz else einstellungen(event),
        'gutschein_platz': gutschein_platz,
        'modus': 'admin' if admin else 'shop',
    }
