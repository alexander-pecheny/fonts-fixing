#set page(width: 25cm, height: auto, margin: 1.6cm, fill: white)
#set text(font: "Helvetica Neue", size: 9pt, fill: rgb("#777"), lang: "ru")

#let line = "Здесь будет сайт ЧР по интеллектуальным играм"
#let cuts = ("Здесь", "будет", "ЧР по", "играм")
#let faces = ("Geist", "Geist Fix")
#let label(name) = text(size: 8pt, tracking: 0.6pt, upper(name))
#let set-in(name, size, body) = text(font: name, size: size, fill: black, body)

#label("The stress mark")
#v(10pt)
#grid(
  columns: (auto, 1fr),
  column-gutter: 14pt,
  row-gutter: 10pt,
  align: horizon,
  ..faces.map(name => (label(name), set-in(name, 30pt, "доро́ги ты́сяча Пу́шкин А́О́У́Ы́Э́Ю́"))).flatten()
)
#v(10pt)
#text(size: 8.5pt)[Geist anchors the combining acute over every Cyrillic vowel, then lists only `kern` under its GPOS `cyrl` script. A shaper that finds the script tag stops looking, so for Russian the mark lands after the letter instead of over it. Registering `mark` and `mkmk` there is the whole repair. Only ы had an anchor in the wrong place, over its right stroke rather than the middle.]

#v(20pt)
#std.line(length: 100%, stroke: 0.5pt + rgb("#ddd"))
#v(12pt)
#label("The spacing")
#v(10pt)

#stack(spacing: 13pt, ..faces.map(name => stack(
  dir: ltr, spacing: 14pt,
  set-in(name, 21pt, line),
  align(horizon, label(name)),
)))

#v(22pt)
#grid(
  columns: (1fr, 1fr),
  column-gutter: 18pt,
  row-gutter: 14pt,
  ..faces.map(label),
  ..cuts.map(cut => faces.map(name => set-in(name, 34pt, cut))).flatten()
)

#v(24pt)
#grid(
  columns: (1fr, 1fr),
  column-gutter: 18pt,
  [As drawn. Geist spaces its Cyrillic as carefully as its Latin, and draws half of it out of the Latin letters outright: а is a, Н is H, Т is T moved twelve units left.],
  [Spaced by two models trained on the fonts macOS ships. One reads a sidebearing off each outline; the other reads how far apart two letters should stand off both their shapes at once. 71 of the 118 letters move, by 6 units where they move at all, and 1,540 pairs are kerned by a median 12. The line ends 0.7% longer.],
)
#v(10pt)
#text(size: 8.5pt)[Largest moves against Geist, in units of 1000 to the em, left side and right: Л −23/0, а +2/+20, J −20/0, з +1/+16, Ъ −16/0, г 0/+13. Both scripts are respaced together, or the pairs the font draws from one set of outlines would come apart: а would drift off a by the couple of units the model reads differently for a Cyrillic side.]
#v(8pt)
#text(size: 8.5pt)[A sidebearing is one side at a time, and two sides are not a pair. Neither side of к nor of т can see the cavity the two of them leave between them; neither side of г knows that its arm reaches over whatever comes next. So the kerning comes from a second model, fitted the same way on the same corpus — 588,000 pairs, families held out whole — which reads the two facing profiles and the shape of the white they enclose, and predicts the distance a designer would leave between the last ink of one letter and the first of the next. It is worth 13.2 units at 1000 upem on a face it has never seen, against 33 for knowing nothing and about 21 for adding up two sidebearings predicted separately.]
#v(8pt)
#text(size: 8.5pt)[Two things follow from the target being a distance between two shapes rather than a number attached to one. Capitals come out further apart than lowercase — across the 359 text faces on this machine two capitals stand 144 units of ink apart against 121 for two lowercase letters — and ЧР, НН and HI all come out exactly where Geist set them. And a pair that already holds a cavity comes out closer, so кт, са and ту stay within a few units of the designer while уд, which the respacing had opened from 194 units to 216, is pulled back to 196. What does move is гр, from 54 to 77: г's arm is the only ink at that height, and играм reads clumped against a plain иг at 160. Last, nothing may end up nearer at its closest approach than the tightest pair the model asks for anywhere in the font. Geist as drawn brings 16 Cyrillic pairs and 16 Latin within 30 units of touching, гт and гх within 8; none here come nearer than 35.]

#v(20pt)
#std.line(length: 100%, stroke: 0.5pt + rgb("#ddd"))
#v(12pt)
#label("Four of the eighteen styles, before and after")
#v(10pt)
#grid(
  columns: (auto, 1fr),
  column-gutter: 14pt,
  row-gutter: 9pt,
  align: horizon,
  ..(("Light", 300, "normal"), ("Regular", 400, "normal"),
     ("Italic", 400, "italic"), ("Bold Italic", 700, "italic")).map(((style, weight, slant)) => (
    label(style),
    stack(spacing: 5pt, ..faces.map(name =>
      text(font: name, size: 17pt, weight: weight, style: slant, fill: black, line))),
  )).flatten()
)
#v(10pt)
#text(size: 8.5pt)[Upper line as drawn, lower rebuilt. Both models have two things taken off every proposal. First the mean disagreement with this face's own Latin, which is a convention and not a judgement: every glyph shifted the same way inside its advance leaves the page unchanged, and on the Italic that came to +40 units on the left against −9 on the right — the whole of what looked like an argument for a wider italic. Then what the model gets wrong on faces it has never seen, so a move survives only if the model can tell it apart from its own error. That figure is the model's, not this font's: how far a particular face disagrees is partly the face being wrong, and on a Geist whose spacing had been thrown away it read 16.6 units against the model's 13.2, enough to leave most of the fault in place.]
