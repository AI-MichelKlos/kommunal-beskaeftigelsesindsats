# Kommunal beskæftigelsesindsats

Interaktivt dashboard om ledighed med fokus på dagpengemodtagere og arbejdsmarkedsparate kontanthjælpsmodtagere.

Dashboardet åbner som standard på **Hele landet**. Øverst kan man vælge en kommune. Når dashboardet viser procentmål, sammenlignes den valgte kommune med det officielle landstal fra samme Jobindsats-måling.

Dashboardet indeholder overblik, udvikling over tid, ydelsessammensætning, nytilmeldte ledige, langtidsledighed, varighed og vej til job. Kommunekort og kommunerangering er bevidst taget ud og kan bygges som et selvstændigt kortdashboard.

Data hentes fra Jobindsats.dk / STAR.

## Automatisk drift

GitHub Actions-workflowet `.github/workflows/update-dashboard.yml` kører dagligt med flere backupforsøg og kan startes manuelt. Jobindsats-token ligger som repository secret `API_ADGANG`.

Dashboardet er klargjort til GitHub Pages fra `main` og repository-roden.
