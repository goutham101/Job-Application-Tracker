import re

from rapidfuzz import fuzz, process

REJECTION_KEYWORDS = (
    "unfortunately",
    "not moving forward",
    "not be moving forward",
    "decided not to proceed",
    "other candidates",
)
INTERVIEW_KEYWORDS = ("schedule", "interview")
CONFIRMATION_KEYWORDS = (
    "thank you for applying",
    "received your application",
    "application received",
)

_NOISE_WORDS = re.compile(
    r"\b(via|careers|recruiting|talent|hiring|greenhouse|lever|workday)\b", re.IGNORECASE
)
_DISPLAY_NAME = re.compile(r'^"?([^"<]+?)"?\s*<')
_DOMAIN = re.compile(r"@([\w.-]+)")


def classify_email(sender: str, subject: str) -> str:
    text = subject.lower()
    if any(k in text for k in REJECTION_KEYWORDS):
        return "rejection"
    if any(k in text for k in INTERVIEW_KEYWORDS):
        return "interview"
    if any(k in text for k in CONFIRMATION_KEYWORDS):
        return "confirmation"
    return "unclassified"


def guess_company_name(sender: str, subject: str) -> str:
    """Best-effort company name guess. Deliberately simple — ambiguous
    cases are left for the human review queue, not resolved here."""
    display_match = _DISPLAY_NAME.match(sender)
    if display_match:
        name = _NOISE_WORDS.sub("", display_match.group(1))
        name = re.sub(r"\s+", " ", name).strip()
        if name:
            return name
    domain_match = _DOMAIN.search(sender)
    if domain_match:
        return domain_match.group(1).split(".")[0]
    return subject


def match_company(
    sender: str, subject: str, companies: list[dict], threshold: int = 85
) -> int | None:
    if not companies:
        return None
    candidate = guess_company_name(sender, subject)
    names = [c["name"] for c in companies]
    result = process.extractOne(candidate, names, scorer=fuzz.WRatio)
    if result and result[1] >= threshold:
        matched_name = result[0]
        return next(c["id"] for c in companies if c["name"] == matched_name)
    return None
