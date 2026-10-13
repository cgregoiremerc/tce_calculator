# Voyage Dashboard v2 (TCE / Lumpsum)

Lancer : `pip install -r requirements.txt` puis `streamlit run Home.py`
Tests : `python -m pytest tests`

- `config.py` : hypothèses, ports, distances, flat rates (valeurs ILLUSTRATIVES à remplacer par les vôtres).
- `voyage_calculations.py` : `compute_voyage`, break-even WS/lumpsum, matrice de sensibilité.
- `ui.py` : formulaire et rendu partagés par les deux pages.
- Distances : `get_distance` est mise en cache. Pour brancher l'API, définir `DISTANCE_API_URL`
  (et `DISTANCE_API_CA_BUNDLE` pour le certificat interne) ; la vérification SSL n'est jamais désactivée.
