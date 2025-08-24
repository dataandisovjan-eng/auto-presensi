import os
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# --- Logging ---
os.makedirs("artifacts", exist_ok=True)
log_filename = f"artifacts/presensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(log_filename, "a", "utf-8"), logging.StreamHandler()],
)

URL_LOGIN = "https://dani.perhutani.co.id/login"


def setup_driver():
    logging.info("⚙️ Mengatur driver...")
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(90)
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal inisialisasi driver: {e}")
        return None


def do_presensi(user_prefix: str, username: str, password: str, mode: str):
    driver = setup_driver()
    if not driver:
        return False

    try:
        logging.info(f"🌐 [{user_prefix}] Membuka halaman login...")
        driver.get(URL_LOGIN)

        wait = WebDriverWait(driver, 30)

        # Input login
        try:
            user_input = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='NPK' or @name='npk']"))
            )
            pass_input = driver.find_element(By.XPATH, "//input[@placeholder='Password' or @type='password']")
            user_input.send_keys(username)
            pass_input.send_keys(password)
            login_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Login') or @type='submit']")
            login_btn.click()
            logging.info(f"🔐 [{user_prefix}] Login dikirim.")
        except Exception as e:
            logging.error(f"❌ [{user_prefix}] Gagal login: {e}")
            driver.quit()
            return False

        # Handle popup Next/Finish
        try:
            while True:
                next_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Next') or contains(text(),'next')]"))
                )
                next_btn.click()
                time.sleep(1)
                logging.info(f"⏭️ [{user_prefix}] Klik Next")
        except TimeoutException:
            logging.info(f"⚠️ [{user_prefix}] Tidak ada tombol Next lagi.")

        try:
            finish_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Finish') or contains(text(),'Selesai')]"))
            )
            finish_btn.click()
            logging.info(f"🏁 [{user_prefix}] Klik Finish")
        except TimeoutException:
            logging.info(f"⚠️ [{user_prefix}] Tidak menemukan tombol Finish, lanjut.")

        # Hapus modal penghalang
        try:
            driver.execute_script(
                "document.querySelectorAll('.modal, .swal-overlay').forEach(e => e.remove());"
            )
            logging.info(f"🛑 [{user_prefix}] Modal dihapus pakai JS.")
        except Exception:
            pass

        # Klik tombol presensi utama
        try:
            presensi_btn = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(text(),'Klik Disini Untuk Presensi') or contains(@href,'/presensi')]")
                )
            )
            presensi_btn.click()
            logging.info(f"✅ [{user_prefix}] Klik: Tombol Presensi Utama.")
        except TimeoutException:
            logging.error(f"❌ [{user_prefix}] Tombol presensi utama tidak ditemukan.")
            driver.save_screenshot(f"artifacts/{user_prefix}_presensi_btn_missing.png")
            driver.quit()
            return False

        # Tunggu popup presensi & klik
        try:
            presensi_popup_btn = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(),'Klik Disini Untuk Presensi') or contains(@class,'swal-button--confirm')]")
                )
            )
            presensi_popup_btn.click()
            logging.info(f"✅ [{user_prefix}] Klik tombol popup presensi.")
            time.sleep(3)
        except TimeoutException:
            logging.error(f"❌ [{user_prefix}] Tombol popup presensi tidak ditemukan.")
            driver.save_screenshot(f"artifacts/{user_prefix}_popup_presensi_missing.png")
            driver.quit()
            return False

        # Verifikasi presensi sukses
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(text(),'Presensi berhasil') or contains(text(),'Anda telah melakukan presensi') or contains(@class,'text-success')]")
                )
            )
            logging.info(f"🎉 [{user_prefix}] Presensi berhasil!")
            return True
        except TimeoutException:
            logging.warning(f"⚠️ [{user_prefix}] Pesan konfirmasi presensi tidak muncul.")
            driver.save_screenshot(f"artifacts/{user_prefix}_presensi_notif_missing.png")
            return False

    finally:
        driver.quit()
        logging.info(f"🚪 [{user_prefix}] Keluar dari browser.")


def main():
    logging.info("⏰ Mulai proses presensi...")
    users = [
        ("USER1", os.environ.get("USER1_USERNAME"), os.environ.get("USER1_PASSWORD")),
        ("USER2", os.environ.get("USER2_USERNAME"), os.environ.get("USER2_PASSWORD")),
    ]
    mode = os.environ.get("FORCE_MODE", "check_in")

    for prefix, user, pw in users:
        if not user or not pw:
            logging.error(f"❌ Username/Password tidak ditemukan di secrets untuk {prefix}!")
            continue
        do_presensi(prefix, user, pw, mode)


if __name__ == "__main__":
    main()
