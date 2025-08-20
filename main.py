import os
import json
import time
import logging
from datetime import datetime
import requests
import pytz

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "https://dani.perhutani.co.id"

# ================= Logging & folder =================
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/presensi.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def save_snap(driver, user_id: str, step: str):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    png = f"logs/{user_id}_{step}_{ts}.png"
    html = f"logs/{user_id}_{step}_{ts}.html"
    try:
        driver.save_screenshot(png)
    except Exception:
        pass
    try:
        with open(html, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except Exception:
        pass
    logging.info(f"[{user_id}] 📸 Saved {png} & {html}")

# Robust click: scroll + JS fallback
def safe_click(driver, elem):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
    try:
        elem.click()
    except Exception:
        driver.execute_script("arguments[0].click();", elem)

# Case-insensitive XPath contains
def ci_contains(text):
    return f"contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')"

# ================= Hari libur & weekend =================
def is_weekend(now_local):
    return now_local.weekday() >= 5  # 5=Sabtu, 6=Minggu

def is_holiday(now_local):
    try:
        year = now_local.year
        url = f"https://dayoffapi.vercel.app/api?year={year}"
        r = requests.get(url, timeout=15)
        data = r.json()
        today = now_local.strftime("%Y-%m-%d")

        holidays = []
        # API kadang dict {data: [...]}, kadang list [...]
        if isinstance(data, dict) and "data" in data:
            for item in data["data"]:
                tgl = item.get("tanggal") or item.get("date") or item.get("tgl")
                if tgl: holidays.append(tgl)
        elif isinstance(data, list):
            for item in data:
                tgl = item.get("tanggal") or item.get("date") or item.get("tgl")
                if tgl: holidays.append(tgl)

        if today in holidays:
            logging.info("📌 Hari libur nasional. Skip presensi.")
            return True
    except Exception as e:
        logging.warning(f"⚠️ Gagal cek API libur: {e}")
    return False

# ================== Selenium session ==================
def start_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1366,900")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def handle_tour_popups(driver, wait, user_id):
    # Klik Next berulang, lalu Finish bila ada
    while True:
        try:
            next_btn = wait.until(EC.element_to_be_clickable((
                By.XPATH, f"//*[self::button or self::a][{ci_contains('next')}]"
            )))
            safe_click(driver, next_btn)
            logging.info(f"[{user_id}] ➡️ Klik Next")
            save_snap(driver, user_id, "popup_next")
            time.sleep(0.8)
        except Exception:
            break
    # Finish (jika ada)
    try:
        finish_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((
            By.XPATH, f"//*[self::button or self::a][{ci_contains('finish')}]"
        )))
        safe_click(driver, finish_btn)
        logging.info(f"[{user_id}] 🏁 Klik Finish")
        save_snap(driver, user_id, "popup_finish")
        time.sleep(1)
    except Exception:
        logging.info(f"[{user_id}] Tidak ada tombol Finish, lanjut dashboard.")

def do_presensi_for_user(user: dict, mode: str):
    user_id = user.get("id") or user.get("name") or user.get("secret_user") or "user"
    username = os.getenv(user["secret_user"], "").strip()
    password = os.getenv(user["secret_pass"], "").strip()

    if not username or not password:
        logging.warning(f"[{user_id}] ⚠️ Secrets kosong. Pastikan {user['secret_user']} & {user['secret_pass']} diset di repo Settings → Secrets.")
        return

    driver = start_driver()
    wait = WebDriverWait(driver, 30)

    try:
        # Login page
        logging.info(f"[{user_id}] 🌐 Buka halaman login")
        driver.get(BASE_URL)
        save_snap(driver, user_id, "open_login")

        # Login
        wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        safe_click(driver, driver.find_element(By.CSS_SELECTOR, "button[type='submit']"))
        logging.info(f"[{user_id}] 🔑 Submit login")
        save_snap(driver, user_id, "after_login_click")
        time.sleep(2)

        # Handle tour popups
        handle_tour_popups(driver, wait, user_id)

        # Tombol oranye: "Klik disini untuk presensi"
        presensi_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH, f"//*[self::button or self::a][{ci_contains('klik disini untuk presensi')}]"
        )))
        safe_click(driver, presensi_btn)
        logging.info(f"[{user_id}] 🟠 Klik tombol presensi utama")
        save_snap(driver, user_id, "clicked_main_presensi")

        # Popup konfirmasi: klik lagi "Klik disini untuk presensi"
        popup_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH, f"//*[self::button or self::a][{ci_contains('klik disini untuk presensi')}]"
        )))
        safe_click(driver, popup_btn)
        logging.info(f"[{user_id}] ✅ Klik tombol presensi di popup ({mode})")
        save_snap(driver, user_id, "clicked_popup_presensi")

    except Exception as e:
        logging.error(f"[{user_id}] ❌ Gagal presensi: {e}")
        save_snap(driver, user_id, "error")
    finally:
        driver.quit()

def should_run_for_user(now_local, user: dict):
    hhmm = now_local.strftime("%H:%M")
    return hhmm == user.get("check_in") or hhmm == user.get("check_out")

def main():
    # Load config
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        logging.error(f"Config error: {e}")
        return

    tz = pytz.timezone(cfg.get("timezone", "Asia/Jakarta"))
    now_local = datetime.now(tz)
    logging.info(f"⏰ Sekarang {now_local.strftime('%Y-%m-%d %H:%M')} ({cfg.get('timezone','Asia/Jakarta')})")

    # Skip weekend/libur nasional (global)
    if is_weekend(now_local):
        logging.info("🚫 Weekend. Skip semua user.")
        return
    if is_holiday(now_local):
        return

    users = cfg.get("users", [])
    if not users:
        logging.warning("Tidak ada user di config.json")
        return

    for user in users:
        if should_run_for_user(now_local, user):
            mode = "pagi" if now_local.strftime("%H:%M") == user.get("check_in") else "sore"
            logging.info(f"[{user.get('id','user')}] ▶️ Waktunya presensi {mode}")
            do_presensi_for_user(user, mode)
        else:
            logging.info(f"[{user.get('id','user')}] Skip (bukan jadwal user ini).")

if __name__ == "__main__":
    main()
