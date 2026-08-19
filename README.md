# Kommunal beskæftigelsesindsats

Interaktivt dashboard om kommunal ledighed og langtidsledighed med fokus på sammenlignelige mål.

Dashboardet åbner som standard på **Hele landet**. Øverst kan man vælge en kommune og slå sammenligning med det officielle landstal til eller fra.

Dashboardet indeholder:

1. Ledighedsprocent og faktiske ledighedstal.
2. Ledige fordelt på dagpenge og arbejdsmarkedsparat kontanthjælp.
3. Langtidsledighed.
4. Indeks 100 for ledighed og langtidsledighed i den valgte kommune og hele landet.
5. Dagpengeandel blandt alle ledige og blandt langtidsledige.

Nytilmeldte ledige, forløbsvarighed og beskæftigelse efter nyledighed er taget ud, fordi de tidligere API-udtræk enten var tomme, fejlfortolkede eller ikke kunne hentes stabilt. De nye sammenligninger beregnes alene fra de to Jobindsats-tabeller, der leverer komplette kommune- og landstal.

Data hentes fra Jobindsats.dk / STAR, tabel `y25i01` for ledighed og tabel `y25i09` for langtidsledighed.

## Automatisk drift

GitHub Actions-workflowet `.github/workflows/update-dashboard.yml` kører dagligt med flere backupforsøg og kan startes manuelt. Jobindsats-token ligger som repository secret `API_ADGANG`.

Dashboardet er klargjort til GitHub Pages fra `main` og repository-roden.
