# Recoon Bot 🎮

Discord games & economy bot — coin flip, aviator crash game, music player (24/7 voice), coin requests/transfers, daily rewards aur per-server prefix.

## Local Setup (Windows)

1. Python 3.11+ install karo, phir:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Project folder me `.env` file banao:
   ```
   DISCORD_TOKEN=tumhara_bot_token
   ```
3. `ffmpeg.exe` project folder me rakho (music bot ke liye) — ya PATH me install karo.
4. `start.bat` chalao ya `python bot.py`.

## Render pe Hosting (Docker runtime)

Repo me sab ready hai: `Dockerfile` (python + ffmpeg), `render.yaml` (Background Worker + persistent disk).

### Steps
1. Render dashboard → **New +** → **Blueprint** → apna GitHub repo (`kp5621279-cell/recoon_bot`) select karo.
2. Render `render.yaml` padh lega aur **recoon-bot** worker bana dega.
3. Env var **`DISCORD_TOKEN`** set karo (Render dashboard → Environment → Add):
   - Value: tumhara Discord bot token (Developer Portal → Bot → Reset Token).
4. **Apply** → deploy hoga (Docker build me ffmpeg automatically install ho jata hai, `ffmpeg.exe` ki zaroorat nahi).
5. Bot Discord me **online** dikhega.

### Zaroori baatein
- **Free plan mat use karna web service ke liye** — Render free web service 15 min idle hone par **so jata hai** (bot offline). Discord bot ke liye **Background Worker (starter, ~$7/mo)** chahiye jo 24/7 chalta hai.
- `DATA_DIR=/var/data` se database **persistent disk** par save hota hai — deploy/restart par coins udte nahi. Blueprint me 1GB disk already configured hai.
- Worker logs dekhne ke liye: Render dashboard → recoon-bot → **Logs**.
- Git push karne par Render **auto-deploy** kar dega (default on).

### Local vs Render ka difference
| | Local PC | Render |
|---|---|---|
| Token | `.env` file | Dashboard env var |
| ffmpeg | `ffmpeg.exe` (folder me) | Dockerfile se install |
| Database | `bot_data.db` (project folder) | `/var/data/bot_data.db` (disk) |

## Commands
| Command | Kaam |
|---|---|
| `!coin <bet> <h/t>` | Coin flip gambling |
| `!aviator <bet>` | Crash game (auto cashout set karo) |
| `!bal` / `!daily` | Balance / 12h reward |
| `!pay` / `!req` | Coins bhejo / maango |
| `!play` / `!skip` / `!stop` | Music |
| `!set p <prefix>` | Server ka prefix badlo |
| `!ping` / `!invite` / `!help` | Utility |
