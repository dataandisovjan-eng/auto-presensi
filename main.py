import os
import requests
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv

load_dotenv()
USERNAME = os.getenv("NPK")
PASSWORD = os.getenv("PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

URL_LOGIN = "https://dani.perhutani.co.id"
LIBUR_API = "https://api-harilibur.vercel.app/api"

def send_telegram(msg: str):
    token = TELEGRAM_TOKEN
    chat_id = TELEGRAM_CHAT_ID
    if not token or not chat_id:
        print("[INFO] TELEGRAM_TOKEN/TELEGRAM_CHAT_ID belum di-set; lewati notifikasi.")
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": msg}, timeout=15)
    except Exception as e:
        print("[WARN] Gagal kirim Telegram:", e)

def is_libur(date_str: str) -> bool:
    try:
        resp = requests.get(LIBUR_API, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for libur in data:
            if libur.get("is_national") and libur.get("holiday_date") == date_str:
                return True
        return False
    except Exception as e:
        print("[WARN] Gagal cek API libur:", e)
        return False

def build_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0")
    chrome_binary = os.getenv("CHROME_BINARY", "/usr/bin/chromium")
    chromedriver_path = os.getenv("CHROMEDRIVER", "/usr/bin/chromedriver")
    if os.path.exists(chrome_binary):
        chrome_options.binary_location = chrome_binary
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(60)
    return driver

def presensi():
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday()

    if weekday >= 5:
        send_telegram("📅 Weekend, presensi skip.")
        return
    if is_libur(today_str):
        send_telegram("📅 Libur nasional, presensi skip.")
        return

    driver = build_driver()
    wait = WebDriverWait(driver, 25)

    try:
        driver.get(URL_LOGIN)
        wait.until(EC.presence_of_element_located((By.NAME, "npk"))).send_keys(USERNAME or "")
        driver.find_element(By.NAME, "password").send_keys(PASSWORD or "")
        driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
        time.sleep(2)

        page_source = driver.page_source
        if "Klik Disini Untuk Presensi" in page_source:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Klik Disini Untuk Presensi')]")))
            btn.click()
            time.sleep(2)
            send_telegram("✅ Presensi berhasil dilakukan.")
            return

        if any(s in page_source for s in ["Sudah Check In", "Sudah Check Out", "Sudah Presensi"]):
            send_telegram("✅ Sudah presensi, tidak perlu klik.")
            return

        send_telegram("⚠️ Tidak menemukan tombol/status presensi di halaman.")
    except Exception as e:
        send_telegram(f"❌ Gagal presensi: {e}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    missing = [k for k in ["NPK", "PASSWORD", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"] if not os.getenv(k)]
    if missing:
        print(f"[WARN] Variabel env berikut belum di-set: {', '.join(missing)}")
    presensi()
