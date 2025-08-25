import os
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# =============================
# LOGGING
# =============================
log_filename = f"presensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename, mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# =============================
# DRIVER SETUP
# =============================
def setup_driver():
    logging.info("⚙️ Mengatur driver...")
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})
        options.add_argument("--log-level=3")
        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(90)
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal setup driver: {e}")
        return None

# =============================
# LOGIN
# =============================
def login(driver, username, password):
    url_login = "https://dani.perhutani.co.id/login"
    logging.info("🌐 Membuka halaman login...")
    driver.get(url_login)

    wait = WebDriverWait(driver, 30)
    try:
        user_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='NPK']")))
        pass_input = driver.find_element(By.XPATH, "//input[@placeholder='Password']")
        user_input.send_keys(username)
        pass_input.send_keys(password)
        login_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Login') or @type='submit']")
        login_btn.click()
        logging.info("🔐 Login dikirim.")
    except Exception as e:
        logging.error(f"❌ Gagal login: {e}")
        return False
    return True

# =============================
# HAPUS POPUP/MODAL
# =============================
def clear_modal(driver):
    try:
        driver.execute_script("""
            let modals = document.querySelectorAll('.modal.show, .modal.fade.show, #announcement');
            modals.forEach(m => m.remove());
        """)
        logging.info("❎ Modal dihapus pakai JS.")
    except Exception:
        pass

# =============================
# CARI DAN KLIK POPUP
# =============================
def click_popup(driver, attempt):
    try:
        popup_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((
            By.XPATH,
            "//*[contains(text(),'Klik Disini Untuk Presensi') or contains(text(),'Presensi') or @class='btn btn-warning']"
        )))
        popup_btn.click()
        logging.info(f"🖱️ Klik tombol popup presensi (percobaan {attempt}).")
        time.sleep(2)
        return True
    except TimeoutException:
        logging.warning(f"⚠️ Popup presensi tidak muncul (percobaan {attempt}).")
        clear_modal(driver)
        time.sleep(2)
        return False

# =============================
# CEK STATUS PRESENSI
# =============================
def get_status(driver):
    try:
        status_div = WebDriverWait(driver, 10).until(EC.presence_of_element_located((
            By.XPATH, "//div[contains(text(),'Sudah Check In') or contains(text(),'Sudah Check Out')]"
        )))
        return status_div.text.strip()
    except TimeoutException:
        return None

# =============================
# PRESENSI
# =============================
def do_presensi(driver, username, mode):
    wait = WebDriverWait(driver, 20)

    try:
        presensi_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(@href,'/presensi') or contains(text(),'Presensi')]")
        ))
        presensi_btn.click()
        logging.info("✅ Klik: Tombol Presensi Utama.")
        time.sleep(2)

        success = False
        for attempt in range(1, 4):
            if not click_popup(driver, attempt):
                continue

            status = get_status(driver)
            if status:
                logging.info(f"ℹ️ Status terdeteksi: {status}")
                if mode == "check_in" and "Sudah Check In" in status:
                    logging.info("🎉 Presensi check_in berhasil!")
                    success = True
                    break
                elif mode == "check_out" and "Sudah Check Out" in status:
                    logging.info("🎉 Presensi check_out berhasil!")
                    success = True
                    break
                else:
                    logging.warning(f"⚠️ Status belum sesuai mode {mode}, coba ulang...")
                    time.sleep(2)
            else:
                logging.warning("⚠️ Tidak menemukan indikator status.")
        if not success:
            logging.error(f"❌ Presensi {mode} gagal setelah 3 percobaan.")
        return success

    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan: {e}")
        return False
    finally:
        logging.info("🚪 Keluar dari browser.")
        driver.quit()

# =============================
# MAIN
# =============================
if __name__ == "__main__":
    mode = os.environ.get("MODE", "check_in")
    username = os.environ.get("USER1_USERNAME")
    password = os.environ.get("USER1_PASSWORD")

    if not username or not password:
        logging.error("❌ Username/Password tidak ditemukan di secrets untuk USER1!")
        exit(1)

    logging.info(f"⏰ Mulai proses presensi untuk USER1 (mode: {mode})...")
    driver = setup_driver()
    if driver and login(driver, username, password):
        clear_modal(driver)
        success = do_presensi(driver, username, mode)
        if not success:
            exit(1)
    else:
        exit(1)
