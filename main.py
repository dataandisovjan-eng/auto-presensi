import sys
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# Konfigurasi logging untuk mencatat aktivitas skrip ke dalam file
log_filename = "presensi.log"
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[
                        logging.FileHandler(log_filename, mode='a', encoding='utf-8'),
                        logging.StreamHandler(sys.stdout)
                    ])

def setup_driver():
    """Mengatur dan menginisialisasi WebDriver."""
    logging.info("⚙️ Mengatur driver...")
    try:
        chrome_options = webdriver.ChromeOptions()
        # Nonaktifkan notifikasi pop-up browser
        chrome_options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})
        # Tambahkan opsi untuk mode headless agar tidak membuka jendela browser
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3")  # Matikan logging dari browser
        
        # Menggunakan Service() tanpa WebDriverManager.
        # Ini akan bekerja di lingkungan yang sudah memiliki chromedriver di PATH.
        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

def main():
    """Fungsi utama untuk menjalankan skrip presensi."""
    # Definisikan kredensial
    # PENTING: Skrip ini sekarang mencari nama variabel yang Anda gunakan di GitHub Secrets.
    # Nama variabel yang digunakan adalah: USER1_USERNAME dan USER1_PASSWORD.
    username = os.environ.get('USER1_USERNAME')
    password = os.environ.get('USER1_PASSWORD')
    url_login = "https://dani.perhutani.co.id/login"

    # Periksa ketersediaan kredensial
    if not username:
        logging.error("❌ Kredensial tidak ditemukan. Pastikan USER1_USERNAME sudah diatur di environment variable.")
    if not password:
        logging.error("❌ Kredensial tidak ditemukan. Pastikan USER1_PASSWORD sudah diatur di environment variable.")

    if not username or not password:
        logging.error("➡️ CARA MEMPERBAIKI:")
        logging.error("   1. Jika menggunakan GitHub Actions, tambahkan 'USER1_USERNAME' dan 'USER1_PASSWORD' ke Secrets repository.")
        logging.error("   2. Jika berjalan secara lokal, atur variabel lingkungan 'USER1_USERNAME' dan 'USER1_PASSWORD' di sistem Anda.")
        return

    logging.info(f"✅ Kredensial ditemukan. Mencoba login sebagai: {username}")
    
    driver = setup_driver()
    if not driver:
        return

    try:
        logging.info("🌐 Buka halaman login...")
        driver.get(url_login)

        # Perbaikan: Menggunakan pencarian yang lebih tangguh untuk elemen username
        username_candidates = [
            (By.ID, "username"),
            (By.NAME, "npk"),
            (By.CSS_SELECTOR, "input[name='npk']"),
            (By.CSS_SELECTOR, "input[type='text']")
        ]
        
        username_input = None
        for by, sel in username_candidates:
            try:
                username_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((by, sel)))
                logging.info("✅ Input username ditemukan.")
                break
            except Exception:
                continue
        
        if not username_input:
            raise RuntimeError("❌ Tidak dapat menemukan field username setelah beberapa percobaan.")

        # Perbaikan: Menggunakan pencarian yang lebih tangguh untuk elemen password
        password_candidates = [
            (By.ID, "password"),
            (By.NAME, "password"),
            (By.CSS_SELECTOR, "input[name='password']"),
            (By.CSS_SELECTOR, "input[type='password']")
        ]
        
        password_input = None
        for by, sel in password_candidates:
            try:
                password_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((by, sel)))
                logging.info("✅ Input password ditemukan.")
                break
            except Exception:
                continue

        if not password_input:
            raise RuntimeError("❌ Tidak dapat menemukan field password setelah beberapa percobaan.")

        # Input username dan password
        username_input.send_keys(username)
        password_input.send_keys(password)
        
        # Kirim form dengan menekan tombol Enter pada field password
        password_input.send_keys(Keys.RETURN)
        logging.info("✅ Form login tersubmit.")
        
        # Tambahkan delay singkat setelah login
        time.sleep(3)

        # Mencari dan menutup semua pop-up yang mungkin muncul
        logging.info("🔎 Mencari dan menutup pop-up...")
        popup_next_buttons = driver.find_elements(By.XPATH, "//*[contains(text(),'Next')]")
        if popup_next_buttons:
            logging.info("Pop-up 'Next' ditemukan. Memproses...")
            for btn in popup_next_buttons:
                try:
                    # Klik tombol 'Next'
                    btn.click()
                    logging.info("⏭️ Klik Next")
                    time.sleep(2) # Beri waktu untuk pop-up berikutnya muncul
                except Exception as e:
                    logging.warning(f"Gagal mengklik Next: {e}")
                    continue
            
            # Mencari tombol 'Finish' atau 'Selesai' di akhir rangkaian pop-up
            try:
                finish_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Finish')] | //*[contains(text(),'Selesai')]"))
                )
                finish_button.click()
                logging.info("🏁 Klik Finish/Selesai.")
                # Tunggu hingga pop-up benar-benar hilang
                WebDriverWait(driver, 10).until(
                    EC.invisibility_of_element_located((By.XPATH, "//*[contains(text(),'Finish')] | //*[contains(text(),'Selesai')]"))
                )
                logging.info("Pop-up berhasil ditutup.")
            except TimeoutException:
                logging.warning("Pop-up finish tidak muncul atau tidak dapat diklik dalam waktu yang ditentukan.")
        else:
            logging.info("Tidak ada pop-up yang ditemukan.")

        # Menunggu tombol presensi utama muncul dan dapat diklik
        logging.info("⏳ Menunggu tombol presensi utama...")
        # Perbarui XPATH untuk mencari tombol presensi utama
        presensi_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn-presensi')]"))
        )
        
        logging.info("✅ Tombol presensi utama ditemukan.")
        presensi_button.click()
        logging.info("✅ Klik: Tombol Presensi Utama.")
        time.sleep(5)  # Beri waktu untuk halaman presensi dimuat

        # Cek apakah presensi berhasil
        # Cari elemen yang menunjukkan status sukses, misalnya "Presensi berhasil" atau "Anda telah melakukan presensi"
        try:
            success_message = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Presensi berhasil')] | //*[contains(text(), 'Anda telah melakukan presensi')]"))
            )
            logging.info("🎉 Presensi berhasil!")
        except TimeoutException:
            logging.warning("⚠️ Pesan konfirmasi presensi tidak ditemukan. Mungkin presensi gagal atau pesan berbeda.")

    except TimeoutException:
        logging.error("❌ Timeout: Elemen tidak ditemukan dalam waktu yang ditentukan.")
    except NoSuchElementException as e:
        logging.error(f"❌ Elemen tidak ditemukan: {e}")
    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan tak terduga: {e}")
    finally:
        if driver:
            logging.info("🚪 Keluar dari browser.")
            driver.quit()

if __name__ == "__main__":
    main()
