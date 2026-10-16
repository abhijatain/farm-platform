"""WhatsApp farmer menu: bounded Meta list rows over owner-checked farm data.

All selectable IDs are generated from canonical PostgreSQL entities and every
subsequent lookup is reauthorized against the linked Firebase user. Interactive
list row limits are ten, so large farms are paginated. No LLM or SQL from chat.
"""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.field import Field
from app.models.season import Season
from app.models.user import User

PAGESIZE = 9
MAX_PAGE = 1000
COMMAND = re.compile(
    r"^(?:(farm|s-farm|f-farm|season|field):([0-9a-fA-F-]{36})|browse:(farms|seasons|fields):(\d{1,4}))$"
)

TRANSLATIONS = {
    "en": {
        "hello": "Farm Platform — choose what you want to see.",
        "browse": "Open menu", "farms": "My farms", "seasons": "My seasons",
        "fields": "My fields", "go_back": "Back to menu",
        "choose_farm": "Choose a farm to see its {kind}.",
        "no_farms": "No farms on this account. Add one in the Farm Platform app.",
        "no_seasons": "No seasons saved for this farm.",
        "no_fields": "No fields saved for this farm.",
        "farm_menu": "Farm: {name}\nChoose what to view.",
        "selected_season": "Season: {name}\nFarm: {farm}\nStatus: {status}\nStarted: {date}\nReply MENU to go back.",
        "selected_field": "Field: {name}\nFarm: {farm}\nReply MENU to go back.",
        "more": "Next page", "intro": "Reply MENU or 1 Farms, 2 Seasons, 3 Fields.",
        "choose": "Select an option", "none": "No entries yet.",
    },
    "hi": {
        "hello": "फार्म प्लेटफ़ॉर्म — जानकारी चुनें।",
        "browse": "मेनू खोलें", "farms": "मेरे फार्म", "seasons": "मेरे सीज़न",
        "fields": "मेरे खेत", "go_back": "मुख्य मेनू",
        "choose_farm": "{kind} देखने के लिए फार्म चुनें।",
        "no_farms": "इस खाते में फार्म नहीं हैं। ऐप में फार्म जोड़ें।",
        "no_seasons": "इस फार्म में कोई सीज़न नहीं है।",
        "no_fields": "इस फार्म में कोई खेत नहीं है।",
        "farm_menu": "फार्म: {name}\nक्या देखना है चुनें।",
        "selected_season": "सीज़न: {name}\nफार्म: {farm}\nस्थिति: {status}\nशुरुआत: {date}\nMENU लिखें।",
        "selected_field": "खेत: {name}\nफार्म: {farm}\nMENU लिखें।",
        "more": "अगला पेज", "intro": "MENU या 1 फार्म, 2 सीज़न, 3 खेत लिखें।",
        "choose": "चुनें", "none": "अभी कोई जानकारी नहीं।",
    },
    "pa": {
        "hello": "ਫਾਰਮ ਪਲੇਟਫਾਰਮ — ਜਾਣਕਾਰੀ ਚੁਣੋ।",
        "browse": "ਮੀਨੂ ਖੋਲ੍ਹੋ", "farms": "ਮੇਰੇ ਫਾਰਮ", "seasons": "ਮੇਰੇ ਸੀਜ਼ਨ",
        "fields": "ਮੇਰੇ ਖੇਤ", "go_back": "ਮੁੱਖ ਮੀਨੂ",
        "choose_farm": "{kind} ਵੇਖਣ ਲਈ ਫਾਰਮ ਚੁਣੋ।",
        "no_farms": "ਇਸ ਖਾਤੇ ਵਿੱਚ ਫਾਰਮ ਨਹੀਂ ਹਨ। ਐਪ ਵਿੱਚ ਫਾਰਮ ਜੋੜੋ।",
        "no_seasons": "ਇਸ ਫਾਰਮ ਵਿੱਚ ਕੋਈ ਸੀਜ਼ਨ ਨਹੀਂ ਹੈ।",
        "no_fields": "ਇਸ ਫਾਰਮ ਵਿੱਚ ਕੋਈ ਖੇਤ ਨਹੀਂ ਹੈ।",
        "farm_menu": "ਫਾਰਮ: {name}\nਕੀ ਵੇਖਣਾ ਹੈ ਚੁਣੋ।",
        "selected_season": "ਸੀਜ਼ਨ: {name}\nਫਾਰਮ: {farm}\nਹਾਲਤ: {status}\nਸ਼ੁਰੂ: {date}\nMENU ਲਿਖੋ।",
        "selected_field": "ਖੇਤ: {name}\nਫਾਰਮ: {farm}\nMENU ਲਿਖੋ।",
        "more": "ਅਗਲਾ ਪੰਨਾ", "intro": "MENU ਜਾਂ 1 ਫਾਰਮ, 2 ਸੀਜ਼ਨ, 3 ਖੇਤ ਲਿਖੋ।",
        "choose": "ਚੁਣੋ", "none": "ਅਜੇ ਕੋਈ ਜਾਣਕਾਰੀ ਨਹੀਂ।",
    },
}


def t(lang: str, key: str, **kwargs: str) -> str:
    """Use a controlled translation and fallback to English."""
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"])[key].format(**kwargs)


def text_message(text: str) -> dict:
    return {"type": "text", "text": {"body": text[:4096]}}


def list_message(text: str, title: str, rows: list[tuple[str, str]]) -> dict:
    """Use the official Meta interactive list schema and per-field limits."""
    if not 1 <= len(rows) <= 10:
        raise ValueError("WhatsApp interactive lists require 1–10 rows")
    return {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": text[:1024]},
            "action": {
                "button": title[:20],
                "sections": [{
                    "title": "Farm Platform",
                    "rows": [
                        {"id": rid[:200], "title": label[:24]}
                        for rid, label in rows
                    ],
                }],
            },
        },
    }


def main_menu(lang: str) -> dict:
    return list_message(t(lang, "hello"), t(lang, "browse"), [
        ("menu:farms", t(lang, "farms")),
        ("menu:seasons", t(lang, "seasons")),
        ("menu:fields", t(lang, "fields")),
    ])


def _parse_uuid(raw: str) -> UUID | None:
    try:
        return UUID(raw)
    except ValueError:
        return None


def _farm(db: Session, user: User, farm_id: UUID) -> Farm | None:
    return db.scalar(select(Farm).where(
        Farm.id == farm_id, Farm.owner_user_id == user.id,
    ))


def _farms_list(db: Session, user: User, kind: str, page: int, lang: str) -> dict:
    """Browse only farms belonging to the authenticated link owner."""
    if page > MAX_PAGE:
        return main_menu(lang)
    farms = db.scalars(
        select(Farm).where(Farm.owner_user_id == user.id)
        .order_by(Farm.name, Farm.id).offset(page * PAGESIZE).limit(PAGESIZE + 1)
    ).all()
    if not farms:
        return text_message(t(lang, "no_farms") if page == 0 else t(lang, "intro"))
    prefix = {"farms": "farm", "seasons": "s-farm", "fields": "f-farm"}[kind]
    rows = [(f"{prefix}:{farm.id}", farm.name) for farm in farms[:PAGESIZE]]
    if len(farms) > PAGESIZE:
        rows.append((f"browse:{kind}:{page + 1}", t(lang, "more")))
    return list_message(
        t(lang, "choose_farm", kind=t(lang, kind)),
        t(lang, "choose"), rows,
    )


def _children(db: Session, user: User, kind: str, farm_id: UUID, lang: str) -> dict:
    """A UUID from a WhatsApp row does not authorize data: check the farm."""
    farm = _farm(db, user, farm_id)
    if farm is None:
        return main_menu(lang)
    if kind == "seasons":
        data = db.scalars(select(Season).where(Season.farm_id == farm.id)
                          .order_by(Season.started_on.desc(), Season.id).limit(10)).all()
        prefix = "season"
    else:
        data = db.scalars(select(Field).where(Field.farm_id == farm.id)
                          .order_by(Field.name, Field.id).limit(10)).all()
        prefix = "field"
    if not data:
        return text_message(t(lang, "no_" + kind) + "\n" + t(lang, "intro"))
    # Paginate a single farm's entries with a stable typed command.
    # A page cursor is a number, never an untrusted SQL fragment.
    return list_message(t(lang, "choose_farm", kind=t(lang, kind)), t(lang, "choose"),
                        [(f"{prefix}:{entry.id}", entry.name) for entry in data[:9]]
                        + ([(f"children:{kind}:{farm.id}:1", t(lang, "more"))]
                           if len(data) > 9 else []))


def _children_page(db: Session, user: User, kind: str, farm_id: UUID, page: int, lang: str) -> dict:
    farm = _farm(db, user, farm_id)
    if farm is None or page > MAX_PAGE:
        return main_menu(lang)
    model = Season if kind == "seasons" else Field
    stmt = select(model).where(model.farm_id == farm.id)
    stmt = (stmt.order_by(Season.started_on.desc(), Season.id) if kind == "seasons"
            else stmt.order_by(Field.name, Field.id))
    entries = db.scalars(stmt.offset(page * PAGESIZE).limit(PAGESIZE + 1)).all()
    if not entries:
        return text_message(t(lang, "intro"))
    prefix = "season" if kind == "seasons" else "field"
    rows = [(f"{prefix}:{row.id}", row.name) for row in entries[:PAGESIZE]]
    if len(entries) > PAGESIZE:
        rows.append((f"children:{kind}:{farm.id}:{page + 1}", t(lang, "more")))
    return list_message(t(lang, "choose_farm", kind=t(lang, kind)), t(lang, "choose"), rows)


def menu_reply(db: Session, user: User, language: str, command: str | None) -> dict:
    """Resolve only explicit menu commands with owner-filtered database queries."""
    cmd = (command or "").strip()
    simple = cmd.casefold()
    if simple in {"", "menu", "help", "hi", "hello", "0"}:
        return main_menu(language)
    if simple in {"1", "farms", "menu:farms"}:
        return _farms_list(db, user, "farms", 0, language)
    if simple in {"2", "seasons", "menu:seasons"}:
        return _farms_list(db, user, "seasons", 0, language)
    if simple in {"3", "fields", "menu:fields"}:
        return _farms_list(db, user, "fields", 0, language)

    child = re.fullmatch(r"children:(seasons|fields):([0-9a-fA-F-]{36}):(\d{1,4})", cmd)
    if child:
        fid = _parse_uuid(child.group(2))
        return _children_page(db, user, child.group(1), fid, int(child.group(3)), language) if fid else main_menu(language)

    match = COMMAND.fullmatch(cmd)
    if match is None:
        return main_menu(language)
    item, raw_id, browse_kind, raw_page = match.groups()
    if browse_kind:
        return _farms_list(db, user, browse_kind, int(raw_page), language)
    target_id = _parse_uuid(raw_id)
    if target_id is None:
        return main_menu(language)
    if item == "farm":
        farm = _farm(db, user, target_id)
        if farm is None:
            return main_menu(language)
        return list_message(t(language, "farm_menu", name=farm.name), t(language, "choose"), [
            (f"s-farm:{farm.id}", t(language, "seasons")),
            (f"f-farm:{farm.id}", t(language, "fields")),
            ("menu:farms", t(language, "go_back")),
        ])
    if item in {"s-farm", "f-farm"}:
        return _children(db, user, "seasons" if item == "s-farm" else "fields", target_id, language)
    if item == "season":
        season = db.scalar(
            select(Season).join(Farm, Season.farm_id == Farm.id).where(
                Season.id == target_id, Farm.owner_user_id == user.id,
            )
        )
        if season is None:
            return main_menu(language)
        farm = _farm(db, user, season.farm_id)
        return text_message(t(language, "selected_season",
                              name=season.name, farm=farm.name,
                              status=season.status, date=season.started_on.isoformat()))
    field = db.scalar(
        select(Field).join(Farm, Field.farm_id == Farm.id).where(
            Field.id == target_id, Farm.owner_user_id == user.id,
        )
    )
    if field is None:
        return main_menu(language)
    farm = _farm(db, user, field.farm_id)
    return text_message(t(language, "selected_field", name=field.name, farm=farm.name))
