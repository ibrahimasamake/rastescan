from app import notify
from app.config import Settings
from tests.conftest import login, make_result, photo_bytes, submit


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def test_email_on_assign_and_resolve(officer_client, inspector, monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    ctx = officer_client.app.state.ctx
    object.__setattr__(ctx.settings, "smtp_host", "smtp.example.org")
    object.__setattr__(ctx.settings, "smtp_from", "roads@example.org")
    object.__setattr__(ctx.settings, "public_base_url", "https://roads.example.org")
    h = login(officer_client)
    code = submit(officer_client, contact_email="citizen@example.com")["code"]
    submit(officer_client, seed=9, lat=13.05)  # no email: nothing sent for this one
    officer_client.post(f"/api/v2/officer/reports/{code}/assign", json={"assignee": "Crew 1"}, headers=h)
    inspector.result = make_result(hazard="None", severity=1, urgency="LOW", box=(0, 0, 0, 0))
    officer_client.post(f"/api/v2/officer/reports/{code}/repair-photo",
                        files={"photo": ("a.jpg", photo_bytes(77), "image/jpeg")}, headers=h)
    subjects = [m["Subject"] for m in FakeSMTP.sent]
    assert subjects == [f"Your road report {code} has been assigned", f"Your road report {code} is resolved"]
    assert all(m["To"] == "citizen@example.com" for m in FakeSMTP.sent)
    assert f"https://roads.example.org/#/r/{code}" in FakeSMTP.sent[1].get_content()


def test_no_email_without_smtp(monkeypatch):
    called = []
    monkeypatch.setattr(notify.smtplib, "SMTP", lambda *a, **k: called.append(a))
    notify.send(Settings(smtp_host=""), "a@b.c", "assigned", code="RS-0001", hazard="Pothole", assignee="X")
    assert called == []
