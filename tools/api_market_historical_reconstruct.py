#!/usr/bin/env python3
"""Reconstruct historical audit input from the ORIGINAL Oct 9 markdown artifact.
Uncertain fixture mappings are deliberately left unresolved.
"""
import argparse,datetime,difflib,json,re,unicodedata
from pathlib import Path
from api_market_audit import api
def norm(s):
    s=unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+"," ",s).strip()
def main():
    a=argparse.ArgumentParser();a.add_argument("--markdown",required=True);a.add_argument("--date",default="2026-10-10");a.add_argument("--output",required=True);args=a.parse_args()
    md=Path(args.markdown).read_text()
    matches=list(re.finditer(r"^## (.+?) – (.+?) \((\d{4}-\d\d-\d\dT[^)]+)\)$",md,re.M))
    allfixtures=api("fixtures",{"date":args.date,"timezone":"Europe/Warsaw"})
    # A second day protects matches close to midnight; kickoff must still match exactly.
    fixtures=allfixtures+api("fixtures",{"date":(datetime.date.fromisoformat(args.date)+datetime.timedelta(days=1)).isoformat(),"timezone":"Europe/Warsaw"})
    seen={f["fixture"]["id"]:f for f in fixtures}
    fixtures=list(seen.values())
    mapping={"gole w meczu":("team_goals","match"),"gole druzyny":("team_goals","team"),"rozne w meczu":("corners","match"),"rozne druzyny":("corners","team"),"faule w meczu":("fouls","match"),"zolte kartki druzyny":("yellow","team"),"strzaly w meczu":("shots","match"),"strzaly celne w meczu":("shots_on_goal","match"),"spalone w meczu":("offsides","match"),"spalone druzyny":("offsides","team")}
    picks=[];audit_matches=[]
    for i,m in enumerate(matches):
        home,away,kickoff=m.groups()
        body=md[m.end():matches[i+1].start() if i+1<len(matches) else len(md)]
        stamp=datetime.datetime.fromisoformat(kickoff)
        scored=[]
        for f in fixtures:
            try:
                ft=datetime.datetime.fromisoformat(f["fixture"]["date"].replace("Z","+00:00"))
                if abs((ft-stamp).total_seconds())>3600:continue
            except Exception:continue
            hn=f["teams"]["home"]["name"];an=f["teams"]["away"]["name"]
            hs=difflib.SequenceMatcher(None,norm(home),norm(hn)).ratio()
            ass=difflib.SequenceMatcher(None,norm(away),norm(an)).ratio()
            scored.append((min(hs,ass),f))
        scored.sort(key=lambda v:v[0],reverse=True)
        # Conservative threshold and unique best candidate; never silently assume an ID.
        best=scored[0] if scored else None
        second=scored[1][0] if len(scored)>1 else 0
        f=best[1] if best and best[0]>=0.80 and best[0]-second>=0.10 else None
        audit_matches.append({"home":home,"away":away,"fixture_id":f["fixture"]["id"] if f else None,"matching_score":round(best[0],3) if best else None})
        for line in body.splitlines():
            if not line.startswith("| ") or line.startswith("| Typ"):continue
            parts=[v.strip() for v in line.strip().strip("|").split("|")]
            if len(parts)!=5:continue
            selection,score,quote,sts,superbet=parts
            typ=re.match(r"(.+?): (powyżej|poniżej) (\d+(?:\.\d+)?) — (.+)",selection)
            if not typ:continue
            subject,direction,threshold,label=typ.groups()
            market,scope=mapping.get(norm(label),(None,None))
            if scope=="match" and subject!="Cały mecz":scope=None
            side=("home" if norm(subject)==norm(home) else "away" if norm(subject)==norm(away) else None) if scope=="team" else None
            try:score=float(score)
            except ValueError:score=None
            picks.append({"fixture_id":f["fixture"]["id"] if f else None,"home":home,"away":away,"kickoff":kickoff,"selection":selection,"final_assessment_pct":score,"best_quote":quote,"sts_quote":sts,"superbet_quote":superbet,"market":market,"market_scope":scope,"team_side":side,"line":float(threshold),"direction":"over" if direction=="powyżej" else "under","historical_match_verified":bool(f)})
    out={"schema":"api-market-audit-input-reconstructed-v1","date":args.date,"source":"GitHub Actions 37932224214 original markdown","picks":picks,"fixture_matching":audit_matches}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print("Picks",len(picks),"matches",len(matches),"resolved",sum(bool(x["fixture_id"]) for x in audit_matches))
    if len(picks)!=98:raise RuntimeError("Expected 98 original positions, got "+str(len(picks)))
if __name__=="__main__":main()
