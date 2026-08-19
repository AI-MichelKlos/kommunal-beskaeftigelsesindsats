# Kommunal beskæftigelsesindsats

Interaktivt dashboard om kommunal ledighed, kontanthjælp og aktivering med fokus på sammenlignelige mål.

Dashboardet åbner som standard på **Hele landet**. Øverst kan man vælge et område og sammenligne med hele landet eller en af de øvrige kommuner.

Dashboardet indeholder:

1. Ledighedsprocent og faktiske ledighedstal.
2. Ledige fordelt på dagpenge og arbejdsmarkedsparat kontanthjælp.
3. Langtidsledighed.
4. Indeks 100 for ledighed og langtidsledighed i den valgte kommune og hele landet.
5. Dagpengeandel blandt alle ledige og blandt langtidsledige.
6. Kontanthjælpsmodtagere som personer, fuldtidspersoner og andel af befolkningen.
7. Fordeling efter visitationskategori.
8. Andel med ordinære løntimer.
9. Aktiveringsgrad og andel aktiveringsberørte.
10. Aktiverede personer, antal forløb og fordeling på fem hovedtyper af aktiveringstilbud.

Nytilmeldte ledige, forløbsvarighed og beskæftigelse efter nyledighed er taget ud, fordi de tidligere API-udtræk enten var tomme, fejlfortolkede eller ikke kunne hentes stabilt. De nye sammenligninger beregnes alene fra de to Jobindsats-tabeller, der leverer komplette kommune- og landstal.

Data hentes fra Jobindsats.dk / STAR. Ledighed og langtidsledighed kommer fra `y25i01` og `y25i09`. Kontanthjælp og visitationskategori kommer fra `y60a02`, aktivering fra `y60c07`, tilbud fra `y60c02` og ordinære løntimer fra `y60j01`.

Kontanthjælpsreformen fra 1. juli 2025 giver et databrud, som fremgår direkte i dashboardet. Små tal kan være diskretioneret og vises derfor som manglende.

## Automatisk drift

GitHub Actions-workflowet `.github/workflows/update-dashboard.yml` kører dagligt med flere backupforsøg og kan startes manuelt. Jobindsats-token ligger som repository secret `API_ADGANG`.

Dashboardet er klargjort til GitHub Pages fra `main` og repository-roden.
