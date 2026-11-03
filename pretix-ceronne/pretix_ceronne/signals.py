# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Club Céronne im ETV Hamburg e.V.
from django.dispatch import receiver
from django.templatetags.static import static
from django.template.loader import get_template
from django.utils.html import format_html
from django.urls import resolve, reverse

from pretix.base.services.cart import CartError
from pretix.base.signals import validate_cart
from pretix.multidomain.urlreverse import eventreverse
from pretix.control.signals import html_head as control_html_head, nav_event
from pretix.presale.signals import footer_link, render_seating_plan

from .daten import saalplan_daten, tischname
from .regeln import einstellungen, pruefen

QUELLCODE_URL = 'https://github.com/danieljark/pretix_plugins'


@receiver(nav_event, dispatch_uid='pretix_ceronne_nav')
def navigation(sender, request=None, **kwargs):
    if not request.user.has_event_permission(request.organizer, request.event, 'event.settings.general:write', request):
        return []
    kw = {'organizer': request.event.organizer.slug, 'event': request.event.slug}
    url = resolve(request.path_info)
    aktiv = url.namespace == 'plugins:pretix_ceronne'
    return [{
        'label': 'Saalplan',
        'url': reverse('plugins:pretix_ceronne:saalplan', kwargs=kw),
        'active': aktiv,
        'icon': 'th',
        'children': [
            {'label': 'Einrichtung', 'url': reverse('plugins:pretix_ceronne:saalplan', kwargs=kw),
             'active': aktiv and url.url_name == 'saalplan'},
            {'label': 'Belegung', 'url': reverse('plugins:pretix_ceronne:belegung', kwargs=kw),
             'active': aktiv and url.url_name == 'belegung'},
        ],
    }]


@receiver(footer_link, dispatch_uid='pretix_ceronne_quellcode')
def quellcode_link(sender, request=None, **kwargs):
    """Link auf den Quellcode in der Shop-Fußzeile – erfüllt die Pflicht der AGPL, den Code den Besuchern anzubieten."""
    return [{'label': 'Quellcode Saalplan-Plugin', 'url': QUELLCODE_URL}]


@receiver(control_html_head, dispatch_uid='pretix_ceronne_gutschein')
def platzauswahl_im_gutschein(sender, request=None, **kwargs):
    """Im Gutschein-Formular neben „Bestimmter Sitzplatz“ einen Saalplan zur Auswahl anbieten."""
    if not sender.seating_plan_id:
        return ''
    url = resolve(request.path_info)
    if url.url_name not in ('event.voucher', 'event.vouchers.add', 'event.vouchers.bulk'):
        return ''
    daten_url = reverse('plugins:pretix_ceronne:daten', kwargs={
        'organizer': sender.organizer.slug, 'event': sender.slug,
    })
    return format_html(
        '<link rel="stylesheet" href="{}">'
        '<script src="{}" defer></script>'
        '<script src="{}" data-daten-url="{}" defer></script>',
        static('pretix_ceronne/saalplan.css'),
        static('pretix_ceronne/saalplan.js'),
        static('pretix_ceronne/gutschein.js'),
        daten_url,
    )


@receiver(render_seating_plan, dispatch_uid='pretix_ceronne_saalplan')
def saalplan_im_shop(sender, request, subevent=None, voucher=None, **kwargs):
    if subevent is not None or not sender.seating_plan_id:
        return ''
    daten = saalplan_daten(sender, request, voucher)
    if not daten['gutschein_platz']:
        daten['status_url'] = eventreverse(sender, 'plugins:pretix_ceronne:status')
    daten['veranstaltung'] = sender.pk
    daten['einloesen_url'] = eventreverse(sender, 'presale:event.redeem')
    daten['gutschein'] = voucher.code if voucher is not None else None
    gruppen = {}
    for p in daten['plaetze']:
        if p['s'] == 'frei':
            vs = daten['varianten'].get(str(p['i']))
            p['optionen'] = [
                {'name': f'seat_{p["i"]}_{v["id"]}', 'text': f'{p["l"]} – {v["name"]} {v["preis"]}', 'variante': v['id']}
                for v in vs
            ] if vs else [{'name': f'seat_{p["i"]}', 'text': p['l'], 'variante': ''}]
            gruppen.setdefault(p['t'], []).append(p)
    return get_template('pretix_ceronne/saalplan.html').render({
        'daten': daten,
        'gruppen': gruppen,
        'frei': sum(1 for p in daten['plaetze'] if p['s'] == 'frei'),
        'regeln': daten['regeln'],
    }, request=request)


@receiver(validate_cart, dispatch_uid='pretix_ceronne_regeln')
def regeln_vor_der_kasse(sender, positions, **kwargs):
    """Buchungsregeln serverseitig durchsetzen, bevor die Kasse beginnt."""
    if not sender.seating_plan_id:
        return
    regeln = einstellungen(sender)
    if regeln['tischmodus'] != 'nur_tische' and not regeln['luecken'] and not regeln['restplatz']:
        return
    # Plätze aus Gutscheinen mit festem Platz sind vorgegeben – für sie gelten die Regeln nicht
    auswahl, gutschein = set(), set()
    for p in positions:
        if not p.seat_id or p.subevent_id is not None:
            continue
        (gutschein if p.voucher_id and p.voucher.seat_id else auswahl).add(p.seat.seat_guid)
    if not auswahl:
        return
    mehrere_zonen = len(sender.seating_plan.layout_data.get('zones', [])) > 1
    alle = sender.seats.filter(subevent__isnull=True).values('seat_guid', 'x', 'y', 'zone_name', 'row_name', 'product_id')
    sitze = [
        {'g': s['seat_guid'], 'x': s['x'] or 0, 'y': s['y'] or 0, 't': tischname(s['zone_name'], s['row_name'], mehrere_zonen)}
        for s in alle
    ]
    frei = set(sender.free_seats().values_list('seat_guid', flat=True))
    unbuchbar = {s['seat_guid'] for s in alle if not s['product_id']}
    belegt = ({s['g'] for s in sitze} - frei - auswahl) | unbuchbar | gutschein
    fehler = pruefen(sitze, belegt, auswahl, regeln)
    if fehler:
        raise CartError(fehler)
