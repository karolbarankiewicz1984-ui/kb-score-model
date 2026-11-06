# Competition identity repair — 2026-11-06

Archived queue contained English/Russian Premier League and German/Austrian Bundesliga under identical display names. Country codes were absent but league IDs were present.

Research mapping introduced: l_4WFCIZ ENG Premier League; l_1Isor4 DEU Bundesliga; l_0ALvwF ITA Serie A; l_0ErfuF ESP La Liga; l_3FJFUl FRA Ligue 1. These mappings derive from fixture examples; independent provider metadata verification is still required.

Unknown IDs remain blocked, conflicting country metadata is rejected, and pre-match timing checks remain unchanged. Spanish LaLiga is normalized to La Liga. Prediction and settlement code use the same mapping. Four tests were added and GitHub Actions run 42185024498 started. Team-name alias coverage and final coverage metrics remain to be verified.
