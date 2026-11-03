# pretix-Plugins des Club Céronne

Eigene Erweiterungen für das Ticketsystem [pretix](https://pretix.eu), entwickelt für den Ticket-Shop des
[Club Céronne im ETV Hamburg e.V.](https://ceronne.de) und hier unter einer freien Lizenz veröffentlicht.

| Plugin | Zweck | Stand |
|---|---|---|
| [`pretix-ceronne`](pretix-ceronne/README.md) | **Saalplan mit Platzwahl** für die Community-Version von pretix: Plan hochladen, Kategorien Produkten zuordnen, Plätze im Shop per Maus, Tastatur oder Liste wählen, Buchungsregeln, Gutscheine mit festem Platz, Belegung und Ausdrucke | im Einsatz, getestet mit pretix 2026.9 |

## Lizenz

Alle Plugins in diesem Repository stehen unter der **GNU Affero General Public License, Version 3 oder später**
(AGPL-3.0-or-later), siehe [`LICENSE`](LICENSE). Das ist dieselbe Lizenz wie die von pretix selbst.

Was das in der Praxis heißt:

- Du darfst den Code **kostenlos nutzen, verändern und weitergeben**, auch für kommerzielle Veranstaltungen.
- Betreibst du einen pretix-Shop mit diesem Plugin, der für andere über das Internet erreichbar ist, musst du den
  **Quellcode der von dir eingesetzten Version** (inkl. deiner Änderungen) den Besuchern unter derselben Lizenz
  zugänglich machen. Das Plugin erledigt das selbst: Es setzt in die Shop-Fußzeile einen Link
  „Quellcode Saalplan-Plugin“ auf dieses Repository. Wenn du das Plugin veränderst, lass den Link auf **deine**
  veröffentlichte Fassung zeigen (Konstante `QUELLCODE_URL` in `pretix_ceronne/signals.py`).
- Es gibt **keine Gewährleistung** (siehe Abschnitte 15 und 16 der Lizenz).

Für pretix selbst gelten zusätzlich dessen eigene Lizenzbedingungen (AGPLv3 mit Zusatzbedingungen, siehe
[pretix-Lizenz](https://pretix.eu/about/en/license)). „pretix“ ist eine Marke der pretix GmbH; dieses Projekt ist
**kein offizielles pretix-Produkt** und steht in keiner Verbindung zur pretix GmbH.

## Mitmachen / Kontakt

Fehler und Verbesserungsvorschläge gern als [Issue](https://github.com/danieljark/pretix_plugins/issues).
Änderungen per Pull-Request werden unter derselben Lizenz (AGPL-3.0-or-later) übernommen.
