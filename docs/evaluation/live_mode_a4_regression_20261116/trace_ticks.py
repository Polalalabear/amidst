import sys,json,math
sys.path.insert(0,"scripts/live_mode")
import replay_advisor as R
raw=json.load(open(sys.argv[1])); lo,hi=int(sys.argv[2]),int(sys.argv[3])
orig=R.LiveDecider.step
def step(self,tick,t_s,tracker,tracking,dets,frames):
    r=orig(self,tick,t_s,tracker,tracking,dets,frames)
    if lo<=tick<=hi:
        gt=raw["infer"][tick].get("gt_xy")
        pe={p:[round(x,1) for x in v["xy"]] for p,v in self.people.tracks.items() if t_s-v.get("t",t_s)<=3} if hasattr(self.people,"tracks") else {}
        print(tick,"gt",[round(x,1) for x in gt] if gt else None,"est",r.get("est_xy") and [round(x,1) for x in r["est_xy"]],"tracks",pe,"pend",self.advisor._pending and (self.advisor._pending["pids"],self.advisor.ready),"ev",[(e["type"],e.get("detail")) for e in r["events"] if e["type"].startswith("ADJ")], "locked",self.locked)
    return r
R.LiveDecider.step=step
R.replay(raw,"review",3.5,2,"reseed",0.7,4.0)
