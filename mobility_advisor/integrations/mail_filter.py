import json
import re

from .. import paths

SENDER_BLACKLIST = [
    "reisebegleitung@deutschebahn.com",
    "outlook_",
]

SUBJECT_BLACKLIST = [
    "angenommen:",
    "abgelehnt:",
    "abgesagt:",
]

SENDER_WHITELIST = [
    "deutschebahn.com",
    "bahn.de",
    "flixbus.com",
    "flixbus.de",
    "expediamail.com",
    "lastminute.de",
    "lufthansa.com",
    "eurowings.com",
    "easyjet.com",
    "enterprise.de",
    "miles-mobility.com",
    "sixt.de",
    "hertz.de",
]

SUBJECT_KEYWORDS = [
    "buchungsbestätigung",
    "buchungsbestaetigung",
    "booking confirmation",
    "auftragsbestätigung",
    "ihre buchung",
    "reisebestätigung",
    "flugbuchung",
    "mietwagen",
    "fahrtbestätigung",
    "rechnung",
    "kündigung",
    "gekündigt",
    "abonnement",
    "mietvertrag",
    "stellenangebot",
    "besichtigungstermin",
    "aktiviert",
]

# Life-event signals that must win categorization even when the sender happens to be a
# booking domain (e.g. a BahnCard non-renewal notice from bahn.de is not a trip booking) —
# checked before CATEGORY_MAP in _get_category so a subscription/relocation/job signal is
# never swallowed by the domain-based booking categories below.
LIFE_EVENT_KEYWORDS = [
    "mietvertrag",
    "kündigung",
    "gekündigt",
    "wird nicht verlängert",
    "nicht automatisch verlängert",
    "stellenangebot",
    "jobangebot",
    "besichtigungstermin",
    "ist aktiviert",
]

BODY_KEYWORDS = [
    "buchungsbestätigung",
    "von: noreply@deutschebahn.com",
    "von: buchungsbestaetigung@bahn.de",
    "von: noreply@booking.flixbus.com",
    "von: noreply@flixbus.com",
    "von: expedia@",
    "von: buchungsbestaetigung@lastminute.de",
]

CATEGORY_MAP = {
    "bahn.de": "booking_rail",
    "deutschebahn.com": "booking_rail",
    "flixbus": "booking_bus",
    "lufthansa.com": "booking_flight",
    "eurowings.com": "booking_flight",
    "easyjet.com": "booking_flight",
    "expediamail.com": "booking_flight",
    "lastminute.de": "booking_flight",
    "enterprise.de": "booking_car",
    "sixt.de": "booking_car",
    "hertz.de": "booking_car",
    "miles-mobility.com": "booking_car",
    "mietvertrag": "life_event",
}


def clean_body(html: str) -> str:
    from bs4 import BeautifulSoup
    text = BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _is_blacklisted(sender_email: str, subject: str) -> bool:
    sender_lower = sender_email.lower()
    subject_lower = subject.lower()
    if any(bl in sender_lower for bl in SENDER_BLACKLIST):
        return True
    if any(bl in subject_lower for bl in SUBJECT_BLACKLIST):
        return True
    return False


def _is_whitelisted(sender_email: str) -> bool:
    return any(wl in sender_email.lower() for wl in SENDER_WHITELIST)


def _matches_subject(subject: str) -> bool:
    return any(kw in subject.lower() for kw in SUBJECT_KEYWORDS)


def _matches_body(body: str) -> bool:
    return any(kw in body.lower() for kw in BODY_KEYWORDS)


def _get_category(sender_email: str, subject: str, body: str) -> str:
    combined = sender_email.lower() + " " + subject.lower() + " " + body.lower()
    if any(kw in combined for kw in LIFE_EVENT_KEYWORDS):
        return "life_event"
    for key, category in CATEGORY_MAP.items():
        if key in combined:
            return category
    return "other_relevant"


def filter_emails(emails: list[dict]) -> list[dict]:
    relevant = []
    for mail in emails:
        sender = mail.get("sender_email", "")
        subject = mail.get("subject", "")
        body = mail.get("body_text", "")

        if _is_blacklisted(sender, subject):
            continue

        if _is_whitelisted(sender) or _matches_subject(subject) or _matches_body(body):
            mail["category"] = _get_category(sender, subject, body)
            relevant.append(mail)

    return relevant


if __name__ == "__main__":
    data_path = paths.DATA_DIR / "mail_raw.json"
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    emails = raw.get("emails", [])

    relevant = filter_emails(emails)

    print(f"{len(relevant)} von {len(emails)} Mails relevant:\n")
    for mail in relevant:
        print(f"[{mail['category']}] {mail['subject'][:60]}")
