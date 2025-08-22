import os
import time
import logging
import json
from datetime import datetime
import pytz

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException

# ====== Konfigurasi umum ======
BASE_URL = "https://dani.perhutani.co.id/login"
ARTIFACT_DIR = "artifacts"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(ARTIFACT_DIR, "presensi.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# Memuat konfigurasi dari config.json
try:
    with open("config.json", "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    logging.error("❌ File config.json tidak ditemukan. Pastikan file ada di direktori yang sama.")
    exit(1)
except json.JSONDecodeError:
    logging.error("❌ Format JSON di config.json tidak valid.")
    exit(1)

TIMEZONE = pytz.timezone(CONFIG.get("timezone", "Asia/Jakarta"))

def now_with_tz():
    return datetime.now(TIMEZONE)

def new_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1366,768")
    return webdriver.Chrome(options=opts)

def wait_dom_ready(driver, timeout=20):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

def scroll_into_view(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.25)

def ci_xpath_contains(text_substr: str):
    # Case-insensitive contains untuk banyak tag klik-able
    t = text_substr.lower()
    return (
        "//*[(self::button or self::a or self::div or self::span or self::p or self::h1 or self::h2 or self::h3)"
        " and contains(translate(normalize-space(.),"
        " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'"
        f"), '{t}')]"
    )

def safe_find_clickable(driver, by, selector, timeout=15):
    el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, selector)))
    scroll_into_view(driver, el)
    return el

def try_click(driver, by, selector, attempts=3, delay=0.6, name_desc=""):
    last_err = None
    for i in range(1, attempts + 1):
        try:
            el = safe_find_clickable(driver, by, selector, timeout=15)
            el.click()
            if name_desc:
                logging.info(f"✅ Klik: {name_desc} (percobaan {i})")
            return True
        except Exception as e:
            last_err = e
            logging.warning(f"⚠️ Gagal klik {name_desc or selector} (percobaan {i}): {e}")
            time.sleep(delay)
    if name_desc:
        logging.error(f"❌ Gagal klik {name_desc} setelah {attempts} percobaan: {last_err}")
    return False

def close_guided_popups(driver, user, max_attempts=30):
    """
    Tutup popup bertingkat/beruntun.
    - Loop dan klik 'Next' sampai tidak ada lagi.
    - Jika 'Finish' atau 'Selesai' ditemukan, klik dan keluar.
    """
    logging.info(f"[{user['name']}] 🔎 Mencari pop-up untuk ditutup...")
    total_clicks = 0

    while total_clicks < max_attempts:
        clicked_any = False
        
        # Prioritas 1: Klik tombol 'Next' jika ada
        try:
            btn_next = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, ci_xpath_contains("next")))
            )
            scroll_into_view(driver, btn_next)
            btn_next.click()
            clicked_any = True
            total_clicks += 1
            logging.info(f"[{user['name']}] ⏭️ Klik Next (total: {total_clicks})")
            time.sleep(1.5)
        except (TimeoutException, StaleElementReferenceException):
            pass

        # Prioritas 2: Klik tombol 'Finish' jika ada
        try:
            btn_finish = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, ci_xpath_contains("finish")))
            )
            scroll_into_view(driver, btn_finish)
            btn_finish.click()
            clicked_any = True
            logging.info(f"[{user['name']}] 🏁 Klik Finish")
            time.sleep(2)
        except (TimeoutException, StaleElementReferenceException):
            pass

        # Prioritas 3: Klik tombol 'Selesai' jika ada
        try:
            btn_selesai = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, ci_xpath_contains("selesai")))
            )
            scroll_into_view(driver, btn_selesai)
            btn_selesai.click()
            clicked_any = True
            logging.info(f"[{user['name']}] 🏁 Klik Selesai")
            time.sleep(2)
        except (TimeoutException, StaleElementReferenceException):
            pass
        
        # Jika tidak ada tombol yang diklik pada putaran ini, asumsikan semua popup telah ditutup dan keluar dari loop
        if not clicked_any:
            logging.info(f"[{user['name']}] 🎉 Semua pop-up berhasil ditutup.")
            break

def login(driver, user):
    username = os.getenv(user["secret_user"])
    password = os.getenv(user["secret_pass"])
    if not username or not password:
        raise RuntimeError(f"Secrets untuk {user['name']} belum diisi. Periksa {user['secret_user']} dan {user['secret_pass']}.")

    driver.get(BASE_URL)
    wait_dom_ready(driver)
    logging.info(f"[{user['name']}] 🌐 Buka halaman login")

    # Field NPK (username) - pencarian lebih robust
    npk_candidates = [
        (By.CSS_SELECTOR, "input[placeholder*='NPK']"),
        (By.CSS_SELECTOR, "input[placeholder*='Username']"),
        (By.NAME, "npk"),
        (By.ID, "npk"),
        (By.CSS_SELECTOR, "input[name='npk']"),
        (By.CSS_SELECTOR, "input[type='text']"),
    ]
    npk_field = None
    for by, sel in npk_candidates:
        try:
            npk_field = WebDriverWait(driver, 12).until(EC.element_to_be_clickable((by, sel)))
            scroll_into_view(driver, npk_field)
            break
        except Exception:
            continue
    if not npk_field:
        raise RuntimeError("Tidak menemukan field NPK/username di halaman login.")

    npk_field.clear()
    npk_field.send_keys(username)

    # Field password - pencarian lebih robust
    pwd_candidates = [
        (By.CSS_SELECTOR, "input[placeholder*='Password']"),
        (By.NAME, "password"),
        (By.ID, "password"),
        (By.CSS_SELECTOR, "input[name='password']"),
        (By.CSS_SELECTOR, "input[type='password']"),
    ]
    pwd_field = None
    for by, sel in pwd_candidates:
        try:
            pwd_field = WebDriverWait(driver, 12).until(EC.element_to_be_clickable((by, sel)))
            scroll_into_view(driver, pwd_field)
            break
        except Exception:
            continue
    if not pwd_field:
        raise RuntimeError("Tidak menemukan field password di halaman login.")

    pwd_field.clear()
    pwd_field.send_keys(password)
    pwd_field.send_keys(Keys.RETURN)

    # Tunggu halaman dashboard (atau minimal DOM tenang)
    time.sleep(2.0)
    wait_dom_ready(driver)
    logging.info(f"[{user['name']}] ✅ Form login tersubmit")

def is_presensi_success_final(driver, user, mode):
    """
    Memverifikasi keberhasilan presensi dengan mencari indikator yang lebih fleksibel.
    """
    logging.info(f"[{user['name']}] ⏳ Memverifikasi status presensi dengan indikator yang lebih fleksibel...")
    
    # Cari teks yang mengindikasikan keberhasilan
    success_keywords = ["berhasil", "sukses", "successfully", "check out", "sudah check out", "sudah check in", "presensi berhasil"]
    
    # Tunggu 30 detik untuk memberikan waktu bagi status berubah
    for _ in range(30):
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            
            # Cek apakah salah satu kata kunci keberhasilan ada di halaman
            for keyword in success_keywords:
                if keyword in body_text:
                    logging.info(f"[{user['name']}] ✅ Teks '{keyword}' ditemukan. Presensi berhasil!")
                    return True

            # Opsi alternatif: Cari tombol presensi utama dan cek apakah dia sudah tidak aktif
            btn_presensi_utama = driver.find_element(By.XPATH, ci_xpath_contains("klik disini untuk presensi"))
            if "disabled" in btn_presensi_utama.get_attribute("class").lower() or "opacity-50" in btn_presensi_utama.get_attribute("class").lower():
                logging.info(f"[{user['name']}] ✅ Tombol presensi utama sudah tidak aktif. Presensi berhasil!")
                return True

        except (NoSuchElementException, StaleElementReferenceException):
            pass
        except Exception as e:
            logging.warning(f"⚠️ Gagal cek status: {e}")

        time.sleep(1)

    logging.warning(f"[{user['name']}] ❌ Tidak ada indikator keberhasilan yang ditemukan setelah menunggu.")
    return False

def lakukan_presensi(driver, user, mode="check_in"):
    """
    Alur:
      - bereskan popup Next/Finish berulang
      - klik tombol oranye 'klik disini untuk presensi'
      - di popup konfirmasi, klik lagi tombol sama
      - verifikasi status akhir (berhasil)
    """
    # Pastikan popup guided/announcement ditutup
    close_guided_popups(driver, user, max_attempts=30)
    time.sleep(3.0) # Tambahan jeda untuk memastikan DOM stabil

    # Tunggu tombol utama ("klik disini untuk presensi") muncul dan bisa diklik
    logging.info(f"[{user['name']}] ⏳ Menunggu tombol presensi...")
    btn_xpath = ci_xpath_contains("klik disini untuk presensi")
    
    try:
        btn_presensi_utama = safe_find_clickable(driver, By.XPATH, btn_xpath, timeout=20)
        logging.info(f"[{user['name']}] ✅ Tombol presensi utama ditemukan.")
    except TimeoutException:
        raise RuntimeError("Tombol presensi utama tidak muncul setelah menutup pop-up.")
        
    # Mencoba klik tombol presensi utama
    ok = try_click(driver, By.XPATH, btn_xpath, attempts=4, delay=1.0, name_desc="Tombol Presensi Utama")
    if not ok:
        # Jika tombol tidak dapat diklik, asumsikan sudah presensi dan berhasil
        logging.info(f"[{user['name']}] ✅ Tombol presensi tidak dapat diklik, menganggap presensi sudah dilakukan.")
        return True

    # Tambahkan jeda untuk memastikan pop-up konfirmasi muncul
    time.sleep(3.5)

    # Mencari pop-up lagi, kali ini lebih agresif
    logging.info(f"[{user['name']}] 🔎 Mencari pop-up tambahan setelah klik pertama...")
    close_guided_popups(driver, user, max_attempts=10)

    # Mencari dan klik tombol konfirmasi di dalam popup yang mungkin muncul
    confirm_btn_xpath = "//*[(self::button or self::a or self::div or self::span) and (contains(text(), 'OK') or contains(text(), 'Ya') or contains(text(), 'Konfirmasi') or contains(text(), 'Submit'))]"
    try:
        confirm_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, confirm_btn_xpath)))
        logging.info(f"[{user['name']}] ✅ Tombol konfirmasi di pop-up ditemukan. Mencoba mengklik...")
        scroll_into_view(driver, confirm_button)
        confirm_button.click()
        logging.info(f"[{user['name']}] ✅ Klik: Tombol Konfirmasi (Popup)")
    except TimeoutException:
        logging.info(f"[{user['name']}] ⏭️ Tidak ada tombol konfirmasi pop-up tambahan yang ditemukan. Lanjut.")
    except Exception as e:
        logging.warning(f"⚠️ Gagal klik tombol konfirmasi pop-up: {e}")
    
    # Tambahkan jeda setelah klik konfirmasi
    time.sleep(5.0)

    # Verifikasi status akhir
    if not is_presensi_success_final(driver, user, mode):
        raise RuntimeError("Verifikasi status presensi gagal.")
        
    time.sleep(6.0) # Jeda lebih lama untuk proses presensi
    # Simpan screenshot bukti
    ss_ok = os.path.join(ARTIFACT_DIR, f"{user['name']}_{mode}.png")
    driver.save_screenshot(ss_ok)
    logging.info(f"[{user['name']}] 📸 Screenshot tersimpan: {ss_ok}")

def run_for_user(user, mode, max_retries=2):
    """
    Jalankan presensi untuk 1 user dengan retry total (ulang dari login jika gagal).
    """
    attempt = 1
    while attempt <= max_retries:
        driver = new_driver()
        try:
            logging.info(f"[{user['name']}] 🔐 Login & presensi (percobaan {attempt}/{max_retries})")
            login(driver, user)
            time.sleep(3.0)
            lakukan_presensi(driver, user, mode)
            logging.info(f"[{user['name']}] ✅ Berhasil {mode}")
            return True
        except Exception as e:
            ss_err = os.path.join(ARTIFACT_DIR, f"{user['name']}_{mode}_error_attempt{attempt}.png")
            try:
                driver.save_screenshot(ss_err)
                logging.warning(f"[{user['name']}] 📸 Screenshot error: {ss_err}")
            except Exception:
                pass
            logging.error(f"[{user['name']}] ❌ Gagal {mode}: {e}")
            attempt += 1
            time.sleep(2.0)
        finally:
            driver.quit()

    logging.error(f"[{user['name']}] ❌ Gagal {mode} setelah {max_retries} percobaan.")
    return False

if __name__ == "__main__":
    now = now_with_tz()
    logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} ({TIMEZONE.zone})")

    # Input manual run (dari workflow_dispatch)
    force_user_input = os.getenv("FORCE_USER", "").strip().lower()
    force_mode_input = os.getenv("FORCE_MODE", "").strip().lower()

    if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch" and (force_user_input or force_mode_input):
        logging.info(f"⚡ Manual run: user={force_user_input or 'all'}, mode={force_mode_input or 'auto'}")
        
        users_to_run = []
        if force_user_input == "all" or not force_user_input:
            users_to_run = CONFIG["users"]
        else:
            for u in CONFIG["users"]:
                if u["name"].lower() == force_user_input or u["id"].lower() == force_user_input:
                    users_to_run.append(u)
                    break
        
        for u in users_to_run:
            mode = force_mode_input
            if not mode:
                # Jika mode tidak dispesifikasi, tentukan otomatis
                if now.hour >= 12:
                    mode = "check_out"
                else:
                    mode = "check_in"
            
            run_for_user(u, mode, max_retries=2)
    else:
        # Mode terjadwal
        hhmm = now.strftime("%H:%M")
        
        for u in CONFIG["users"]:
            mode = None
            if hhmm == u["check_in"]:
                mode = "check_in"
            elif hhmm == u["check_out"]:
                mode = "check_out"
            
            if mode:
                logging.info(f"[{u['name']}] ✨ Jadwal cocok untuk {mode}. Menjalankan skrip...")
                run_for_user(u, mode, max_retries=2)
            else:
                logging.info(f"[{u['name']}] ⏭️ Skip (bukan jadwal user ini).")
