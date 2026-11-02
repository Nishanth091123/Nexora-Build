# Nexora Build 1.9 – Part 2: Estimation upgrade

Version **1.9.0**. Existing estimates and data are not changed.

## New in Estimate & BOQ
- **Quick / Oral Estimate** (first tab). Enter total built-up area, floors, bedrooms and toilets, then press Generate.
  - You get an Economy – Premium range and three cards: Economy, Standard, Premium, each with ₹/sq ft.
  - It also shows the cost split and the main materials (cement, steel, sand, aggregate, bricks).
  - **"Make the Detailed Estimate from this"** opens the full BOQ with the same inputs.
  - If bedrooms or toilets are missing it asks for them. It never guesses.
- **Floor-wise BOQ.** The same item appears in one row with Ground, First, Second, Third and Common columns, then Total, Rate and Amount. There is a filter by category.
- **Area Statement.** Built-up, carpet (approx.), common/stair area and remarks for each floor.
- **Key Quantities.** Excavation, PCC, RCC, steel, brickwork, plaster, flooring, tiles, painting, doors, windows and staircase.
- **Payment Schedule.**
  - The default is: Advance 10%, Foundation 15%, one stage for each roof slab, Finishing 15%, Handover 5%.
  - You can edit names and %, and add or remove stages. Apply works only when the total is 100%. Then press **Save** on the estimate.
- **Loan Documents checklist.** Estimate report, BOQ, architectural plan, structural drawings, site photos, approval documents, loan form and ID proof. Each row has Upload or Replace and shows Uploaded or Pending.
- **Export menu:**
  - BOQ Excel, with new sheets: Floor-wise BOQ, Area Statement, Payment Schedule, Key Quantities.
  - Detailed Estimate PDF.
  - **Bank Loan Estimate PDF**: letterhead, owner details, area statement, abstract of cost, ₹/sq ft, stage-wise payments, and a "For Praganya Construction – Nishanth S (Proprietor)" signature line. No seal is printed; you sign the printed copy.
  - **Client Copy PDF**: work-group totals and main materials only, with no item rates and no margin line.
- **Settings → Units & Rates → Estimate defaults.** GST %, Overhead & profit % and Contingency % used for every new estimate.

Older saved estimates: open one, press Inputs → Calculate → Save once to get the new tables.

## Install
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
scripts\github_push.bat
```
It must end with **NEXORA 1.9 API: ALL GOOD**.

## Test checklist
1. Estimate → Quick / Oral Estimate → 2400 sq ft, G+1, 3 bed, 3 toilet → Generate → three cards appear, with Economy the lowest.
2. "Make the Detailed Estimate from this" → the Overview shows the BOQ.
3. Floor-wise BOQ tab → the columns show Ground / First, and the Area Statement shows carpet area smaller than built-up.
4. Payment Schedule → change Advance to 20% and another stage to keep the total at 100 → Apply → Save.
5. Export → Bank Loan Estimate PDF → it shows Praganya Construction, the owner name, the abstract and the payment stages.
6. Export → Client Copy PDF → there is no rate column and no "Contractor margin" line.
7. Loan Documents → upload a PDF for "BOQ (Excel)" → the row shows Uploaded.
8. Settings → Units & Rates → set GST 12% → a new estimate shows GST 12%.
