from __future__ import annotations

from collections import Counter
from datetime import datetime, time
from typing import List, Tuple

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cruise_hackathon_winner.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JSON_SORT_KEYS"] = False
db = SQLAlchemy(app)


# -------------------- MODELS -------------------- #
class Cruise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    departure_port = db.Column(db.String(120), nullable=False)
    arrival_port = db.Column(db.String(120), nullable=False)
    sailing_date = db.Column(db.String(20), nullable=False)
    duration_nights = db.Column(db.Integer, nullable=False)
    ship_name = db.Column(db.String(120), nullable=False)
    base_price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=False)
    highlights = db.Column(db.Text, nullable=False)

    cabins = db.relationship("Cabin", backref="cruise", lazy=True, cascade="all, delete-orphan")
    activities = db.relationship("Activity", backref="cruise", lazy=True, cascade="all, delete-orphan")
    bookings = db.relationship("Booking", backref="cruise", lazy=True, cascade="all, delete-orphan")


class Cabin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cruise_id = db.Column(db.Integer, db.ForeignKey("cruise.id"), nullable=False)
    cabin_number = db.Column(db.String(20), nullable=False)
    cabin_type = db.Column(db.String(50), nullable=False)
    deck = db.Column(db.String(50), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    features = db.Column(db.String(300), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    is_available = db.Column(db.Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("cruise_id", "cabin_number", name="uq_cruise_cabin"),)


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cruise_id = db.Column(db.Integer, db.ForeignKey("cruise.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # Restaurant, Show, Casino
    venue = db.Column(db.String(120), nullable=False)
    day_number = db.Column(db.Integer, nullable=False)
    slot_label = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False, default=0)
    description = db.Column(db.Text, nullable=False)
    tags = db.Column(db.String(250), nullable=False)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(25), unique=True, nullable=False)
    customer_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    guests_count = db.Column(db.Integer, nullable=False)
    preferences = db.Column(db.String(250), nullable=True)
    cruise_id = db.Column(db.Integer, db.ForeignKey("cruise.id"), nullable=False)
    cabin_id = db.Column(db.Integer, db.ForeignKey("cabin.id"), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default="Confirmed", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    cabin = db.relationship("Cabin")
    reserved_activities = db.relationship("BookingActivity", backref="booking", lazy=True, cascade="all, delete-orphan")


class BookingActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)

    activity = db.relationship("Activity")


# -------------------- HELPERS -------------------- #
def parse_time(value: str) -> time:
    hour, minute = map(int, value.split(":"))
    return time(hour, minute)


def overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    start_a, end_a = parse_time(a_start), parse_time(a_end)
    start_b, end_b = parse_time(b_start), parse_time(b_end)
    return start_a < end_b and start_b < end_a


def validate_schedule(activity_ids: List[int]) -> Tuple[bool, str | None]:
    if not activity_ids:
        return True, None

    items = Activity.query.filter(Activity.id.in_(activity_ids)).order_by(Activity.day_number, Activity.start_time).all()
    for i, current in enumerate(items):
        for other in items[i + 1:]:
            if current.day_number == other.day_number and overlaps(current.start_time, current.end_time, other.start_time, other.end_time):
                return False, f"Schedule conflict between '{current.title}' and '{other.title}' on Day {current.day_number}."
    return True, None


def activity_remaining_capacity(activity: Activity) -> int:
    reserved_count = BookingActivity.query.filter_by(activity_id=activity.id).count()
    return activity.capacity - reserved_count


def booking_reference() -> str:
    return "CRZ-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")


def ai_recommendation(cruise: Cruise, guests_count: int, preferences: str) -> dict:
    preferences = (preferences or "").lower()
    tokens = set(preferences.replace(",", " ").split())

    cabin_options = []
    for cabin in cruise.cabins:
        if not cabin.is_available or cabin.capacity < guests_count:
            continue
        score = 0
        if "luxury" in tokens and cabin.cabin_type in {"Suite", "Balcony"}:
            score += 6
        if "budget" in tokens and cabin.cabin_type == "Interior":
            score += 6
        if ("view" in tokens or "sea" in tokens or "romantic" in tokens) and cabin.cabin_type in {"Ocean View", "Balcony"}:
            score += 4
        if guests_count >= 3 and cabin.capacity >= guests_count:
            score += 2
        score += max(0, cabin.capacity - guests_count)
        cabin_options.append((score, cabin))

    cabin_options.sort(key=lambda x: (-x[0], x[1].price))
    best_cabin = cabin_options[0][1] if cabin_options else None

    activity_scores = []
    for activity in cruise.activities:
        remaining = activity_remaining_capacity(activity)
        if remaining < guests_count:
            continue

        score = 0
        tags = set(activity.tags.lower().split(","))
        if "family" in tokens and "family" in tags:
            score += 5
        if "romantic" in tokens and "romantic" in tags:
            score += 5
        if "food" in tokens and activity.category == "Restaurant":
            score += 5
        if "casino" in tokens and activity.category == "Casino":
            score += 5
        if "entertainment" in tokens and activity.category == "Show":
            score += 5
        if "luxury" in tokens and "luxury" in tags:
            score += 4
        if activity.price == 0:
            score += 1
        activity_scores.append((score, activity))

    activity_scores.sort(key=lambda x: (-x[0], x[1].day_number, x[1].start_time))
    selected = []
    for _, activity in activity_scores:
        valid = True
        for chosen in selected:
            if chosen.day_number == activity.day_number and overlaps(chosen.start_time, chosen.end_time, activity.start_time, activity.end_time):
                valid = False
                break
        if valid:
            selected.append(activity)
        if len(selected) == 4:
            break

    return {
        "recommended_cabin": best_cabin,
        "recommended_activities": selected,
        "summary": preferences or "premium cruise experience"
    }


def ai_concierge_answer(message: str) -> dict:
    text = (message or "").lower().strip()

    if not text:
        return {"title": "Ask me anything", "answer": "Try asking about cabins, restaurants, shows, casino, or the best cruise for families."}

    rules = [
        (("family", "kids", "children"), "Family Travel Advice",
         "Choose cruises with family lunch experiences, comedy shows, and higher-capacity cabins like Balcony or Suite."),
        (("romantic", "honeymoon", "couple"), "Romantic Experience Advice",
         "Pick Ocean View or Balcony cabins and reserve fine dining plus evening shows for a premium couple experience."),
        (("casino", "poker", "roulette", "blackjack"), "Casino Advice",
         "Casino sessions have limited capacity, so book early. Avoid overlapping them with dinner or evening show slots."),
        (("restaurant", "food", "dining", "dinner", "lunch", "breakfast"), "Dining Advice",
         "Reserve food experiences first because they are tied to fixed meal slots. The booking engine prevents overlapping reservations."),
        (("show", "entertainment", "music", "comedy"), "Entertainment Advice",
         "Choose a mix of prime-time and late-night shows to maximize your schedule without time clashes."),
        (("budget", "cheap", "affordable"), "Budget Advice",
         "Interior cabins with free shows and included breakfast give the best value."),
        (("luxury", "premium", "best"), "Luxury Advice",
         "For a luxury demo, show Suite or Balcony cabins, premium dinners, premium casino tables, and the analytics dashboard."),
    ]

    for keywords, title, answer in rules:
        if any(word in text for word in keywords):
            return {"title": title, "answer": answer}

    return {
        "title": "Cruise Concierge",
        "answer": "This platform helps guests choose cruises, cabins, restaurants, shows, and casino experiences with smart schedule validation and database-backed booking."
    }


# -------------------- PAGES -------------------- #
@app.route("/")
def home():
    cruises = Cruise.query.order_by(Cruise.sailing_date.asc()).all()
    stats = {
        "cruises": Cruise.query.count(),
        "cabins": Cabin.query.count(),
        "activities": Activity.query.count(),
        "bookings": Booking.query.count(),
    }
    return render_template("index.html", cruises=cruises, stats=stats)


@app.route("/cruises")
def cruises_page():
    departure_port = request.args.get("departure_port", "").strip()
    sailing_date = request.args.get("sailing_date", "").strip()

    query = Cruise.query
    if departure_port:
        query = query.filter(Cruise.departure_port.ilike(f"%{departure_port}%"))
    if sailing_date:
        query = query.filter(Cruise.sailing_date == sailing_date)

    cruises = query.order_by(Cruise.sailing_date.asc()).all()
    return render_template("cruises.html", cruises=cruises, departure_port=departure_port, sailing_date=sailing_date)


@app.route("/cruise/<int:cruise_id>")
def cruise_detail(cruise_id: int):
    cruise = Cruise.query.get_or_404(cruise_id)
    cabins = Cabin.query.filter_by(cruise_id=cruise.id, is_available=True).order_by(Cabin.price.asc()).all()
    activities = Activity.query.filter_by(cruise_id=cruise.id).order_by(Activity.day_number.asc(), Activity.start_time.asc()).all()

    grouped = {}
    for activity in activities:
        grouped.setdefault(activity.day_number, []).append(activity)

    return render_template("cruise_detail.html", cruise=cruise, cabins=cabins, grouped_activities=grouped)


@app.route("/booking/<int:cruise_id>")
def booking_page(cruise_id: int):
    cruise = Cruise.query.get_or_404(cruise_id)
    cabins = Cabin.query.filter_by(cruise_id=cruise.id, is_available=True).order_by(Cabin.price.asc()).all()
    activities = Activity.query.filter_by(cruise_id=cruise.id).order_by(Activity.day_number.asc(), Activity.start_time.asc()).all()
    return render_template("booking.html", cruise=cruise, cabins=cabins, activities=activities)


@app.route("/dashboard")
def dashboard():
    bookings = Booking.query.order_by(Booking.created_at.desc()).limit(12).all()
    total_revenue = round(sum(item.total_amount for item in Booking.query.all()), 2)

    cruise_counts = Counter(item.cruise.name for item in Booking.query.all())
    category_counts = Counter()
    for reservation in BookingActivity.query.all():
        category_counts[reservation.activity.category] += 1

    analytics = {
        "total_revenue": total_revenue,
        "total_bookings": Booking.query.count(),
        "available_cabins": Cabin.query.filter_by(is_available=True).count(),
        "occupied_cabins": Cabin.query.filter_by(is_available=False).count(),
        "popular_cruises": cruise_counts.most_common(5),
        "activity_mix": dict(category_counts),
    }
    return render_template("dashboard.html", bookings=bookings, analytics=analytics)


@app.route("/api-docs")
def api_docs():
    return render_template("api_docs.html")


# -------------------- APIs -------------------- #
@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "application": "Cruise Hackathon Winner"})


@app.route("/api/cruises")
def api_cruises():
    departure_port = request.args.get("departure_port", "").strip()
    sailing_date = request.args.get("sailing_date", "").strip()

    query = Cruise.query
    if departure_port:
        query = query.filter(Cruise.departure_port.ilike(f"%{departure_port}%"))
    if sailing_date:
        query = query.filter(Cruise.sailing_date == sailing_date)

    cruises = query.order_by(Cruise.sailing_date.asc()).all()
    return jsonify([
        {
            "id": cruise.id,
            "code": cruise.code,
            "name": cruise.name,
            "ship_name": cruise.ship_name,
            "departure_port": cruise.departure_port,
            "arrival_port": cruise.arrival_port,
            "sailing_date": cruise.sailing_date,
            "duration_nights": cruise.duration_nights,
            "base_price": cruise.base_price,
            "highlights": cruise.highlights.split("|"),
            "description": cruise.description,
        }
        for cruise in cruises
    ])


@app.route("/api/cruise/<int:cruise_id>")
def api_cruise(cruise_id: int):
    cruise = Cruise.query.get_or_404(cruise_id)
    return jsonify({
        "id": cruise.id,
        "name": cruise.name,
        "ship_name": cruise.ship_name,
        "departure_port": cruise.departure_port,
        "arrival_port": cruise.arrival_port,
        "sailing_date": cruise.sailing_date,
        "duration_nights": cruise.duration_nights,
        "cabins": [
            {
                "id": cabin.id,
                "cabin_number": cabin.cabin_number,
                "cabin_type": cabin.cabin_type,
                "deck": cabin.deck,
                "capacity": cabin.capacity,
                "price": cabin.price,
                "features": cabin.features,
                "is_available": cabin.is_available,
            }
            for cabin in cruise.cabins
        ],
        "activities": [
            {
                "id": activity.id,
                "title": activity.title,
                "category": activity.category,
                "venue": activity.venue,
                "day_number": activity.day_number,
                "slot_label": activity.slot_label,
                "start_time": activity.start_time,
                "end_time": activity.end_time,
                "capacity": activity.capacity,
                "remaining_capacity": activity_remaining_capacity(activity),
                "price": activity.price,
            }
            for activity in cruise.activities
        ]
    })


@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    payload = request.get_json(force=True)
    cruise = Cruise.query.get_or_404(payload.get("cruise_id"))
    guests_count = int(payload.get("guests_count", 2))
    preferences = payload.get("preferences", "")

    result = ai_recommendation(cruise, guests_count, preferences)

    return jsonify({
        "success": True,
        "summary": result["summary"],
        "recommended_cabin": None if result["recommended_cabin"] is None else {
            "id": result["recommended_cabin"].id,
            "cabin_number": result["recommended_cabin"].cabin_number,
            "cabin_type": result["recommended_cabin"].cabin_type,
            "capacity": result["recommended_cabin"].capacity,
            "price": result["recommended_cabin"].price,
        },
        "recommended_activities": [
            {
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "day_number": item.day_number,
                "time": f"{item.start_time} - {item.end_time}",
                "venue": item.venue,
            }
            for item in result["recommended_activities"]
        ]
    })


@app.route("/api/concierge", methods=["POST"])
def api_concierge():
    payload = request.get_json(force=True)
    result = ai_concierge_answer(payload.get("message", ""))
    return jsonify({"success": True, **result})


@app.route("/api/book", methods=["POST"])
def api_book():
    payload = request.get_json(force=True)

    required_fields = ["customer_name", "email", "phone", "guests_count", "cruise_id", "cabin_id", "activity_ids"]
    missing = [field for field in required_fields if field not in payload]
    if missing:
        return jsonify({"success": False, "message": f"Missing fields: {', '.join(missing)}"}), 400

    guests_count = int(payload["guests_count"])
    cruise = Cruise.query.get(payload["cruise_id"])
    cabin = Cabin.query.get(payload["cabin_id"])
    activity_ids = [int(item) for item in payload.get("activity_ids", [])]

    if not cruise:
        return jsonify({"success": False, "message": "Cruise not found."}), 404
    if not cabin or cabin.cruise_id != cruise.id:
        return jsonify({"success": False, "message": "Selected cabin is invalid for this cruise."}), 400
    if not cabin.is_available:
        return jsonify({"success": False, "message": "Selected cabin is already booked."}), 400
    if guests_count > cabin.capacity:
        return jsonify({"success": False, "message": "Guest count exceeds selected cabin capacity."}), 400

    ok, error_message = validate_schedule(activity_ids)
    if not ok:
        return jsonify({"success": False, "message": error_message}), 400

    activities = Activity.query.filter(Activity.id.in_(activity_ids)).all()
    for activity in activities:
        if activity.cruise_id != cruise.id:
            return jsonify({"success": False, "message": f"Activity '{activity.title}' does not belong to this cruise."}), 400
        if activity_remaining_capacity(activity) < guests_count:
            return jsonify({"success": False, "message": f"'{activity.title}' does not have enough remaining capacity."}), 400

    total_amount = cabin.price + (sum(item.price for item in activities) * guests_count)

    booking = Booking(
        reference=booking_reference(),
        customer_name=payload["customer_name"],
        email=payload["email"],
        phone=payload["phone"],
        guests_count=guests_count,
        preferences=payload.get("preferences", ""),
        cruise_id=cruise.id,
        cabin_id=cabin.id,
        total_amount=total_amount,
        status="Confirmed",
    )
    db.session.add(booking)
    db.session.flush()

    for activity in activities:
        for _ in range(guests_count):
            db.session.add(BookingActivity(booking_id=booking.id, activity_id=activity.id))

    cabin.is_available = False
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Booking confirmed successfully.",
        "reference": booking.reference,
        "total_amount": total_amount
    }), 201


@app.route("/api/bookings")
def api_bookings():
    items = Booking.query.order_by(Booking.created_at.desc()).all()
    return jsonify([
        {
            "reference": booking.reference,
            "customer_name": booking.customer_name,
            "email": booking.email,
            "phone": booking.phone,
            "guests_count": booking.guests_count,
            "cruise_name": booking.cruise.name,
            "cabin": f"{booking.cabin.cabin_number} ({booking.cabin.cabin_type})",
            "activities": [entry.activity.title for entry in booking.reserved_activities],
            "total_amount": booking.total_amount,
            "status": booking.status,
            "created_at": booking.created_at.isoformat(),
        }
        for booking in items
    ])


@app.route("/api/analytics")
def api_analytics():
    bookings = Booking.query.all()
    return jsonify({
        "total_revenue": round(sum(item.total_amount for item in bookings), 2),
        "total_bookings": len(bookings),
        "available_cabins": Cabin.query.filter_by(is_available=True).count(),
        "occupied_cabins": Cabin.query.filter_by(is_available=False).count(),
        "cruises": Cruise.query.count(),
        "activities": Activity.query.count(),
    })


@app.route("/setup")
def setup():
    db.drop_all()
    db.create_all()
    seed_database()
    return "Database reset and sample data loaded."


# -------------------- SEED DATA -------------------- #
def seed_database():
    if Cruise.query.first():
        return

    cruises = [
        Cruise(
            code="KOCHI-GOA-3N",
            name="Arabian Luxe Escape",
            departure_port="Kochi",
            arrival_port="Goa",
            sailing_date="2026-04-20",
            duration_nights=3,
            ship_name="MV Celestial Pearl",
            base_price=18999,
            image_url="https://images.unsplash.com/photo-1516496636080-14fb876e029d?q=80&w=1400&auto=format&fit=crop",
            description="A premium Arabian Sea cruise focused on sunset dining, live entertainment, elegant cabins, and a luxury casino floor.",
            highlights="Premium dining|Smart planner|Family friendly|Luxury evening experiences",
        ),
        Cruise(
            code="CHENNAI-MALE-5N",
            name="Maldives Sapphire Voyage",
            departure_port="Chennai",
            arrival_port="Malé",
            sailing_date="2026-05-02",
            duration_nights=5,
            ship_name="MV Sapphire Horizon",
            base_price=27999,
            image_url="https://images.unsplash.com/photo-1500375592092-40eb2168fd21?q=80&w=1400&auto=format&fit=crop",
            description="An immersive ocean journey with blue-water cabins, signature restaurants, curated shows, and premium guest experiences.",
            highlights="Ocean-view journeys|Chef specials|Themed shows|Concierge-style recommendations",
        ),
        Cruise(
            code="MUMBAI-LAKSHADWEEP-4N",
            name="Island Harmony Retreat",
            departure_port="Mumbai",
            arrival_port="Lakshadweep",
            sailing_date="2026-05-18",
            duration_nights=4,
            ship_name="MV Island Symphony",
            base_price=22999,
            image_url="https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1400&auto=format&fit=crop",
            description="A content-rich island cruise designed for families, first-time travelers, and users who want a complete digital booking experience.",
            highlights="Family itinerary|Responsive booking|High-capacity dining|Entertainment rich",
        ),
    ]
    db.session.add_all(cruises)
    db.session.flush()

    cabin_types = [
        ("Interior", "Deck 3", 2, 0, "Compact luxury, queen bed, digital concierge", "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?q=80&w=1000&auto=format&fit=crop"),
        ("Ocean View", "Deck 5", 2, 3500, "Window sea view, premium washroom, lounge chair", "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?q=80&w=1000&auto=format&fit=crop"),
        ("Balcony", "Deck 7", 3, 7000, "Private balcony, mini bar, sea-facing lounge", "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?q=80&w=1000&auto=format&fit=crop"),
        ("Suite", "Deck 9", 4, 14000, "Living area, butler service, premium deck access", "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?q=80&w=1000&auto=format&fit=crop"),
    ]

    for cruise in cruises:
        prefix = cruise.code.split("-")[0][:2]
        for idx, (cabin_type, deck, capacity, extra, features, image_url) in enumerate(cabin_types, start=1):
            for room in range(1, 4):
                db.session.add(Cabin(
                    cruise_id=cruise.id,
                    cabin_number=f"{prefix}{idx}{room:02d}",
                    cabin_type=cabin_type,
                    deck=deck,
                    capacity=capacity,
                    price=cruise.base_price + extra + (room * 500),
                    features=features,
                    image_url=image_url,
                    is_available=True,
                ))

    activity_seeds = [
        ("Azure Breakfast Buffet", "Restaurant", "Azure Dining Hall", 1, "Breakfast", "08:00", "09:00", 120, 0, "International breakfast buffet with live counters.", "family,food,breakfast"),
        ("Captain's Signature Lunch", "Restaurant", "Royal Bay", 1, "Lunch", "13:00", "14:00", 90, 499, "Chef-led lunch with premium service.", "food,premium,family"),
        ("Moonlight Fine Dinner", "Restaurant", "Skyline Grill", 1, "Dinner", "19:00", "20:00", 80, 999, "Romantic starlit dinner experience.", "romantic,food,luxury"),
        ("Ocean Illusion Show", "Show", "Pearl Theatre", 1, "Prime Show", "19:30", "20:30", 150, 0, "Visual illusion show with cinematic storytelling.", "family,entertainment"),
        ("Symphony of Waves", "Show", "Pearl Theatre", 1, "Late Show", "21:15", "22:15", 150, 299, "Music performance with immersive lighting.", "romantic,entertainment"),
        ("Blackjack Social", "Casino", "Golden Reef Casino", 1, "Casino Hour", "20:45", "21:45", 40, 799, "Guided blackjack tables for all levels.", "casino,nightlife"),
        ("Sunrise Wellness Breakfast", "Restaurant", "Azure Dining Hall", 2, "Breakfast", "08:00", "09:00", 110, 199, "Healthy breakfast with wellness menu.", "food,wellness"),
        ("Family Carnival Lunch", "Restaurant", "Lagoon Kitchen", 2, "Lunch", "13:00", "14:00", 100, 399, "Fun lunch experience for families.", "family,food"),
        ("Comedy Splash Live", "Show", "Coral Stage", 2, "Evening Show", "18:30", "19:30", 140, 0, "Interactive comedy experience.", "family,entertainment"),
        ("Taste of India Dinner", "Restaurant", "Spice Route", 2, "Dinner", "19:45", "20:45", 90, 599, "Regional Indian tasting menu.", "food,family"),
        ("Roulette Royale", "Casino", "Golden Reef Casino", 2, "Late Night", "21:00", "22:00", 35, 999, "Premium roulette with hosted table support.", "casino,luxury"),
        ("Starlight Gala", "Show", "Pearl Theatre", 3, "Prime Show", "19:00", "20:00", 160, 499, "Grand final-night show with dance and projection art.", "entertainment,luxury,romantic"),
        ("Poker Masters Table", "Casino", "Golden Reef Casino", 3, "Late Night", "21:00", "22:00", 24, 1299, "Advanced poker table for premium guests.", "casino,luxury"),
        ("Chef's Farewell Brunch", "Restaurant", "Royal Bay", 3, "Brunch", "10:30", "11:30", 100, 699, "Signature farewell brunch for final-day guests.", "food,premium,romantic"),
    ]

    for cruise in cruises:
        allowed_days = min(3, cruise.duration_nights)
        for seed in activity_seeds:
            if seed[3] <= allowed_days:
                db.session.add(Activity(
                    cruise_id=cruise.id,
                    title=seed[0],
                    category=seed[1],
                    venue=seed[2],
                    day_number=seed[3],
                    slot_label=seed[4],
                    start_time=seed[5],
                    end_time=seed[6],
                    capacity=seed[7],
                    price=seed[8],
                    description=seed[9],
                    tags=seed[10],
                ))

    db.session.commit()


with app.app_context():
    db.create_all()
    seed_database()


if __name__ == "__main__":
    app.run(debug=True)
