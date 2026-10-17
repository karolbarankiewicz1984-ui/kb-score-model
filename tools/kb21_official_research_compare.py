"""Compare transcribed official organizer fixture facts to ESPN discovery data.

Five core leagues, research only. A match means same teams + league + kickoff,
not independently authenticated organizer evidence. Calendar Gate stays BLOCKED;
other scoped leagues and signed-off data still required.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from tools.kb21_fixture_crosscheck import _canonical, _instant

LEAGUE_ALIASES = {
    "eng.1": [
        ["manchester city", "man city"],
        ["newcastle united", "newcastle"],
        ["brighton hove albion", "brighton and hove albion", "brighton"],
        ["afc bournemouth", "bournemouth"],
        ["nottingham forest", "nott m forest", "nott'm forest"],
        ["tottenham hotspur", "tottenham", "spurs"],
        ["hull city", "hull"],
        ["ipswich town", "ipswich"],
        ["leeds united", "leeds"],
        ["manchester united", "man utd", "man united"],
        ["aston villa", "villa"],
    ],
    "esp.1": [
        ["rcd espanyol", "rcd espanyol de barcelona", "espanyol"],
        ["atletico de madrid", "atletico madrid", "atletico"],
        ["fc barcelona", "barcelona", "barca"],
        ["real betis", "betis"],
        ["ca osasuna", "osasuna"],
        ["r racing club", "racing club", "racing santander", "real racing club"],
        ["celta vigo", "celta", "rc celta"],
        ["deportivo alaves", "alaves"],
        ["malaga", "malaga cf"],
        ["real sociedad", "sociedad"],
        ["real madrid", "madrid"],
        ["getafe", "getafe cf"],
        ["rayo vallecano", "rayo"],
        ["valencia", "valencia cf"],
        ["athletic club", "athletic bilbao"],
        ["villarreal", "villarreal cf"],
        ["elche", "elche cf"],
    ],
    "ita.1": [
        ["inter", "inter milan", "internazionale"],
        ["ac milan", "milan"],
        ["as roma", "roma"],
        ["ssc napoli", "napoli"],
        ["venezia", "venezia fc"],
        ["bologna", "bologna fc"],
        ["ac fiorentina", "fiorentina"],
        ["como", "como 1907"],
        ["atalanta", "atalanta bc"],
        ["juventus", "juventus fc"],
        ["udinese", "udinese calcio"],
        ["us lecce", "lecce"],
        ["parma", "parma calcio"],
        ["torino", "torino fc"],
        ["lazio", "ss lazio"],
        ["genoa", "genoa cfc"],
        ["monza", "ac monza"],
        ["cagliari", "cagliari calcio"],
    ],
    "ger.1": [
        ["union berlin", "1 fc union berlin"],
        ["borussia dortmund", "dortmund"],
        ["hamburger sv", "hamburg"],
        ["vfb stuttgart", "stuttgart"],
        ["sv werder bremen", "werder bremen"],
        ["sc paderborn 07", "sc paderborn", "paderborn"],
        ["fc schalke 04", "schalke 04", "schalke"],
        ["1 fsv mainz 05", "fsv mainz 05", "mainz 05", "mainz"],
        ["sv elversberg", "elversberg"],
        ["fc augsburg", "augsburg"],
        ["fc bayern munchen", "bayern munich", "bayern munchen", "bayern"],
        ["rb leipzig", "leipzig"],
        ["bayer 04 leverkusen", "bayer leverkusen", "leverkusen"],
        ["sport club freiburg", "sc freiburg", "freiburg"],
        ["borussia monchengladbach", "monchengladbach", "m gladbach"],
        ["tsg hoffenheim", "hoffenheim"],
    ],
    "fra.1": [
        ["rc strasbourg alsace", "rc strasbourg", "strasbourg"],
        ["paris saint germain", "paris sg", "psg"],
        ["losc", "lille", "lille osc"],
        ["stade brestois 29", "stade brestois", "brest"],
        ["estac troyes", "troyes"],
        ["rc lens", "lens"],
        ["angers sco", "angers"],
        ["olympique de marseille", "marseille"],
        ["paris fc", "paris"],
        ["stade rennais fc", "stade rennais", "rennes"],
        ["fc lorient", "lorient"],
        ["as monaco", "monaco"],
        ["havre ac", "le havre", "le havre ac"],
        ["aj auxerre", "auxerre"],
        ["olympique lyonnais", "lyon"],
        ["ogc nice", "nice"],
    ],
}


def _alias_index(league):
    mapping = {}
    for group in LEAGUE_ALIASES.get(league, []):
        key = _canonical(group[0])
        for alternative in group:
            normalized = _canonical(alternative)
            if normalized in mapping and mapping[normalized] != key:
                raise ValueError(f"Ambiguous alias {league} / {alternative}")
            mapping[normalized] = key
    return mapping


def _team(league, value):
    norm = _canonical(value)
    return _alias_index(league).get(norm, norm)


def _club_pair(league, name):
    parts = name.split(" - ", 1) if isinstance(name, str) else []
    if len(parts) != 2:
        return None
    result = tuple(_team(league, x) for x in parts)
    return result if all(result) else None


def compare(queue, research):
    if not isinstance(queue, dict) or not isinstance(queue.get("fixtures"), list):
        raise ValueError("Expected KB21 queue with fixtures list")
    if not isinstance(research, dict) or research.get("schema") != "kb21-official-research-v1":
        raise ValueError("Expected unsigned official fixture research")
    if research.get("status") != "OFFICIAL_WEB_RESEARCH_UNSIGNED" or not isinstance(research.get("days"), dict):
        raise ValueError("Unsigned research required; don't accept purported signoff")
    days = sorted(set(queue.get("days", [])))
    result = {
        "status": "UNSIGNED_OFFICIAL_SOURCE_COMPARISON",
        "calendar_gate": "BLOCKED", "publication": "DIAGNOSTIC / NO PLAY",
        "organizer_authenticated": False, "human_signoff": False,
        "covered_competitions": sorted({code for day in research["days"].values()
                                        for code in day.keys()}),
        "days": {},
    }
    for day in days:
        day_data = research["days"].get(day, {})
        rows = []
        for league, source in sorted(day_data.items()):
            official = source.get("fixtures", [])
            if (not isinstance(official, list)
                    or not isinstance(source.get("official_source_url"), str)
                    or not source["official_source_url"].startswith("https://")
                    or not isinstance(source.get("source_reviewer_signed"), bool)
                    or source["source_reviewer_signed"]):
                raise ValueError(f"Invalid or misleading official research {day} / {league}")
            espn = [f for f in queue["fixtures"] if f.get("date_warsaw") == day
                    and str(f.get("fixture_id", "")).split(":")[0] == league]
            used = set()
            comparisons = []
            for record in official:
                identity = (_team(league, record.get("home")),
                            _team(league, record.get("away")))
                time = _instant(record.get("kickoff"))
                if not all(identity) or time is None or time.strftime("%Y-%m-%d") == "":  # UTC aware required
                    comparisons.append({"official_fixture": record,
                                        "status": "INVALID_OFFICIAL_RESEARCH_ENTRY",
                                        "espn_fixture_id": None})
                    continue
                matches_teams = []
                matches_time = []
                for candidate in espn:
                    if _club_pair(league, candidate.get("fixture", "")) != identity:
                        continue
                    matches_teams.append(candidate)
                    other = _instant(candidate.get("kickoff"))
                    if other is not None and abs((other - time).total_seconds()) <= 300:
                        matches_time.append(candidate)
                if len(matches_time) == 1:
                    target = matches_time[0].get("fixture_id")
                    if target in used or not target:
                        status, matched_id = "DUPLICATE_ESPN_IDENTITY", None
                    else:
                        used.add(target)
                        status, matched_id = "SAME_FIXTURE_IN_TWO_SOURCES", target
                else:
                    matched_id = None
                    status = ("AMBIGUOUS_ESPN_IDENTITY" if len(matches_time) > 1 else
                              "START_TIME_CONFLICT" if matches_teams else
                              "MISSING_FROM_ESPN")
                comparisons.append({"official_fixture": record,
                                    "status": status, "espn_fixture_id": matched_id})
            extra = [{"fixture_id": f.get("fixture_id"), "fixture": f.get("fixture"),
                      "kickoff": f.get("kickoff")}
                     for f in espn if f.get("fixture_id") not in used]
            counts = Counter(record["status"] for record in comparisons)
            league_status = (
                "TWO_SOURCE_REVIEW_CANDIDATE" if (
                    len(comparisons) == len(espn)
                    and len(used) == len(comparisons)
                    and not extra
                ) else "IDENTITY_OR_COVERAGE_REVIEW_REQUIRED")
            rows.append({
                "league_id": league,
                "competition": source.get("competition"),
                "official_url": source["official_source_url"],
                "official_research_fixture_count": len(official),
                "espn_fixture_count": len(espn),
                "matched_count": len(used),
                "comparison_counts": dict(sorted(counts.items())),
                "unmatched_espn": extra,
                "fixtures": comparisons,
                "status": league_status,
                "organizer_verified": False,
                "official_full_card_signed": False,
            })
        result["days"][day] = rows
    result["note"] = (
        "Fixture facts were transcribed from organizer pages for review. "
        "This is not a live official API, not a second signed human review, and NOT "
        "a Calendar Gate PASS. Never infer sporting scores or betting picks from this."
    )
    return result


def render(report):
    out = ["# KB Score 2.1 — porównanie oficjalnych źródeł z ESPN", "",
           "**BADANIE WSTĘPNE / NO PLAY — niezatwierdzone źródła, Calendar Gate BLOCKED.**", "",
           "| Dzień | Liga | W oficjalnym zestawieniu | ESPN | Zgodne | Stan |",
           "|---|---|---:|---:|---:|---|"]
    for day, rows in report["days"].items():
        for row in rows:
            out.append(f"| {day} | {row['competition']} | {row['official_research_fixture_count']} | "
                       f"{row['espn_fixture_count']} | {row['matched_count']} | {row['status']} |")
    out.extend(["", "## Różnice wymagające wyjaśnienia", ""])
    for day, rows in report["days"].items():
        for row in rows:
            problem = [f for f in row["fixtures"] if f["status"] != "SAME_FIXTURE_IN_TWO_SOURCES"]
            if problem or row["unmatched_espn"]:
                out.append(f"### {day} — {row['competition']}")
                for f in problem:
                    official = f["official_fixture"]
                    out.append(f"- Organizator: {official.get('home')} — {official.get('away')} "
                               f"({official.get('kickoff')}); {f['status']}")
                for f in row["unmatched_espn"]:
                    out.append(f"- Tylko ESPN: {f['fixture']} ({f['kickoff']})")
                out.append("")
    out.append("Do otwarcia kalendarza wymagane także pozostałe ligi, oficjalny odczyt "
               "każdego dnia oraz niezależne zatwierdzenie. Sama zgodność dwóch list "
               "nie odblokowuje typowania.")
    return "\n".join(out) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("official_research")
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-md", required=True)
    args = p.parse_args()
    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    research = json.loads(Path(args.official_research).read_text(encoding="utf-8"))
    report = compare(queue, research)
    for fname, content in [
        (args.output_json, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
        (args.output_md, render(report)),
    ]:
        path = Path(fname)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print("KB21 official-source research compared; unsigned / NO PLAY")


if __name__ == "__main__":
    main()
