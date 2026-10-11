# Quizly – Backend

Django-REST-Backend für **Quizly**: Aus einem YouTube-Video wird automatisch ein Quiz mit 10 Fragen erzeugt. Der Ablauf: Die Tonspur wird mit **yt-dlp** und **FFmpeg** geladen, lokal mit **Whisper** transkribiert, und **Gemini Flash** formuliert daraus die Fragen. Die Anmeldung läuft über **JWT in HttpOnly-Cookies**.

Das Backend gehört zum vorgegebenen Schul-Frontend (Developer Akademie), das unverändert bleibt.

---

## Inhalt
1. [Funktionen](#funktionen)
2. [Tech-Stack](#tech-stack)
3. [Voraussetzungen](#voraussetzungen)
4. [Installation](#installation)
5. [Konfiguration (.env)](#konfiguration-env)
6. [Backend und Frontend starten](#backend-und-frontend-starten)
7. [API-Übersicht](#api-übersicht)
8. [Authentifizierung und Sicherheit](#authentifizierung-und-sicherheit)
9. [KI-Pipeline](#ki-pipeline)
10. [Tests](#tests)
11. [Admin](#admin)
12. [Projektstruktur](#projektstruktur)
13. [Bekannte Einschränkungen und Abweichungen](#bekannte-einschränkungen-und-abweichungen)

---

## Funktionen
- Registrierung, Login, Token-Refresh und Logout. Die JWTs liegen ausschließlich in HttpOnly-Cookies.
- Logout macht **beide Tokens sofort ungültig**: Der Refresh-Token kommt auf die Blacklist, der Access-Token wird über seine `jti` gesperrt.
- Ein Quiz aus einer YouTube-URL erzeugen: `watch?v=`, `youtu.be`, Shorts, Embed und Live-Links werden automatisch vereinheitlicht.
- Eigene Quizze auflisten, ansehen, Titel und Beschreibung bearbeiten und löschen. Fremde Quizze sind geschützt (403).
- Django-Admin zum Bearbeiten von Quizzen **und** einzelnen Fragen.

## Tech-Stack
| Bereich | Technik |
|---|---|
| Framework | Django 6.1, Django REST Framework 3.18 |
| Auth | djangorestframework-simplejwt 5.5 (inkl. Token-Blacklist), eigene Cookie-Authentifizierung |
| CORS | django-cors-headers |
| KI / Medien | yt-dlp (+ yt-dlp-ejs), FFmpeg, openai-whisper (lokal, CPU), google-genai (Gemini) |
| Datenbank | SQLite (Entwicklung) |

## Voraussetzungen
| Software | Version | Warum |
|---|---|---|
| **Python** | **3.12** (nicht 3.13) | `torch==2.2.2` (für Whisper) gibt es höchstens für Python 3.12 |
| **FFmpeg** | global installiert, im `PATH` | yt-dlp wandelt damit die Tonspur in mp3 um, Whisper liest Audio damit |
| **Node.js** | **≥ 22**, im `PATH` | JavaScript-Runtime, die yt-dlp für YouTube braucht. Die passenden Skripte liefert das Python-Paket `yt-dlp-ejs` |
| Gemini-API-Key | – | Erstellen in Google AI Studio |
| Schul-Frontend | – | Separates Repository, wird über VS Code Live Server gestartet |

Installation von FFmpeg und Node.js, z. B. unter macOS mit Homebrew: `brew install ffmpeg node`. Prüfen:
```bash
python3.12 --version
ffmpeg -version
node --version      # v22 oder neuer
```

> **Intel-Mac:** `requirements.txt` pinnt die getestete Kombination `torch==2.2.2`, `numpy==1.26.4`, `numba==0.59.1` und `llvmlite==0.42.0`. torch 2.2.2 ist die letzte Version für macOS x86_64 und braucht NumPy 1.x. Bitte **kein** `pip install -U` auf diese Pakete ausführen.

## Installation
```bash
git clone <repository-url> quizly_backend
cd quizly_backend

python3.12 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip check                           # erwartet: No broken requirements found.

cp .env.example .env                # dann .env ausfüllen (siehe nächster Abschnitt)
python manage.py migrate
python manage.py createsuperuser    # optional, für den Admin
```

## Konfiguration (.env)
Alle Einstellungen kommen aus der Datei `.env`. Die Vorlage ist [`.env.example`](.env.example), dort ist jede Variable kommentiert. Die `.env` enthält Secrets und wird **nicht** committet.

| Variable | Pflicht | Standard | Zweck |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | **ja** | – | Signiert Sessions und JWTs. Erzeugen mit `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_DEBUG` | nein | `False` | Für die lokale Entwicklung `True` setzen (Fehlerseiten, Admin-CSS). Im Produktivbetrieb nie `True` |
| `DJANGO_ALLOWED_HOSTS` | nein | `127.0.0.1,localhost` | Hosts, auf die Django antwortet |
| `FRONTEND_ORIGINS` | nein | `http://127.0.0.1:5500` | Origin(s) des Frontends für CORS und die CSRF-Origin-Prüfung |
| `AUTH_COOKIE_SECURE` | nein | `False` | Cookies nur über HTTPS senden. Im Produktivbetrieb `True` |
| `GEMINI_API_KEY` | **ja** (für Quizze) | – | API-Key für Gemini |
| `GEMINI_MODEL` | nein | `gemini-3.5-flash-lite` | Gemini-Modell |
| `GEMINI_TIMEOUT_SECONDS` | nein | `120` | Timeout pro Gemini-Anfrage |
| `WHISPER_MODEL` | nein | `tiny` | Lokales Whisper-Modell (`tiny`, `base`, `small` …) |
| `QUIZ_MAX_VIDEO_SECONDS` | nein | `600` | Maximale Videolänge, siehe Einschränkungen |
| `YTDLP_JS_RUNTIME` | nein | `node` | JS-Runtime für yt-dlp (`node`, `deno`, `bun`) |

## Backend und Frontend starten
```bash
source venv/bin/activate
python manage.py runserver 127.0.0.1:8000
```

Das Schul-Frontend erwartet die API unter `http://127.0.0.1:8000/api/`. So startest du es:
1. Das Frontend-Repository in VS Code öffnen. Der Ordner selbst muss das Root sein, weil die Seiten absolute Pfade wie `/pages/...` nutzen.
2. Mit **Live Server** starten und **genau über `http://127.0.0.1:5500`** öffnen.

> **Wichtig:** Über `http://localhost:5500` funktioniert der Login nicht. `localhost` und `127.0.0.1` gelten für Cookies als verschiedene Sites, deshalb schickt der Browser die Cookies nicht mit. Startet Live Server auf einem anderen Port, muss `FRONTEND_ORIGINS` in der `.env` angepasst werden.

## API-Übersicht
Alle Endpoints liegen unter `/api/` und erwarten bzw. liefern JSON.

| Methode | Pfad | Zugriff | Erfolg | Fehler |
|---|---|---|---|---|
| POST | `/api/register/` | öffentlich | 201 `{"detail": "User created successfully!"}` | 400 |
| POST | `/api/login/` | öffentlich | 200 `{"detail": "Login successfully!", "user": {id, username, email}}`, setzt `access_token` und `refresh_token` als Cookies | 401 |
| POST | `/api/token/refresh/` | Refresh-Cookie | 200 `{"detail": "Token refreshed"}`, setzt ein neues `access_token`-Cookie | 401 |
| POST | `/api/logout/` | angemeldet | 200 `{"detail": "Log-Out successfully! All Tokens will be deleted. Refresh token is now invalid."}`, löscht beide Cookies | 401 |
| POST | `/api/quizzes/` | angemeldet | 201: vollständiges Quiz, Fragen **mit** `created_at`/`updated_at` | 400, 401, 500 |
| GET | `/api/quizzes/` | angemeldet | 200: eigene Quizze, neueste zuerst, Fragen ohne Zeitstempel | 401 |
| GET | `/api/quizzes/{id}/` | Besitzer | 200 | 401, 403 (fremdes Quiz), 404 |
| PATCH | `/api/quizzes/{id}/` | Besitzer | 200: aktualisiertes Quiz (nur `title`, `description`) | 400, 401, 403, 404 |
| DELETE | `/api/quizzes/{id}/` | Besitzer | 204 (leerer Body) | 401, 403, 404 |

Request für ein neues Quiz: `{"url": "https://www.youtube.com/watch?v=..."}`. In der Antwort heißt das Feld `video_url`, und die URL ist immer auf das Format `watch?v=<id>` vereinheitlicht.

## Authentifizierung und Sicherheit
- **JWT in HttpOnly-Cookies:**
  - Der Access-Token gilt 15 Minuten, der Refresh-Token 1 Tag.
  - Die Cookies sind `HttpOnly`, `SameSite=Lax`, `Path=/`. `Secure` wird über `AUTH_COOKIE_SECURE` gesteuert.
  - Tokens stehen nie im Response-Body, und das Frontend kann sie nicht lesen. Der `Authorization`-Header wird bewusst ignoriert.
- **CSRF-Schutz** (das Frontend sendet kein CSRF-Token, daher mehrschichtig):
  - **Origin-Prüfung:** Cookie-authentifizierte POST-, PATCH- und DELETE-Requests (und der Refresh) müssen einen `Origin` aus `FRONTEND_ORIGINS` mitbringen. Fehlt der `Origin`, gilt ersatzweise der `Referer`. Fehlen beide, kommt **403**.
  - Beim Login wird nur geprüft, wenn ein `Origin` oder `Referer` vorhanden ist.
  - **Nur JSON:** Formular-Requests werden mit **415** abgelehnt.
  - CORS ist nur für `FRONTEND_ORIGINS` und mit Credentials freigegeben. CORS ist ausdrücklich **kein** CSRF-Schutz.
- **Logout:** Der Refresh-Token kommt auf die Blacklist, die `jti` des Access-Tokens wird gesperrt.
  - Ist der Access-Token schon abgelaufen, bleibt es laut Vertrag bei **401**. Kommt der Request vom Frontend-Origin, werden die Cookies trotzdem gelöscht und der Refresh-Token gesperrt.
- **Rechte:** Standardmäßig ist eine Anmeldung Pflicht (`IsAuthenticated`). Ein fremdes Quiz ergibt **403**, eine unbekannte ID **404**.
- **XSS:** Das Frontend rendert den Quiz-Titel per `innerHTML`. Titel und Beschreibung werden deshalb serverseitig von HTML-Tags befreit.
- **Secrets** kommen nur aus der `.env`. Logs enthalten nur die Video-URL und den Fehler, nie Keys oder Tokens.

**Postman/curl:** Für POST, PATCH und DELETE mit Cookies muss der Header `Origin: http://127.0.0.1:5500` gesetzt sein, sonst kommt 403. Login, Registrierung und GET-Requests funktionieren ohne.

## KI-Pipeline
```
URL prüfen und vereinheitlichen
  → yt-dlp: Metadaten lesen (Länge prüfen) → nur die Tonspur laden → FFmpeg → mp3 (temporärer Ordner)
  → Whisper (lokal, CPU, fp16=False) → Transkript (Sprache wird automatisch erkannt)
  → Transkript prüfen (genug Sprache?)
  → Gemini: JSON nach festem Schema (Titel, Beschreibung, 10 Fragen × 4 Optionen)
  → strenge Validierung (genau 10 Fragen, 4 verschiedene Optionen, answer ist eine davon)
  → atomar speichern
```
- Der Request ist **synchron**: `POST /api/quizzes/` antwortet erst mit dem fertigen Quiz (201). Bei einem kurzen Video und Whisper `tiny` dauert das typischerweise einige Sekunden bis wenige Minuten.
- Das **Whisper-Modell** wird beim ersten Aufruf nach `~/.cache/whisper` geladen (`tiny` ist etwa 75 MB) und bleibt danach im Arbeitsspeicher.
- Das Quiz entsteht in der **Sprache des Videos**, mit korrekter Rechtschreibung, also auch mit echten Umlauten.
- **Temporäre Audiodateien** liegen in einem temporären Systemordner und werden immer gelöscht, auch bei Fehlern.
- **Fehler:**
  - Bei ungeeigneter Eingabe kommt **400**: ungültige URL, Video zu lang oder zu wenig Sprache.
  - Bei Verarbeitungsfehlern kommt **500** mit `{"detail": "Quiz could not be generated. Please try again later."}`. Das betrifft Download, Whisper, Gemini (z. B. Überlastung, Quota, Timeout) und ungültige KI-Daten. Die Details stehen im Server-Log.
  - In keinem Fehlerfall wird ein halbes Quiz gespeichert.

## Tests
```bash
python manage.py test
```
- Die Suite hat 164 Tests: Registrierung, Login, Cookies, CSRF-Origin, Refresh, Logout, Rechte, CRUD, KI-Services, Unicode, Nebenläufigkeit und den Debug-Modus.
- **Alle externen Dienste sind gemockt** (yt-dlp, Whisper, Gemini). Es gibt keine Netzwerkzugriffe, keine Kosten, und torch wird nicht geladen.
- Weitere Checks:
```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

## Admin
`http://127.0.0.1:8000/admin/` (mit dem per `createsuperuser` angelegten Account).
- Quizze bearbeiten, inklusive ihrer Fragen direkt auf der Quiz-Seite.
- Einzelne Fragen eigenständig bearbeiten.
- Die Optionen werden als JSON-Liste gepflegt, z. B. `["A", "B", "C", "D"]`. Es müssen genau 4 verschiedene sein, und `answer` muss eine davon sein.
- Benutzer verwalten.

Ohne `DJANGO_DEBUG=True` liefert `runserver` keine statischen Dateien aus, dem Admin fehlt dann das CSS.

## Projektstruktur
```
core/                 Settings, URLs, env-Helfer (core/env.py)
auth_app/             User-Model, gesperrte Access-Tokens, Admin
  api/                serializers, views, urls, authentication (Cookie-JWT), utils (Cookies, Origin, Token-Widerruf)
  tests/
quizzes_app/          Quiz/Question-Models, Admin, validators, utils (URL- und Text-Normalisierung)
  api/                serializers, views, urls, permissions, exceptions
  services/           audio (yt-dlp), transcription (Whisper), gemini, quiz_builder, quiz_pipeline
  tests/
```

## Bekannte Einschränkungen und Abweichungen
**Bewusste Abweichungen vom API-Vertrag:**
- **Maximale Videolänge:** Videos über `QUIZ_MAX_VIDEO_SECONDS` (Standard 10 Minuten) oder ohne bekannte Länge (Livestreams) werden mit **400** abgelehnt. Der Vertrag kennt keine Längengrenze. Die Grenze schützt vor sehr langen CPU-Laufzeiten von Whisper und ist konfigurierbar.
- **Zu wenig Sprache:** Transkripte mit weniger als 20 Wörtern **und** weniger als 100 Zeichen werden mit **400** abgelehnt, z. B. Musik ohne Gesang oder ein Whisper-Artefakt wie „Vielen Dank.“.
  - Das ist eine einfache **Heuristik**, keine Prüfung der inhaltlichen Qualität.
  - Das Zeichenkriterium sorgt dafür, dass Sprachen ohne Leerzeichen (z. B. Japanisch) nicht blockiert werden.
- **403 bei fremdem oder fehlendem Origin:** Das gilt auch für Endpoints, bei denen der Vertrag kein 403 nennt (POST `/api/quizzes/`, Logout, Refresh). Grund ist der CSRF-Schutz. Mit dem Schul-Frontend tritt das nicht auf.
- **415** für Requests ohne JSON und **405** für `PUT` (nur `PATCH` ist vorgesehen).

**Technische Grenzen:**
- **Immer nur eine Transkription gleichzeitig pro Prozess:** Whispers gemeinsam genutztes Modell ist nicht thread-sicher, deshalb serialisiert ein `threading.Lock` die Transkriptionen. Weitere Quiz-Anfragen warten so lange.
  - Ein `threading.Lock` wirkt nur **innerhalb eines Prozesses**. Mit mehreren Worker-Prozessen (z. B. gunicorn `-w 2`) hätte jeder Prozess sein eigenes Modell und seinen eigenen Lock.
- **Kein Rate-Limit** (laut Vertrag „No limit“): Viele parallele Quiz-Anfragen belasten CPU und Gemini-Quota.
- **YouTube ändert sich regelmäßig:** Scheitern Downloads, helfen meist neuere Versionen von `yt-dlp` und dem passenden `yt-dlp-ejs`. Beide müssen gemeinsam aktualisiert werden.
- **Gemini** kann zeitweise überlastet sein (503). Die API antwortet dann mit 500, und man versucht es später erneut.
- Gesperrte Access-Tokens (`BlockedAccessToken`) werden nicht automatisch aufgeräumt. Das Feld `expires_at` ist für ein späteres Aufräumen vorbereitet.
- SimpleJWT 5.5 nennt offiziell nur Django bis 5.2. Mit Django 6.1 ist es durch die Testsuite abgesichert.
- **Ausgelegt für die lokale Entwicklung:** `python manage.py check --deploy` weist auf HTTPS-Einstellungen hin (HSTS, SSL-Redirect, Secure-Cookies). Für den Produktivbetrieb wären HTTPS, `AUTH_COOKIE_SECURE=True`, ein starker `DJANGO_SECRET_KEY` und eine Produktiv-Datenbank nötig.

**Grenzen des vorgegebenen Frontends (nicht Teil dieses Backends):**
- Bei Registrierungsfehlern zeigt das Frontend nur Fehler zum Feld `username` an. Fehler zu E-Mail oder Passwort erscheinen als „undefined“, obwohl die API sie korrekt liefert.
- Der Spielfortschritt liegt nur im Arbeitsspeicher des Browsers. Nach einem Reload ist er weg, und es gibt keinen API-Endpoint dafür.
- Impressum und Datenschutz enthalten im Frontend Platzhaltertext.
