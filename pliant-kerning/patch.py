import sys, io, os
from fontTools.ttLib import TTFont
from swap import swap_a
from autokern import propose, add_lookup

def patch(src, dst):
    font = TTFont(src)
    n = swap_a(font)
    buf = io.BytesIO(); font.save(buf)
    pairs = propose(font, buf.getvalue())
    k = add_lookup(font, pairs)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    font.save(dst)
    return n, k

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    n, k = patch(src, dst)
    print(f'{os.path.basename(src)}: swapped {n} glyph pairs, added {k} kern pairs')
