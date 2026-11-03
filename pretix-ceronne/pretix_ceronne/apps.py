# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Club Céronne im ETV Hamburg e.V.
from django.utils.translation import gettext_lazy as _

from pretix.base.plugins import PluginConfig

from . import __version__


class PluginApp(PluginConfig):
    default = True
    name = "pretix_ceronne"
    verbose_name = "Céronne Saalplan"

    class PretixPluginMeta:
        name = _("Céronne Saalplan")
        author = "Club Céronne im ETV Hamburg"
        description = _(
            "Saalplan hochladen, Sitzplatz-Kategorien Produkten zuordnen und im Shop Plätze "
            "per Maus oder Tastatur auswählen lassen."
        )
        visible = True
        version = __version__
        category = "FEATURE"
        compatibility = "pretix>=2025.1.0"

    def ready(self):
        from . import signals  # NOQA
