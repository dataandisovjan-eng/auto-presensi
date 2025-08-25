import os
import sys
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ================== LOGGING ==================
log_filename = f"presensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# ================== DRIVER SETUP ==================
def setup_driver():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2
    })

    service = ChromeService()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(90)
    return driver

# ================== PRESENSI FUNCTION ==================
def do_presensi(user, username, password, mode="check_in"):
    logging.info(f"⏰ Mulai proses presensi untuk {user}...")

    if not username or not password:
        logging.error(f"❌ Username/Password tidak ditemukan di secrets untuk {user}!")
        return False

    driver = None
    try:
        driver = setup_driver()
        wait = WebDriverWait(driver, 30)

        # 1. Buka halaman login
        logging.info(f"🌐 [{user}] Membuka halaman login...")
        driver.get("https://dani.perhutani.co.id/login")

        # 2. Isi login
        username_input = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//input[@placeholder='NPK']")))
        password_input = driver.find_element(
            By.XPATH, "//input[@placeholder='Password']")
        username_input.send_keys(username)
        password_input.send_keys(password)
        login_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(),'Login') or contains(text(),'Masuk')]")))
        login_btn.click()
        logging.info(f"🔐 [{user}] Login dikirim.")

        # 3. Tutup popup announcement jika ada
        try:
            time.sleep(3)
            driver.execute_script("""
                var modals=document.getElementsByClassName('modal');
                for(var i=0;i<modals.length;i++){modals[i].remove();}
            """)
            logging.info(f"❎ [{user}] Modal dihapus pakai JS.")
        except Exception:
            pass

        # 4. Klik tombol presensi utama
        presensi_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(.,'Presensi') or contains(@href,'presensi')] | //i[contains(@class,'fa-fingerprint')]")))
        presensi_btn.click()
        logging.info(f"✅ [{user}] Klik: Tombol Presensi Utama.")

        # 5. Tunggu popup presensi
        time.sleep(5)  # kasih waktu popup muncul
        try:
            popup_btn = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((
                By.XPATH,
                "//*[contains(text(),'Klik Disini Untuk Presensi') "
                "or contains(@class,'btn-warning') "
                "or contains(@class,'btn-presensi') "
                "or contains(@class,'btn') and contains(.,'Presensi')]"
            )))
            popup_btn.click()
            logging.info(f"🖱️ [{user}] Klik tombol popup presensi.")
        except TimeoutException:
            logging.error(f"❌ [{user}] Popup presensi tidak muncul.")
            screenshot = f"presensi_popup_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            html_dump = f"presensi_popup_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            driver.save_screenshot(screenshot)
            with open(html_dump, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logging.warning(f"📸 Screenshot disimpan: {screenshot}")
            logging.warning(f"📝 HTML halaman disimpan: {html_dump}")
            return False

        # 6. Verifikasi berhasil
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class,'card') and (contains(.,'Checkin') or contains(.,'Checkout')) and contains(@class,'bg-success')]")))
            logging.info(f"🎉 [{user}] Presensi {mode} berhasil!")
            return True
        except TimeoutException:
            logging.warning(f"⚠️ [{user}] Tidak menemukan indikator keberhasilan.")
            screenshot = f"presensi_notif_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(screenshot)
            logging.warning(f"📸 Screenshot disimpan: {screenshot}")
            return False

    except Exception as e:
        logging.error(f"❌ [{user}] Terjadi kesalahan: {e}")
        return False
    finally:
        if driver:
            driver.quit()
            logging.info(f"🚪 [{user}] Keluar dari browser.")

# ================== MAIN ==================
if __name__ == "__main__":
    USERS = {
        "USER1": {
            "username": os.environ.get("USER1_USERNAME"),
            "password": os.environ.get("USER1_PASSWORD")
        }
    }

    success = True
    for key, creds in USERS.items():
        if creds["username"] and creds["password"]:
            ok = do_presensi(key, creds["username"], creds["password"], mode="check_in")
            if not ok:
                success = False
        else:
            logging.error(f"❌ Username/Password tidak ditemukan di secrets untuk {key}!")
            success = False

    if not success:
        sys.exit(1)
