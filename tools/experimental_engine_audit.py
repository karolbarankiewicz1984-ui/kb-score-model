"""Aggregate experimental market calibration from frozen settlements."""
import argparse
import json
from pathlib import Path

def audit(settlements):
    markets={}
    for file in settlements:
        for row in file.get("rows",[]):
            if row.get("status")!="SETTLED":continue
            for event in row.get("events",[]):
                market=event["market"]
                entry=markets.setdefault(market,{"n":0,"hits":0,"brier_sum":0.0,"bins":{}})
                p=event["probability"]
                hit=int(event["occurred"])
                entry["n"]+=1
                entry["hits"]+=hit
                entry["brier_sum"]+=(p-hit)**2
                band=min(9,int(p*10))
                bin_=entry["bins"].setdefault(f"{band*10}-{band*10+9}%",{"n":0,"hits":0,"p_sum":0.0})
                bin_["n"]+=1
                bin_["hits"]+=hit
                bin_["p_sum"]+=p
    for entry in markets.values():
        n=entry["n"]
        entry["hit_rate"]=round(entry["hits"]/n,5)
        entry["brier_score"]=round(entry.pop("brier_sum")/n,6)
        for bin_ in entry["bins"].values():
            bin_["hit_rate"]=round(bin_["hits"]/bin_["n"],5)
            bin_["mean_probability"]=round(bin_.pop("p_sum")/bin_["n"],5)
    return {"schema":"experimental-audit-v1","markets":markets,"register_writes":False,
            "kb_n_effect":0,"dev_n_effect":0}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("inputs",nargs="+")
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    target=Path(args.output)
    if not str(target).startswith("reports/experimental_engine/audit/"):
        raise ValueError("isolated audit output only")
    files=[json.loads(Path(f).read_text(encoding="utf-8")) for f in args.inputs]
    result=audit(files)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(target),"markets":len(result["markets"])}))
if __name__=="__main__":main()
