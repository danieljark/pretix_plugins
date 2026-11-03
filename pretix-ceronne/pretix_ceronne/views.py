# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Club Céronne im ETV Hamburg e.V.
import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import translation
from django.utils.text import slugify
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView, View

from pretix.base.models import SeatCategoryMapping, SeatingPlan
from pretix.base.models.seating import SeatingPlanLayoutValidator
from pretix.base.services.seating import (
    SeatProtected, generate_seats, validate_plan_change,
)
from pretix.control.permissions import EventPermissionRequiredMixin

from . import pdf
from .daten import saalplan_daten
from .regeln import TISCHMODI, einstellungen


class SaalplanView(EventPermissionRequiredMixin, TemplateView):
    """Saalplan der Veranstaltung wählen bzw. hochladen und Kategorien Produkten zuordnen."""
    permission = 'event.settings.general:write'
    template_name = 'pretix_ceronne/control_saalplan.html'

    def _url(self, **query):
        url = reverse('plugins:pretix_ceronne:saalplan', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug,
        })
        if query:
            url += '?' + '&'.join(f'{k}={v}' for k, v in query.items())
        return url

    def _gewaehlter_plan(self):
        event = self.request.event
        pid = self.request.GET.get('plan')
        if pid:
            return event.organizer.seating_plans.filter(pk=pid).first()
        return event.seating_plan

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = self.request.event
        plan = self._gewaehlter_plan()
        zuordnung = {
            m.layout_category: m.product_id
            for m in event.seat_category_mappings.filter(subevent__isnull=True)
        }
        produkte = list(event.items.filter(active=True).order_by('category__position', 'position'))
        kategorien = []
        if plan:
            anzahl = {}
            for s in plan.iter_all_seats():
                anzahl[s.category] = anzahl.get(s.category, 0) + 1
            for k in plan.layout_data.get('categories', []):
                kategorien.append({
                    'name': k['name'],
                    'farbe': k.get('color') or '#999999',
                    'plaetze': anzahl.get(k['name'], 0),
                    'produkt': zuordnung.get(k['name']),
                })
        ctx.update({
            'plan': plan,
            'aktiver_plan': event.seating_plan,
            'plaene': event.organizer.seating_plans.order_by('name'),
            'kategorien': kategorien,
            'produkte': produkte,
            'reihe': event.has_subevents,
            'plaetze_gesamt': event.seats.filter(subevent__isnull=True).count(),
            'plaetze_verkauft': event.taken_seats().count() if event.seating_plan else 0,
            'regeln': einstellungen(event),
            'tischmodi': TISCHMODI,
        })
        return ctx

    def post(self, request, *args, **kwargs):
        aktion = request.POST.get('aktion')
        if aktion == 'hochladen':
            return self._hochladen()
        if aktion == 'speichern':
            return self._speichern()
        if aktion == 'entfernen':
            return self._entfernen()
        return redirect(self._url())

    def _hochladen(self):
        datei = self.request.FILES.get('datei')
        name = (self.request.POST.get('name') or '').strip()
        if not datei:
            messages.error(self.request, 'Bitte eine Saalplan-Datei (JSON) auswählen.')
            return redirect(self._url())
        if datei.size > 5 * 1024 * 1024:
            messages.error(self.request, 'Die Datei ist zu groß (höchstens 5 MB).')
            return redirect(self._url())
        try:
            daten = json.loads(datei.read().decode('utf-8'))
            layout = json.dumps(daten)
            SeatingPlanLayoutValidator()(layout)
        except (ValueError, UnicodeDecodeError):
            messages.error(self.request, 'Die Datei ist keine gültige JSON-Datei.')
            return redirect(self._url())
        except ValidationError as e:
            messages.error(self.request, 'Der Saalplan ist ungültig: ' + '; '.join(e.messages))
            return redirect(self._url())
        plan = SeatingPlan.objects.create(
            organizer=self.request.event.organizer,
            name=name or daten.get('name') or datei.name,
            layout=layout,
        )
        plan.log_action('pretix_ceronne.saalplan.hochgeladen', user=self.request.user)
        messages.success(self.request, f'Saalplan „{plan.name}“ hochgeladen. Jetzt die Kategorien zuordnen und speichern.')
        return redirect(self._url(plan=plan.pk))

    def _speichern(self):
        event = self.request.event
        if event.has_subevents:
            messages.error(self.request, 'Veranstaltungsreihen werden nicht unterstützt.')
            return redirect(self._url())
        plan = event.organizer.seating_plans.filter(pk=self.request.POST.get('plan')).first()
        if not plan:
            messages.error(self.request, 'Bitte einen Saalplan auswählen.')
            return redirect(self._url())
        produkte = {str(p.pk): p for p in event.items.all()}
        zuordnung = {}
        for k in plan.get_categories():
            pid = self.request.POST.get('kategorie_' + k.name)
            if pid and pid in produkte:
                zuordnung[k.name] = produkte[pid]
        try:
            with transaction.atomic():
                validate_plan_change(event, None, plan)
                event.seating_plan = plan
                event.save(update_fields=['seating_plan'])
                event.seat_category_mappings.filter(subevent__isnull=True).delete()
                SeatCategoryMapping.objects.bulk_create([
                    SeatCategoryMapping(event=event, layout_category=k, product=p)
                    for k, p in zuordnung.items()
                ])
                generate_seats(event, None, plan, zuordnung)
                event.settings.seating_choice = True
                self._regeln_speichern()
                event.cache.clear()
        except SeatProtected as e:
            messages.error(self.request, str(e))
            return redirect(self._url(plan=plan.pk))
        event.log_action('pretix_ceronne.saalplan.gespeichert', user=self.request.user, data={
            'plan': plan.pk, 'zuordnung': {k: p.pk for k, p in zuordnung.items()},
        })
        frei = len([k for k in plan.get_categories() if k.name not in zuordnung])
        hinweis = f' {frei} Kategorie(n) ohne Produkt sind im Shop nicht buchbar.' if frei else ''
        messages.success(self.request, 'Saalplan gespeichert.' + hinweis)
        return redirect(self._url())

    def _regeln_speichern(self):
        s = self.request.event.settings
        modus = self.request.POST.get('tischmodus')
        s.ceronne_tischmodus = modus if modus in dict(TISCHMODI) else 'beides'
        s.ceronne_luecken = self.request.POST.get('luecken') == 'on'
        s.ceronne_restplatz = self.request.POST.get('restplatz') == 'on'
        s.ceronne_vorschlag = self.request.POST.get('vorschlag') == 'on'

    def _entfernen(self):
        event = self.request.event
        try:
            with transaction.atomic():
                validate_plan_change(event, None, None)
                generate_seats(event, None, None, {})
                event.seat_category_mappings.filter(subevent__isnull=True).delete()
                event.seating_plan = None
                event.save(update_fields=['seating_plan'])
                event.cache.clear()
        except SeatProtected as e:
            messages.error(self.request, str(e))
            return redirect(self._url())
        event.log_action('pretix_ceronne.saalplan.entfernt', user=self.request.user)
        messages.success(self.request, 'Saalplan von der Veranstaltung entfernt.')
        return redirect(self._url())


class BelegungView(EventPermissionRequiredMixin, TemplateView):
    """Saalplan mit verkauften Plätzen (Bestellung, Name) und Plätze sperren/freigeben."""
    permission = 'event.settings.general:write'
    template_name = 'pretix_ceronne/control_belegung.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = self.request.event
        if event.seating_plan:
            daten = saalplan_daten(event, self.request, admin=True)
            ctx['daten'] = daten
            ctx['verkauft'] = sorted((p for p in daten['plaetze'] if p['s'] == 'verkauft'), key=lambda p: (p['t'], p['l']))
            ctx['reserviert'] = sorted((p for p in daten['plaetze'] if p['s'] == 'gutschein'), key=lambda p: (p['t'], p['l']))
            zaehler = {}
            for p in daten['plaetze']:
                zaehler[p['s']] = zaehler.get(p['s'], 0) + 1
            ctx['zaehler'] = zaehler
        return ctx

    def post(self, request, *args, **kwargs):
        event = request.event
        gesperrt = set(request.POST.getlist('gesperrt'))
        sitze = event.seats.filter(subevent__isnull=True)
        verkauft = set(event.taken_seats().values_list('seat_guid', flat=True))
        an = sitze.filter(seat_guid__in=gesperrt - verkauft, blocked=False).update(blocked=True)
        aus = sitze.filter(blocked=True).exclude(seat_guid__in=gesperrt).update(blocked=False)
        event.cache.clear()
        event.log_action('pretix_ceronne.saalplan.sperren', user=request.user, data={'gesperrt': sorted(gesperrt)})
        messages.success(request, f'Gespeichert: {an} Platz/Plätze gesperrt, {aus} freigegeben.')
        return redirect(reverse('plugins:pretix_ceronne:belegung', kwargs={
            'organizer': event.organizer.slug, 'event': event.slug,
        }))


class SaalplanDatenView(EventPermissionRequiredMixin, View):
    """Plan als JSON für die Platzauswahl im Gutschein-Formular – ohne Namen der Käufer."""
    permission = None

    def get(self, request, *args, **kwargs):
        if not request.event.seating_plan:
            return JsonResponse({'fehler': 'kein Saalplan'}, status=404)
        return JsonResponse(saalplan_daten(request.event, request, admin=True, mit_namen=False))


class SaalplanPdfView(EventPermissionRequiredMixin, View):
    """Saalliste (Tisch für Tisch mit Namen) oder Saalplan in Schwarz-Weiß als PDF."""
    permission = 'event.orders:read'
    art = 'liste'

    def get(self, request, *args, **kwargs):
        event = request.event
        if not event.seating_plan:
            return HttpResponse('Kein Saalplan', status=404)
        # Ausdrucke immer auf Deutsch (Datum, Preise, Platzbezeichnungen), unabhängig von der Backend-Sprache
        with translation.override('de'):
            daten = saalplan_daten(event, request, admin=True)
            if self.art == 'liste':
                inhalt, name = pdf.saalliste(event, daten), 'saalliste'
            else:
                inhalt, name = pdf.saalplan(event, daten, request.GET.get('format', 'A4')), 'saalplan'
        antwort = HttpResponse(inhalt, content_type='application/pdf')
        antwort['Content-Disposition'] = f'inline; filename="{name}-{slugify(event.slug)}.pdf"'
        return antwort


def status_im_shop(request, *args, **kwargs):
    """Live-Status für den Shop: welche buchbaren Plätze gerade frei sind. Kurz zwischengespeichert, damit viele
    gleichzeitige Besucher den Server nicht belasten."""
    event = request.event
    if not event.seating_plan_id:
        return JsonResponse({'frei': []})
    schluessel = f'pretix_ceronne_status_{event.pk}'
    frei = cache.get(schluessel)
    if frei is None:
        frei = sorted(event.free_seats().filter(subevent__isnull=True, product__isnull=False).values_list('seat_guid', flat=True))
        cache.set(schluessel, frei, 3)
    antwort = JsonResponse({'frei': frei})
    antwort['Cache-Control'] = 'no-store'
    return antwort
