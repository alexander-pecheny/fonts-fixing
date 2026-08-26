#set page(width: 25cm, height: auto, margin: 1.6cm, fill: white)
#set text(font: "Helvetica Neue", size: 9pt, fill: rgb("#777"))

#let line = "Здесь будет сайт ЧР по интеллектуальным играм"
#let cuts = ("Здесь", "будет", "ЧР по", "играм")
#let faces = ("Jost", "Jost Uniform", "Jost Spaced")
#let label(name) = text(size: 8pt, tracking: 0.6pt, upper(name))
#let set-in(name, size, body) = text(font: name, size: size, fill: black, body)

#label("The same line, three ways")
#v(10pt)

#stack(spacing: 13pt, ..faces.map(name => stack(
  dir: ltr, spacing: 14pt,
  set-in(name, 21pt, line),
  align(horizon, label(name)),
)))

#v(22pt)
#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 18pt,
  row-gutter: 14pt,
  ..faces.map(label),
  ..cuts.map(cut => faces.map(name => set-in(name, 34pt, cut))).flatten()
)

#v(24pt)
#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 18pt,
  row-gutter: 6pt,
  [As drawn, at weight 400. Jost kerns about half the Latin pairs that attract kerning and a third of the Cyrillic ones, so its Cyrillic was not neglected.],
  [Kerned so the blurred line shows an even width of light. 25 pairs moved, median −10 units; the spread of those widths falls from 0.50 to 0.15. The line ends 0.6% shorter.],
  [Sidebearings predicted from the outlines alone, by a model trained on the Latin of the fonts macOS ships and on no Cyrillic at all. 66 letters moved, 10 units on average, and the line ends 0.2% longer.],
)
#v(10pt)
#text(size: 8.5pt)[Largest moves against Jost, in units of 1000 to the em. Uniform: гр +40, ал +35, ам +35, уд −25, те +25. Spaced: Зд −91, уд −77, де −76, ам +70, ет +48, ЧР −48.]
