"""
TRAFFICQ AI — Comparison Video Generator  (fixed for matplotlib 3.9)
Side-by-side: Static fixed-timer  vs  TRAFFICQ AI Adaptive Agents
"""
from __future__ import annotations
import os, random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Arc
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter
import matplotlib.patheffects as pe
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

# ── Palette ───────────────────────────────────────────────────────────────────
BG, PANEL, ROAD, INTER = "#06111F","#0C1B2E","#0E2035","#081525"
SIG_G, SIG_R = "#22C55E","#EF4444"
TEXT, TEXT2, DIVIDER = "#C8D8F0","#64748B","#1E3A5F"
EMERG_C, CORR_C = "#EF4444","#22C55E"
CAR_COLS = ["#3B8BD4","#1D9E75","#D85A30","#7F77DD","#F59E0B","#A78BFA"]

# ── Grid constants (axis units 0-10) ─────────────────────────────────────────
IX=[2.5,7.5]; IY=[7.0,3.0]; RW=1.1; LO=0.25
INAMES_MAP = {(0,0):"NW",(1,0):"NE",(0,1):"SW",(1,1):"SE"}

# ── Sim constants ─────────────────────────────────────────────────────────────
FPS=15; TOTAL_FRAMES=400; CYCLE=60.0; MIN_G=15.0; DT=1.0/FPS
NS_RATE=1.1; EW_RATE=0.48; DISCHARGE=1.4

# ═══════════════════ SIMULATION ═══════════════════════════════════════════════
@dataclass
class ISig:
    name:str; phase:str="NS"; timer:float=0.0
    ns_g:float=30.0; ew_g:float=30.0
    ns_q:float=0.0;  ew_q:float=0.0
    ns_w:float=0.0;  ew_w:float=0.0
    override:bool=False

@dataclass
class Dot:
    lane:str; pos:float=0.0
    waiting:bool=False; color:str="#3B8BD4"; is_emg:bool=False

class Sim:
    INAMES=["NW","NE","SW","SE"]
    LANE_STOP = {
        "EB_t":[("NW","EW",0.27),("NE","EW",0.73)],
        "WB_t":[("NE","EW",0.27),("NW","EW",0.73)],
        "EB_b":[("SW","EW",0.27),("SE","EW",0.73)],
        "WB_b":[("SE","EW",0.27),("SW","EW",0.73)],
        "SB_l":[("NW","NS",0.27),("SW","NS",0.73)],
        "NB_l":[("SW","NS",0.27),("NW","NS",0.73)],
        "SB_r":[("NE","NS",0.27),("SE","NS",0.73)],
        "NB_r":[("SE","NS",0.27),("NE","NS",0.73)],
    }
    ALL_LANES=["EB_t","WB_t","EB_b","WB_b","SB_l","NB_l","SB_r","NB_r"]

    def __init__(self, mode="static", seed=42):
        self.mode=mode; self.rng=random.Random(seed); self.t=0.0
        offsets={"NW":0.0,"NE":5.0,"SW":2.0,"SE":8.0}
        self.sigs={n:ISig(name=n,
                          phase="NS" if n in("NW","NE") else "EW",
                          timer=offsets[n])
                   for n in self.INAMES}
        self.cum_wait=0.0; self.cum_exits=0.001
        self.hist_wait=[]; self.hist_cong=[]; self.hist_thru=[]
        self.dots:List[Dot]=self._init_dots()
        self.emg={"active":False,"prog":0.0,"done":False}

    def _init_dots(self):
        d=[]
        for lk in self.ALL_LANES:
            for _ in range(3):
                d.append(Dot(lane=lk,pos=self.rng.random(),
                             color=self.rng.choice(CAR_COLS)))
        return d

    def step(self):
        self.t+=DT
        self._sigs(); self._queues(); self._dots(); self._emg_tick(); self._rec()

    def _sigs(self):
        for s in self.sigs.values():
            if s.override: continue
            s.timer+=DT
            dur=s.ns_g if s.phase=="NS" else s.ew_g
            if s.timer>=dur:
                s.phase="EW" if s.phase=="NS" else "NS"; s.timer=0.0
                if self.mode=="adaptive" and s.phase=="NS":
                    ns_sc=s.ns_q*(1+s.ns_w/12); ew_sc=s.ew_q*(1+s.ew_w/12)
                    tot=ns_sc+ew_sc
                    if tot>0.5:
                        r=ns_sc/tot; g=max(MIN_G,min(CYCLE-MIN_G,round(r*CYCLE)))
                        s.ns_g=float(g); s.ew_g=CYCLE-g
                    else: s.ns_g=30.0; s.ew_g=30.0

    def _queues(self):
        for s in self.sigs.values():
            s.ns_q+=max(0,NS_RATE*DT+self.rng.gauss(0,.04))
            s.ew_q+=max(0,EW_RATE*DT+self.rng.gauss(0,.02))
            if s.phase=="NS":
                d=min(s.ns_q,DISCHARGE*DT); s.ns_q-=d; self.cum_exits+=d
                s.ns_w=max(0,s.ns_w-d*.4); s.ew_w+=DT
                self.cum_wait+=s.ew_q*DT
            else:
                d=min(s.ew_q,DISCHARGE*DT); s.ew_q-=d; self.cum_exits+=d
                s.ew_w=max(0,s.ew_w-d*.4); s.ns_w+=DT
                self.cum_wait+=s.ns_q*DT

    def _blocked(self, dot:Dot)->bool:
        for iname,need,sp in self.LANE_STOP.get(dot.lane,[]):
            dist=sp-dot.pos
            if 0<dist<0.13:
                s=self.sigs[iname]
                if s.override:
                    return dot.lane not in("EB_t",)
                if s.phase!=need: return True
        return False

    def _dots(self):
        keep=[]
        for d in self.dots:
            if d.is_emg:
                keep.append(d); continue
            if not self._blocked(d):
                d.pos=(d.pos+self.rng.uniform(.007,.013))%1.0
            d.waiting=self._blocked(d)
            keep.append(d)
        # spawn if thin
        if len(keep)<38 and self.rng.random()<.35:
            lk=self.rng.choice(self.ALL_LANES)
            keep.append(Dot(lane=lk,pos=.02,color=self.rng.choice(CAR_COLS)))
        self.dots=keep

    def dispatch_emg(self):
        if not self.emg["done"] and not self.emg["active"]:
            self.emg={"active":True,"prog":0.0,"done":False}
            for n in("NW","NE"):
                self.sigs[n].override=True
                self.sigs[n].phase="EW"; self.sigs[n].timer=0.0
            self.dots.append(Dot(lane="EB_t",pos=0.01,color=EMERG_C,is_emg=True))

    def _emg_tick(self):
        if not self.emg["active"]: return
        self.emg["prog"]=min(1.05,self.emg["prog"]+0.022)
        for d in self.dots:
            if d.is_emg: d.pos=self.emg["prog"]
        if self.emg["prog"]>=1.02:
            self.emg["active"]=False; self.emg["done"]=True
            for n in("NW","NE"):
                self.sigs[n].override=False
                self.sigs[n].phase="NS"; self.sigs[n].timer=0.0
            self.dots=[d for d in self.dots if not d.is_emg]

    def _rec(self):
        tq=sum(s.ns_q+s.ew_q for s in self.sigs.values())
        self.hist_wait.append(self.cum_wait/self.cum_exits)
        self.hist_cong.append(min(100,tq/4/7*100))
        self.hist_thru.append(self.cum_exits/max(.1,self.t)*60)

    @property
    def M(self):
        if self.hist_wait:
            return {"w":self.hist_wait[-1],"c":self.hist_cong[-1],"t":self.hist_thru[-1]}
        return {"w":0,"c":0,"t":0}


# ═══════════════════ DRAWING ══════════════════════════════════════════════════
def setup_ax(ax):
    ax.set_facecolor(PANEL); ax.set_xlim(0,10); ax.set_ylim(0,10)
    ax.set_aspect("equal"); ax.axis("off")

def draw_grid(ax):
    # Dot grid
    for gx in np.arange(.5,10,.7):
        for gy in np.arange(.5,10,.7):
            ax.plot(gx,gy,".",color="#0F2540",markersize=1.1,zorder=0)
    # Roads
    for iy in IY:
        ax.add_patch(Rectangle((0,iy-RW),10,RW*2,color=ROAD,zorder=1))
    for ix in IX:
        ax.add_patch(Rectangle((ix-RW,0),RW*2,10,color=ROAD,zorder=1))
    # Lane marks
    for iy in IY:
        ax.plot([0,10],[iy,iy],color="#1A3020",lw=.7,ls=(0,(5,8)),zorder=2)
    for ix in IX:
        ax.plot([ix,ix],[0,10],color="#1A3020",lw=.7,ls=(0,(5,8)),zorder=2)
    # Intersection boxes
    for ix in IX:
        for iy in IY:
            ax.add_patch(Rectangle((ix-RW,iy-RW),RW*2,RW*2,color=INTER,zorder=3))
    # Edge arrows
    kw=dict(fontsize=7,color=TEXT2,ha="center",va="center",zorder=4,fontfamily="monospace")
    for ix in IX:
        ax.text(ix,9.55,"↓",**kw); ax.text(ix,.4,"↑",**kw)
    for iy in IY:
        ax.text(.35,iy+.22,"→",**kw); ax.text(9.65,iy-.22,"←",**kw)

def dot_xy(d:Dot)->Tuple[float,float]:
    t=d.pos
    if d.lane=="EB_t": return (t*10, IY[0]+LO)
    if d.lane=="WB_t": return ((1-t)*10, IY[0]-LO)
    if d.lane=="EB_b": return (t*10, IY[1]+LO)
    if d.lane=="WB_b": return ((1-t)*10, IY[1]-LO)
    if d.lane=="SB_l": return (IX[0]-LO, (1-t)*10)
    if d.lane=="NB_l": return (IX[0]+LO, t*10)
    if d.lane=="SB_r": return (IX[1]-LO, (1-t)*10)
    if d.lane=="NB_r": return (IX[1]+LO, t*10)
    return (5,5)

def draw_signals(ax, sigs:Dict[str,ISig], frame:int):
    blink=frame%12<6
    for ci,ix in enumerate(IX):
        for ri,iy in enumerate(IY):
            nm=INAMES_MAP[(ci,ri)]; s=sigs[nm]
            # Queue bars
            def qcol(q): return SIG_G if q<2 else("#F59E0B" if q<5 else SIG_R)
            nh=min(s.ns_q/8*1.8,2.0); eh=min(s.ew_q/8*1.8,2.0)
            ax.add_patch(Rectangle((ix-.2,iy+RW+.05),.4,nh,
                         color=qcol(s.ns_q),alpha=.5,zorder=4))
            ax.add_patch(Rectangle((ix+RW+.05,iy-.2),eh,.4,
                         color=qcol(s.ew_q),alpha=.5,zorder=4))
            # Signal dots: N, S, W, E
            ns_c=SIG_G if s.phase=="NS" else SIG_R
            ew_c=SIG_G if s.phase=="EW" else SIG_R
            if s.override: ns_c=EMERG_C if blink else SIG_G; ew_c=SIG_G
            for lx,ly,lc in[(ix-.25,iy+RW+.25,ns_c),(ix+.25,iy-RW-.25,ns_c),
                             (ix-RW-.25,iy-.25,ew_c),(ix+RW+.25,iy+.25,ew_c)]:
                ax.add_patch(Circle((lx,ly),.19,color="#050F1A",zorder=5))
                ax.add_patch(Circle((lx,ly),.13,color=lc,zorder=6,
                             alpha=.95 if lc==SIG_G else .8))
            # Label
            ax.text(ix,iy,nm,color=TEXT2,fontsize=6.5,
                    ha="center",va="center",zorder=7,fontfamily="monospace")
            if s.override:
                ax.text(ix,iy-.42,"OVERRIDE",color=CORR_C,fontsize=5,
                        ha="center",va="center",zorder=7,fontfamily="monospace")
            # Phase timer arc
            dur=s.ns_g if s.phase=="NS" else s.ew_g
            frac=min(1.0,s.timer/max(dur,1)); th=90-frac*360
            arc=Arc((ix,iy),.72,.72,angle=0,theta1=th,theta2=90,
                    color=SIG_G if s.phase=="NS" else "#3B8BD4",lw=1.8,zorder=6)
            ax.add_patch(arc)

def draw_dots(ax, sim:Sim, frame:int):
    for d in sim.dots:
        x,y=dot_xy(d)
        if not(.08<x<9.92 and .08<y<9.92): continue
        c=d.color if not d.waiting else "#374151"
        r=.23 if d.is_emg else .14
        ax.add_patch(Circle((x,y),r,color=c,zorder=8+(2 if d.is_emg else 0)))
        if d.is_emg:
            bl=frame%10<5
            ax.add_patch(Circle((x,y),r+.11,color=EMERG_C if bl else "#F59E0B",
                         alpha=.38,zorder=7))
            ax.plot([x-.09,x+.09],[y,y],color="white",lw=1.4,zorder=11)
            ax.plot([x,x],[y-.09,y+.09],color="white",lw=1.4,zorder=11)
        elif d.waiting:
            ax.add_patch(Circle((x,y-.22),.06,color=SIG_R,alpha=.65,zorder=9))

def draw_corridor(ax, sim:Sim):
    if not sim.emg["active"]: return
    x1=min(10.0,sim.emg["prog"]*10)
    ax.add_patch(Rectangle((0,IY[0]-RW),x1,RW*2,color=CORR_C,alpha=.10,zorder=2))
    ax.plot([0,x1],[IY[0]+LO,IY[0]+LO],color=CORR_C,lw=1.8,alpha=.55,zorder=7)

def draw_stuck_emg(ax, frame:int):
    """Static sim: ambulance stuck in queue at NW intersection."""
    blink=frame%14<7
    x=IX[0]-1.3; y=IY[0]+LO
    ax.add_patch(Circle((x,y),.23,color=EMERG_C,zorder=10))
    if blink:
        ax.add_patch(Circle((x,y),.35,color=EMERG_C,alpha=.3,zorder=9))
    ax.plot([x-.09,x+.09],[y,y],color="white",lw=1.4,zorder=11)
    ax.plot([x,x],[y-.09,y+.09],color="white",lw=1.4,zorder=11)
    ax.text(x,y-.45,"STUCK",color=EMERG_C,fontsize=5.5,ha="center",
            fontfamily="monospace",fontweight="bold",zorder=12)


# ═══════════════════ MAIN ════════════════════════════════════════════════════
def main():
    print("Initialising simulations …")
    sim_s=Sim(mode="static",  seed=42)
    sim_a=Sim(mode="adaptive",seed=42)
    for _ in range(30): sim_s.step(); sim_a.step()

    # ── Figure ────────────────────────────────────────────────────────────────
    fig=plt.figure(figsize=(16,9),facecolor=BG,dpi=100)
    from matplotlib.gridspec import GridSpec
    gs=GridSpec(3,3,figure=fig,
                height_ratios=[.55,5.4,2.6],
                width_ratios=[5,.06,5],
                hspace=.07,wspace=.0)

    ax_hdr   = fig.add_subplot(gs[0,:])
    ax_s     = fig.add_subplot(gs[1,0])
    ax_div   = fig.add_subplot(gs[1,1])
    ax_a     = fig.add_subplot(gs[1,2])
    ax_stats = fig.add_subplot(gs[2,:])

    ax_hdr.set_facecolor(BG);   ax_hdr.axis("off")
    ax_div.set_facecolor(DIVIDER); ax_div.axis("off")
    ax_stats.set_facecolor(PANEL); ax_stats.axis("off")

    # Header text
    ax_hdr.text(.5,.72,"TRAFFICQ AI  —  Static  vs  Adaptive Agent Comparison",
                transform=ax_hdr.transAxes,fontsize=17,color=TEXT,
                ha="center",va="center",fontweight="bold",fontfamily="monospace",
                path_effects=[pe.withStroke(linewidth=4,foreground=BG)])
    ax_hdr.text(.5,.2,
                "Scenario: Morning Rush (08:00–09:00)  ·  N-S density 72%  ·  E-W density 38%  ·  RCOEM Hackathon 2025",
                transform=ax_hdr.transAxes,fontsize=8.5,color=TEXT2,
                ha="center",va="center",fontfamily="monospace")

    # Metric history inset axes
    ax_wh=inset_axes(ax_stats,width="43%",height="60%",loc="lower left",
                     bbox_to_anchor=(.015,.06,1,1),bbox_transform=ax_stats.transAxes)
    ax_ch=inset_axes(ax_stats,width="43%",height="60%",loc="lower right",
                     bbox_to_anchor=(-.025,.06,1,1),bbox_transform=ax_stats.transAxes)
    for axh in(ax_wh,ax_ch):
        axh.set_facecolor(INTER)
        for sp in axh.spines.values(): sp.set_edgecolor(DIVIDER)
        axh.tick_params(colors=TEXT2,labelsize=6.5)
    ax_wh.set_title("Average Wait Time (s)",color=TEXT2,fontsize=7,pad=2)
    ax_ch.set_title("Congestion Index (%)",  color=TEXT2,fontsize=7,pad=2)
    ax_wh.set_ylabel("seconds",   color=TEXT2,fontsize=6.5)
    ax_ch.set_ylabel("congestion",color=TEXT2,fontsize=6.5)
    lws,=ax_wh.plot([],[],color=SIG_R,lw=1.6,label="Static")
    lwa,=ax_wh.plot([],[],color=SIG_G,lw=1.6,label="Adaptive")
    lcs,=ax_ch.plot([],[],color=SIG_R,lw=1.6)
    lca,=ax_ch.plot([],[],color=SIG_G,lw=1.6)
    ax_wh.legend(fontsize=6,facecolor=INTER,labelcolor=TEXT2,
                 edgecolor=DIVIDER,loc="upper left")

    txt_stats=ax_stats.text(.5,.94,"",transform=ax_stats.transAxes,
                            fontsize=8.5,color=TEXT2,ha="center",va="top",
                            fontfamily="monospace")
    txt_improv=ax_stats.text(.5,.78,"",transform=ax_stats.transAxes,
                             fontsize=11,color=SIG_G,ha="center",va="top",
                             fontfamily="monospace",fontweight="bold")

    emg_frame=[None]   # frame when emergency was dispatched

    def animate(fr:int):
        # ── Step ─────────────────────────────────────────────────────────────
        for _ in range(2): sim_s.step(); sim_a.step()

        # ── Emergency at frame 250 ───────────────────────────────────────────
        if fr==250:
            sim_a.dispatch_emg()
            emg_frame[0]=fr

        # ── Clear sim panels ─────────────────────────────────────────────────
        ax_s.cla(); ax_a.cla()
        setup_ax(ax_s); setup_ax(ax_a)

        # Titles
        ax_s.set_title("APPROACH 1 — Static Fixed Signals",
                        color=SIG_R,fontsize=10.5,pad=5,
                        fontfamily="monospace",fontweight="bold")
        ax_a.set_title("APPROACH 2 — TRAFFICQ AI Adaptive Agents",
                        color=SIG_G,fontsize=10.5,pad=5,
                        fontfamily="monospace",fontweight="bold")

        # ── Draw ─────────────────────────────────────────────────────────────
        draw_grid(ax_s); draw_grid(ax_a)
        draw_corridor(ax_a,sim_a)
        draw_signals(ax_s,sim_s.sigs,fr)
        draw_signals(ax_a,sim_a.sigs,fr)
        draw_dots(ax_s,sim_s,fr)
        draw_dots(ax_a,sim_a,fr)

        # Emergency stuck on static side
        if emg_frame[0] is not None and fr<330:
            draw_stuck_emg(ax_s,fr)
            ax_s.text(5,9.4,"Ambulance waiting — no corridor override",
                      color=SIG_R,fontsize=6.5,ha="center",
                      fontfamily="monospace",zorder=12)
        if emg_frame[0] is not None and sim_a.emg["active"]:
            ax_a.text(5,9.4,"Agent 03 — Green corridor ACTIVE",
                      color=CORR_C,fontsize=6.5,ha="center",
                      fontfamily="monospace",fontweight="bold",zorder=12)

        # ── Stats text ────────────────────────────────────────────────────────
        ms=sim_s.M; ma=sim_a.M
        txt_stats.set_text(
            f"STATIC  wait={ms['w']:.1f}s  cong={ms['c']:.0f}%  thru={ms['t']:.0f}/min"
            f"       ADAPTIVE  wait={ma['w']:.1f}s  cong={ma['c']:.0f}%  thru={ma['t']:.0f}/min"
        )

        if fr>80 and ms["w"]>0 and ma["w"]>0:
            impv=(ms["w"]-ma["w"])/ms["w"]*100
            txt_improv.set_text(f"↑ {impv:.0f}% reduction in avg wait time")
        elif fr<=80:
            txt_improv.set_text("")

        # ── History lines ─────────────────────────────────────────────────────
        xs=list(range(len(sim_s.hist_wait)))
        lws.set_data(xs,sim_s.hist_wait); lwa.set_data(xs,sim_a.hist_wait)
        lcs.set_data(xs,sim_s.hist_cong); lca.set_data(xs,sim_a.hist_cong)
        if xs:
            ax_wh.set_xlim(0,max(1,len(xs)))
            ax_wh.set_ylim(0,max(5,max(sim_s.hist_wait+sim_a.hist_wait)*1.15))
            ax_ch.set_xlim(0,max(1,len(xs)))
            ax_ch.set_ylim(0,105)

        return []

    print(f"Rendering {TOTAL_FRAMES} frames at {FPS} fps …")
    anim=FuncAnimation(fig,animate,frames=TOTAL_FRAMES,
                       interval=1000//FPS,blit=False)

    out_dir=os.path.join(os.path.dirname(__file__),"..","output")
    os.makedirs(out_dir,exist_ok=True)
    mp4=os.path.join(out_dir,"trafficq_comparison.mp4")
    gif=os.path.join(out_dir,"trafficq_comparison.gif")

    try:
        wr=FFMpegWriter(fps=FPS,bitrate=2000,
                        extra_args=["-vcodec","libx264","-pix_fmt","yuv420p"])
        anim.save(mp4,writer=wr,dpi=100)
        print(f"✅  MP4 saved → {mp4}")
        plt.close(fig); return mp4
    except Exception as e:
        print(f"FFMpeg error ({e}), saving GIF …")
        wr=PillowWriter(fps=FPS)
        anim.save(gif,writer=wr,dpi=100)
        print(f"✅  GIF saved → {gif}")
        plt.close(fig); return gif

if __name__=="__main__":
    p=main(); print(f"\nVideo ready: {p}")
