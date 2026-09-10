import base64
import collections
import hashlib
import hmac
import io
import json
import logging
import os
import re
import smtplib
import sqlite3
import threading
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile
from email.mime.text import MIMEText
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from .free_model_pool import FreeModelPool
except ImportError:  # Direct production entrypoint: python chat_server.py
    from free_model_pool import FreeModelPool


def _extract_docx_text(data_url: str, max_chars: int = 8000) -> str:
    """Extract plain text from a base64-encoded .docx data URL."""
    try:
        raw = data_url.split(",", 1)[1] if "," in data_url else data_url
        buf = io.BytesIO(base64.b64decode(raw))
        with zipfile.ZipFile(buf) as z:
            if "word/document.xml" not in z.namelist():
                return ""
            xml_bytes = z.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        chunks = []
        for elem in root.iter(f"{{{ns}}}t"):
            if elem.text:
                chunks.append(elem.text)
        text = " ".join(chunks).strip()
        return text[:max_chars]
    except Exception:
        return ""


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()

DB_PATH = Path(__file__).resolve().parent / "users.db"


def _init_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at REAL NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at REAL NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        sender TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at REAL NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS notes (
        user_id TEXT PRIMARY KEY,
        text TEXT NOT NULL DEFAULT '',
        updated_at REAL NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_audit_log (
        id TEXT PRIMARY KEY,
        ts REAL NOT NULL,
        ip_hash TEXT NOT NULL,
        agent TEXT,
        model TEXT,
        tier TEXT,
        reason TEXT,
        query_len INTEGER,
        reply_len INTEGER,
        moderation TEXT,
        blocked INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_consent_log (
        id TEXT PRIMARY KEY,
        ts REAL NOT NULL,
        ip_hash TEXT NOT NULL,
        user_id TEXT,
        consent_version TEXT,
        source TEXT,
        path TEXT,
        locale TEXT,
        user_agent TEXT,
        accepted_at_client TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS contact_messages (
        id TEXT PRIMARY KEY,
        ts REAL NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        company TEXT,
        service TEXT,
        message TEXT NOT NULL,
        email_sent INTEGER DEFAULT 0,
        email_error TEXT,
        recipients TEXT
    )""")
    conn.commit()
    conn.close()


_init_db()

_audit_logger = logging.getLogger("chat_audit")
_audit_logger.setLevel(logging.INFO)
_audit_fh = logging.FileHandler(Path(__file__).resolve().parent / "chat_audit.log")
_audit_fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
_audit_logger.addHandler(_audit_fh)

MAINTENANCE_FLAG = Path(__file__).resolve().parent / "maintenance.flag"
MAINTENANCE_KEY = os.environ.get("MAINTENANCE_KEY", "nanotech-maint-2026")

_LOGIN_ATTEMPTS = {}
_LOGIN_LOCK = threading.Lock()
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SEC = 600


def _login_rate_limited(ip):
    now = time.time()
    with _LOGIN_LOCK:
        attempts = [t for t in _LOGIN_ATTEMPTS.get(ip, []) if now - t < _LOGIN_WINDOW_SEC]
        _LOGIN_ATTEMPTS[ip] = attempts
        return len(attempts) >= _LOGIN_MAX_ATTEMPTS


def _record_login_failure(ip):
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.setdefault(ip, []).append(time.time())


def _clear_login_failures(ip):
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.pop(ip, None)


def _is_maintenance():
    return MAINTENANCE_FLAG.exists()


def _toggle_maintenance(on):
    if on:
        MAINTENANCE_FLAG.write_text("1")
    else:
        MAINTENANCE_FLAG.unlink(missing_ok=True)


MAINTENANCE_HTML = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>NanoTech Hub — Maintenance</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f0f2ff;font-family:Inter,system-ui,sans-serif;color:#1e1b4b}
.card{text-align:center;padding:60px 40px;max-width:520px}
h1{font-size:2rem;margin-bottom:12px}
p{font-size:1.1rem;color:#6366f1;margin-bottom:8px}
.sub{font-size:0.9rem;color:#64748b}
</style></head>
<body><div class="card">
<h1>We'll be right back</h1>
<p>NanoTech Hub is currently undergoing scheduled maintenance.</p>
<p class="sub">Please check back shortly. Contact info@nanotech.icu if urgent.</p>
</div></body></html>"""

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 10
_rate_buckets = collections.defaultdict(list)
_rate_lock = threading.Lock()


def _hash_ip(ip):
    return hashlib.sha256((ip or "unknown").encode()).hexdigest()[:16]


def _check_rate_limit(ip_hash):
    now = time.time()
    with _rate_lock:
        bucket = _rate_buckets[ip_hash]
        bucket[:] = [t for t in bucket if now - t < RATE_LIMIT_WINDOW]
        if len(bucket) >= RATE_LIMIT_MAX:
            return False
        bucket.append(now)
        return True


_BLOCKED_PATTERNS = re.compile(
    r"(?:"
    r"how\s+to\s+(?:make|build|create|synthesize|cook)\s+(?:a\s+)?(?:bomb|explosive|weapon|meth|drug|poison|ricin|anthrax|sarin)"
    r"|how\s+to\s+(?:hack|break\s+into|crack|exploit|ddos|dos\s+attack)"
    r"|how\s+to\s+(?:kill|murder|assassinate|harm|hurt|torture|kidnap|rape)"
    r"|how\s+to\s+(?:steal|rob|burglar|shoplift|fraud|scam|launder)"
    r"|(?:child|minor|underage|kid)\s*(?:porn|sex|nude|naked|exploit)"
    r"|(?:porn|hentai|xxx|nsfw|sex\s+story|erotic\s+fiction|sexual\s+fantasy)"
    r"|(?:suicide|self[\s-]?harm)\s+(?:method|how|way|instruction)"
    r"|(?:как\s+(?:сделать|создать|приготовить|собрать)\s+(?:бомб|взрывчатк|оружи|наркотик|яд))"
    r"|(?:как\s+(?:убить|навредить|отравить|взломать|ограбить|украсть))"
    r"|(?:детск\w*\s*порн|педофил)"
    r"|(?:порно|секс\s*(?:истори|рассказ)|эротик)"
    r"|(?:суицид|самоубийств)\s*(?:способ|метод|как)"
    r")",
    re.IGNORECASE
)

_BLOCKED_OUTPUT_PATTERNS = re.compile(
    r"(?:"
    r"(?:step\s*\d+[:\.]?\s*(?:obtain|acquire|mix|combine|ignite|detonate))"
    r"|(?:ingredients?\s*(?:needed|required)\s*:.*(?:nitrate|sulfur|phosphor|acetone|peroxide))"
    r"|(?:here(?:'s| is) how (?:to|you can) (?:hack|kill|make a bomb|synthesize))"
    r"|(?:вот\s+как\s+(?:сделать|убить|взломать|отравить))"
    r")",
    re.IGNORECASE
)

MODERATION_REFUSAL = (
    "I'm sorry, but I can't help with that request. "
    "This AI assistant is designed for business and technology questions only. "
    "If you need help, please contact info@nanotech.icu."
)


def _moderate_input(message):
    if _BLOCKED_PATTERNS.search(message):
        return False, "blocked_input"
    return True, "ok"


def _moderate_output(reply):
    if _BLOCKED_OUTPUT_PATTERNS.search(reply):
        return False, "blocked_output"
    return True, "ok"


def _audit_log(ip_hash, agent, model, tier, reason, query_len, reply_len, moderation, blocked):
    try:
        log_id = uuid.uuid4().hex[:12]
        conn = _db()
        conn.execute(
            "INSERT INTO chat_audit_log (id, ts, ip_hash, agent, model, tier, reason, query_len, reply_len, moderation, blocked) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (log_id, time.time(), ip_hash, agent, model, tier, reason, query_len, reply_len, moderation, 1 if blocked else 0)
        )
        conn.commit()
        conn.close()
        _audit_logger.info(
            "ip=%s agent=%s model=%s tier=%s reason=%s qlen=%d rlen=%d mod=%s blocked=%s",
            ip_hash, agent, model or "-", tier or "-", reason or "-",
            query_len, reply_len, moderation, blocked
        )
    except Exception:
        pass


def _log_chat_consent(ip_hash, user_id, consent_version, source, path, locale, user_agent, accepted_at_client):
    try:
        log_id = uuid.uuid4().hex[:12]
        conn = _db()
        conn.execute(
            "INSERT INTO chat_consent_log (id, ts, ip_hash, user_id, consent_version, source, path, locale, user_agent, accepted_at_client) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                log_id,
                time.time(),
                ip_hash,
                user_id,
                consent_version,
                source,
                path,
                locale,
                user_agent,
                accepted_at_client,
            ),
        )
        conn.commit()
        conn.close()
        _audit_logger.info(
            "consent ip=%s user=%s version=%s source=%s path=%s locale=%s ua=%s accepted_at=%s",
            ip_hash,
            user_id or "-",
            consent_version or "-",
            source or "-",
            path or "-",
            locale or "-",
            (user_agent or "-")[:120],
            accepted_at_client or "-",
        )
    except Exception:
        pass


def _hash_pw(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
    return "scrypt:" + salt.hex() + ":" + dk.hex()


def _verify_pw(password: str, stored: str) -> bool:
    if stored.startswith("scrypt:"):
        try:
            _, salt_hex, dk_hex = stored.split(":", 2)
            dk = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=16384, r=8, p=1, dklen=32)
            return hmac.compare_digest(dk.hex(), dk_hex)
        except Exception:
            return False
    # legacy plain SHA-256 (no salt) — accept on login, rehash handled by caller
    return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), stored)


def _db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _get_user_by_token(token):
    if not token:
        return None
    conn = _db()
    row = conn.execute(
        "SELECT u.* FROM users u JOIN sessions s ON u.id = s.user_id WHERE s.token = ?",
        (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _admin_login_emails():
    raw = (
        os.environ.get("ADMIN_LOGIN_EMAILS")
        or os.environ.get("ADMIN_LOGIN_EMAIL")
        or os.environ.get("ADMIN_EMAIL")
        or "alexpask@gmail.com"
    )
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _is_admin_email(email):
    return (email or "").strip().lower() in _admin_login_emails()


def _public_user_payload(user):
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "is_admin": _is_admin_email(user.get("email")),
    }


def _smtp_config():
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    admin_email = os.environ.get("ADMIN_EMAIL", "alex.pavsky@gmail.com").strip()
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    try:
        port = int(os.environ.get("SMTP_PORT", "465").strip() or "465")
    except ValueError:
        port = 465
    # Gmail app passwords are often pasted with spaces; strip them for auth.
    password = os.environ.get("SMTP_PASS", "").strip().replace(" ", "")
    from_email = os.environ.get("SMTP_FROM", smtp_user or admin_email).strip()
    return {
        "host": host,
        "port": port,
        "user": smtp_user,
        "password": password,
        "admin": admin_email,
        "from": from_email,
        "ready": bool(host and smtp_user and password and from_email and admin_email),
    }


def _contact_recipients():
    """Where contact-form notifications should be delivered.

    Prefer CONTACT_TO (comma-separated). Fall back to ADMIN_EMAIL.
    Does not force info@nanotech.icu — that mailbox is separate from the form.
    """
    raw = (
        os.environ.get("CONTACT_TO")
        or os.environ.get("ADMIN_EMAIL")
        or "alex.pavsky@gmail.com"
    ).strip()
    recipients = []
    seen = set()
    for part in raw.split(","):
        email = part.strip().lower()
        if email and "@" in email and email not in seen:
            seen.add(email)
            recipients.append(email)
    return recipients or ["alex.pavsky@gmail.com"]


def _send_email(subject, body, to_email, reply_to=""):
    cfg = _smtp_config()
    if not cfg["ready"]:
        return False, "smtp_not_configured"
    recipients = [e.strip() for e in str(to_email).split(",") if e.strip()]
    if not recipients:
        return False, "no_recipients"
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = cfg["from"]
        msg["To"] = ", ".join(recipients)
        if reply_to:
            msg["Reply-To"] = reply_to

        if cfg["port"] == 465:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15) as smtp:
                smtp.login(cfg["user"], cfg["password"])
                smtp.send_message(msg, from_addr=cfg["from"], to_addrs=recipients)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as smtp:
                smtp.starttls()
                smtp.login(cfg["user"], cfg["password"])
                smtp.send_message(msg, from_addr=cfg["from"], to_addrs=recipients)
        return True, None
    except Exception as exc:
        print(f"Email send error: {exc}")
        return False, str(exc)


def _send_async(target, *args):
    threading.Thread(target=target, args=args, daemon=True).start()


def _send_admin_notification(source, user_name, user_email, message_text, extra_lines=None):
    cfg = _smtp_config()
    recipients = _contact_recipients()
    details = "\n".join(extra_lines or [])
    if details:
        details = details + "\n\n"
    body = (
        f"New message from {source}:\n\n"
        f"From: {user_name} <{user_email}>\n\n"
        f"{details}"
        f"Message:\n{message_text}\n\n"
        f"Delivered to: {', '.join(recipients)}\n"
        f"Reply directly or use the admin inbox ({cfg['admin']})."
    )
    return _send_email(
        subject=f"NanoTech {source}: {user_name}",
        body=body,
        to_email=",".join(recipients),
        reply_to=user_email,
    )


def _save_contact_message(name, email, company, service, message, email_sent, email_error, recipients):
    msg_id = uuid.uuid4().hex
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO contact_messages "
        "(id, ts, name, email, company, service, message, email_sent, email_error, recipients) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            msg_id,
            time.time(),
            name,
            email,
            company,
            service,
            message,
            1 if email_sent else 0,
            (email_error or "")[:500],
            ",".join(recipients or []),
        ),
    )
    conn.commit()
    conn.close()
    # Also append a plain-text ledger so submissions survive even if email is down.
    try:
        log_path = Path(__file__).resolve().parent / "contact-submissions.jsonl"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "id": msg_id,
                "ts": time.time(),
                "name": name,
                "email": email,
                "company": company,
                "service": service,
                "message": message,
                "email_sent": bool(email_sent),
                "email_error": email_error,
                "recipients": recipients,
            }, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"contact log write error: {exc}")
    return msg_id


def _send_user_reply_email(user_name, user_email, message_text):
    cfg = _smtp_config()
    first_name = (user_name or "there").split(" ")[0]
    body = (
        f"Hi {first_name},\n\n"
        f"{message_text}\n\n"
        f"Best regards,\n"
        f"Alex Pavsky\n"
        f"{cfg['admin']}"
    )
    return _send_email(
        subject="Reply from Alex Pavsky",
        body=body,
        to_email=user_email,
        reply_to=cfg["admin"],
    )


def _admin_conversations():
    conn = _db()
    rows = conn.execute(
        """
        SELECT
            u.id,
            u.name,
            u.email,
            u.created_at,
            COUNT(m.id) AS message_count,
            MAX(m.created_at) AS last_message_at,
            (
                SELECT sender
                FROM messages
                WHERE user_id = u.id
                ORDER BY created_at DESC
                LIMIT 1
            ) AS last_sender,
            (
                SELECT text
                FROM messages
                WHERE user_id = u.id
                ORDER BY created_at DESC
                LIMIT 1
            ) AS last_text
        FROM users u
        LEFT JOIN messages m ON m.user_id = u.id
        GROUP BY u.id
        ORDER BY COALESCE(MAX(m.created_at), u.created_at) DESC
        """
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        item = dict(row)
        if _is_admin_email(item.get("email")):
            continue
        item["message_count"] = int(item["message_count"] or 0)
        item["needs_reply"] = item["message_count"] > 0 and item.get("last_sender") == "user"
        result.append(item)
    return result


def _admin_messages_for_user(user_id):
    conn = _db()
    user_row = conn.execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    if not user_row:
        conn.close()
        return None
    if _is_admin_email(user_row["email"]):
        conn.close()
        return None
    msg_rows = conn.execute(
        "SELECT id, sender, text, created_at FROM messages WHERE user_id = ? ORDER BY created_at ASC",
        (user_id,)
    ).fetchall()
    conn.close()
    return {
        "user": dict(user_row),
        "messages": [dict(r) for r in msg_rows],
    }


MODEL_POOL = FreeModelPool()
CHAT_MODELS = MODEL_POOL.models

DEFAULT_MODEL_ID = CHAT_MODELS[0]["id"]
MODEL_BY_ID = {item["id"]: item for item in CHAT_MODELS}
ALLOWED_MODEL_IDS = set(MODEL_BY_ID)
VISION_MODEL_IDS = {item["id"] for item in CHAT_MODELS if item.get("vision")}

TIER_S = [m for m in CHAT_MODELS if m.get("tier") == "S"]
TIER_M = [m for m in CHAT_MODELS if m.get("tier") == "M"]
TIER_H = [m for m in CHAT_MODELS if m.get("tier") == "H"]
VISION_MODELS = [m for m in CHAT_MODELS if m.get("vision")]
CODING_MODELS = [m for m in CHAT_MODELS if m.get("coding")]
SEARCH_MODELS = [m for m in CHAT_MODELS if m.get("search")]
REASONING_MODELS = [m for m in CHAT_MODELS if m.get("reasoning")]

_COMPLEX_PATTERNS = re.compile(
    r"(?:анализ|проанализируй|сравни|compare|analyze|explain\s+in\s+detail|"
    r"step[\s-]by[\s-]step|пошагов|таблиц|table|spreadsheet|"
    r"swot|roi\b|revenue|strategy|стратеги|бизнес[\s-]план|business\s+plan|"
    r"legal|юридич|contract|договор|compliance|"
    r"medical|медицин|diagnos|диагноз|"
    r"algorithm|алгоритм|architect|архитектур|"
    r"write\s+(?:a\s+)?(?:full|complete|detailed)|"
    r"напиши\s+(?:полн|подробн|детальн)|"
    r"(?:pros?\s+and\s+cons?|плюсы\s+и\s+минусы)|"
    r"(?:multi[\s-]?step|многошагов)|"
    r"(?:in[\s-]?depth|углубл)|"
    r"research|исследован|"
    r"(?:\d+\s*[\.\)]\s*.*){3,})",
    re.IGNORECASE
)

_CODE_PATTERNS = re.compile(
    r"(?:code|код|script|скрипт|function|функци|debug|дебаг|"
    r"python|javascript|typescript|html|css|sql|react|"
    r"api\s+(?:endpoint|integration)|"
    r"fix\s+(?:the|this|my)\s+(?:bug|error|code)|"
    r"почини|исправь\s+(?:код|ошибк)|"
    r"implement|реализуй|"
    r"```|def\s+\w+|class\s+\w+|import\s+\w+|const\s+\w+|function\s+\w+)",
    re.IGNORECASE
)

_SEARCH_PATTERNS = re.compile(
    r"(?:latest|newest|current|today|2024|2025|2026|"
    r"последн|новост|сегодня|актуальн|"
    r"what\s+(?:is|are)\s+the\s+(?:latest|current|new)|"
    r"search\s+for|find\s+(?:info|information)|"
    r"who\s+won|what\s+happened|"
    r"price\s+of|stock|weather|"
    r"погода|курс\s+(?:доллар|евро|валют))",
    re.IGNORECASE
)

_SIMPLE_PATTERNS = re.compile(
    r"^(?:hi|hello|hey|привет|здравствуй|добрый\s+день|"
    r"thanks|спасибо|thank\s+you|"
    r"ok|okay|ок|хорошо|понятно|"
    r"yes|no|да|нет|"
    r"bye|пока|до\s+свидания|"
    r"how\s+are\s+you|как\s+дела|"
    r"what\s+(?:is|are)\s+\w+\??|"
    r"who\s+(?:is|are)\s+\w+\??|"
    r"(?:what|when|where|how)\s+.{0,40}\??)$",
    re.IGNORECASE
)

def _pick_available(candidates):
    key = "route:" + ",".join(sorted({str(m.get("provider", "")) for m in candidates if m}))
    return MODEL_POOL.pick([m for m in candidates if m], key=key)


def _route_request(message, attachments, agent_id="auto"):
    agent = AGENT_BY_ID.get(agent_id, AGENTS["auto"])
    has_images = any(a.get("kind") == "image" for a in attachments)
    has_files = any(a.get("kind") in ("text", "file") for a in attachments)
    msg_len = len(message)
    msg_lower = message.lower().strip()

    vision_pool = VISION_MODELS

    if agent.get("force_vision") or has_images:
        best = _pick_available(vision_pool)
        if best:
            return best, "H", "vision"

    if agent.get("prefer_search"):
        best = _pick_available(SEARCH_MODELS) or _pick_available(TIER_H)
        if best:
            return best, "H", "search"

    if agent.get("prefer_coding"):
        best = _pick_available(CODING_MODELS) or _pick_available(TIER_H)
        if best:
            return best, "H", "coding"

    force_tier = agent.get("force_tier")
    if force_tier == "H":
        best = _pick_available(TIER_H) or _pick_available(TIER_M)
        if best:
            return best, "H", agent_id
    elif force_tier == "M":
        best = _pick_available(TIER_M) or _pick_available(TIER_H)
        if best:
            return best, "M", agent_id

    if agent_id != "auto":
        best = _pick_available(TIER_M) or _pick_available(TIER_H)
        if best:
            return best, "M", agent_id

    if msg_len < 80 and _SIMPLE_PATTERNS.match(msg_lower):
        best = _pick_available(TIER_S) or _pick_available(TIER_M)
        if best:
            return best, "S", "simple"

    if _CODE_PATTERNS.search(message):
        best = _pick_available(CODING_MODELS) or _pick_available(TIER_H)
        if best:
            return best, "H", "coding"

    if has_files:
        best = _pick_available(TIER_H) or _pick_available(TIER_M)
        if best:
            return best, "H", "file_analysis"

    if msg_len > 500 or _COMPLEX_PATTERNS.search(message):
        best = _pick_available(TIER_H) or _pick_available(TIER_M)
        if best:
            return best, "H", "complex"

    if msg_len > 30 and _SEARCH_PATTERNS.search(message):
        best = _pick_available(SEARCH_MODELS)
        if best:
            return best, "H", "search"

    best = _pick_available(TIER_M) or _pick_available(TIER_H) or _pick_available(TIER_S)
    if best:
        return best, "M", "general"

    return MODEL_BY_ID[DEFAULT_MODEL_ID], "M", "fallback"


def _max_tokens_for_tier(tier):
    if tier == "S":
        return 512
    if tier == "M":
        return 1024
    return 2048


def _quality_check(reply, tier, reason):
    if not reply or not reply.strip():
        return False
    stripped = reply.strip()
    if len(stripped) < 10:
        return False
    return True


MAX_ATTACHMENTS = 4
MAX_TEXT_ATTACHMENT_CHARS = 12000
MAX_BODY_BYTES = 40 * 1024 * 1024
MAX_IMAGE_DATA_URL_CHARS = 36_000_000


_BASE_PROMPT = (
    "You are NanoTech Hub's AI assistant. "
    "If asked about pricing, give rough ranges and say exact pricing depends on requirements. "
    "If asked to schedule, direct to info@nanotech.icu or +44 7593 012313. "
)

AGENTS = {
    "auto": {
        "id": "auto",
        "label": "Auto",
        "icon": "fa-wand-magic-sparkles",
        "description": "Automatically picks the best mode for your request",
        "system_prompt": _BASE_PROMPT + "Be concise and professional. If files are attached, reason from provided text/metadata and clearly note any limits.",
    },
    "general": {
        "id": "general",
        "label": "General",
        "icon": "fa-comments",
        "description": "Friendly assistant for everyday questions",
        "system_prompt": _BASE_PROMPT + "Be helpful, friendly, and concise. Answer clearly in the user's language.",
        "force_tier": "M",
    },
    "coding": {
        "id": "coding",
        "label": "Coding",
        "icon": "fa-code",
        "description": "Write, debug, and review code",
        "system_prompt": _BASE_PROMPT + (
            "You are a senior software engineer. "
            "Always format code in fenced code blocks with the language tag. "
            "Explain your reasoning step by step. "
            "If the request is ambiguous, ask a clarifying question before writing code."
        ),
        "force_tier": "H",
        "prefer_coding": True,
    },
    "analyst": {
        "id": "analyst",
        "label": "Analyst",
        "icon": "fa-chart-line",
        "description": "Data analysis, tables, documents, and files",
        "system_prompt": _BASE_PROMPT + (
            "You are a data analyst. "
            "Structure your answers with headings, bullet points, and tables where appropriate. "
            "When analyzing files, extract key insights and present them clearly. "
            "Always provide actionable conclusions."
        ),
        "force_tier": "H",
    },
    "research": {
        "id": "research",
        "label": "Research",
        "icon": "fa-magnifying-glass",
        "description": "In-depth research with web search",
        "system_prompt": _BASE_PROMPT + (
            "You are a research specialist. "
            "Provide thorough, well-structured answers with multiple perspectives. "
            "Cite sources when possible. "
            "Use headings and numbered lists for clarity."
        ),
        "force_tier": "H",
        "prefer_search": True,
    },
    "vision": {
        "id": "vision",
        "label": "Vision",
        "icon": "fa-eye",
        "description": "Analyze and describe images",
        "system_prompt": _BASE_PROMPT + (
            "You are a visual analysis expert. "
            "Describe images in detail, identify objects, text, patterns, and context. "
            "If asked to extract information from screenshots or documents, be thorough and precise."
        ),
        "force_vision": True,
        "force_tier": "H",
    },
}

AGENT_BY_ID = {a["id"]: a for a in AGENTS.values()}
DEFAULT_AGENT = "auto"

SYSTEM_PROMPT = AGENTS["auto"]["system_prompt"]


def _clean_text(value, limit):
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _provider_available(provider):
    return MODEL_POOL.provider_available(provider)



def _sanitize_attachments(value):
    if not isinstance(value, list):
        return []

    cleaned = []
    for item in value[:MAX_ATTACHMENTS]:
        if not isinstance(item, dict):
            continue

        name = _clean_text(item.get("name"), 200)
        file_type = _clean_text(item.get("type"), 100)
        kind = _clean_text(item.get("kind"), 20)
        size = item.get("size") if isinstance(item.get("size"), int) else 0
        base = {
            "name": name,
            "type": file_type,
            "size": size,
        }

        if kind == "image":
            data_url = item.get("data_url")
            if (
                isinstance(data_url, str)
                and data_url.startswith("data:image/")
                and len(data_url) <= MAX_IMAGE_DATA_URL_CHARS
            ):
                cleaned.append({**base, "kind": "image", "data_url": data_url})
            continue

        if kind == "text":
            text = item.get("text") if isinstance(item.get("text"), str) else ""
            truncated = bool(item.get("truncated"))
            if len(text) > MAX_TEXT_ATTACHMENT_CHARS:
                text = text[:MAX_TEXT_ATTACHMENT_CHARS]
                truncated = True
            cleaned.append({**base, "kind": "text", "text": text, "truncated": truncated})
            continue

        if kind == "doc":
            data_url = item.get("data_url")
            max_size = MAX_IMAGE_DATA_URL_CHARS * 2
            if isinstance(data_url, str) and len(data_url) <= max_size:
                cleaned.append({**base, "kind": "doc", "data_url": data_url})
            continue

        cleaned.append({**base, "kind": "file"})

    return cleaned


def _build_user_content(message, attachments, model):
    parts = []
    warning = ""
    base_message = message.strip()
    if base_message:
        parts.append({"type": "text", "text": base_message})

    text_blocks = []
    file_notes = []

    for item in attachments:
        kind = item.get("kind")
        name = item.get("name") or "unnamed"
        file_type = item.get("type") or "unknown"

        if kind == "image":
            if model in VISION_MODEL_IDS:
                parts.append({"type": "image_url", "image_url": {"url": item.get("data_url")}})
            else:
                warning = "Image attached, but selected model is text-only. Choose a Vision model to analyze images."
                file_notes.append(f"image: {name}")
            continue

        if kind == "text":
            text = item.get("text") if isinstance(item.get("text"), str) else ""
            if text:
                chunk = f"[Attached text file: {name}]\n{text}"
                if item.get("truncated"):
                    chunk += "\n[File content truncated]"
                text_blocks.append(chunk)
            else:
                file_notes.append(f"file: {name} ({file_type})")
            continue

        if kind == "doc":
            data_url = item.get("data_url", "")
            text = _extract_docx_text(data_url) if data_url else ""
            if text:
                text_blocks.append(f"[Attached document: {name}]\n{text}")
            else:
                file_notes.append(f"document: {name} (could not extract text)")
            continue

        file_notes.append(f"file: {name} ({file_type})")

    if text_blocks:
        parts.append({"type": "text", "text": "\n\n".join(text_blocks)})

    if file_notes:
        parts.append({"type": "text", "text": "Attached file metadata:\n- " + "\n- ".join(file_notes)})

    if not parts:
        parts.append({"type": "text", "text": "Please help with my attached files."})

    if len(parts) == 1 and parts[0].get("type") == "text":
        return parts[0].get("text", ""), warning

    return parts, warning


def _call_free_model(model, system_prompt, user_content, max_tokens=512):
    return MODEL_POOL.call_model(model, system_prompt, user_content, max_tokens=max_tokens)


class Handler(SimpleHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json_with_cookie(self, status: int, payload: dict, cookie_value: str) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Set-Cookie", cookie_value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect_with_cookie(self, location: str, cookie_value: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Set-Cookie", cookie_value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _maintenance_cookie(self, value: str, max_age: int) -> str:
        host = (self.headers.get("Host", "") or "").split(":", 1)[0].lower()
        is_local = host in {"127.0.0.1", "localhost", "::1"}
        parts = [f"maint_bypass={value}", "Path=/", f"Max-Age={max_age}", "SameSite=Lax", "HttpOnly"]
        if not is_local:
            parts.append("Secure")
        return "; ".join(parts)

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _get_token(self):
        auth = self.headers.get("Authorization", "")
        return auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""

    def _client_ip(self):
        return self.headers.get("X-Real-IP") or self.client_address[0]

    def _get_admin_actor(self):
        if self._check_maintenance_bypass():
            return {"mode": "owner_bypass"}
        user = _get_user_by_token(self._get_token())
        if user and _is_admin_email(user.get("email")):
            return user
        return None

    def _send_html(self, status, html):
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _check_maintenance_bypass(self):
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        if qs.get("mkey", [None])[0] == MAINTENANCE_KEY:
            return True
        try:
            from http.cookies import SimpleCookie
            c = SimpleCookie()
            c.load(self.headers.get("Cookie", ""))
            v = c.get("maint_bypass")
            return bool(v and v.value == MAINTENANCE_KEY)
        except Exception:
            return False

    def do_GET(self) -> None:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)

        if parsed.path == "/api/maintenance-ui":
            qs = parse_qs(parsed.query)
            key = qs.get("key", [None])[0]
            cookie_on = self._maintenance_cookie(MAINTENANCE_KEY, 2592000)
            has_bypass = self._check_maintenance_bypass()
            if not has_bypass and key == MAINTENANCE_KEY:
                self._redirect_with_cookie("/api/maintenance-ui", cookie_on)
                return

            if not has_bypass:
                self._send_html(
                    200,
                    """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>NanoTech — Owner Login</title>
  <style>
    :root{--bg:#0b1020;--card:rgba(255,255,255,.06);--border:rgba(255,255,255,.12);--text:#e7e9ff;--muted:rgba(231,233,255,.75);--accent:#7c3aed}
    *{box-sizing:border-box}
    body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:radial-gradient(1200px 600px at 30% 20%, rgba(124,58,237,.35), transparent 55%),radial-gradient(1000px 600px at 80% 60%, rgba(34,197,94,.18), transparent 60%),var(--bg);font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,Arial,sans-serif;color:var(--text)}
    .card{width:min(520px,92vw);padding:22px 22px 18px;border:1px solid var(--border);background:var(--card);border-radius:18px;backdrop-filter: blur(12px)}
    h1{font-size:18px;margin:0 0 10px 0}
    .muted{color:var(--muted);font-size:12px;line-height:1.35}
    form{margin-top:14px;display:flex;gap:10px}
    input{flex:1;border:1px solid var(--border);background:rgba(255,255,255,.06);color:var(--text);padding:10px 12px;border-radius:12px;font-size:13px;outline:none}
    button{border:1px solid rgba(124,58,237,.55);background:rgba(124,58,237,.18);color:var(--text);padding:10px 12px;border-radius:12px;font-size:13px;cursor:pointer}
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>Owner login</h1>
    <div class=\"muted\">Enter your <b>MAINTENANCE_KEY</b> once — after that it works without a key (cookie lasts 30 days).</div>
    <form id=\"f\">
      <input id=\"k\" type=\"password\" placeholder=\"MAINTENANCE_KEY\" autocomplete=\"off\" />
      <button type=\"submit\">Log in</button>
    </form>
    <div class=\"muted\" style=\"margin-top:10px\">The key is in your <code>.env</code> file (line <code>MAINTENANCE_KEY=...</code>).</div>
  </div>
  <script>
    const f = document.getElementById('f');
    const k = document.getElementById('k');
    f.addEventListener('submit', async (e) => {
      e.preventDefault();
      const key = (k.value || '').trim();
      if (!key) return;
      try{
        const r = await fetch(`/api/maintenance-login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          cache: 'no-store',
          body: JSON.stringify({ key })
        });
        const j = await r.json();
        if (!r.ok) throw new Error(j && j.error ? j.error : 'forbidden');
        location.href = '/api/maintenance-ui';
      }catch(err){
        alert('Invalid key');
      }
    });
  </script>
</body>
</html>""",
                )
                return

            self._send_html(
                200,
                """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>NanoTech — Maintenance</title>
  <style>
    :root{--bg:#0b1020;--card:rgba(255,255,255,.06);--border:rgba(255,255,255,.12);--text:#e7e9ff;--muted:rgba(231,233,255,.75);--green:#22c55e;--gray:#6b7280;--accent:#7c3aed}
    *{box-sizing:border-box}
    body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:radial-gradient(1200px 600px at 30% 20%, rgba(124,58,237,.35), transparent 55%),radial-gradient(1000px 600px at 80% 60%, rgba(34,197,94,.18), transparent 60%),var(--bg);font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,Arial,sans-serif;color:var(--text)}
    .card{width:min(720px,92vw);padding:22px 22px 18px;border:1px solid var(--border);background:var(--card);border-radius:18px;backdrop-filter: blur(12px)}
    .top{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}
    h1{font-size:18px;letter-spacing:.2px;margin:0}
    .pill{padding:6px 10px;border-radius:999px;font-size:12px;border:1px solid var(--border);color:var(--muted)}
    .statusRow{margin-top:14px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
    .statusText{display:flex;flex-direction:column;gap:4px}
    .statusMain{font-weight:650}
    .statusSub{font-size:12px;color:var(--muted)}
    .switch{position:relative;width:58px;height:34px;flex:0 0 auto}
    .switch input{opacity:0;width:0;height:0}
    .slider{position:absolute;cursor:pointer;inset:0;background:rgba(107,114,128,.45);border:1px solid var(--border);transition:.18s;border-radius:999px}
    .slider:before{content:"";position:absolute;height:26px;width:26px;left:4px;top:3px;background:#fff;transition:.18s;border-radius:999px}
    .switch input:checked + .slider{background:rgba(34,197,94,.55)}
    .switch input:checked + .slider:before{transform:translateX(24px)}
    .actions{margin-top:16px;display:flex;gap:10px;flex-wrap:wrap}
    button,a.btn{appearance:none;border:1px solid var(--border);background:rgba(255,255,255,.06);color:var(--text);padding:10px 12px;border-radius:12px;font-size:13px;text-decoration:none;cursor:pointer}
    button.primary{border-color:rgba(124,58,237,.55);background:rgba(124,58,237,.18)}
    button:disabled{opacity:.55;cursor:not-allowed}
    .hint{margin-top:12px;font-size:12px;color:var(--muted);line-height:1.35}
    .sep{height:1px;background:rgba(255,255,255,.10);margin:14px 0 12px}
    code{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:12px;color:#dbeafe}
  </style>
</head>
<body>
  <div class=\"card\">
    <div class=\"top\">
      <h1>Maintenance Toggle</h1>
      <div class=\"pill\" id=\"pill\">loading…</div>
    </div>

    <div class=\"statusRow\">
      <div class=\"statusText\">
        <div class=\"statusMain\" id=\"statusMain\">—</div>
        <div class=\"statusSub\" id=\"statusSub\">—</div>
      </div>

      <label class=\"switch\" title=\"Site accessible / under maintenance\">
        <input id=\"toggle\" type=\"checkbox\" />
        <span class=\"slider\"></span>
      </label>
    </div>

    <div class=\"actions\">
      <button class=\"primary\" id=\"openBtn\">Open site as owner</button>
      <button class=\"primary\" id=\"inboxBtn\">Open message inbox</button>
      <button id=\"logoutBtn\">Revoke owner access (logout)</button>
      <button id=\"refreshBtn\">Refresh status</button>
    </div>

    <div class=\"sep\"></div>
    <div class=\"hint\">
      - Toggle <b>right</b> = <b>Site accessible</b> (maintenance OFF)
      <br/>
      - Toggle <b>left</b> = <b>Site under maintenance</b> (maintenance ON)
      <br/>
      - This page is private. Do not share this URL.
    </div>
  </div>

  <script>
    const pill = document.getElementById('pill');
    const toggle = document.getElementById('toggle');
    const statusMain = document.getElementById('statusMain');
    const statusSub = document.getElementById('statusSub');
    const refreshBtn = document.getElementById('refreshBtn');
    const openBtn = document.getElementById('openBtn');
    const inboxBtn = document.getElementById('inboxBtn');
    const logoutBtn = document.getElementById('logoutBtn');

    function setBusy(b){
      toggle.disabled = b;
      refreshBtn.disabled = b;
      openBtn.disabled = b;
      inboxBtn.disabled = b;
      logoutBtn.disabled = b;
      pill.textContent = b ? 'working…' : pill.textContent;
    }

    function paint(maintenance){
      const isOnline = !maintenance;
      toggle.checked = isOnline;
      if (isOnline){
        pill.textContent = 'SITE ACCESSIBLE';
        pill.style.borderColor = 'rgba(34,197,94,.55)';
        statusMain.textContent = 'Site is accessible to all users';
        statusSub.textContent = 'maintenance: OFF';
      } else {
        pill.textContent = 'UNDER MAINTENANCE';
        pill.style.borderColor = 'rgba(107,114,128,.55)';
        statusMain.textContent = 'Site is offline (maintenance)';
        statusSub.textContent = 'maintenance: ON';
      }
    }

    async function getStatus(){
      const r = await fetch(`/api/maintenance`, {cache:'no-store'});
      const j = await r.json();
      if (!r.ok) throw new Error(j && j.error ? j.error : 'status_failed');
      paint(!!j.maintenance);
    }

    async function setMaintenance(on){
      const action = on ? 'on' : 'off';
      const r = await fetch(`/api/maintenance?action=${action}`, {cache:'no-store'});
      const j = await r.json();
      if (!r.ok) throw new Error(j && j.error ? j.error : 'toggle_failed');
      paint(!!j.maintenance);
    }

    toggle.addEventListener('change', async () => {
      setBusy(true);
      try{
        const wantOnline = toggle.checked;
        await setMaintenance(!wantOnline);
      }catch(e){
        await getStatus().catch(()=>{});
        alert('Error: ' + (e && e.message ? e.message : e));
      }finally{
        setBusy(false);
      }
    });

    refreshBtn.addEventListener('click', async () => {
      setBusy(true);
      try{ await getStatus(); }
      catch(e){ alert('Error: ' + (e && e.message ? e.message : e)); }
      finally{ setBusy(false); }
    });

    openBtn.addEventListener('click', () => {
      location.href = `/api/maintenance?action=open`;
    });

    inboxBtn.addEventListener('click', () => {
      location.href = `/api/admin-inbox`;
    });

    logoutBtn.addEventListener('click', async () => {
      setBusy(true);
      try{
        const r = await fetch(`/api/maintenance?action=logout`, {cache:'no-store'});
        const j = await r.json();
        if (!r.ok) throw new Error(j && j.error ? j.error : 'logout_failed');
        alert('Owner access revoked');
      }catch(e){
        alert('Error: ' + (e && e.message ? e.message : e));
      }finally{
        setBusy(false);
      }
    });

    (async () => {
      setBusy(true);
      try{ await getStatus(); }
      catch(e){
        pill.textContent = 'FORBIDDEN';
        statusMain.textContent = 'Access denied';
        statusSub.textContent = 'Re-login at /api/maintenance-ui';
      }
      setBusy(false);
    })();
  </script>
</body>
</html>""",
            )
            return

        if parsed.path == "/api/maintenance":
            qs = parse_qs(parsed.query)
            key = qs.get("key", [None])[0]
            if key != MAINTENANCE_KEY and not self._check_maintenance_bypass():
                self._send_json(403, {"error": "forbidden"})
                return
            action = qs.get("action", [None])[0]
            cookie_on = self._maintenance_cookie(MAINTENANCE_KEY, 2592000)
            cookie_off = self._maintenance_cookie("", 0)
            if action == "on":
                _toggle_maintenance(True)
                self._send_json_with_cookie(200, {"maintenance": True, "message": "Site is now OFFLINE"}, cookie_on)
            elif action == "off":
                _toggle_maintenance(False)
                self._send_json_with_cookie(200, {"maintenance": False, "message": "Site is now ONLINE"}, cookie_on)
            elif action == "login":
                self._send_json_with_cookie(200, {"ok": True, "message": "Bypass enabled"}, cookie_on)
            elif action == "open":
                self._redirect_with_cookie("/", cookie_on)
            elif action == "logout":
                self._send_json_with_cookie(200, {"ok": True, "message": "Bypass disabled"}, cookie_off)
            else:
                self._send_json(200, {"maintenance": _is_maintenance()})
            return

        if parsed.path == "/api/admin-inbox":
            self._send_html(
                200,
                """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>NanoTech — Admin Inbox</title>
  <style>
    :root{--bg:#0b1020;--card:rgba(255,255,255,.06);--card2:rgba(255,255,255,.04);--border:rgba(255,255,255,.12);--text:#e7e9ff;--muted:rgba(231,233,255,.72);--accent:#7c3aed;--green:#22c55e;--red:#ef4444}
    *{box-sizing:border-box}
    body{margin:0;min-height:100vh;background:radial-gradient(1200px 600px at 20% 10%, rgba(124,58,237,.25), transparent 55%),radial-gradient(1000px 600px at 80% 70%, rgba(34,197,94,.16), transparent 60%),var(--bg);font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,Arial,sans-serif;color:var(--text)}
    .shell{max-width:1320px;margin:0 auto;padding:24px}
    .top{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:18px}
    .title{font-size:22px;font-weight:700}
    .top-actions{display:flex;gap:10px;flex-wrap:wrap}
    .pill{padding:8px 12px;border:1px solid var(--border);border-radius:999px;font-size:12px;color:var(--muted)}
    .pill.ok{border-color:rgba(34,197,94,.45);color:#bbf7d0}
    .pill.bad{border-color:rgba(239,68,68,.45);color:#fecaca}
    .btn{appearance:none;border:1px solid var(--border);background:rgba(255,255,255,.06);color:var(--text);padding:10px 14px;border-radius:12px;font-size:13px;cursor:pointer;text-decoration:none}
    .btn.primary{border-color:rgba(124,58,237,.55);background:rgba(124,58,237,.18)}
    .layout{display:grid;grid-template-columns:360px 1fr;gap:16px}
    .panel{border:1px solid var(--border);background:var(--card);border-radius:18px;backdrop-filter:blur(12px);min-height:74vh}
    .sidebar-head,.thread-head{padding:16px 18px;border-bottom:1px solid rgba(255,255,255,.08)}
    .sidebar-head strong,.thread-head strong{display:block;font-size:15px}
    .sidebar-head span,.thread-head span{display:block;margin-top:4px;font-size:12px;color:var(--muted)}
    .conversation-list{padding:10px;display:flex;flex-direction:column;gap:8px;max-height:calc(74vh - 78px);overflow:auto}
    .conversation-item{padding:14px;border:1px solid rgba(255,255,255,.08);background:var(--card2);border-radius:14px;cursor:pointer;transition:.18s}
    .conversation-item:hover,.conversation-item.active{border-color:rgba(124,58,237,.45);background:rgba(124,58,237,.12)}
    .conversation-top{display:flex;align-items:center;justify-content:space-between;gap:10px}
    .conversation-name{font-weight:650}
    .conversation-time{font-size:11px;color:var(--muted)}
    .conversation-email{margin-top:3px;font-size:12px;color:var(--muted)}
    .conversation-preview{margin-top:8px;font-size:12px;color:var(--muted);line-height:1.4}
    .badge{display:inline-flex;align-items:center;justify-content:center;padding:2px 8px;border-radius:999px;font-size:11px;border:1px solid rgba(34,197,94,.3);color:#bbf7d0;background:rgba(34,197,94,.08)}
    .thread{display:flex;flex-direction:column;height:74vh}
    .thread-messages{flex:1;overflow:auto;padding:18px;display:flex;flex-direction:column;gap:12px}
    .msg{max-width:78%;padding:12px 14px;border-radius:16px;border:1px solid rgba(255,255,255,.08);line-height:1.45;white-space:pre-wrap}
    .msg.user{align-self:flex-start;background:rgba(255,255,255,.05)}
    .msg.admin{align-self:flex-end;background:rgba(124,58,237,.18);border-color:rgba(124,58,237,.35)}
    .msg-time{margin-top:6px;font-size:11px;color:var(--muted)}
    .thread-empty{margin:auto;color:var(--muted);text-align:center;padding:24px}
    .reply-box{padding:16px 18px;border-top:1px solid rgba(255,255,255,.08)}
    .reply-status{min-height:18px;margin-bottom:8px;font-size:12px;color:var(--muted)}
    .reply-status.error{color:#fecaca}
    .reply-status.success{color:#bbf7d0}
    .reply-form{display:flex;gap:10px}
    .reply-form textarea{flex:1;min-height:92px;resize:vertical;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.05);color:var(--text);padding:12px 14px;border-radius:14px;font:inherit;outline:none}
    .reply-form button{align-self:flex-end}
    @media (max-width: 960px){
      .layout{grid-template-columns:1fr}
      .panel{min-height:auto}
      .conversation-list{max-height:320px}
      .thread{height:auto;min-height:70vh}
      .msg{max-width:90%}
    }
  </style>
</head>
<body>
  <div class=\"shell\">
    <div class=\"top\">
      <div class=\"title\">Admin Inbox</div>
      <div class=\"top-actions\">
        <div class=\"pill\" id=\"emailStatus\">Checking email setup…</div>
        <a class=\"btn\" href=\"/api/maintenance-ui\">Maintenance</a>
        <button class=\"btn primary\" id=\"refreshBtn\">Refresh</button>
      </div>
    </div>
    <div class=\"layout\">
      <div class=\"panel\">
        <div class=\"sidebar-head\">
          <strong>Registered users</strong>
          <span>Open a conversation to reply from alex.pavsky@gmail.com.</span>
        </div>
        <div class=\"conversation-list\" id=\"conversationList\">
          <div class=\"thread-empty\">Loading users…</div>
        </div>
      </div>
      <div class=\"panel thread\">
        <div class=\"thread-head\">
          <strong id=\"threadTitle\">Select a conversation</strong>
          <span id=\"threadMeta\">Messages sent here are stored in the user dashboard and emailed from your Gmail SMTP account.</span>
        </div>
        <div class=\"thread-messages\" id=\"threadMessages\">
          <div class=\"thread-empty\">Choose a user on the left.</div>
        </div>
        <div class=\"reply-box\">
          <div class=\"reply-status\" id=\"replyStatus\"></div>
          <form class=\"reply-form\" id=\"replyForm\">
            <textarea id=\"replyInput\" placeholder=\"Write a reply to the selected user…\" required></textarea>
            <button class=\"btn primary\" type=\"submit\">Send reply</button>
          </form>
        </div>
      </div>
    </div>
  </div>
  <script>
    const authToken = localStorage.getItem('auth_token') || '';
    const conversationList = document.getElementById('conversationList');
    const threadTitle = document.getElementById('threadTitle');
    const threadMeta = document.getElementById('threadMeta');
    const threadMessages = document.getElementById('threadMessages');
    const replyForm = document.getElementById('replyForm');
    const replyInput = document.getElementById('replyInput');
    const replyStatus = document.getElementById('replyStatus');
    const refreshBtn = document.getElementById('refreshBtn');
    const emailStatus = document.getElementById('emailStatus');
    let conversations = [];
    let currentUserId = '';

    function escapeHtml(value){
      return String(value || '').replace(/[&<>\"']/g, ch => {
        if (ch === '&') return '&amp;';
        if (ch === '<') return '&lt;';
        if (ch === '>') return '&gt;';
        if (ch === '\"') return '&quot;';
        return '&#39;';
      });
    }

    function formatTime(ts){
      if (!ts) return 'No messages';
      const d = new Date(ts * 1000);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
    }

    async function api(url, options){
      const request = Object.assign({ cache: 'no-store' }, options || {});
      request.headers = Object.assign({}, request.headers || {}, authToken ? { Authorization: 'Bearer ' + authToken } : {});
      const res = await fetch(url, request);
      if (res.status === 401 || res.status === 403) {
        throw new Error('admin_auth_required');
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || data.message || 'request_failed');
      return data;
    }

    async function loadEmailStatus(){
      try{
        const data = await api('/api/admin/email-status');
        if (data.ready){
          emailStatus.className = 'pill ok';
          emailStatus.textContent = 'Email ready: ' + data.from;
        } else {
          emailStatus.className = 'pill bad';
          emailStatus.textContent = 'Email not configured';
        }
      }catch(err){
        emailStatus.className = 'pill bad';
        emailStatus.textContent = 'Email status unavailable';
      }
    }

    function renderConversationList(){
      if (!conversations.length){
        conversationList.innerHTML = '<div class=\"thread-empty\">No registered users yet.</div>';
        return;
      }
      conversationList.innerHTML = conversations.map(c => {
        const badge = c.needs_reply ? '<span class=\"badge\">Needs reply</span>' : '';
        return '<div class=\"conversation-item ' + (c.id === currentUserId ? 'active' : '') + '\" data-user-id=\"' + escapeHtml(c.id) + '\">' +
          '<div class=\"conversation-top\">' +
            '<div class=\"conversation-name\">' + escapeHtml(c.name) + '</div>' +
            '<div class=\"conversation-time\">' + escapeHtml(formatTime(c.last_message_at || c.created_at)) + '</div>' +
          '</div>' +
          '<div class=\"conversation-email\">' + escapeHtml(c.email) + '</div>' +
          '<div class=\"conversation-preview\">' + (badge ? badge + ' · ' : '') + escapeHtml(c.last_text || 'No messages yet') + '</div>' +
        '</div>';
      }).join('');
      conversationList.querySelectorAll('.conversation-item').forEach(el => {
        el.addEventListener('click', () => openConversation(el.dataset.userId));
      });
    }

    async function loadConversations(preferredUserId){
      const data = await api('/api/admin/conversations');
      conversations = data.conversations || [];
      if (!currentUserId && conversations.length) currentUserId = preferredUserId || conversations[0].id;
      renderConversationList();
      if (currentUserId) await openConversation(currentUserId);
    }

    function renderThread(data){
      if (!data || !data.user){
        threadTitle.textContent = 'Conversation not found';
        threadMeta.textContent = 'Select another user.';
        threadMessages.innerHTML = '<div class=\"thread-empty\">Conversation not found.</div>';
        return;
      }
      threadTitle.textContent = data.user.name + ' — ' + data.user.email;
      threadMeta.textContent = 'User dashboard + email thread';
      if (!data.messages || !data.messages.length){
        threadMessages.innerHTML = '<div class=\"thread-empty\">No messages yet for this user.</div>';
        return;
      }
      threadMessages.innerHTML = data.messages.map(m => (
        '<div class=\"msg ' + escapeHtml(m.sender) + '\">' +
          '<div>' + escapeHtml(m.text) + '</div>' +
          '<div class=\"msg-time\">' + escapeHtml(formatTime(m.created_at)) + '</div>' +
        '</div>'
      )).join('');
      threadMessages.scrollTop = threadMessages.scrollHeight;
    }

    async function openConversation(userId){
      currentUserId = userId;
      renderConversationList();
      const data = await api('/api/admin/messages?user_id=' + encodeURIComponent(userId));
      renderThread(data);
    }

    replyForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = (replyInput.value || '').trim();
      if (!currentUserId || !text) return;
      replyStatus.className = 'reply-status';
      replyStatus.textContent = 'Sending…';
      try{
        await api('/api/admin/reply', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: currentUserId, text })
        });
        replyInput.value = '';
        replyStatus.className = 'reply-status success';
        replyStatus.textContent = 'Reply sent.';
        await loadConversations(currentUserId);
      }catch(err){
        replyStatus.className = 'reply-status error';
        replyStatus.textContent = err && err.message ? err.message : 'Failed to send reply.';
      }
    });

    refreshBtn.addEventListener('click', async () => {
      replyStatus.className = 'reply-status';
      replyStatus.textContent = '';
      await loadEmailStatus();
      await loadConversations(currentUserId);
    });

    (async () => {
      await loadEmailStatus();
      await loadConversations();
    })().catch(err => {
      if (err && err.message === 'admin_auth_required') {
        conversationList.innerHTML = '<div class=\"thread-empty\">Log in with the admin account to access this inbox.</div>';
        threadMessages.innerHTML = '<div class=\"thread-empty\">Admin access required. Sign in on the main site, then reopen this page.</div>';
        return;
      }
      conversationList.innerHTML = '<div class=\"thread-empty\">Failed to load inbox.</div>';
      threadMessages.innerHTML = '<div class=\"thread-empty\">' + escapeHtml(err && err.message ? err.message : 'Unknown error') + '</div>';
    });
  </script>
</body>
</html>""",
            )
            return

        if parsed.path == "/api/admin/email-status":
            if not self._get_admin_actor():
                self._send_json(403, {"error": "admin_auth_required"})
                return
            cfg = _smtp_config()
            self._send_json(200, {"ready": cfg["ready"], "from": cfg["from"], "admin": cfg["admin"]})
            return

        if parsed.path == "/api/admin/conversations":
            if not self._get_admin_actor():
                self._send_json(403, {"error": "admin_auth_required"})
                return
            self._send_json(200, {"conversations": _admin_conversations()})
            return

        if parsed.path == "/api/admin/messages":
            if not self._get_admin_actor():
                self._send_json(403, {"error": "admin_auth_required"})
                return
            user_id = parse_qs(parsed.query).get("user_id", [""])[0].strip()
            if not user_id:
                self._send_json(400, {"error": "user_id_required"})
                return
            payload = _admin_messages_for_user(user_id)
            if not payload:
                self._send_json(404, {"error": "user_not_found"})
                return
            self._send_json(200, payload)
            return

        if _is_maintenance() and not self._check_maintenance_bypass():
            if not parsed.path.startswith("/api/"):
                self._send_html(503, MAINTENANCE_HTML)
                return

        if self.path == "/api/agents":
            agents_list = [
                {
                    "id": a["id"],
                    "label": a["label"],
                    "icon": a.get("icon", "fa-robot"),
                    "description": a.get("description", ""),
                }
                for a in AGENTS.values()
            ]
            self._send_json(
                200,
                {
                    "default_agent": DEFAULT_AGENT,
                    "agents": agents_list,
                    "orchestration": MODEL_POOL.public_status(),
                },
            )
            return

        if self.path == "/api/models":
            agents_list = [
                {
                    "id": a["id"],
                    "label": a["label"],
                    "icon": a.get("icon", "fa-robot"),
                    "description": a.get("description", ""),
                }
                for a in AGENTS.values()
            ]
            self._send_json(
                200,
                {
                    "default_agent": DEFAULT_AGENT,
                    "agents": agents_list,
                    "orchestration": MODEL_POOL.public_status(),
                },
            )
            return

        if self.path == "/api/auth/me":
            user = _get_user_by_token(self._get_token())
            if not user:
                self._send_json(401, {"error": "not_authenticated"})
                return
            self._send_json(200, _public_user_payload(user))
            return

        if self.path == "/api/user/messages":
            user = _get_user_by_token(self._get_token())
            if not user:
                self._send_json(401, {"error": "not_authenticated"})
                return
            conn = _db()
            rows = conn.execute(
                "SELECT id, sender, text, created_at FROM messages WHERE user_id = ? ORDER BY created_at ASC",
                (user["id"],)
            ).fetchall()
            conn.close()
            self._send_json(200, {"messages": [dict(r) for r in rows]})
            return

        if self.path == "/api/user/notes":
            user = _get_user_by_token(self._get_token())
            if not user:
                self._send_json(401, {"error": "not_authenticated"})
                return
            conn = _db()
            row = conn.execute("SELECT text FROM notes WHERE user_id = ?", (user["id"],)).fetchone()
            conn.close()
            self._send_json(200, {"text": row["text"] if row else ""})
            return

        super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/maintenance-login":
            try:
                body = self._read_body()
            except Exception:
                self._send_json(400, {"error": "invalid_json"})
                return
            key = (body.get("key") or "").strip()
            if key != MAINTENANCE_KEY:
                self._send_json(403, {"error": "forbidden"})
                return
            cookie_on = self._maintenance_cookie(MAINTENANCE_KEY, 2592000)
            self._send_json_with_cookie(200, {"ok": True, "message": "Bypass enabled"}, cookie_on)
            return

        if _is_maintenance() and not self._check_maintenance_bypass():
            self._send_json(503, {"error": "maintenance", "message": "Site is under maintenance."})
            return

        if self.path == "/api/auth/register":
            try:
                body = self._read_body()
            except Exception:
                self._send_json(400, {"error": "invalid_json"})
                return
            name = (body.get("name") or "").strip()
            email = (body.get("email") or "").strip().lower()
            password = body.get("password") or ""
            if not name or not email or len(password) < 6:
                self._send_json(400, {"error": "Name, email, and password (min 6 chars) required."})
                return
            if _is_admin_email(email):
                self._send_json(403, {"error": "This email is reserved and cannot self-register."})
                return
            conn = _db()
            if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
                conn.close()
                self._send_json(409, {"error": "Email already registered."})
                return
            uid = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (uid, name, email, _hash_pw(password), time.time())
            )
            token = uuid.uuid4().hex
            conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, uid, time.time()))
            conn.commit()
            conn.close()
            self._send_json(200, {"token": token, "user": _public_user_payload({"id": uid, "name": name, "email": email})})
            return

        if self.path == "/api/auth/login":
            client_ip = self._client_ip()
            if _login_rate_limited(client_ip):
                self._send_json(429, {"error": "Too many failed login attempts. Please try again later."})
                return
            try:
                body = self._read_body()
            except Exception:
                self._send_json(400, {"error": "invalid_json"})
                return
            email = (body.get("email") or "").strip().lower()
            password = body.get("password") or ""
            conn = _db()
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not row or not _verify_pw(password, row["password_hash"]):
                conn.close()
                _record_login_failure(client_ip)
                self._send_json(401, {"error": "Invalid email or password."})
                return
            _clear_login_failures(client_ip)
            user = dict(row)
            # Rehash legacy SHA-256 passwords to scrypt on successful login
            if not user["password_hash"].startswith("scrypt:"):
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (_hash_pw(password), user["id"]))
            token = uuid.uuid4().hex
            conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user["id"], time.time()))
            conn.commit()
            conn.close()
            self._send_json(200, {"token": token, "user": _public_user_payload(user)})
            return

        if self.path == "/api/auth/logout":
            token = self._get_token()
            if token:
                conn = _db()
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
                conn.close()
            self._send_json(200, {"ok": True})
            return

        if self.path == "/api/admin/reply":
            if not self._get_admin_actor():
                self._send_json(403, {"error": "admin_auth_required"})
                return
            try:
                body = self._read_body()
            except Exception:
                self._send_json(400, {"error": "invalid_json"})
                return
            user_id = (body.get("user_id") or "").strip()
            text = (body.get("text") or "").strip()
            if not user_id or not text:
                self._send_json(400, {"error": "user_id_and_text_required"})
                return
            convo = _admin_messages_for_user(user_id)
            if not convo:
                self._send_json(404, {"error": "user_not_found"})
                return
            now = time.time()
            mid = uuid.uuid4().hex
            conn = _db()
            conn.execute(
                "INSERT INTO messages (id, user_id, sender, text, created_at) VALUES (?, ?, 'admin', ?, ?)",
                (mid, user_id, text, now)
            )
            conn.commit()
            conn.close()
            _send_async(_send_user_reply_email, convo["user"]["name"], convo["user"]["email"], text)
            self._send_json(200, {
                "message": {"id": mid, "sender": "admin", "text": text, "created_at": now},
                "email_ready": _smtp_config()["ready"],
            })
            return

        if self.path == "/api/user/messages":
            user = _get_user_by_token(self._get_token())
            if not user:
                self._send_json(401, {"error": "not_authenticated"})
                return
            try:
                body = self._read_body()
            except Exception:
                self._send_json(400, {"error": "invalid_json"})
                return
            text = (body.get("text") or "").strip()
            if not text:
                self._send_json(400, {"error": "Message text required."})
                return
            mid = uuid.uuid4().hex
            now = time.time()
            conn = _db()
            conn.execute(
                "INSERT INTO messages (id, user_id, sender, text, created_at) VALUES (?, ?, 'user', ?, ?)",
                (mid, user["id"], text, now)
            )
            admin_mid = uuid.uuid4().hex
            admin_text = "Thanks. Your message was sent to Alex. You'll get a personal reply here and by email."
            conn.execute(
                "INSERT INTO messages (id, user_id, sender, text, created_at) VALUES (?, ?, 'admin', ?, ?)",
                (admin_mid, user["id"], admin_text, now + 0.001)
            )
            conn.commit()
            conn.close()
            _send_async(_send_admin_notification, "dashboard", user["name"], user["email"], text, None)
            self._send_json(200, {
                "message": {"id": mid, "sender": "user", "text": text, "created_at": now},
                "email_ready": _smtp_config()["ready"],
            })
            return

        if self.path == "/api/user/notes":
            user = _get_user_by_token(self._get_token())
            if not user:
                self._send_json(401, {"error": "not_authenticated"})
                return
            try:
                body = self._read_body()
            except Exception:
                self._send_json(400, {"error": "invalid_json"})
                return
            text = body.get("text", "")
            conn = _db()
            conn.execute(
                "INSERT INTO notes (user_id, text, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET text = excluded.text, updated_at = excluded.updated_at",
                (user["id"], text, time.time())
            )
            conn.commit()
            conn.close()
            self._send_json(200, {"ok": True})
            return

        if self.path == "/api/contact":
            try:
                body = self._read_body()
            except Exception:
                self._send_json(400, {"error": "invalid_json"})
                return
            name = (body.get("name") or "").strip()
            email = (body.get("email") or "").strip()
            company = (body.get("company") or "").strip()
            service = (body.get("service") or "").strip()
            message = (body.get("message") or "").strip()
            if not name or not email or not message:
                self._send_json(400, {"error": "Name, email, and message are required."})
                return
            extra_lines = [
                f"Company: {company or 'N/A'}",
                f"Service interest: {service or 'N/A'}",
            ]
            recipients = _contact_recipients()
            cfg = _smtp_config()
            email_sent = False
            email_error = None
            if not cfg["ready"]:
                email_error = "smtp_not_configured"
                print("CONTACT FORM: SMTP not configured — message saved but email NOT sent")
            else:
                # Send synchronously so the client gets an honest result.
                ok, err = _send_admin_notification(
                    "contact form", name, email, message, extra_lines
                )
                email_sent = bool(ok)
                email_error = err
                if not ok:
                    print(f"CONTACT FORM: email failed: {err}")

            msg_id = _save_contact_message(
                name, email, company, service, message,
                email_sent, email_error, recipients,
            )

            if email_sent:
                self._send_json(200, {
                    "ok": True,
                    "email_sent": True,
                    "email_ready": True,
                    "id": msg_id,
                    "recipients": recipients,
                })
            else:
                # Message is stored server-side, but email delivery failed.
                # Do not claim success to the visitor.
                self._send_json(503, {
                    "ok": False,
                    "email_sent": False,
                    "email_ready": cfg["ready"],
                    "error": "We could not deliver your message by email right now. Please email info@nanotech.icu directly, or try again later.",
                    "id": msg_id,
                    "email_error": email_error,
                })
            return

        if self.path == "/api/chat-consent":
            try:
                body = self._read_body()
            except Exception:
                self._send_json(400, {"error": "invalid_json"})
                return

            client_ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
            ip_hash = _hash_ip(client_ip)
            user = _get_user_by_token(self._get_token())

            consent_version = str(body.get("consent_version") or "").strip()[:40]
            source = str(body.get("source") or "").strip()[:80]
            path = str(body.get("path") or "").strip()[:255]
            locale = str(body.get("locale") or "").strip()[:32]
            accepted_at_client = str(body.get("accepted_at") or "").strip()[:64]
            user_agent = self.headers.get("User-Agent", "")[:500]

            _log_chat_consent(
                ip_hash,
                user["id"] if user else None,
                consent_version,
                source,
                path,
                locale,
                user_agent,
                accepted_at_client,
            )

            try:
                consent_entry = {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                    "acceptedAtClient": accepted_at_client,
                    "consentVersion": consent_version,
                    "source": source,
                    "path": path,
                    "locale": locale,
                    "ipHash": ip_hash,
                    "userId": user["id"] if user else None,
                    "userAgent": user_agent,
                }
                with open("chat-consent-logs.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(consent_entry) + "\n")
            except Exception as e:
                print("Error saving consent log:", e)

            self._send_json(200, {"ok": True})
            return

        if self.path != "/api/chat":
            self._send_json(404, {"error": "not_found"})
            return

        client_ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
        ip_hash = _hash_ip(client_ip)

        if not _check_rate_limit(ip_hash):
            _audit_log(ip_hash, "-", None, None, None, 0, 0, "rate_limited", True)
            self._send_json(429, {"error": "rate_limited", "message": "Too many requests. Please wait a moment."})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0

        if length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "payload_too_large"})
            return

        try:
            raw = self.rfile.read(length) if length > 0 else b"{}"
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            self._send_json(400, {"error": "invalid_json"})
            return

        message = body.get("message") if isinstance(body.get("message"), str) else ""
        attachments = _sanitize_attachments(body.get("attachments"))
        if not message.strip() and not attachments:
            self._send_json(400, {"error": "missing_message"})
            return

        agent_id = body.get("agent") if isinstance(body.get("agent"), str) else DEFAULT_AGENT
        if agent_id not in AGENT_BY_ID:
            agent_id = DEFAULT_AGENT
        agent = AGENT_BY_ID[agent_id]
        system_prompt = agent.get("system_prompt", SYSTEM_PROMPT)

        input_ok, mod_reason = _moderate_input(message)
        if not input_ok:
            _audit_log(ip_hash, agent_id, None, None, None, len(message), 0, mod_reason, True)
            self._send_json(200, {"reply": MODERATION_REFUSAL, "model": "moderation", "agent": agent_id, "tier": "-", "reason": mod_reason})
            return

        model, tier, reason = _route_request(message, attachments, agent_id)
        model_id = model["id"]
        max_tokens = _max_tokens_for_tier(tier)
        user_content, warning = _build_user_content(message, attachments, model_id)
        print(f"[CHAT] agent={agent_id} model={model_id} tier={tier} reason={reason} max_tokens={max_tokens}")

        try:
            reply, err = _call_free_model(model, system_prompt, user_content, max_tokens)
            print(f"[CHAT] model={model_id} err={err} reply_len={len(reply) if reply else 0}")

            if err or not _quality_check(reply or "", tier, reason):
                MODEL_POOL.record_failure(model, err or {"code": "quality_check_failed"})
                print(f"[CHAT] failover from {model_id} (err={err})")
                for fallback in MODEL_POOL.fallback_chain(
                    model,
                    tier,
                    require_vision=reason == "vision",
                ):
                    fallback_content, _ = _build_user_content(message, attachments, fallback["id"])
                    reply2, err2 = _call_free_model(fallback, system_prompt, fallback_content, max_tokens)
                    print(
                        f"[CHAT] fallback={fallback['id']} provider={fallback['provider']} "
                        f"err={err2} reply_len={len(reply2) if reply2 else 0}"
                    )
                    if reply2 and _quality_check(reply2, tier, reason):
                        reply = reply2
                        model = fallback
                        model_id = fallback["id"]
                        break
                    MODEL_POOL.record_failure(fallback, err2 or {"code": "quality_check_failed"})
                    time.sleep(0.25)

            if not reply:
                _audit_log(ip_hash, agent_id, model_id, tier, reason, len(message), 0, "no_reply", False)
                self._send_json(502, {"error": "upstream_error", "message": "All models failed to respond."})
                return

            output_ok, out_mod = _moderate_output(reply)
            if not output_ok:
                _audit_log(ip_hash, agent_id, model_id, tier, reason, len(message), len(reply), out_mod, True)
                reply = MODERATION_REFUSAL

            _audit_log(ip_hash, agent_id, model.get("label", model_id), tier, reason, len(message), len(reply), "ok" if output_ok else out_mod, not output_ok)

            # Save to log file
            try:
                log_entry = {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                    "userMessage": message,
                    "aiReply": reply
                }
                with open("chat-logs.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry) + "\n")
            except Exception as e:
                print("Error saving chat log:", e)

            response_payload = {
                "reply": reply,
                "model": model.get("label", model_id),
                "agent": agent_id,
                "tier": tier,
                "reason": reason,
            }
            if warning:
                response_payload["warning"] = warning

            self._send_json(200, response_payload)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self._send_json(500, {"error": "server_error", "message": str(exc)})


def main() -> None:
    web_root = Path(__file__).resolve().parent
    os.chdir(web_root)

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Serving NanoTech website on http://{host}:{port}")
    print("Chat endpoint: POST /api/chat")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
