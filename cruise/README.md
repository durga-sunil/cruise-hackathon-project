# CruiseVerse AI - Hackathon Winner Edition

This version is designed specifically to score high against the assignment requirements.

## What it covers
- Mobile-friendly responsive web application
- Content-rich pages with multiple cruises, cabins, restaurants, shows, and casino events
- REST APIs for cruises, recommendations, concierge assistant, analytics, and bookings
- Database backend using SQLite + SQLAlchemy
- Smart slot validation to prevent overlapping events
- AI-style recommendation engine
- AI concierge assistant for demo impact
- Dashboard for live execution and presentation

## Pages
- `/` Home
- `/cruises` Cruise listing and filtering
- `/cruise/<id>` Cruise detail page
- `/booking/<id>` Smart booking flow
- `/dashboard` Analytics dashboard
- `/api-docs` API overview for judges

## APIs
- `GET /api/health`
- `GET /api/cruises`
- `GET /api/cruise/<id>`
- `POST /api/recommend`
- `POST /api/concierge`
- `POST /api/book`
- `GET /api/bookings`
- `GET /api/analytics`

## Run
```bash
pip install -r requirements.txt
python app.py
```

Open:
- `http://127.0.0.1:5000/`

Reset sample data:
- `http://127.0.0.1:5000/setup`

## Best live demo order
1. Show landing page and explain the concept
2. Search cruises by port/date
3. Open one cruise and show cabins + activities
4. Open booking page
5. Use recommendation engine
6. Ask the AI concierge a question
7. Intentionally choose conflicting activities to show validation
8. Complete a booking
9. Open dashboard and show analytics

## Future upgrades for finals
- login/signup
- payment gateway
- QR boarding pass
- email notifications
- real LLM integration
- admin CRUD panel
- downloadable ticket PDF
