import os
import random
import string
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, text
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL missing. Add it inside the .env file."
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    tracking_number = Column(String(30), unique=True, nullable=False, index=True)

    sender_name = Column(String(120), nullable=False)
    sender_phone = Column(String(30), nullable=False)
    sender_email = Column(String(150), nullable=True)

    receiver_name = Column(String(120), nullable=False)
    receiver_phone = Column(String(30), nullable=False)

    pickup_address = Column(String(500), nullable=False)
    delivery_address = Column(String(500), nullable=False)

    parcel_type = Column(String(80), nullable=False)
    weight = Column(Float, nullable=False, default=1.0)

    status = Column(String(60), nullable=False, default="Booked")

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Quick Courier")

BASE_DIR = Path(__file__).resolve().parent


def create_tracking_number():
    return "SC-" + "".join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=10,
        )
    )


def load_html():
    with open(BASE_DIR / "index.html", "r", encoding="utf-8") as file:
        return file.read()


@app.get("/quick-courier-logo.png", include_in_schema=False)
def quick_courier_logo():
    logo_path = BASE_DIR / "quick-courier-logo.png"

    if not logo_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Quick Courier logo file not found",
        )

    return FileResponse(
        path=logo_path,
        media_type="image/png",
    )


def render_page(
    page="home",
    message="",
    shipment=None,
    shipments=None,
):
    html = load_html()

    html = html.replace("{{PAGE}}", page)
    html = html.replace("{{MESSAGE}}", message or "")

    if shipment:
        shipment_html = f"""
        <div class="result-card">
            <div class="result-head">
                <div>
                    <small>Tracking Number</small>
                    <h2>{shipment.tracking_number}</h2>
                </div>
                <span class="status">{shipment.status}</span>
            </div>

            <div class="details">
                <div>
                    <small>Sender</small>
                    <strong>{shipment.sender_name}</strong>
                </div>

                <div>
                    <small>Receiver</small>
                    <strong>{shipment.receiver_name}</strong>
                </div>

                <div>
                    <small>Pickup</small>
                    <strong>{shipment.pickup_address}</strong>
                </div>

                <div>
                    <small>Delivery</small>
                    <strong>{shipment.delivery_address}</strong>
                </div>

                <div>
                    <small>Parcel</small>
                    <strong>{shipment.parcel_type} · {shipment.weight} kg</strong>
                </div>

                <div>
                    <small>Last Updated</small>
                    <strong>{shipment.updated_at}</strong>
                </div>
            </div>
        </div>
        """
    else:
        shipment_html = ""

    html = html.replace(
        "{{SHIPMENT_RESULT}}",
        shipment_html,
    )

    rows = ""

    if shipments:
        for s in shipments:
            rows += f"""
            <tr>
                <td><strong>{s.tracking_number}</strong></td>
                <td>{s.sender_name}<br><small>{s.sender_phone}</small></td>
                <td>{s.receiver_name}<br><small>{s.receiver_phone}</small></td>
                <td>{s.parcel_type}<br><small>{s.weight} kg</small></td>
                <td><span class="status">{s.status}</span></td>
                <td>
                    <form method="post" action="/admin/update/{s.id}" class="status-form">
                        <select name="status">
                            <option {"selected" if s.status == "Booked" else ""}>Booked</option>
                            <option {"selected" if s.status == "Picked Up" else ""}>Picked Up</option>
                            <option {"selected" if s.status == "In Transit" else ""}>In Transit</option>
                            <option {"selected" if s.status == "Out for Delivery" else ""}>Out for Delivery</option>
                            <option {"selected" if s.status == "Delivered" else ""}>Delivered</option>
                            <option {"selected" if s.status == "Cancelled" else ""}>Cancelled</option>
                        </select>
                        <button class="btn small" type="submit">Save</button>
                    </form>
                </td>
            </tr>
            """

    html = html.replace(
        "{{ADMIN_ROWS}}",
        rows or '<tr><td colspan="6" class="empty">No shipments yet.</td></tr>',
    )

    return html


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(
        render_page(page="home")
    )


@app.get("/book", response_class=HTMLResponse)
def book_page():
    return HTMLResponse(
        render_page(page="book")
    )


@app.post("/book")
def create_shipment(
    sender_name: str = Form(...),
    sender_phone: str = Form(...),
    sender_email: str = Form(""),
    receiver_name: str = Form(...),
    receiver_phone: str = Form(...),
    pickup_address: str = Form(...),
    delivery_address: str = Form(...),
    parcel_type: str = Form(...),
    weight: float = Form(...),
):
    db = SessionLocal()

    try:
        tracking_number = create_tracking_number()

        while (
            db.query(Shipment)
            .filter(
                Shipment.tracking_number
                == tracking_number
            )
            .first()
        ):
            tracking_number = create_tracking_number()

        shipment = Shipment(
            tracking_number=tracking_number,
            sender_name=sender_name.strip(),
            sender_phone=sender_phone.strip(),
            sender_email=sender_email.strip() or None,
            receiver_name=receiver_name.strip(),
            receiver_phone=receiver_phone.strip(),
            pickup_address=pickup_address.strip(),
            delivery_address=delivery_address.strip(),
            parcel_type=parcel_type.strip(),
            weight=weight,
            status="Booked",
        )

        db.add(shipment)
        db.commit()
        db.refresh(shipment)

        return RedirectResponse(
            url=f"/track?tracking_number={shipment.tracking_number}",
            status_code=303,
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


@app.get("/track", response_class=HTMLResponse)
def track_page(
    tracking_number: str = "",
):
    shipment = None
    message = ""

    if tracking_number.strip():
        db = SessionLocal()

        try:
            shipment = (
                db.query(Shipment)
                .filter(
                    Shipment.tracking_number
                    == tracking_number.strip().upper()
                )
                .first()
            )

            if not shipment:
                message = "Tracking number not found."

        finally:
            db.close()

    return HTMLResponse(
        render_page(
            page="track",
            message=message,
            shipment=shipment,
        )
    )


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    db = SessionLocal()

    try:
        shipments = (
            db.query(Shipment)
            .order_by(
                Shipment.created_at.desc()
            )
            .all()
        )

        return HTMLResponse(
            render_page(
                page="admin",
                shipments=shipments,
            )
        )

    finally:
        db.close()


@app.post("/admin/update/{shipment_id}")
def update_status(
    shipment_id: int,
    status: str = Form(...),
):
    allowed = [
        "Booked",
        "Picked Up",
        "In Transit",
        "Out for Delivery",
        "Delivered",
        "Cancelled",
    ]

    if status not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Invalid status",
        )

    db = SessionLocal()

    try:
        shipment = (
            db.query(Shipment)
            .filter(
                Shipment.id == shipment_id
            )
            .first()
        )

        if not shipment:
            raise HTTPException(
                status_code=404,
                detail="Shipment not found",
            )

        shipment.status = status
        shipment.updated_at = datetime.utcnow()

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    return RedirectResponse(
        url="/admin",
        status_code=303,
    )


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "PostgreSQL connected",
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {exc}",
        )