# Nexora Build 1.22 – "Understand exactly"

## What was wrong
* A drawing that has sizes written on it (PDF / DXF) was read by measuring the lines, and a size text was given to
  whichever room *region* it fell in. Open plans (hall + dining), rotated texts and stair treads confused it, so rooms
  got other rooms' sizes, a staircase became a full-width strip, and written sizes were changed by "tidying".
* The request reader only knew fixed keywords, so a sentence in Tamil / Tanglish / another word order was
  partly ignored – and the app did not say what it had ignored.

## What 1.22 does
1. **Written size wins.** Each size text is paired with ONE room name (name above, size below). Written sizes are never
   changed by tidying. A room keeps its own drawn walls only when they match; otherwise it is placed at its name with the
   written size and the notes say *"walls drawn for it measure X but Y is written – the written size is used"*.
2. **Width-only labels** ("STAIRCASE 3'6" WIDE") are matched to the step lines drawn next to the name (3.5' × length).
3. **Check list.** After reading, the notes list every written size that was kept, every difference, rooms without a
   written size, and rooms that overlap because the drawing's own lines do not agree with its written sizes.
4. **Any language.** The request is read by the free AI (Gemini / Groq / OpenRouter) first; the old keyword reader is the
   fallback. The AI's numbers are accepted only if they are in your text (or Tamil number words), inside sane limits.
5. **Nothing silent.** Things the generator cannot do yet (exact position, "kitchen next to dining") appear as
   "⚠ Not applied: …". Room sizes you write are used as the wanted size and the plan notes say whether each was kept.

## Know-how
* Best accuracy: upload the DXF, or a vector PDF. Pictures (JPG / PNG) are read by AI vision: sizes are copied exactly as
  written, positions are approximate – check the table before "Confirm".
* The concept generator ("AI plan") fits rooms into the plot, so asked sizes can change; for exact sizes upload a drawing.
