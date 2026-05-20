from datetime import date, datetime, timedelta
def local_now():
    return datetime.now()
import json
import re

import requests
from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, Text, or_
from sqlalchemy.orm import Mapped, mapped_column

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instruments.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Instrument(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    device_name: Mapped[str] = mapped_column(String(255), nullable=False)
    test_types: Mapped[str] = mapped_column(String(255), default="")
    serial_number: Mapped[str] = mapped_column(String(255), default="")
    last_verification: Mapped[date | None]
    next_verification: Mapped[date | None]
    certificate_number: Mapped[str] = mapped_column(String(255), default="")
    passport_info: Mapped[str] = mapped_column(String(255), default="")
    note: Mapped[str] = mapped_column(String(1000), default="")
    in_verification: Mapped[bool] = mapped_column(default=False)
    fgis_data: Mapped[str] = mapped_column(Text, default="")
    fgis_sync_date: Mapped[datetime | None]


class ActionLog(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)

    action: Mapped[str] = mapped_column(String(50))

    device_name: Mapped[str] = mapped_column(String(255))

    description: Mapped[str] = mapped_column(String(1000))

    username: Mapped[str] = mapped_column(String(255), default='system')

    ip_address: Mapped[str] = mapped_column(String(255), default='unknown')

    created_at: Mapped[datetime] = mapped_column(default=local_now)


def parse_date(raw_date: str | None) -> date | None:
    if not raw_date:
        return None
    return datetime.strptime(raw_date, "%Y-%m-%d").date()


def add_log(action: str, device_name: str, description: str):

    ip = request.headers.get(
        'X-Forwarded-For',
        request.remote_addr
    )

    username = request.headers.get(
        'X-User',
        'operator'
    )

    log = ActionLog(
        action=action,
        device_name=device_name,
        description=description,
        username=username,
        ip_address=ip
    )

    db.session.add(log)
    db.session.commit()



def extract_fgis_id(certificate_number: str):

    if not certificate_number:
        return None

    match = re.search(r'/(\d+)$', certificate_number)

    if not match:
        return None

    return match.group(1)


def load_fgis_data(certificate_number: str):

    fgis_id = extract_fgis_id(certificate_number)

    if not fgis_id:
        return None

    url = f"https://fgis.gost.ru/fundmetrology/eapi/vri/{fgis_id}"

    try:

        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }
        )

        if response.status_code != 200:
            return None

        return response.json()

    except Exception as e:

        print(e)

        return None


@app.route("/")
def index():
    search = request.args.get("search", "").strip()

    query = Instrument.query
    if search:

        add_log(
            "SEARCH",
            "SYSTEM",
            f"Поиск: {search}"
        )

        like_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Instrument.device_name.ilike(like_pattern),
                Instrument.test_types.ilike(like_pattern),
                Instrument.serial_number.ilike(like_pattern),
                Instrument.certificate_number.ilike(like_pattern),
                Instrument.passport_info.ilike(like_pattern),
                Instrument.note.ilike(like_pattern),
            )
        )

    instruments = query.order_by(
        Instrument.next_verification.asc().nullslast(),
        Instrument.device_name.asc(),
    ).all()

    return render_template(
        "index.html",
        instruments=instruments,
        search=search,
        today=date.today(),
        month_ahead=date.today() + timedelta(days=30),
    )


@app.route("/add", methods=["POST"])
def add_instrument():
    instrument = Instrument(
        device_name=request.form.get("device_name", "").strip(),
        test_types=request.form.get("test_types", "").strip(),
        serial_number=request.form.get("serial_number", "").strip(),
        last_verification=parse_date(request.form.get("last_verification")),
        next_verification=parse_date(request.form.get("next_verification")),
        certificate_number=request.form.get("certificate_number", "").strip(),
        passport_info=request.form.get("passport_info", "").strip(),
        note=request.form.get("note", "").strip(),
        in_verification=request.form.get("in_verification") == "on",
    )
    db.session.add(instrument)
    db.session.commit()
    add_log(
        "ADD",
        instrument.device_name,
        f"Добавлено средство измерений № {instrument.serial_number}"
    )
    return redirect(url_for("index"))


@app.route("/edit/<int:instrument_id>", methods=["GET", "POST"])
def edit_instrument(instrument_id: int):
    instrument = Instrument.query.get_or_404(instrument_id)

    if request.method == "POST":
        changes = []

        fields = {

            "Наименование": (
                instrument.device_name,
                request.form.get("device_name", "").strip()
            ),

            "Испытания": (
                instrument.test_types,
                request.form.get("test_types", "").strip()
            ),

            "Заводской номер": (
                instrument.serial_number,
                request.form.get("serial_number", "").strip()
            ),

            "Свидетельство": (
                instrument.certificate_number,
                request.form.get("certificate_number", "").strip()
            ),

            "Паспорт": (
                instrument.passport_info,
                request.form.get("passport_info", "").strip()
            ),

            "Примечание": (
                instrument.note,
                request.form.get("note", "").strip()
            ),
        }

        for field_name, values in fields.items():

            old_value, new_value = values

            if str(old_value) != str(new_value):

                changes.append(
                    f"{field_name}: "
                    f"'{old_value}' → '{new_value}'"
                )

        instrument.device_name = request.form.get("device_name", "").strip()
        instrument.test_types = request.form.get("test_types", "").strip()
        instrument.serial_number = request.form.get("serial_number", "").strip()
        instrument.last_verification = parse_date(request.form.get("last_verification"))
        instrument.next_verification = parse_date(request.form.get("next_verification"))
        instrument.certificate_number = request.form.get("certificate_number", "").strip()
        instrument.passport_info = request.form.get("passport_info", "").strip()
        instrument.note = request.form.get("note", "").strip()
        instrument.in_verification = request.form.get("in_verification") == "on"
        db.session.commit()

        if changes:
            add_log(
                "EDIT",
                instrument.device_name,
                " | ".join(changes)
            )
        return redirect(url_for("index"))

    return render_template("edit.html", instrument=instrument)


@app.route('/instrument/<int:instrument_id>')
def instrument_card(instrument_id):

    instrument = Instrument.query.get_or_404(instrument_id)

    today = date.today()

    add_log(
        "VIEW",
        instrument.device_name,
        f"Открыта карточка прибора ID={instrument.id}"
    )

    use_cached = False

    if instrument.fgis_sync_date:

        delta = datetime.now() - instrument.fgis_sync_date

        if delta.total_seconds() < 86400:

            use_cached = True

    fgis_data = None

    if use_cached and instrument.fgis_data:
        try:
            fgis_data = json.loads(instrument.fgis_data)
        except Exception:
            fgis_data = None

    if fgis_data is None:
        fgis_data = load_fgis_data(
            instrument.certificate_number
        )
        if fgis_data:
            instrument.fgis_data = json.dumps(fgis_data, ensure_ascii=False)
            instrument.fgis_sync_date = datetime.now()
            db.session.commit()
            add_log(
                "FGIS_SYNC",
                instrument.device_name,
                "Синхронизация с ФГИС"
            )

    fgis = None

    if fgis_data:

        result = fgis_data.get("result", {})

        mi = result.get("miInfo", {}).get("singleMI", {})

        vri = result.get("vriInfo", {})

        means = result.get("means", {})
        mieta = means.get("mieta", []) if isinstance(means, dict) else []
        etalons = []
        for item in mieta:
            if not isinstance(item, dict):
                continue
            etalons.append(
                {
                    "title": item.get("title") or item.get("name") or item.get("type"),
                    "modification": item.get("modification"),
                    "number": item.get("number") or item.get("manufactureNum"),
                    "reg_number": item.get("regNumber") or item.get("registryNumber"),
                }
            )

        fgis = {

            "type_number": mi.get("mitypeNumber"),

            "type_title": mi.get("mitypeTitle"),

            "modification": mi.get("modification"),

            "manufacture_year": mi.get("manufactureYear"),

            "verification_date": vri.get("vrfDate"),

            "valid_date": vri.get("validDate"),

            "organization": vri.get("organization"),

            "method": vri.get("docTitle"),

            "cert_num": (
                vri
                .get("applicable", {})
                .get("certNum")
            ),
            "etalons": etalons,
        }

    if fgis:
        try:
            instrument.last_verification = datetime.strptime(
                fgis["verification_date"],
                "%d.%m.%Y"
            ).date()

            instrument.next_verification = datetime.strptime(
                fgis["valid_date"],
                "%d.%m.%Y"
            ).date()

            db.session.commit()
        except Exception:
            pass

    return render_template(
        "instrument_card.html",
        instrument=instrument,
        today=today,
        fgis=fgis
    )


@app.route("/delete/<int:instrument_id>", methods=["POST"])
def delete_instrument(instrument_id: int):
    instrument = Instrument.query.get_or_404(instrument_id)
    add_log(
        "DELETE",
        instrument.device_name,
        f"Удалено СИ № {instrument.serial_number}"
    )
    db.session.delete(instrument)
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/logs")
def logs():
    logs = ActionLog.query.order_by(
        ActionLog.created_at.desc()
    ).all()

    return render_template(
        "logs.html",
        logs=logs
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)
