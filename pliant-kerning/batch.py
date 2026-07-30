# /// script
# dependencies = ["fonttools", "uharfbuzz", "numpy"]
# ///
"""Patch every Pliant .ttf in place: swap in the double-storey `a`, autokern Cyrillic.

Everything is staged to a temp dir first, so a failure on any one file installs nothing.

    uv run batch.py
"""
import glob, os, shutil, sys, tempfile, traceback
from patch import patch
ROOT=os.path.expanduser('~/Library/Fonts/Pliant')
files=sorted(glob.glob(ROOT+'/*.ttf'))+sorted(glob.glob(ROOT+'/static/*.ttf'))
tmp=tempfile.mkdtemp(prefix='pliant-staged-')
rows=[]
for f in files:
    out=os.path.join(tmp, os.path.basename(f))
    try:
        n,k=patch(f,out); rows.append((os.path.basename(f),n,k,None))
    except Exception as e:
        rows.append((os.path.basename(f),0,0,repr(e))); traceback.print_exc()
bad=[r for r in rows if r[3]]
print(f'\n{len(rows)-len(bad)}/{len(rows)} patched, {len(bad)} failed')
for r in rows: print(f'  {r[0]:48} swap={r[1]:2d} kern={r[2]:5d} {r[3] or ""}')
if bad: sys.exit(1)
for f in files:
    shutil.copyfile(os.path.join(tmp, os.path.basename(f)), f)
print('\ninstalled in place')
