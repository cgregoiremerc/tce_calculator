# Voyage Dashboard v2 (TCE / Lumpsum)

Run: `pip install -r requirements.txt` then `streamlit run Home.py`
(Home.py is only the router; the landing page is the TCE Calculator.)
Tests: `python -m pytest tests`

- `voyage_calculations.py`: `compute_voyage`, WS / lumpsum break-even, sensitivity matrix.
- `ui.py`: form and rendering shared by the two pages.
- `config.py`: default assumptions and CSV loading.
- Distance API: `get_distance` is cached. To plug it in, set `DISTANCE_API_URL`
  (and `DISTANCE_API_CA_BUNDLE` for the internal certificate); SSL verification is never disabled.

## Updating the data
Everything lives in `data/` (CSV, editable with Excel): `prices.csv` (add one row per day),
`flat_rates.csv`, `distances.csv`, `ports.csv` (port costs, wait days, ECA), `vessels.csv`
(MR/LR1/LR2 profiles) and `routes.csv` (favourite routes). All values shipped are illustrative.
Then `git add . && git commit && git push`.
