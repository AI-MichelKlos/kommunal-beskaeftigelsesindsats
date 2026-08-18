# Kommunal beskæftigelsesindsats

Interaktivt dashboard om kommunal ledighed med fokus på dagpengemodtagere og arbejdsmarkedsparate kontanthjælpsmodtagere.

Dashboardet indeholder overblik, kommunekort, kommunerangering, udvikling over tid, ydelsessammensætning, nytilmeldte ledige, langtidsledighed, varighed og vej til job.

Data hentes fra Jobindsats.dk / STAR. Kortgeometri hentes fra Dataforsyningen i browseren.

## Automatisk drift

GitHub Actions-workflowet `.github/workflows/update-dashboard.yml` kører dagligt med flere backupforsøg og kan startes manuelt. Jobindsats-token skal ligge som repository secret `API_ADGANG`.

Dashboardet er klargjort til GitHub Pages fra `main` og repository-roden.
