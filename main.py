import os
import time
import base64
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ========== KONFIGURASI ==========
URL_LOGIN = "https://dani.perhutani.co.id/"
ARTIFACT_DIR = "artifacts"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

USERS = {
    "USER1": {
        "username": os.getenv("USER1_USERNAME"),
        "password": os.getenv("USER1_PASSWORD")
    },
    "USER2": {
        "username": os.getenv("USER2_USERNAME"),
        "password": os.getenv("USER2_PASSWORD")
    },
}

# Lokasi dummy (koordinat kantor)
DUMMY_LAT = "-6.2988228"
DUMMY_LONG = "106.8328309"
DUMMY_LOKASI = "Simulasi lokasi kantor"

# Foto dummy base64 (1×1 px PNG hitam)
DUMMY_BASE64 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/w8AAwMCAO2sUAAAAABJRU5ErkJggg=="
)

# Mode bisa "check_in" atau "check_out"
MODE = os.getenv("MODE", "check_in")

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ========== UTIL ==========

def save_artifacts(driver, prefix):
    """Simpan screenshot & HTML untuk debugging"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(ARTIFACT_DIR, f"{prefix}_{ts}.png")
    html_path = os.path.join(ARTIFACT_DIR, f"{prefix}_{ts}.html")
    try:
        driver.save_screenshot(screenshot_path)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logging.warning(f"📸 Screenshot disimpan: {screenshot_path}")
        logging.warning(f"📝 HTML disimpan: {html_path}")
    except Exception as e:
        logging.error(f"Gagal simpan artifact: {e}")

def setup_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-notifications")
    driver = webdriver.Chrome(options=opts)
    driver.set_window_size(1280, 800)
    return driver

def login(driver, username, password):
    driver.get(URL_LOGIN)
    logging.info("🌐 Membuka halaman login...")
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.NAME, "npk"))
    )
    driver.find_element(By.NAME, "npk").send_keys(username)
    driver.find_element(By.NAME, "password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    logging.info("🔐 Login dikirim.")
    time.sleep(3)

def close_modals(driver):
    # Hapus modal pop-up jika ada
    driver.execute_script("""
        var modals = document.querySelectorAll('.modal.show');
        modals.forEach(m => m.remove());
    """)
    logging.info("❎ Modal dihapus pakai JS.")

def isi_form_presensi(driver):
    """Bypass lokasi & isi form presensi"""
    driver.execute_script(f"""
        document.getElementById('result_lat').value = "{DUMMY_LAT}";
        document.getElementById('result_long').value = "{DUMMY_LONG}";
        document.getElementById('lokasi').value = "{DUMMY_LOKASI}";
        document.getElementById('fotobase64').value = "{DUMMY_BASE64}";
    """)
    logging.info("📍 Lokasi & foto dummy diisi.")

def presensi(driver, user, mode):
    try:
        login(driver, user["username"], user["password"])
        close_modals(driver)

        # Klik tombol utama
        btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(.,'Presensi')]"))
        )
        btn.click()
        logging.info("✅ Klik: Tombol Presensi Utama.")

        # Tunggu popup presensi
        popup = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "announcement"))
        )
        logging.info("🖱️ Popup presensi muncul.")

        # Isi form dummy
        isi_form_presensi(driver)

        # Klik tombol presensi di popup
        submit = driver.find_element(By.ID, "presensi")
        submit.click()
        logging.info(f"🖱️ Klik tombol presensi untuk {mode}.")

        # Verifikasi status
        time.sleep(5)
        page_text = driver.find_element(By.TAG_NAME, "body").text
        if mode == "check_in" and "Sudah Check In" in page_text:
            logging.info(f"🎉 Presensi {mode} berhasil! Status: Sudah Check In")
            return True
        elif mode == "check_out" and "Sudah Check Out" in page_text:
            logging.info(f"🎉 Presensi {mode} berhasil! Status: Sudah Check Out")
            return True
        else:
            logging.warning("⚠️ Tidak menemukan indikator keberhasilan.")
            save_artifacts(driver, f"status_not_updated_{mode}")
            return False

    except Exception as e:
        logging.error(f"❌ Presensi gagal: {e}")
        save_artifacts(driver, f"presensi_error_{mode}")
        return False

# ========== MAIN ==========
if __name__ == "__main__":
    logging.info(f"⏰ Mulai proses presensi (mode: {MODE})...")

    driver = setup_driver()
    success = False

    if USERS["USER1"]["username"] and USERS["USER1"]["password"]:
        success = presensi(driver, USERS["USER1"], MODE)
    else:
        logging.error("❌ Username/Password tidak ditemukan di secrets untuk USER1!")

    driver.quit()
    if not success:
        raise SystemExit(1)
