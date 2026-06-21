# SPX 0DTE Academy Dashboard v1.0

Training-only dashboard for learning SPX-style 0DTE chart reading, candle recognition, fast decision-making, and 15-minute simulated trade management.

## What it does

- Replays hard SPX-style 1-minute sessions
- Lets you enter CALL-bias or PUT-bias simulated trades
- Forces a 15-minute training clock
- Scores entry and exit quality
- Critiques VWAP/EMA alignment, value location, candle confirmation, chasing, MFE/MAE, and move capture
- Includes Candle Coach and Academy Lessons tabs
- Saves a local browser journal of scored reps
- Uses synthetic hard-mode data by default, so no API key is required

## Training tabs

1. **Training Arena** — chart, replay controls, entry/exit buttons, checklist, open trade panel.
2. **Candle Coach** — explains the current candle and gives Long/Short/Wait quality.
3. **Trade Critique** — shows grade, score, mistake tags, P/L, MFE/MAE, and exit capture.
4. **Performance Journal** — tracks scored reps in browser localStorage.
5. **Academy Lessons** — built-in lessons for A+ entries, candle reading, and exits.

## Run locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

Backend runs on `http://localhost:5000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on the Vite URL shown in the terminal, usually `http://localhost:5173`.

## Optional live/proxy data

By default, the simulator uses synthetic SPX-style hard-mode candles. You can optionally set:

```bash
POLYGON_API_KEY=your_key
TRAINER_PROXY_TICKER=SPY
TRAINER_SYMBOL=SPX
```

The app will still remain a training simulator only. It does not send orders.

## Render deployment notes

The included `render.yaml` keeps the existing structure. For production deployment, build the frontend and serve it with your preferred static hosting or extend the Flask backend to serve the built frontend.

## Safety

This is not a trading bot and not financial advice. It is a training tool to build discipline around reading candles, waiting for confirmation, and managing simulated SPX-style 0DTE trades.
