# Verification of the digitised WRD guidebook tables

Source: Punjab Department of Water Resources, *Flood Preparedness Guidebook 2026* (PDF
captured 2026-08-10, sha1 6bf23d33). The PDF is not committed because it prints personal
phone numbers of officials; only the tables below are.

Method: `scripts/digitise_guidebook.py` parses the PDF's text layer into the CSVs in this
folder and renders the source pages to PNG (`data/raw/wrd/pages/`, not committed). Each CSV
was then read against its rendered page, row by row, on 2026-09-05. Printed page numbers are
four less than the PDF page index (printed page 11 is PDF page 15).

| table | printed page | PDF page | rows | result |
|---|---|---|---|---|
| `thresholds.csv` (section 3.2) | 11 | 15 | 10 stations | every band matches the page; river column corrected after the first pass assigned Ferozepur to the Beas and Madhopur to the Ghaggar (parser lag, fixed) |
| `peaks_harike_hussainiwala.csv` (section 3.3 I) | 12 | 16 | 38 years | all 38 rows match, including the blanks for Hussainiwala D/S in 2002 and 2004 and the unclassed years marked "-" |
| `peaks_ropar.csv` (section 3.3 II) | 13 | 17 | 38 years | all rows match; 1995 prints D/S 171,522 above U/S 161,418 as on the page |
| `peaks_dhilwan.csv` (section 3.3 III) | 14 | 18 | 38 years | all rows match, dates converted from DD-MM-YYYY to ISO |
| `travel_times.csv` (Annexure Z) | 118 | 122 | 12 reaches | all reaches match; the printed totals are 219 km / 52 h (Sutlej to Harike), 236 km / 72 h (Ghaggar), 215 km / 72 h (Beas) |

Printed inconsistencies kept as printed:

- Dhilwan bands: Low 80,000 to 1,50,000 and Med 2,00,000 to 3,00,000 leave 1,50,000 to
  2,00,000 unclassified. `constants.ControlPoint` classifies that gap as low and says so.
- The Beas reach distances sum to 215.3 km against a printed total of 215.
- Annexure Z states "Beas Maximum Discharge 1988 Dhilwan = 3.90 lacs cusecs" while table
  III gives the 1988 Dhilwan maximum as 166,000 cusecs on 29-09-1988. Table III is used;
  the note is recorded.
- Annexure Z states "16-8-08 Dhilwan = 0.87 lacs cusecs" while table III gives 87,800 on
  17-08-2008 (one day apart, same magnitude).

Class counts in the Harike table: H = 5 (1988, 1994, 1995, 2023, 2025), M = 4, L = 14,
unclassed = 15.
