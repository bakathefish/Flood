# EOS-04 L2B scenes land here (gitignored)

Download recipe (free, ~5-min registration):
1. Register at https://bhoonidhi.nrsc.gov.in/bhoonidhi/registration.html
   (email + mobile OTP, user type "Academic"; no documents).
2. Log in -> Browse & Order -> satellite EOS-04 -> product SAR(MRS)_L2B
   (and SAR(CRS)_L2B) -> AOI: Punjab bbox 73.85-76.95E / 29.53-32.60N.
3. Search two windows: flood 2025-08-16 .. 2025-09-17 (prefer DESCENDING
   passes - NDEM's own products used dsc) and pre-monsoon 2025-07-01 ..
   2025-08-10 (same orbit/mode if possible, enables change-mode detection).
4. Add L2B ARD items to cart -> OpenData_DirectDownload -> download the
   GeoTIFFs into this folder (keep original filenames - dates are parsed).
5. Run:  python pipeline/compare_eos04.py
   Protocol + pre-declared acceptance bands: docs/notes/eos04.md

Bulk/API alternative: mail bhoonidhi@nrsc.gov.in with a static public IPv4
for STAC API whitelisting (not needed for the cart path).
