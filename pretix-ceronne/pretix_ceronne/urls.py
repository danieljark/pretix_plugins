# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Club Céronne im ETV Hamburg e.V.
from django.urls import re_path

from .views import (
    BelegungView, SaalplanDatenView, SaalplanPdfView, SaalplanView, status_im_shop,
)

urlpatterns = [
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/saalplan/$',
            SaalplanView.as_view(), name='saalplan'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/saalplan/belegung/$',
            BelegungView.as_view(), name='belegung'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/saalplan/daten\.json$',
            SaalplanDatenView.as_view(), name='daten'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/saalplan/saalliste\.pdf$',
            SaalplanPdfView.as_view(art='liste'), name='saalliste'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/saalplan/saalplan\.pdf$',
            SaalplanPdfView.as_view(art='plan'), name='saalplan_pdf'),
]

# Shop-Adressen (unterhalb der Veranstaltung)
event_patterns = [
    re_path(r'^saalplan/status\.json$', status_im_shop, name='status'),
]
