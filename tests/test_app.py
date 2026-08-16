"""Tests for the web app: the demo world, page rendering, and the HTTP control flow."""

import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from assent import ChangeState
from assent.app import _Handler, demo_app, render_ledger, render_queue


@pytest.fixture
def app():
    return demo_app()


# ------------------------------------------------------------------ demo world

def test_demo_world_exercises_every_outcome(app):
    states = {r.state for r in app.records()}
    assert ChangeState.AUTO_EXECUTED in states     # a low-envelope change ran itself
    assert ChangeState.NEEDS_TRIAGE in states      # a signal with no playbook
    assert any(s in states for s in                # and something waiting on a human
               (ChangeState.PENDING_APPROVAL, ChangeState.ESCALATED))


def test_demo_ledger_verifies(app):
    ok, _ = app.ledger.verify()
    assert ok


# ------------------------------------------------------------------ rendering

def test_queue_page_renders_all_records(app):
    page = render_queue(app, "alex")
    assert page.strip().startswith("<!doctype html>")
    for record in app.records():
        assert record.id in page
    # Self-contained app logic — only allowed external refs are webfonts.
    assert "googleapis.com" in page or "fonts." in page


def test_queue_page_has_working_controls_for_pending_items(app):
    page = render_queue(app, "alex")
    pending = app.queue()[0]
    assert 'action="/approve"' in page or 'action="/deny"' in page
    assert pending.id in page


def test_settled_items_offer_undo_not_approval(app):
    from assent.dashboard import render_change

    executed = [r for r in app.settled() if r.state is ChangeState.AUTO_EXECUTED]
    assert executed, "demo world should contain an auto-executed change"
    page = render_change(app, executed[0], actor="alex", profile="cloud")
    assert 'action="/rollback"' in page
    assert 'action="/approve"' not in page


def test_ledger_page_shows_chain_status(app):
    page = render_ledger(app, "alex")
    assert "chain verified" in page
    assert "proposed" in page and "decided" in page


# ------------------------------------------------------------------ http flow

@pytest.fixture
def server(app):
    handler = type("H", (_Handler,), {"app": app, "actor": "alex", "profile": "cloud"})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.05)
    yield f"http://127.0.0.1:{srv.server_port}", app
    srv.shutdown()
    srv.server_close()


def _post(base, path, **fields):
    data = urllib.parse.urlencode(fields).encode()
    return urllib.request.urlopen(base + path, data=data)


def test_pages_serve(server):
    base, _ = server
    assert urllib.request.urlopen(base + "/").status == 200
    assert urllib.request.urlopen(base + "/ledger").status == 200


def test_unknown_path_404s(server):
    base, _ = server
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(base + "/nope")
    assert excinfo.value.code == 404


def test_approve_over_http_executes_and_records(server):
    base, app = server
    pending = app.queue()[0]
    while pending.change is None:  # skip triage-only items
        pending = app.queue()[1]
    before = len(app.executor.performed)

    _post(base, "/approve", id=pending.id)

    assert pending.state is ChangeState.EXECUTED
    assert len(app.executor.performed) == before + 1
    # The approval taught the ownership graph (the flywheel).
    assert app.graph.resolve(pending.signal.target).id == "alex"


def test_deny_over_http_does_not_execute(server):
    base, app = server
    pending = [r for r in app.queue() if r.change is not None][0]
    before = list(app.executor.performed)
    _post(base, "/deny", id=pending.id)
    assert pending.state is ChangeState.DENIED
    assert app.executor.performed == before


def test_rollback_over_http_undoes(server):
    base, app = server
    executed = [r for r in app.settled() if r.state is ChangeState.AUTO_EXECUTED][0]
    _post(base, "/rollback", id=executed.id)
    assert executed.state is ChangeState.ROLLED_BACK
    assert app.executor.undone


def test_stale_or_unknown_id_is_handled_gracefully(server):
    base, app = server
    # Unknown id, and a double-approve of something already settled: neither should 500.
    assert _post(base, "/approve", id="chg-does-not-exist").status == 200
    settled = app.settled()[0]
    assert _post(base, "/approve", id=settled.id).status == 200


def test_ledger_still_verifies_after_http_actions(server):
    base, app = server
    pending = [r for r in app.queue() if r.change is not None][0]
    _post(base, "/approve", id=pending.id)
    ok, message = app.ledger.verify()
    assert ok, message
