"""
Backend support for the portfolio workspace: who a risk profile belongs to,
the growth/defensive sleeve on each valued holding, and projections of a
saved portfolio that never invent their inputs.
"""

QUIZ = [{"question_id": i, "answer": 3} for i in range(1, 11)]
OBJECTIVE = {
    "monthly_income": 4000, "monthly_expenses": 2500, "total_investable_assets": 50000,
    "investment_amount": 10000, "employment_type": "employed",
    "time_horizon_years": 15, "has_emergency_fund": "yes",
}


def _profile(client, name, user_id=None):
    body = {"name": name, "quiz_answers": QUIZ, "objective_inputs": OBJECTIVE, "uses_isa": True}
    if user_id is not None:
        body["user_id"] = user_id
    r = client.post("/api/risk-profile", json=body)
    assert r.status_code == 200, r.text
    return r.json()["user_id"]


def _quick(client, name, user_id=None):
    body = {"name": name, "loss_reaction": 3, "time_horizon_choice": 4, "financial_cushion": 3,
            "investment_amount": 10_000, "uses_isa": False}
    if user_id is not None:
        body["user_id"] = user_id
    r = client.post("/api/risk-profile/quick", json=body)
    assert r.status_code == 200, r.text
    return r.json()["user_id"]


class TestIdentity:
    def test_two_people_with_the_same_name_are_two_users(self, api):
        client, _ = api
        assert _profile(client, "Ada") != _profile(client, "Ada")

    def test_a_returning_browser_updates_its_own_user(self, api):
        client, _ = api
        first = _profile(client, "Ada")
        assert _profile(client, "Ada Lovelace", user_id=first) == first

    def test_an_unknown_id_starts_a_new_user(self, api):
        client, _ = api
        assert _profile(client, "Ada", user_id=987_654) != 987_654

    def test_the_quick_route_follows_the_same_rules(self, api):
        client, _ = api
        first = _quick(client, "Grace")
        assert _quick(client, "Grace") != first
        assert _quick(client, "Grace", user_id=first) == first


class TestPerformanceSleeves:
    def test_each_holding_says_which_side_it_is_on(self, api, create_portfolio):
        client, _ = api
        pid = create_portfolio(client)
        holdings = client.get(f"/api/performance/{pid}").json()["holdings"]
        assert {h["ticker"]: h["sleeve"] for h in holdings} == {"VUAG.L": "growth", "IGLT.L": "defensive"}


class TestSavedProjection:
    def test_projects_with_the_figures_stored_when_opened(self, api, create_portfolio):
        client, _ = api
        pid = create_portfolio(client)
        r = client.post("/api/monte-carlo", json={
            "portfolio_id": pid, "initial_investment": 10_000, "monthly_contribution": 100,
            "years": 5, "n_simulations": 200, "real_terms": True,
        })
        assert r.status_code == 200, r.text
        assert len(r.json()["percentile_50"]) == 6

    def test_refuses_rather_than_inventing_missing_figures(self, api, create_portfolio):
        from backend.db.database import SessionLocal
        from backend.db.models import Portfolio

        client, _ = api
        pid = create_portfolio(client)
        with SessionLocal() as db:
            db.get(Portfolio, pid).expected_return = None
            db.commit()
        r = client.post("/api/monte-carlo", json={
            "portfolio_id": pid, "initial_investment": 10_000, "monthly_contribution": 0,
            "years": 5, "n_simulations": 200,
        })
        assert r.status_code == 422
        assert "expected return" in r.json()["detail"]

    def test_an_unknown_portfolio_is_not_found(self, api):
        client, _ = api
        r = client.post("/api/monte-carlo", json={
            "portfolio_id": 987_654, "initial_investment": 10_000, "monthly_contribution": 0,
            "years": 5, "n_simulations": 200,
        })
        assert r.status_code == 404
