import os
import argparse
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 📌 Setup logging
os.makedirs("artifacts", exist_ok=True)
log_file = f"artifacts/presensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
)

def get_credentials(user):
    username = os.getenv(f"{user}_USERNAME")
    password = os.getenv(f"{user}_PASSWORD")

    if not username or not password:
        logging.error(f"❌ Username/Password tidak ditemukan di secrets untuk {user}!")
        raise SystemExit(1)

    return username, password

def run_presensi(user, mode):
    logging.info(f"⏰ Mulai proses presensi untuk {user} - mode {mode}...")

    username, password = get_credentials(user)

    # ✅ Setup webdriver headless
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        logging.info("🌐 Membuka halaman login...")
        driver.get("https://dani.perhutani.co.id/")

        # 🔑 Login
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "npk"))
        ).send_keys(username)

        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]").click()
        logging.info("✅ Login berhasil, masuk sistem.")

        # Tutup popup kalau ada
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "announcement"))
            )
            driver.execute_script("""
                let modal = document.getElementById('announcement');
                if(modal) { modal.remove(); }
            """)
            logging.info("✅ Popup ditutup pakai JS.")
        except:
            logging.info("⚠️ Tidak ada popup aktif.")

        # Klik presensi
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Presensi"))
        ).click()
        logging.info("✅ Klik tombol Presensi.")

        # Konfirmasi
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "swal2-title"))
            )
            logging.info("✅ Konfirmasi presensi muncul.")
        except:
            fname = f"artifacts/presensi_notif_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(fname)
            logging.warning(f"⚠️ Pesan konfirmasi presensi tidak ditemukan. Screenshot: {fname}")

    except Exception as e:
        fname = f"artifacts/error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        driver.save_screenshot(fname)
        logging.error(f"❌ Terjadi kesalahan: {e}")
    finally:
        driver.quit()
        logging.info("🚪 Keluar dari browser.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="USER1", help="Pilih USER1 atau USER2")
    parser.add_argument("--mode", default="check_in", help="Mode: check_in / check_out")
    args = parser.parse_args()

    run_presensi(args.user, args.mode)
