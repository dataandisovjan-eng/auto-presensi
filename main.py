import os
import json
import logging
from datetime import datetime, timedelta
import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# === Load config.json ===
with open("config.json", "r") as f:
    config = json.load(f)

TIMEZONE = pytz.timezone(config.get("timezone", "Asia/Jakarta"))

# === Fungsi cek waktu fleksibel ===
def is_time_to_presensi(now, target_time, tolerance=10):
    """
    Cek apakah waktu sekarang masuk dalam range target_time ± tolerance (menit).
    """
    target = datetime.strptime(target_time, "%H:%M").time()
    target_dt = now.replace(hour=target.hour, minute=target.minute, second=0, microsecond=0)

    delta = abs((now - target_dt).total_seconds() / 60.0)
    return delta <= tolerance

# === Fungsi presensi ===
def presensi(username, password, action="checkin"):
    url = "https://dani.perhutani.co.id"
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
        wait = WebDriverWait(driver, 15)

        logging.info("🌐 Membuka halaman login...")
        driver.get(url)

        # Login
        wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(username)
        wait.until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(password)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Login')]"))).click()

        # Tutup pop-up pemberitahuan (bisa muncul 0,1 atau banyak)
        try:
            while True:
                popup_next = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'Next') or contains(text(),'Finish')]")))
                popup_next.click()
                logging.info("👉 Popup diklik (Next/Finish).")
        except:
            logging.info("✅ Tidak ada popup lagi.")

        # Klik tombol presensi (halaman utama)
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]")))
        btn.click()
        logging.info("🟠 Tombol presensi utama diklik.")

        # Klik tombol presensi di pop-up terakhir
        popup_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]")))
        popup_btn.click()
        logging.info("✅ Presensi berhasil dikirim.")

        driver.quit()
    except Exception as e:
        logging.error(f"❌ Error saat presensi: {e}")

# === Main loop untuk semua user ===
def main():
    now = datetime.now(TIMEZONE)
    logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} ({config['timezone']})")

    for user in config["users"]:
        uname = os.getenv(user["secret_user"])
        pwd = os.getenv(user["secret_pass"])

        if not uname or not pwd:
            logging.warning(f"[{user['id']}] {user['name']} → Username/password belum diatur di Secrets!")
            continue

        do_checkin = is_time_to_presensi(now, user["check_in"])
        do_checkout = is_time_to_presensi(now, user["check_out"])

        if do_checkin:
            logging.info(f"[{user['id']}] {user['name']} → Saatnya presensi pagi.")
            presensi(uname, pwd, "checkin")
        elif do_checkout:
            logging.info(f"[{user['id']}] {user['name']} → Saatnya presensi sore.")
            presensi(uname, pwd, "checkout")
        else:
            logging.info(f"[{user['id']}] {user['name']} → Skip (bukan jadwal user ini).")

if __name__ == "__main__":
    main()
