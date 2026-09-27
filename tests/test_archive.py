"""
Archiving takes a portfolio off its owner's list without deleting anything:
it still opens, with its ledger and history, and restoring puts it back.
"""


def _listed(client, archived=False):
    r = client.get("/api/portfolios/user/1" + ("/archived" if archived else ""))
    assert r.status_code == 200, r.text
    return {p["portfolio_id"]: p for p in r.json()}


class TestArchive:
    def test_a_new_portfolio_is_not_archived(self, api, create_portfolio):
        client, _ = api
        pid = create_portfolio(client)
        detail = client.get(f"/api/portfolio/{pid}").json()
        assert detail["archived"] is False and detail["archived_at"] is None
        assert _listed(client)[pid]["archived_at"] is None

    def test_archiving_moves_it_to_the_archived_list(self, api, create_portfolio):
        client, _ = api
        pid = create_portfolio(client)
        r = client.post(f"/api/portfolio/{pid}/archive")
        assert r.status_code == 200, r.text
        assert r.json()["portfolio_id"] == pid and r.json()["archived_at"]
        assert pid not in _listed(client)
        assert _listed(client, archived=True)[pid]["archived_at"] == r.json()["archived_at"]

    def test_an_archived_portfolio_still_opens_with_its_record(self, api, create_portfolio):
        client, _ = api
        pid = create_portfolio(client)
        client.post(f"/api/portfolio/{pid}/archive")
        detail = client.get(f"/api/portfolio/{pid}").json()
        assert detail["archived"] is True and detail["archived_at"]
        assert client.get(f"/api/performance/{pid}").status_code == 200
        assert client.get(f"/api/transactions/{pid}").json()

    def test_restoring_puts_it_back(self, api, create_portfolio):
        client, _ = api
        pid = create_portfolio(client)
        client.post(f"/api/portfolio/{pid}/archive")
        r = client.post(f"/api/portfolio/{pid}/restore")
        assert r.status_code == 200, r.text
        assert r.json() == {"portfolio_id": pid, "archived_at": None}
        assert pid in _listed(client) and pid not in _listed(client, archived=True)
        assert client.get(f"/api/portfolio/{pid}").json()["archived"] is False

    def test_both_are_safe_to_repeat_and_keep_the_first_date(self, api, create_portfolio):
        client, _ = api
        pid = create_portfolio(client)
        first = client.post(f"/api/portfolio/{pid}/archive").json()["archived_at"]
        again = client.post(f"/api/portfolio/{pid}/archive")
        assert again.status_code == 200 and again.json()["archived_at"] == first
        client.post(f"/api/portfolio/{pid}/restore")
        assert client.post(f"/api/portfolio/{pid}/restore").status_code == 200

    def test_an_unknown_portfolio_is_not_found(self, api):
        client, _ = api
        assert client.post("/api/portfolio/987654/archive").status_code == 404
        assert client.post("/api/portfolio/987654/restore").status_code == 404

    def test_an_archived_portfolio_still_takes_money(self, api, create_portfolio):
        client, _ = api
        pid = create_portfolio(client)
        client.post(f"/api/portfolio/{pid}/archive")
        r = client.post(f"/api/portfolio/{pid}/contribute", json={"amount_gbp": 500})
        assert r.status_code == 200, r.text

    def test_a_row_with_no_active_flag_counts_as_on_the_list_and_can_be_archived(self, api, create_portfolio):
        from backend.db.database import SessionLocal
        from backend.db.models import Portfolio

        client, _ = api
        pid = create_portfolio(client)
        with SessionLocal() as db:
            db.query(Portfolio).filter(Portfolio.id == pid).update({"is_active": None})
            db.commit()
        assert pid in _listed(client)
        assert client.get(f"/api/portfolio/{pid}").json()["archived"] is False

        assert client.post(f"/api/portfolio/{pid}/archive").json()["archived_at"]
        assert pid not in _listed(client) and pid in _listed(client, archived=True)
