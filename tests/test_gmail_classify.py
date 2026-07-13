from app.gmail_classify import classify_email, guess_company_name, match_company


def test_classify_rejection():
    assert classify_email(
        "no-reply@greenhouse.io", "Update on your application: we've decided not to proceed"
    ) == "rejection"


def test_classify_interview():
    assert classify_email(
        "recruiting@lever.co", "Let's schedule your interview"
    ) == "interview"


def test_classify_confirmation():
    assert classify_email(
        "no-reply@myworkday.com", "Thank you for applying to Acme Corp"
    ) == "confirmation"


def test_classify_unclassified():
    assert classify_email("friend@gmail.com", "lunch tomorrow?") == "unclassified"


def test_guess_company_name_from_display_name():
    assert guess_company_name('"Stripe via Greenhouse" <no-reply@greenhouse.io>', "") == "Stripe"


def test_guess_company_name_falls_back_to_domain():
    assert guess_company_name("jobs@stripe.com", "") == "stripe"


def test_match_company_above_threshold():
    companies = [{"id": 1, "name": "Stripe"}, {"id": 2, "name": "Ramp"}]
    sender = '"Stripe via Greenhouse" <no-reply@greenhouse.io>'
    assert match_company(sender, "", companies) == 1


def test_match_company_no_match_returns_none():
    companies = [{"id": 1, "name": "Stripe"}]
    assert match_company("jobs@totallydifferentco.com", "", companies) is None


def test_match_company_empty_list_returns_none():
    assert match_company("jobs@stripe.com", "", []) is None
