import os
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# =======================
# Setup Logging
# =======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


# =======================
# Secrets Loader
# =======================
def get_credentials(user_alias="USER1"):
    """
    Ambil username & password dari GitHub Secrets.
    Mencoba beberapa kemungkinan nama secrets.
    """
    alternatives = [
        (f"{user_alias}_USERNAME", f"{user_alias}_PASSWORD"),
        (f"{user_alias}_USER", f"{user_alias}_PASS"),
        (f"{user_alias}_ID", f"{user_alias}_PWD"),
        (f"{user_alias}_NPK", f"{user_alias}_PASSWORD"),
        (f"{user_alias}_USERNAME", f"{user_alias}_PASS"),
    ]

    for user_key, pass_key in alternatives:
        username = os.getenv(user_key)
        password = os.getenv(pass_key)
        if username and password:
            logging.info(f"✅ Kredensial ditemukan pakai {user_key}/{pass_key}")
            return username, password

    logging.error(f"❌ Username/Password tidak ditemukan di secrets untuk {user_alias}!")
    return None, None


# =======================
# Selenium Presensi
# =======================
def presensi(username, password, mode="check_in"):
    logging.info("⚙️ Mengatur driver...")
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--headless=new")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    wait = WebDriverWait(driver, 15)

    try:
        logging.info("🌐 Buka halaman login...")
        driver.get("https://dani.perhutani.co.id/")

        # Input NPK
        logging.info("🔎 Cari field NPK...")
        npk_field = wait.until(EC.presence_of_element_located((By.ID, "npk")))
        npk_field.send_keys(username)

        # Input Password
        pwd_field = driver.find_element(By.ID, "password")
        pwd_field.send_keys(password)

        # Klik tombol login
        login_btn = driver.find_element(By.XPATH, "//button[contains(., 'Login')]")
        login_btn.click()
        logging.info("✅ Klik tombol login.")

        # Tunggu pop-up jika ada
        logging.info("🔎 Mencari pop-up untuk ditutup...")
        time.sleep(5)
        try:
            next_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Next')]")
            for idx, btn in enumerate(next_buttons, 1):
                btn.click()
                logging.info(f"⏭️ Klik Next (total: {idx})")
                time.sleep(1)
        except Exception:
            logging.info("⚠️ Tidak menemukan tombol Finish, lanjut.")

        # Hapus modal kalau masih ada
        logging.info("🛑 Periksa modal/pop-up aktif...")
        try:
            driver.execute_script("""
                let modal = document.querySelector('#announcement');
                if (modal) { modal.remove(); }
            """)
            logging.info("❎ Modal dihapus pakai JS.")
        except Exception:
            logging.info("ℹ️ Tidak ada modal aktif.")

        # Tunggu tombol presensi utama
        logging.info("⏳ Menunggu tombol presensi utama...")
        presensi_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'presensi')]")))
        presensi_btn.click()
        logging.info("✅ Klik: Tombol Presensi Utama.")

        # Tunggu pesan notifikasi
        try:
            notif = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "swal2-title")))
            logging.info(f"🎉 Presensi berhasil: {notif.text}")
        except Exception:
            logging.warning("⚠️ Pesan konfirmasi presensi tidak ditemukan.")
            filename = f"presensi_notif_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(filename)
            logging.info(f"📸 Screenshot disimpan: {filename}")

    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan: {e}")
    finally:
        logging.info("🚪 Keluar dari browser.")
        driver.quit()


# =======================
# Main Execution
# =======================
if __name__ == "__main__":
    logging.info("⏰ Mulai proses presensi...")

    # Ambil kredensial (contoh pakai USER1 → Andi)
    username, password = get_credentials("USER1")
    if not username or not password:
        exit(1)

    # Jalankan presensi
    presensi(username, password, mode="check_in")

    logging.info("✅ Selesai.")
