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
        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(90) # Meningkatkan page load timeout
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

def main():
    """Fungsi utama untuk menjalankan skrip presensi."""
    # Definisikan kredensial
    username = os.environ.get('USER1_USERNAME')
    password = os.environ.get('USER1_PASSWORD')
    url_login = "https://dani.perhutani.co.id/login"

    # Periksa ketersediaan kredensial
    if not username or not password:
        logging.error("❌ Kredensial tidak ditemukan. Pastikan 'USER1_USERNAME' dan 'USER1_PASSWORD' sudah diatur.")
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

        wait = WebDriverWait(driver, 30)
        username_input = None

        # Logika pencarian yang lebih fleksibel, mencari elemen di halaman utama atau di dalam iframe
        try:
            logging.info("🔎 Mencari field username di halaman utama...")
            # Coba cari dengan beberapa atribut yang mungkin
            username_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@id='username' or @name='username' or @placeholder='Username'] | //input[contains(@type, 'text') and contains(@class, 'form-control')]")))
            logging.info("✅ Field username ditemukan di halaman utama.")
            driver.switch_to.default_content()
        except TimeoutException:
            logging.info("❌ Field username tidak ditemukan di halaman utama. Mencoba mencari di dalam iframe...")
            try:
                iframe = wait.until(
                    EC.presence_of_element_located((By.TAG_NAME, "iframe"))
                )
                driver.switch_to.frame(iframe)
                logging.info("✅ Berhasil beralih ke iframe.")
                # Coba cari di dalam iframe
                username_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@id='username' or @name='username' or @placeholder='Username'] | //input[contains(@type, 'text') and contains(@class, 'form-control')]")))
                logging.info("✅ Field username ditemukan di dalam iframe.")
            except TimeoutException:
                logging.error("❌ Gagal menemukan iframe atau field username di dalamnya.")
                raise # Lempar kembali exception jika gagal di kedua tempat

        # Lanjutkan mengisi form dan klik login jika elemen ditemukan
        if username_input:
            username_input.send_keys(username)
            password_input = driver.find_element(By.XPATH, "//input[@id='password' or @name='password' or @placeholder='Password'] | //input[contains(@type, 'password') and contains(@class, 'form-control')]")
            password_input.send_keys(password)
            
            # Mencari tombol login
            logging.info("🔎 Mencari tombol login...")
            login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Login') or contains(text(), 'Masuk') or @type='submit']")))
            login_button.click()
            logging.info("✅ Klik tombol login.")

        # Pindah kembali ke konten utama setelah login
        driver.switch_to.default_content()
        logging.info("✅ Kembali ke konten utama.")

        # Logika penanganan pop-up yang lebih tangguh
        logging.info("🔎 Mencari pop-up untuk ditutup...")
        try:
            wait_for_popup = WebDriverWait(driver, 15)
            next_clicked_count = 0
            # Coba klik tombol "Next" berulang kali sampai tidak ada lagi
            while True:
                try:
                    next_button = wait_for_popup.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Next') or contains(text(),'next')]")))
                    next_button.click()
                    next_clicked_count += 1
                    logging.info(f"⏭️ Klik Next (total: {next_clicked_count})")
                    time.sleep(1) # Tunggu sebentar agar pop-up baru muncul
                except TimeoutException:
                    logging.info("Tidak ada tombol 'Next' lagi. Lanjut ke 'Finish'.")
                    break # Keluar dari loop jika tidak ada tombol Next
            
            # Coba klik tombol "Finish"
            finish_button = wait_for_popup.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Finish') or contains(text(),'Selesai') or contains(text(),'finish')]")))
            finish_button.click()
            logging.info("🏁 Klik Finish/Selesai.")
            logging.info("✅ Pop-up berhasil ditutup.")
        except TimeoutException:
            logging.info("Tidak ada pop-up yang ditemukan.")
        except Exception as e:
            logging.warning(f"Gagal menutup pop-up: {e}")

        # Menunggu tombol presensi utama muncul dan dapat diklik
        logging.info("⏳ Menunggu tombol presensi utama...")
        presensi_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn-presensi')]"))
        )
        
        logging.info("✅ Tombol presensi utama ditemukan.")
        presensi_button.click()
        logging.info("✅ Klik: Tombol Presensi Utama.")
        time.sleep(5)

        # Cek apakah presensi berhasil
        try:
            success_message = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Presensi berhasil') or contains(text(), 'Anda telah melakukan presensi')]"))
            )
            logging.info("🎉 Presensi berhasil!")
        except TimeoutException:
            logging.warning("⚠️ Pesan konfirmasi presensi tidak ditemukan. Mungkin presensi gagal atau pesan berbeda.")

    except TimeoutException as e:
        logging.error(f"❌ Timeout: Elemen tidak ditemukan dalam waktu yang ditentukan.")
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
