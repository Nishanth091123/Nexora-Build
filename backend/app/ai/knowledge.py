"""Built-in civil engineering knowledge used by the assistant (searched like documents, cited as sources).

Content is general guidance from Indian Standards / NBC / TNCDBR and common good site practice.
Each entry names its source so answers can cite it. Structural sizes must still be confirmed by a
qualified engineer – the assistant says so when it gives sizes.
"""
from __future__ import annotations

# (id, category, title, tamil title, tags/keywords (en + ta + tanglish), text, source)
# categories: code | material | site | design | vastu | general
KB: list[tuple[str, str, str, str, str, str, str]] = [
    # ------------------------------------------------------------------ codes & standards
    ("is456-grade", "code", "Minimum concrete grade and cement content", "குறைந்தபட்ச கான்கிரீட் தரம்",
     "concrete grade m20 m25 minimum durability exposure cement content water cement ratio w/c கான்கிரீட் grade",
     "IS 456:2000 Table 5 (durability): for reinforced concrete the minimum grade is M20 in mild exposure, "
     "M25 moderate, M30 severe, M35 very severe and M40 extreme. Minimum cement content for RCC is 300 kg/m³ "
     "(mild and moderate), 320 kg/m³ (severe), with maximum free water-cement ratio 0.55 (mild), 0.50 (moderate) "
     "and 0.45 (severe). Coastal areas (within about 1 km of the sea) are generally treated as severe or worse. "
     "Nexora always uses at least M20 for RCC.",
     "IS 456:2000 cl. 6.1.2, 8.2.4, Table 3 & Table 5"),
    ("is456-cover", "code", "Nominal cover to reinforcement", "கம்பிக்கு கவர்",
     "cover concrete cover reinforcement slab beam column footing nominal cover கவர் cover block",
     "IS 456:2000 Table 16: nominal cover for mild exposure 20 mm, moderate 30 mm, severe 45 mm, very severe 50 mm, "
     "extreme 75 mm (for mild exposure it may be reduced by 5 mm for main bars up to 12 mm). Columns: longitudinal "
     "bars at least 40 mm cover (or bar diameter, whichever is more); footings at least 50 mm. "
     "Typical house practice: slab 20 mm, beam 25 mm, column 40 mm, footing 50 mm. Use proper cover blocks, not stones.",
     "IS 456:2000 cl. 26.4 & Table 16"),
    ("is456-column", "code", "Column reinforcement rules", "தூண் கம்பி விதிகள்",
     "column minimum size reinforcement longitudinal steel ties stirrups pitch column size g+1 g+2 தூண் pillar",
     "IS 456:2000 cl. 26.5.3: longitudinal steel in a column is at least 0.8% and at most 4% (6% absolute max) of "
     "the gross area; at least 4 bars in a rectangular column and 6 in a circular column; bar diameter not less "
     "than 12 mm. Lateral ties: diameter not less than 1/4 of the largest bar and not less than 6 mm; pitch not more "
     "than the least lateral dimension, 16 × smallest longitudinal bar diameter, or 300 mm. IS 13920:2016 "
     "(ductile detailing, seismic) asks for a minimum column dimension of 300 mm. Many G+1 houses in low seismic "
     "zones use 230 × 300 mm or 230 × 380 mm columns, but the actual size must come from a structural design for "
     "the loads, spans and soil.",
     "IS 456:2000 cl. 26.5.3; IS 13920:2016 cl. 7.1"),
    ("is456-slab", "code", "Slab thickness and reinforcement", "ஸ்லாப் தடிமன்",
     "slab thickness depth span ratio reinforcement distribution bars spacing roof slab ஸ்லாப் thickness",
     "IS 456:2000 cl. 23.2.1: basic span/effective depth ratios are 7 for cantilevers, 20 for simply supported and "
     "26 for continuous spans (up to 10 m), modified for steel stress. Minimum slab steel is 0.12% of the gross "
     "section for HYSD (TMT) bars (0.15% for mild steel); bar diameter not more than 1/8 of slab thickness. "
     "Main bar spacing not more than 3 × effective depth or 300 mm; distribution bars not more than 5 × effective "
     "depth or 450 mm. Residential slabs are commonly 125–150 mm thick for 3.5–4.5 m spans.",
     "IS 456:2000 cl. 23.2.1, 26.3.3, 26.5.2"),
    ("is456-beam", "code", "Beam reinforcement rules", "பீம் விதிகள்",
     "beam minimum steel stirrups spacing beam size depth plinth beam lintel பீம்",
     "IS 456:2000 cl. 26.5.1: minimum tension steel As/bd = 0.85/fy (about 0.17% for Fe500); maximum 4% of bD. "
     "Stirrup spacing not more than 0.75d or 300 mm. IS 13920:2016 asks for beam width at least 200 mm and "
     "width/depth ratio more than 0.3. Typical house beams are 230 mm wide and span/12 to span/15 deep, "
     "subject to design.",
     "IS 456:2000 cl. 26.5.1; IS 13920:2016 cl. 6.1"),
    ("is456-curing", "code", "Curing period", "க்யூரிங் காலம்",
     "curing days water curing ponding slab curing column curing opc ppc க்யூரிங் thanni ஊற்றுதல்",
     "IS 456:2000 cl. 13.5.1: exposed concrete surfaces must be kept continuously moist for at least 7 days with "
     "OPC and at least 10 days with blended cements (PPC / PSC) or mineral admixtures; in hot, dry weather extend "
     "to at least 10 days (OPC) and 14 days (blended). Slabs: ponding with small bunds; columns: wet hessian cloth "
     "wrapped and kept wet; walls / plaster: spray 2–3 times a day for 7 days.",
     "IS 456:2000 cl. 13.5.1"),
    ("is456-stripping", "code", "Formwork (centring) removal time", "சென்ட்ரிங் பிரிக்கும் நேரம்",
     "formwork removal centring shuttering deshuttering props stripping time days சென்ட்ரிங் பிரித்தல்",
     "IS 456:2000 cl. 11.3.1 (OPC, normal temperature): vertical faces of columns, walls, beams 16–24 hours; "
     "slab soffit (props left under) 3 days; beam soffit (props left under) 7 days; props to slabs spanning up to "
     "4.5 m – 7 days, over 4.5 m – 14 days; props to beams spanning up to 6 m – 14 days, over 6 m – 21 days. "
     "For PPC / slower cements or cold weather allow more time.",
     "IS 456:2000 cl. 11.3.1"),
    ("is456-workability", "code", "Slump (workability) of concrete", "ஸ்லம்ப்",
     "slump workability slump cone test concrete water ஸ்லம்ப் test",
     "IS 456:2000 cl. 7.1: slump 25–75 mm for lightly reinforced / mass concrete and PCC, 50–100 mm for normal "
     "RCC slabs, beams, columns and walls, 75–100 mm for heavily reinforced sections and pumped concrete. "
     "Adding extra water on site to increase slump reduces strength – use a plasticiser instead.",
     "IS 456:2000 cl. 7.1 (workability table)"),
    ("is456-mix", "code", "Nominal mixes (M10 – M20)", "கான்கிரீட் மிக்ஸ் விகிதம்",
     "mix ratio nominal mix 1:1.5:3 1:2:4 m20 m15 m10 pcc rcc concrete mix ratio கலவை",
     "IS 456:2000 Table 9 nominal mixes (cement : sand : aggregate by volume): M10 ≈ 1:3:6, M15 ≈ 1:2:4, "
     "M20 ≈ 1:1.5:3. Design mix (IS 10262) is preferred for M20 and above, and is required above M20. "
     "Dry volume of materials ≈ 1.54 × wet volume. One bag of cement = 50 kg ≈ 0.0347 m³.",
     "IS 456:2000 cl. 9.3 & Table 9; IS 10262:2019"),
    ("is1786", "code", "TMT steel grades (IS 1786)", "டிஎம்டி கம்பி தரம்",
     "steel tmt fe500 fe500d fe550 fe415 grade rebar கம்பி steel grade d grade",
     "IS 1786:2008 covers high strength deformed bars: Fe415, Fe415D, Fe500, Fe500D, Fe550, Fe550D, Fe600. "
     "The number is the minimum 0.2% proof / yield stress in N/mm². 'D' grades have lower carbon, sulphur and "
     "phosphorus and higher elongation (more ductile) – preferred for houses in seismic zones III and above. "
     "Fe500 / Fe500D is the common choice for houses. Weight of a bar = d²/162 kg per metre (d in mm).",
     "IS 1786:2008"),
    ("cement-codes", "code", "Cement types and their standards", "சிமெண்ட் வகைகள்",
     "cement opc ppc psc 53 grade 43 grade is 269 is 1489 is 455 சிமெண்ட் cement type",
     "OPC 33/43/53 – IS 269:2015; PPC (fly ash based) – IS 1489 (Part 1):2015; PSC (slag) – IS 455:2015. "
     "The grade (33/43/53) is the 28-day compressive strength in N/mm². PPC and PSC gain strength slower but "
     "give better durability, lower heat and better resistance to sulphates and chlorides.",
     "IS 269:2015; IS 1489 (Part 1):2015; IS 455:2015"),
    ("nbc-rooms", "code", "Minimum room sizes (NBC)", "குறைந்தபட்ச அறை அளவு",
     "room size minimum habitable room kitchen bathroom toilet ceiling height nbc அறை அளவு",
     "NBC 2016 Part 3: a habitable room should be at least 9.5 m² (about 102 sq ft) with minimum width 2.4 m when "
     "there is only one room; with two or more rooms, one room 9.5 m² and others at least 7.5 m². Ceiling height "
     "of habitable rooms at least 2.75 m. Kitchen at least 5.0 m² with width 1.8 m. Bathroom 1.8 m² (width 1.2 m), "
     "WC 1.1 m² (width 0.9 m), combined bath + WC 2.8 m². Local rules (TNCDBR) prevail where they differ.",
     "NBC 2016 Part 3 cl. 8"),
    ("nbc-stair", "code", "Staircase dimensions (residential)", "படிக்கட்டு அளவுகள்",
     "staircase stair riser tread width headroom handrail படிக்கட்டு steps stair size",
     "NBC 2016 Part 4 (residential low-rise): stair width at least 0.9 m (1.0 m common); riser not more than "
     "190 mm; tread not less than 250 mm; headroom at least 2.2 m; handrail 900 mm high. Keep riser and tread "
     "uniform in a flight; 2R + T between 550 and 700 mm is comfortable. Max about 15 risers per flight.",
     "NBC 2016 Part 4"),
    ("tncdbr-setback", "code", "Tamil Nadu setbacks (TNCDBR 2019)", "தமிழ்நாடு செட்பேக்",
     "setback tncdbr front side rear setback road width tamil nadu building rules dtcp cmda செட்பேக் vidu",
     "Tamil Nadu Combined Development and Building Rules 2019 fix the front setback from the road width and the "
     "side / rear setbacks from plot size and building height, plus FSI and plot coverage limits. Nexora's design "
     "engine applies these automatically – ask 'setback for 30x40, 20 ft road, G+1' to see the exact numbers. "
     "Always confirm with the local body (DTCP / CMDA / corporation) before submitting.",
     "TNCDBR 2019 (G.O. Ms. No. 18, 2019)"),
    ("is875-loads", "code", "Design loads for houses", "வடிவமைப்பு சுமைகள்",
     "live load dead load floor load terrace load wind earthquake is 875 is 1893 seismic zone load",
     "IS 875 (Part 2):1987 imposed loads for residential buildings: rooms, kitchens, toilets 2.0 kN/m²; stairs, "
     "balconies, corridors 3.0 kN/m²; accessible roof 1.5 kN/m². Wind loads per IS 875 (Part 3):2015 and "
     "earthquake per IS 1893 (Part 1):2016 (Tamil Nadu is mostly Zone II and III; Chennai is Zone III).",
     "IS 875 Part 2 & 3; IS 1893 (Part 1):2016"),
    ("is2212-brick", "code", "Brick masonry good practice", "செங்கல் கட்டு",
     "brick masonry brickwork mortar 1:6 1:4 soaking bricks joint thickness courses per day செங்கல் கட்டு",
     "IS 2212:1991: soak bricks before use; joints about 10 mm; break vertical joints; raise not more than about "
     "1 m height per day; cure for 7 days. Mortar 1:6 for 230 mm walls, 1:4 for 115 mm partition walls (with "
     "hoop iron / mesh every 4th course). Bricks: IS 1077 (class 3.5 minimum for load bearing).",
     "IS 2212:1991; IS 1077:1992"),
    ("is1661-plaster", "code", "Plastering thickness and mix", "பூச்சு (Plaster)",
     "plaster plastering thickness mix internal external ceiling 12mm 20mm பூச்சு plastering",
     "IS 1661:1972 good practice: internal walls 12 mm in 1:5 or 1:6, ceilings 6–10 mm in 1:4 / 1:3, external walls "
     "18–20 mm in two coats (1:4 or 1:5) with waterproofing compound in the outer coat. Hack concrete surfaces / "
     "apply bonding coat; fix chicken mesh at RCC–brick junctions; cure 7 days.",
     "IS 1661:1972"),

    # ------------------------------------------------------------------ materials
    ("mat-opc-ppc", "material", "OPC vs PPC vs PSC – which to use", "OPC / PPC / PSC எதை பயன்படுத்துவது",
     "opc ppc psc cement comparison which cement coastal area slab plaster foundation best cement எந்த சிமெண்ட்",
     "OPC 53: fast early strength – useful for precast, quick deshuttering and cold weather; more heat, so more "
     "shrinkage cracks if curing is poor. PPC: slower early strength, lower heat, better durability and finish – "
     "good for foundations, masonry, plaster and general RCC of houses (cure 10+ days). PSC: best resistance to "
     "chlorides and sulphates – preferred in coastal / saline areas, foundations in aggressive soil. "
     "For a coastal house: PSC or PPC with M25+, low w/c, 45–50 mm cover and good curing.",
     "IS 269, IS 1489, IS 455; IS 456 Table 3"),
    ("mat-sand", "material", "M-Sand vs P-Sand vs river sand", "எம்-சாண்ட் / பி-சாண்ட்",
     "m sand p sand river sand manufactured sand plastering sand concrete sand silt test எம் சாண்ட்",
     "M-Sand (manufactured sand, 0–4.75 mm) is allowed for concrete by IS 383:2016; use it for concrete and "
     "masonry. P-Sand (plastering sand, finer, 0–2.36 mm) is for plastering. Check: silt content by the field "
     "jar test (not more than about 8% by volume), no flaky particles, washed product. River sand is restricted "
     "in Tamil Nadu; M-Sand from TN PWD-approved units is the common choice.",
     "IS 383:2016"),
    ("mat-blocks", "material", "Red brick vs AAC block vs fly ash brick vs solid block", "செங்கல் / AAC / ஃப்ளை ஆஷ்",
     "aac block red brick fly ash brick solid block comparison wall cost weight insulation செங்கல் aac",
     "Red clay brick (IS 1077): good strength and moisture behaviour, more mortar and labour. AAC block "
     "(IS 2185 Part 3): about 1/3 the weight of brick, better heat insulation, faster laying with thin-bed "
     "adhesive, less load on the frame – but needs care against water absorption (good plaster, no direct "
     "dampness at plinth level). Fly ash brick (IS 12894): uniform size, less plaster, eco-friendly. Solid "
     "concrete block (IS 2185 Part 1): strong, cheap per wall area, heavier, hotter. For framed RCC houses AAC "
     "often reduces structure cost; for load-bearing walls use bricks or solid blocks.",
     "IS 1077; IS 2185 (Part 1 & 3); IS 12894"),
    ("mat-steel", "material", "Choosing TMT steel", "டிஎம்டி கம்பி தேர்வு",
     "tmt steel brand choose fe500d primary secondary steel rust weight check கம்பி வாங்க",
     "Use Fe500D (IS 1786) from a BIS-licensed producer; check the ISI mark, grade and heat number rolled on the "
     "bar and ask for the test certificate. Check weight: 8 mm = 0.395 kg/m, 10 mm = 0.617, 12 mm = 0.889, "
     "16 mm = 1.58, 20 mm = 2.47 kg/m. Light surface rust is acceptable; flaky / pitted rust is not. Store on "
     "sleepers above ground and covered.",
     "IS 1786:2008"),
    ("mat-aggregate", "material", "Coarse aggregate (blue metal / jelly)", "ஜல்லி",
     "aggregate jelly blue metal 20mm 40mm 12mm coarse aggregate ஜல்லி",
     "IS 383:2016: use clean, hard, angular aggregate; 20 mm for RCC slabs, beams and columns, 12 mm for thin "
     "sections / precast, 40 mm for PCC and mass concrete. Avoid flaky / elongated pieces and dust; wash if dusty. "
     "Maximum size not more than 1/4 of the minimum section thickness and 5 mm less than the bar spacing / cover.",
     "IS 383:2016; IS 456 cl. 5.3.3"),
    ("mat-waterproof", "material", "Waterproofing methods (terrace, toilet, sump)", "நீர்க்காப்பு முறைகள்",
     "waterproofing terrace roof toilet bathroom sump tank leakage membrane crystalline coating brickbat "
     "ஒழுகுதல் water proof terrace leak",
     "Terrace: slope 1:100 to drains; options – brickbat coba with integral waterproof compound (traditional, "
     "heavy), cementitious polymer coating (2 coats + mesh at corners), elastomeric/PU liquid membrane (best for "
     "exposed roofs, re-coat every 5–7 years), APP/SBS membrane with protection screed. Toilets: polymer "
     "cementitious coating on floor + 300 mm up the walls (1.8 m in the shower), fillet at corners, 48-hour ponding "
     "test before tiling. Sump / water tank: crystalline admixture in concrete or crystalline coating on the inner "
     "face (safe for drinking water when certified). Always fill cracks and pipe sleeves with polymer mortar first.",
     "Good practice; IS 2645 (integral waterproofing compounds)"),
    ("mat-tiles", "material", "Floor tiles – vitrified, ceramic, granite", "தரை டைல்ஸ்",
     "tiles vitrified ceramic granite flooring anti skid double charge gvt pgvt marble டைல்ஸ்",
     "Vitrified tiles (IS 15622 / ISO 13006 class BIa) have water absorption ≤ 0.5% – good for living / bedrooms "
     "(double charge for heavy traffic, GVT/PGVT for designs). Ceramic tiles absorb more water – walls and dado. "
     "Anti-skid matt tiles (R10/R11) for toilets, balconies and ramps. Granite for kitchen tops, steps and "
     "parking. Lay on tile adhesive (C1/C2) rather than thick mortar for large tiles; leave 2–3 mm joints with "
     "spacers; add 5–8% wastage (10% for diagonal laying).",
     "IS 15622; good practice"),
    ("mat-paint", "material", "Paint system for a house", "பெயிண்ட் முறை",
     "paint putty primer emulsion exterior interior texture distemper coats பெயிண்ட்",
     "Interior: 2 coats wall putty (after plaster cures ~28 days) + 1 coat primer + 2 coats emulsion; distemper "
     "is the budget option. Exterior: alkali-resistant primer + 2 coats exterior emulsion (elastomeric for "
     "crack-bridging in rain areas). Approx. coverage: emulsion 10–12 m² per litre per coat, primer 8–10 m², "
     "putty 1 kg per m² for 2 coats.",
     "Manufacturer guidance; good practice"),
    ("mat-pipes", "material", "Plumbing pipes – CPVC, UPVC, PVC, PPR", "குழாய் வகைகள்",
     "pipe cpvc upvc pvc ppr gi plumbing hot water drainage swr pipe குழாய்",
     "CPVC (IS 15778): hot and cold water inside the house. UPVC (IS 4985 / IS 12818): cold water supply and "
     "external lines. PPR: hot / cold water with heat-fused joints. SWR PVC (IS 13592): soil, waste and rain "
     "water. Avoid GI for new supply lines (rusting). Test all water lines at about 1.5 × working pressure before "
     "concealing.",
     "IS 15778; IS 4985; IS 13592"),
    ("mat-wires", "material", "Electrical wires and MCBs", "மின் வயர்",
     "wire electrical cable mcb rccb elcb sq mm copper frls earthing வயர்",
     "Use FR / FRLS copper wires (IS 694): 1.5 mm² lights and fans, 2.5 mm² 6/16 A sockets, 4 mm² AC / geyser "
     "circuits, 6 mm² main / sub-mains (depends on load and length). Separate MCB per circuit, a 30 mA RCCB for "
     "shock protection, and proper earthing (IS 3043) with an earth pit.",
     "IS 694; IS 732; IS 3043"),

    # ------------------------------------------------------------------ site troubleshooting
    ("site-plaster-cracks", "site", "Plaster cracks – causes and repair", "பூச்சு விரிசல்",
     "plaster crack hairline crack shrinkage crack wall crack repair விரிசல் crack varudhu",
     "Common causes: rich mix or too much cement, plaster too thick in one coat, no curing, fast drying in sun / "
     "wind, missing mesh at RCC–brick joints, plastering before masonry settles. Hairline (map) cracks: rake out, "
     "fill with acrylic crack filler / polymer putty before painting. Joint cracks at beam / column: cut a V "
     "groove, fill with polymer mortar, fix fibre mesh tape, re-plaster. Prevent: 1:5 / 1:6 mix, two coats for "
     "thick plaster, chicken mesh 150 mm each side of joints, cure 7 days. Wide or growing cracks (more than about "
     "3 mm, diagonal, at openings) may be structural – get an engineer to check before covering them.",
     "IS 1661; good practice"),
    ("site-concrete-cracks", "site", "Cracks in concrete (slab, beam, column)", "கான்கிரீட் வெடிப்பு",
     "concrete crack slab crack beam crack column crack shrinkage crack structural crack epoxy injection வெடிப்பு",
     "Types: plastic shrinkage cracks (fine, random, appear within hours – fast drying, no curing), drying shrinkage "
     "(map pattern, weeks later), thermal cracks, and structural cracks (at mid-span bottom of slabs / beams, diagonal "
     "near beam supports, or along bars with rust stains). Fine non-structural cracks (< 0.3 mm): seal with "
     "low-viscosity epoxy or polymer cement slurry; cracks 0.3–3 mm: epoxy injection through ports. Cracks along steel "
     "with rust, cracks wider than about 3 mm, deflection or cracks that keep growing must be checked by a structural "
     "engineer before repair. Prevent: right w/c ratio, proper vibration, curing from the first day (IS 456 "
     "cl. 13.5), covering fresh concrete in sun / wind, and correct cover.",
     "IS 456:2000 cl. 13.5, 35.3.2; good practice"),
    ("site-dampness", "site", "Dampness on walls (rising damp, efflorescence)", "சுவர் ஈரம்",
     "damp dampness wall moisture rising damp efflorescence salt white patches seepage ஈரம் ஊறல்",
     "Rising damp at the bottom of walls: missing / broken DPC at plinth – provide a 40 mm DPC (1:1.5:3 with "
     "waterproof compound) in new work; for existing walls use chemical DPC injection and remove plaster 1 m high, "
     "re-plaster with waterproof mortar. Efflorescence (white salt): from salts in bricks / sand / water – dry "
     "brush (no water), treat with efflorescence remover, use washed sand and good bricks. Seepage from toilets / "
     "terrace: find the source (ponding test, pipe pressure test) before repairing the wall.",
     "IS 3067 (damp proofing); good practice"),
    ("site-honeycomb", "site", "Honeycombing in concrete", "கான்கிரீட் தேன்கூடு",
     "honeycomb honeycombing voids concrete column bottom vibration segregation கான்கிரீட் ஓட்டை",
     "Causes: poor vibration, dry or segregated concrete, congested steel, formwork leaking slurry, dropping "
     "concrete from height. Minor surface honeycomb: chip loose material, wet, apply bonding agent and fill with "
     "polymer-modified mortar. Deep honeycomb in columns / beams (steel visible, through-section): get the "
     "structural engineer to check – may need micro-concrete jacketing or grouting. Prevent: needle vibrator, "
     "slump 75–100 mm with plasticiser, cover blocks, seal formwork joints, pour columns in lifts.",
     "IS 456 cl. 13.3; good practice"),
    ("site-slab-leak", "site", "Roof slab leakage", "மேல்தள ஒழுகல்",
     "roof leak slab leakage terrace leak ceiling dampness monsoon ஒழுகுது leakage",
     "Check: terrace slope and blocked drains, cracks in the screed / parapet joint, gaps around pipes, cold "
     "joints. Repair: clean, open and seal cracks with polymer / PU sealant, fillet at the parapet junction, "
     "then an elastomeric / PU waterproof coating with fibre mesh at corners; re-grade low spots. Ponding test "
     "for 48 hours after repair. If the slab itself is cracked or the steel is rusting, consult an engineer.",
     "Good practice"),
    ("site-settlement", "site", "Settlement / foundation cracks", "அடித்தள விரிசல்",
     "settlement crack foundation crack diagonal crack floor sinking differential settlement அடித்தளம் crack",
     "Diagonal (stair-step) cracks near corners or openings, doors jamming and floors sinking suggest foundation "
     "settlement. Monitor with tell-tales (date-marked glass / plaster strips) for a few weeks; check drainage and "
     "leaking pipes near the foundation; check soil (black cotton / filled soil). Do not just patch – get a "
     "structural engineer; remedies include underpinning, micro-piles or soil stabilisation.",
     "Good practice"),
    ("site-column-plumb", "site", "Column out of plumb / misaligned", "தூண் சாய்வு",
     "column plumb alignment out of line column shift bulging formwork தூண் சாய்ந்து",
     "Tolerance (IS 456 cl. 11.2 / good practice): plumb within about 5 mm per 3 m height; position within "
     "±10 mm. Check plumb with a plumb bob on two faces before and after pouring, brace formwork properly, and use "
     "a centre-line string from fixed reference pillars. Large errors after concreting must be reviewed by the "
     "engineer (jacketing / eccentric load check) – do not hack the column.",
     "IS 456 cl. 11.2; good practice"),
    ("site-concrete-cube", "site", "Concrete cube test and acceptance", "கியூப் சோதனை",
     "cube test concrete strength 7 day 28 day sample acceptance criteria compressive strength கியூப் test",
     "IS 456 cl. 15 & 16: take 150 mm cubes (3 per sample) from each pour; sampling frequency by volume "
     "(1–5 m³ → 1 sample, 6–15 → 2, 16–30 → 3 …). Test at 28 days (7-day result is about 65–70% for OPC). "
     "Acceptance for M20 and above: mean of 4 non-overlapping consecutive samples ≥ fck + 0.825 × standard "
     "deviation (rounded) and individual ≥ fck – 4 N/mm² (IS 456:2000 Amendment 3).",
     "IS 456:2000 cl. 15, 16 & Table 11"),
    ("site-rain", "site", "Concreting in rain / hot weather", "மழை / வெயிலில் கான்கிரீட்",
     "rain concreting hot weather monsoon slab casting rain cover polythene மழையில் slab போடலாமா",
     "Avoid casting a slab in heavy rain; if rain starts, cover finished areas with polythene, stop at a planned "
     "construction joint (near mid-span of slab / one-third span of beams, never at supports), and remove "
     "watery slurry before restarting. Hot weather (> 35 °C): pour early morning / evening, keep aggregates "
     "shaded and wet, start curing as soon as the surface sets, use a retarder if trips are long.",
     "IS 7861 (Part 1 & 2); IS 456 cl. 13.4"),
    ("site-termite", "site", "Anti-termite treatment", "கரையான் தடுப்பு",
     "termite anti termite treatment pre construction soil treatment கரையான்",
     "IS 6313 (Part 2): pre-construction soil treatment with a registered termiticide at foundation trenches, "
     "plinth filling and along walls before flooring; external perimeter after construction. Keep a record of the "
     "chemical, dilution and area for warranty.",
     "IS 6313 (Part 2)"),

    # ------------------------------------------------------------------ design advice
    ("design-cost-saving", "design", "Cost-saving ideas for a house", "செலவு குறைக்கும் வழிகள்",
     "reduce cost cost effective save money cheap budget house construction ideas செலவு குறைக்க",
     "Keep the plan compact and rectangular (fewer corners), stack toilets and kitchens vertically for short "
     "plumbing, use standard door / window sizes, AAC or fly ash blocks for framed structures, rat-trap bond for "
     "garden walls, filler slab for short spans (with engineer approval), M-Sand, PPC, limit specifications to "
     "Standard where the finish is hidden, and buy steel / cement in bulk at the right stage. Avoid cutting on "
     "structure, waterproofing and electrical safety.",
     "Good practice"),
    ("design-ventilation", "design", "Light and ventilation", "வெளிச்சம் / காற்றோட்டம்",
     "ventilation window size light cross ventilation window area காற்றோட்டம் jannal",
     "NBC 2016 Part 3: window / ventilator openings at least 1/10 of the floor area for habitable rooms (1/6 is "
     "better in hot-humid climates); toilets need a ventilator of at least 0.3 m² or mechanical exhaust. Place "
     "openings on opposite walls for cross ventilation; shade West and South windows with sunshades.",
     "NBC 2016 Part 3"),
    ("design-sump-tank", "design", "Sump and overhead tank size", "சம்ப் / டேங்க் அளவு",
     "sump size water tank capacity overhead tank litres per person storage சம்ப் tank size",
     "IS 1172: domestic demand about 135 litres per person per day (150–200 in practice). Common sizing: overhead "
     "tank ≈ 1 day's demand, sump ≈ 1.5–2 days. Example: 5 people × 135 L = 675 L/day → 1000 L overhead tank and "
     "a 6000–10000 L sump if supply is irregular.",
     "IS 1172:1993"),

    # ------------------------------------------------------------------ vastu
    ("vastu-basics", "vastu", "Vastu basics used by Nexora", "வாஸ்து அடிப்படை",
     "vastu basics direction kitchen south east master bedroom south west pooja north east வாஸ்து",
     "Traditional guidance applied by the Vastu module: kitchen South-East (next choice North-West); master "
     "bedroom South-West; pooja North-East / East / North; toilets North-West / West / South (never North-East or "
     "centre); staircase South / West / South-West; living room North / East / North-East; entrance North, East or "
     "North-East preferred; keep the centre (Brahmasthan) and North-East open and light; overhead tank over "
     "South-West, sump in North-East. These are traditional preferences, not structural rules.",
     "Nexora Vastu module (traditional guidance)"),
]

CATEGORY_LABEL = {"code": "Code & Standards", "material": "Material Guide", "site": "Site Troubleshooting",
                  "design": "Design Advice", "vastu": "Vastu", "general": "General"}


def entries() -> list[dict]:
    return [{"id": i, "category": c, "title": t, "title_ta": tt, "tags": tags, "text": text, "source": src}
            for i, c, t, tt, tags, text, src in KB]


# ------------------------------------------------------------------ material guide (structured, for the Material Guide tab)
MATERIAL_GUIDE: list[dict] = [
    {"key": "cement", "name": "Cement", "name_ta": "சிமெண்ட்", "rate_code": "cement", "items": [
        {"name": "OPC 53", "standard": "IS 269", "use": "Precast, early deshuttering, cold weather, high-grade RCC",
         "pros": "Fast strength gain", "cons": "More heat & shrinkage cracks; needs careful curing"},
        {"name": "PPC", "standard": "IS 1489-1", "use": "Foundations, masonry, plaster, general house RCC",
         "pros": "Durable, smooth finish, lower heat, usually cheaper", "cons": "Slower early strength – cure 10+ days"},
        {"name": "PSC", "standard": "IS 455", "use": "Coastal / saline areas, aggressive soil, sumps",
         "pros": "Best chloride & sulphate resistance", "cons": "Slow early strength; less available in some towns"},
    ], "tips": ["Use within 3 months of the manufacture date (printed on the bag).",
                "Stack max 10 bags high on a raised platform, away from walls, covered with polythene.",
                "Check the ISI mark, grade, weight 50 kg and that there are no lumps."], "kb": "mat-opc-ppc"},
    {"key": "steel", "name": "TMT Steel", "name_ta": "டிஎம்டி கம்பி", "rate_code": "steel", "items": [
        {"name": "Fe500D", "standard": "IS 1786", "use": "All RCC of houses, seismic zones III+",
         "pros": "Ductile, good bendability", "cons": "Slightly costlier than Fe500"},
        {"name": "Fe500", "standard": "IS 1786", "use": "General RCC in low seismic zones",
         "pros": "Common, economical", "cons": "Lower elongation than D grade"},
        {"name": "Fe550D", "standard": "IS 1786", "use": "Heavier structures, designed members",
         "pros": "Higher strength – less steel", "cons": "Use only if the design is done for Fe550"},
    ], "tips": ["Bar weight per metre = d²/162 kg (8 mm 0.395, 10 mm 0.617, 12 mm 0.889, 16 mm 1.58).",
                "Check ISI mark, grade and heat number rolled on the bar; ask for the mill test certificate."],
     "kb": "mat-steel"},
    {"key": "masonry", "name": "Bricks & Blocks", "name_ta": "செங்கல் / பிளாக்", "rate_code": "brick", "items": [
        {"name": "Red clay brick", "standard": "IS 1077", "use": "Load-bearing & framed walls",
         "pros": "Strong, familiar, good moisture behaviour", "cons": "More mortar, labour and weight"},
        {"name": "AAC block", "standard": "IS 2185-3", "use": "Framed RCC buildings, upper floors",
         "pros": "Light (≈1/3 weight), insulating, fast laying", "cons": "Needs care against dampness; special adhesive"},
        {"name": "Fly ash brick", "standard": "IS 12894", "use": "Framed and low-rise load-bearing walls",
         "pros": "Uniform size, less plaster, eco-friendly", "cons": "Quality varies by supplier"},
        {"name": "Solid concrete block", "standard": "IS 2185-1", "use": "Compound walls, ground floors",
         "pros": "Strong, cheap per m²", "cons": "Heavy, hotter interiors"},
    ], "tips": ["Soak clay bricks before laying; AAC blocks are only damped.",
                "Check bricks: uniform colour, metallic ring when struck, no cracks, ≤ 20% water absorption."],
     "kb": "mat-blocks"},
    {"key": "sand", "name": "Sand", "name_ta": "மணல்", "rate_code": "msand", "items": [
        {"name": "M-Sand", "standard": "IS 383", "use": "Concrete and masonry mortar",
         "pros": "Consistent grading, available", "cons": "Must be washed – check silt"},
        {"name": "P-Sand", "standard": "IS 1542", "use": "Plastering", "pros": "Fine, smooth finish",
         "cons": "Not for concrete"},
    ], "tips": ["Silt jar test: not more than about 8% by volume.", "Buy from TN PWD-approved M-Sand units."],
     "kb": "mat-sand"},
    {"key": "aggregate", "name": "Aggregate (Jelly)", "name_ta": "ஜல்லி", "rate_code": "agg20", "items": [
        {"name": "20 mm", "standard": "IS 383", "use": "RCC slabs, beams, columns", "pros": "Standard size", "cons": "-"},
        {"name": "12 mm", "standard": "IS 383", "use": "Thin sections, precast, congested steel",
         "pros": "Fits tight spaces", "cons": "Needs more cement paste"},
        {"name": "40 mm", "standard": "IS 383", "use": "PCC bed, mass concrete", "pros": "Economical", "cons": "Not for RCC"},
    ], "tips": ["Avoid flaky / dusty aggregate; wash if dusty."], "kb": "mat-aggregate"},
    {"key": "concrete", "name": "Concrete grades", "name_ta": "கான்கிரீட் தரம்", "rate_code": "", "items": [
        {"name": "M10 / M7.5", "standard": "IS 456", "use": "PCC bed under footings, levelling",
         "pros": "Cheap", "cons": "Not for reinforced work"},
        {"name": "M20", "standard": "IS 456", "use": "Minimum for RCC (mild exposure)", "pros": "Standard for houses",
         "cons": "Design mix preferred"},
        {"name": "M25 – M30", "standard": "IS 456", "use": "Coastal / moderate–severe exposure, sumps, heavy loads",
         "pros": "More durable", "cons": "Needs design mix & quality control"},
    ], "tips": ["Ready-mix (RMC) gives consistent quality for slabs.", "Never add water at site to improve flow."],
     "kb": "is456-grade"},
    {"key": "waterproofing", "name": "Waterproofing", "name_ta": "நீர்க்காப்பு", "rate_code": "waterproof", "items": [
        {"name": "Cementitious polymer coating", "standard": "-", "use": "Toilets, balconies, sumps (inside)",
         "pros": "Easy, tiles bond well", "cons": "Not for exposed movement cracks"},
        {"name": "PU / elastomeric liquid membrane", "standard": "-", "use": "Exposed terraces",
         "pros": "Flexible, UV resistant", "cons": "Re-coat every 5–7 years"},
        {"name": "Crystalline admixture / coating", "standard": "-", "use": "Sumps, water tanks, basements",
         "pros": "Self-sealing hairline cracks", "cons": "Needs wet curing"},
        {"name": "Brickbat coba", "standard": "-", "use": "Traditional terrace treatment",
         "pros": "Insulation + slope", "cons": "Heavy; fails if cracked"},
    ], "tips": ["Do a 48-hour ponding test before tiling or screeding."], "kb": "mat-waterproof"},
    {"key": "flooring", "name": "Flooring", "name_ta": "தரை", "rate_code": "floor_tile", "items": [
        {"name": "Vitrified tiles", "standard": "IS 15622", "use": "Living, bedrooms", "pros": "Low absorption, many designs",
         "cons": "Slippery when wet (use matt in wet areas)"},
        {"name": "Anti-skid ceramic", "standard": "IS 15622", "use": "Toilets, balconies", "pros": "Safe", "cons": "Absorbs more"},
        {"name": "Granite", "standard": "-", "use": "Kitchen top, steps, parking", "pros": "Very durable", "cons": "Costlier"},
    ], "tips": ["Add 5–8% wastage (10% for diagonal laying)."], "kb": "mat-tiles"},
    {"key": "paint", "name": "Paint", "name_ta": "பெயிண்ட்", "rate_code": "paint_int", "items": [
        {"name": "Interior emulsion", "standard": "IS 15489", "use": "Inside walls", "pros": "Washable", "cons": "Needs putty + primer"},
        {"name": "Exterior emulsion / elastomeric", "standard": "IS 15489", "use": "Outside walls",
         "pros": "Weather & crack resistant", "cons": "Costlier"},
        {"name": "Distemper", "standard": "IS 427", "use": "Budget interiors", "pros": "Cheap", "cons": "Not washable"},
    ], "tips": ["Start putty only after plaster has cured about 28 days."], "kb": "mat-paint"},
    {"key": "plumbing", "name": "Pipes", "name_ta": "குழாய்கள்", "rate_code": "", "items": [
        {"name": "CPVC", "standard": "IS 15778", "use": "Hot & cold water inside", "pros": "Handles hot water", "cons": "Costlier"},
        {"name": "UPVC", "standard": "IS 4985", "use": "Cold water lines", "pros": "Cheap, durable", "cons": "Not for hot water"},
        {"name": "SWR PVC", "standard": "IS 13592", "use": "Drainage, soil & rain water", "pros": "Ring-fit joints", "cons": "-"},
    ], "tips": ["Pressure-test water lines before concealing."], "kb": "mat-pipes"},
]
