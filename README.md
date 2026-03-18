# odds* ⚽🏀

> Dashboard IA de prédictions sportives — Football & NBA
> Bento grid interactif · Gemini 2.0 · Multi-source APIs

![odds* dashboard](https://via.placeholder.com/1200x600/0f0f0f/7C5EF0?text=odds*+dashboard)

---

## ✨ Fonctionnalités

- **Bento grid** interactif avec drag & drop (style Stoken)
- **Football** : Prédictions, H2H, Forme, Cotes, xG (Poisson)
- **NBA** : Scores live, prédictions, stats joueurs
- **Highlights** : Vidéos Scorebat en temps réel
- **Agent IA** : Chat Gemini 2.0 Flash avec contexte live
- **Bankroll** : Tracker ROI, win rate, courbe de gains
- **Multi-source** : API-Football + RapidAPI + Football-Data.org

---

## 🚀 Installation

### Prérequis
- Python 3.9+
- Comptes sur les APIs listées ci-dessous

### Installation rapide

```bash
# 1. Cloner le repo
git clone https://github.com/TON_USERNAME/odds-star.git
cd odds-star

# 2. Environnement virtuel
python3.9 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows

# 3. Dépendances
pip install -r requirements.txt

# 4. Lancer
streamlit run app.py
```

L'app s'ouvre sur **http://localhost:8501** 🎉

---

## 🔑 APIs utilisées

| API | Usage | Lien | Free tier |
|-----|-------|------|-----------|
| API-Football | Fixtures, prédictions, H2H | [api-sports.io](https://api-sports.io) | 100 req/jour |
| Balldontlie | Matchs NBA, stats | [balldontlie.io](https://www.balldontlie.io) | Gratuit avec clé |
| The Odds API | Cotes bookmakers | [the-odds-api.com](https://the-odds-api.com) | 500 req/mois |
| Scorebat | Highlights vidéo | [scorebat.com](https://www.scorebat.com/video-api/) | 100 req/heure |
| NewsAPI | Sentiment actualités | [newsapi.org](https://newsapi.org) | 100 req/jour |
| Open-Meteo | Météo | [open-meteo.com](https://open-meteo.com) | Illimité |
| Gemini AI | Chat IA | [aistudio.google.com](https://aistudio.google.com) | Gratuit |
| RapidAPI Football | Backup données | [rapidapi.com](https://rapidapi.com) | Free tier |

### Configuration des clés

Dans l'app → **⚙️ Paramètres** → remplir les champs API.

Ou directement dans `app.py` (ligne ~30) dans `DEFAULT_KEYS`.

---

## 📁 Structure

```
odds-star/
├── app.py              # Application complète (single-file)
├── requirements.txt    # Dépendances Python
├── README.md           # Ce fichier
└── .gitignore          # Fichiers à ignorer
```

---

## 🔒 Sécurité

⚠️ **Ne committez jamais vos clés API** dans Git.

Utilisez les variables d'environnement ou Streamlit Secrets :

```toml
# .streamlit/secrets.toml (ne pas committer)
[api_keys]
api_football = "votre_clé"
gemini = "votre_clé"
```

Puis dans `app.py` :
```python
import streamlit as st
keys = st.secrets.get("api_keys", DEFAULT_KEYS)
```

---

## 🌐 Déploiement sur Streamlit Cloud

1. Pushez le code sur GitHub
2. Allez sur [share.streamlit.io](https://share.streamlit.io)
3. "New app" → sélectionnez votre repo
4. Ajoutez vos clés dans **Secrets** (Settings → Secrets)
5. Deploy !

---

## 📊 Stack technique

- **Frontend** : Streamlit + HTML/CSS/JS (bento grid via `st.components`)
- **Charts** : Plotly (gauges, heatmaps, radar, bar charts)
- **IA** : Google Gemini 2.0 Flash
- **Cache** : Pickle local + `@st.cache_data` (TTL 6h)
- **Style** : Space Grotesk + Space Mono (Google Fonts)

---

## 📝 License

MIT — libre d'utilisation personnelle.

---

*Made with ⚽ by odds\**
