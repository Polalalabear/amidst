# Usage: python charts.py <stats.json> <out_dir>  (macOS font STHeiti for CJK labels)
import json,sys,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
fm.fontManager.addfont('/System/Library/Fonts/STHeiti Light.ttc')
plt.rcParams.update({'font.family':'Heiti TC','font.size':10,'axes.edgecolor':'#c3c2b7','axes.labelcolor':'#52514e',
 'xtick.color':'#52514e','ytick.color':'#52514e','figure.facecolor':'#fcfcfb','axes.facecolor':'#fcfcfb','svg.fonttype':'none'})
st=json.load(open(sys.argv[1])); out=sys.argv[2]
C=['#2a78d6','#eb6834','#1baf7a']; INK='#0b0b0b'; INK2='#52514e'
def clean(ax):
    for s in ('top','right'): ax.spines[s].set_visible(False)
    ax.grid(axis='x',color='#e4e3dd',lw=0.8); ax.set_axisbelow(True)
# 1 lost seconds by cause
fig,ax=plt.subplots(figsize=(7.2,2.9),dpi=110)
cats=[('BEFORE_FIRST_SEED','開場尚未鎖定（seed 前）'),('NO_TRACKLET_FOR_VISIBLE_CAMERA','目標鏡頭沒有軌跡片段（上游）'),('CANDIDATE_UNSELECTED','有候選但沒選（覆核可救）')]
evs=['A4-1','B4-1']; y=[1,0]
for i,ev in enumerate(evs):
    left=0
    for j,(k,lab) in enumerate(cats):
        v=st[ev]['miss_cause_ticks'].get(k,0)*0.2
        if v:
            ax.barh(y[i],v,left=left,color=C[j],height=0.5,edgecolor='#fcfcfb',lw=2,label=lab if i==1 or (i==0 and j<2) else None)
            ax.text(left+v/2,y[i]+0.29,f'{v:.1f} s',ha='center',va='bottom',color=INK,fontsize=8.5)
        left+=v
    ax.text(left+0.08,y[i],f'合計 {left:.1f} s',va='center',color=INK2,fontsize=9)
h,l=ax.get_legend_handles_labels(); d=dict(zip(l,h))
ax.legend([d[c[1]] for c in cats],[c[1] for c in cats],loc='upper center',bbox_to_anchor=(0.5,-0.2),ncol=3,frameon=False,fontsize=8.5)
ax.set_yticks(y,evs); ax.set_ylim(-0.4,1.65); ax.set_xlim(0,4.9); ax.set_xlabel('規則組失聯秒（目標可偵測卻顯示 GAP）')
ax.set_title('失聯秒成因：覆核架構只救得回 B4-1 的 0.4 s；橘色段偵測其實存在',loc='left',color=INK,fontsize=11)
clean(ax); fig.tight_layout(); fig.savefig(out+'/lost_seconds_by_cause.png'); plt.close(fig)
# 2 candidate distribution
fig,ax=plt.subplots(figsize=(7.2,3.0),dpi=110)
groups=[('DP3:0','DP3（接受片段）\n0 個候選'),('DP1:1','DP1（切鏡）\n1 個候選'),('DP1:2','DP1（切鏡）\n2 個候選')]
import numpy as np
x=np.arange(len(groups)); w=0.36
for i,ev in enumerate(evs):
    vals=[st[ev]['dp_candidates'].get(g,0) for g,_ in groups]
    # A4-1 request list has one duplicated 37.4 s DP1 request; count unique DP times
    if ev=='A4-1': vals[1]=8
    b=ax.bar(x+(i-0.5)*w,vals,w,color=C[i],edgecolor='#fcfcfb',lw=2,label=ev)
    for xi,v in zip(x+(i-0.5)*w,vals): ax.text(xi,v+0.15,str(v),ha='center',color=INK,fontsize=9)
ax.set_xticks(x,[g[1] for g in groups],fontsize=8.5); ax.set_ylabel('決策點數'); ax.set_ylim(0,10.5)
ax.legend(frameon=False,loc='upper right'); ax.set_title('34 個決策點中只有 2 個有 ≥2 個候選（B4-1 24.8／25.0 s）',loc='left',color=INK,fontsize=11)
for s in ('top','right'): ax.spines[s].set_visible(False)
ax.grid(axis='y',color='#e4e3dd',lw=0.8); ax.set_axisbelow(True)
fig.tight_layout(); fig.savefig(out+'/decision_point_candidates.png'); plt.close(fig)
# 3 latency strip
fig,ax=plt.subplots(figsize=(7.2,2.6),dpi=110)
rng=np.random.default_rng(0)
models=['terra6.1','sol6.1']
for i,m in enumerate(models):
    v=np.array(st['latency_raw'][m])/1000
    ax.scatter(v,i+rng.uniform(-0.18,0.18,len(v)),s=14,color=C[i],alpha=0.7,edgecolor='none')
    p50=np.median(v); ax.plot([p50,p50],[i-0.3,i+0.3],color=INK,lw=2)
    ax.text(p50,i+0.33,f'p50 {p50:.1f} s',ha='center',va='bottom',fontsize=8.5,color=INK)
for t,lab in [(2,'原 2 s 逾時'),(5,'formal 5 s'),(8,'D313 8 s')]:
    ax.axvline(t,color='#a3a29b',lw=1,ls='--'); ax.text(t,1.75,lab,ha='center',fontsize=8,color=INK2)
ax.scatter([0],[-0.75],marker='|',s=200,color=INK2); ax.text(0.12,-0.75,'規則 ≈ 0 s',va='center',fontsize=8.5,color=INK2)
ax.set_yticks([0,1],models); ax.set_ylim(-1.05,2.0); ax.set_xlim(-0.2,8.6); ax.set_xlabel('單次成功呼叫牆鐘（s），D325 全部 190 次')
ax.set_title('LLM 每個決策點要等 3–8 s；規則立即回答',loc='left',color=INK,fontsize=11)
clean(ax); fig.tight_layout(); fig.savefig(out+'/llm_latency.png'); plt.close(fig)
