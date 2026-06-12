"""
API regression suite for nanotech.icu.

Endpoints: GET /  · GET /script.js  · GET /api/auth/me
           POST /api/auth/{login,register,logout}
           POST /api/{contact,chat,chat-consent}

Each test asserts: status code · Content-Type · JSON shape · error body.
"""

import re
import pytest

pytestmark = pytest.mark.api


# Static / page-level checks

class TestStaticEndpoints:
    """Sanity checks for the public HTML and JS bundle the site depends on."""

    def test_landing_page_returns_html(self, api_client):
        # Metric: status 200 + HTML content-type + non-empty body + latency < 5s
        response = api_client.get('/')
        assert response.status_code == 200
        assert 'text/html' in response.headers.get('content-type', '')
        assert '<title>' in response.text.lower()
        assert response.elapsed.total_seconds() < 5.0

    def test_script_bundle_is_served(self, api_client):
        # Metric: script.js is reachable, served as JS, and contains the API contract
        # the frontend relies on (so QA catches accidental bundle reverts).
        response = api_client.get('/script.js')
        assert response.status_code == 200
        assert 'javascript' in response.headers.get('content-type', '')
        assert "/api/chat" in response.text
        assert "/api/contact" in response.text


# Auth API

class TestAuthApi:
    """Unauthenticated and validation paths for the /api/auth/* surface."""

    def test_me_without_token_returns_401(self, api_client):
        # Metric: status 401 + JSON error contract `{ "error": "not_authenticated" }`
        response = api_client.get('/api/auth/me')
        assert response.status_code == 401
        body = response.json()
        assert body == {'error': 'not_authenticated'}

    def test_login_with_invalid_credentials(self, api_client):
        # Metric: status 401 + frontend-facing error message present
        response = api_client.post(
            '/api/auth/login',
            json={'email': 'nobody@example.com', 'password': 'wrong-password'},
        )
        assert response.status_code == 401
        body = response.json()
        assert 'error' in body
        assert re.search(r'invalid', body['error'], re.IGNORECASE)

    def test_register_validation_error(self, api_client):
        # Metric: status 400 + descriptive error mentioning required fields
        response = api_client.post('/api/auth/register', json={})
        assert response.status_code == 400
        body = response.json()
        assert 'error' in body
        assert re.search(r'name.*email.*password', body['error'], re.IGNORECASE)

    def test_logout_is_idempotent(self, api_client):
        # Metric: logout returns 200 and `{ "ok": true }` even without an active session
        response = api_client.post('/api/auth/logout', json={})
        assert response.status_code == 200
        assert response.json() == {'ok': True}


# Contact form API

class TestContactApi:
    """Server-side validation for the public contact form endpoint."""

    def test_contact_requires_payload(self, api_client):
        # Metric: status 400 + structured JSON error
        response = api_client.post('/api/contact', json={})
        assert response.status_code == 400
        body = response.json()
        assert 'error' in body
        assert re.search(r'required', body['error'], re.IGNORECASE)

    def test_contact_partial_payload_still_rejected(self, api_client):
        # Metric: missing-message scenario must be blocked (frontend never sends it)
        response = api_client.post(
            '/api/contact',
            json={'name': 'QA Bot', 'email': 'qa@example.com'},
        )
        assert response.status_code == 400
        assert 'error' in response.json()


# Chat API + consent

class TestChatApi:
    """Validation contract for the LLM chat surface (no live LLM calls here)."""

    def test_chat_requires_message(self, api_client):
        # Metric: status 400 + machine-readable error code `missing_message`
        response = api_client.post('/api/chat', json={})
        assert response.status_code == 400
        assert response.json() == {'error': 'missing_message'}

    def test_chat_consent_accepts_payload(self, api_client):
        # Metric: status 200 + `{ "ok": true }` for a well-formed consent record.
        # The site fires this when a user accepts the chat disclaimer.
        response = api_client.post(
            '/api/chat-consent',
            json={
                'accepted_at': '2026-01-01T00:00:00Z',
                'consent_version': 'qa-test',
                'source': 'pytest',
                'path': '/',
                'locale': 'en-US',
            },
        )
        assert response.status_code == 200
        assert response.json() == {'ok': True}
