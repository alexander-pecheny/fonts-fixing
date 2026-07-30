import numpy as np
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.basePen import BasePen

class FlattenPen(BasePen):
    def __init__(self, glyphSet, steps=12):
        super().__init__(glyphSet); self.steps=steps; self.polys=[]; self.cur=None
    def _moveTo(self,p): self.cur=[p]
    def _lineTo(self,p): self.cur.append(p)
    def _curveToOne(self,p1,p2,p3):
        p0=self.cur[-1]
        for i in range(1,self.steps+1):
            t=i/self.steps; mt=1-t
            self.cur.append((mt**3*p0[0]+3*mt*mt*t*p1[0]+3*mt*t*t*p2[0]+t**3*p3[0],
                             mt**3*p0[1]+3*mt*mt*t*p1[1]+3*mt*t*t*p2[1]+t**3*p3[1]))
    def _qCurveToOne(self,p1,p2):
        p0=self.cur[-1]
        for i in range(1,self.steps+1):
            t=i/self.steps; mt=1-t
            self.cur.append((mt*mt*p0[0]+2*mt*t*p1[0]+t*t*p2[0], mt*mt*p0[1]+2*mt*t*p1[1]+t*t*p2[1]))
    def _closePath(self):
        if self.cur: self.polys.append(self.cur); self.cur=None
    def _endPath(self): self._closePath()

def outline(font, gname):
    gs = font.getGlyphSet()
    rec = DecomposingRecordingPen(gs); gs[gname].draw(rec)
    fp = FlattenPen(gs); rec.replay(fp); fp._closePath()
    return [p for p in fp.polys if len(p) > 2]

def profile(font, gname, ys):
    """returns (right_x, left_x) arrays over ys; nan where no ink"""
    polys = outline(font, gname)
    R = np.full(len(ys), np.nan); L = np.full(len(ys), np.nan)
    for i, y in enumerate(ys):
        xs = []
        for poly in polys:
            pts = poly + [poly[0]]
            for (x0,y0),(x1,y1) in zip(pts, pts[1:]):
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (x1-x0)*(y-y0)/(y1-y0))
        if xs: R[i]=max(xs); L[i]=min(xs)
    return R, L
