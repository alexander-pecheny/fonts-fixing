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
  [Sidebearings predicted from the outlines alone by a model trained on the fonts macOS ships. 71 of the 118 letters move, by 6 units where they move at all. The kerning is then reworked, 2,870 pairs of it, and the line ends 0.5% longer.],
)
#v(10pt)
#text(size: 8.5pt)[Largest moves against Geist, in units of 1000 to the em, left side and right: Л −23/0, а +2/+20, J −20/0, з +1/+16, Ъ −16/0, г 0/+13. Both scripts are respaced together, or the pairs the font draws from one set of outlines would come apart: а would drift off a by the couple of units the model reads differently for a Cyrillic side. Reading one side at a time cannot see a pair either, and у and д both moved out, which opened уд by another 23 units, so any pair that was already open and has opened further is kerned back to where the designer left it.]
#v(8pt)
#text(size: 8.5pt)[The kerning is then evened on the other reading — not the white between two letters but how close their ink ever comes, which is what the eye catches in a word. All four gaps in играм measure within five units of each other as white, yet г and р stand 349 units apart for nine tenths of their height and 67 apart at the top where г's arm reaches over, while иг keeps a plain 160 all the way up. Geist kerns гр 40 units tighter still. So a pair pinched by an overhang is opened and one whose ink never approaches is pulled in, each held inside the band its own font occupies and moved at most 60 units: уд −24 to −104, гр −40 to 0, иг 0 to −20, Ту −50 to −130, and in the Latin rp −40 to −20. Two round letters are exempt from the first rule, since о meets о as closely as г meets р but gradually, over a third of its height rather than at a single lid. This is the one pass that overrules the designer, and it repairs a real fault on the way: as drawn, 16 Cyrillic pairs come within 30 units of touching and гт and гх within 8. None now do, and the spread of those approaches falls from 0.35 to 0.20 across the Cyrillic and from 0.31 to 0.16 across the Latin.]

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
#text(size: 8.5pt)[Upper line as drawn, lower rebuilt. The model knows Geist's own Latin to between 7 and 11 units, and each proposal has that much subtracted from it, so a move only survives if the model can tell it apart from its own error. Before that, the mean disagreement on each side is taken off as well: every glyph shifted the same way inside its advance leaves the page unchanged, so that part of the reading is a convention and not a judgement. On the Italic it came to +40 units on the left against −9 on the right, and it was the whole of what looked like an argument for a wider italic.]
