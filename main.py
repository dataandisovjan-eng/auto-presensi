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
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

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
        "//*[(self::button or self::a or self::div or self::span)"
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

def close_guided_popups(driver, user, max_rounds=20):
    """
    Tutup popup bertingkat/beruntun:
    - klik 'Next' berulang kali
    - klik 'Finish' jika muncul
    - klik 'Selesai' jika muncul
    Jalankan beberapa putaran untuk antisipasi popup acak.
    """
    logging.info(f"[{user['name']}] 🔎 Mencari pop-up untuk ditutup...")
    
    # Looping untuk mengklik tombol pop-up
    for r in range(1, max_rounds + 1):
        closed_any = False
        
        # Coba klik tombol 'Next'
        try:
            btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, ci_xpath_contains("next")))
            )
            scroll_into_view(driver, btn)
            btn.click()
            closed_any = True
            logging.info(f"[{user['name']}] ⏭️ Klik Next (round {r})")
            time.sleep(1.5)
        except (TimeoutException, StaleElementReferenceException):
            # Jika tombol 'Next' tidak ditemukan, coba cari tombol 'Finish'
            pass
        
        # Coba klik tombol 'Finish' atau 'Selesai'
        try:
            btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, ci_xpath_contains("finish")))
            )
            scroll_into_view(driver, btn)
            btn.click()
            closed_any = True
            logging.info(f"[{user['name']}] 🏁 Klik Finish (round {r})")
            time.sleep(1.5)
        except (TimeoutException, StaleElementReferenceException):
            # Jika tombol 'Finish' tidak ditemukan, coba cari tombol 'Selesai'
            pass

        try:
            btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, ci_xpath_contains("selesai")))
            )
            scroll_into_view(driver, btn)
            btn.click()
            closed_any = True
            logging.info(f"[{user['name']}] 🏁 Klik Selesai (round {r})")
            time.sleep(1.5)
        except (TimeoutException, StaleElementReferenceException):
            pass

        if not closed_any:
            # Tidak ada pop-up yang terdeteksi, keluar dari loop
            logging.info(f"[{user['name']}] 🎉 Semua pop-up ditutup setelah {r} round.")
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

def lakukan_presensi(driver, user, mode="check_in"):
    """
    Alur:
      - bereskan popup Next/Finish berulang
      - klik tombol oranye 'klik disini untuk presensi'
      - di popup konfirmasi, klik lagi tombol sama
    Dengan retry yang kuat di setiap langkah.
    """
    # Pastikan popup guided/announcement ditutup
    close_guided_popups(driver, user, max_rounds=20)
    time.sleep(2.0) # Tambahan jeda untuk memastikan DOM stabil

    # Mencari tombol utama ("klik disini untuk presensi")
    btn_xpath = ci_xpath_contains("klik disini untuk presensi")
    btn_candidates = [
        (By.XPATH, btn_xpath),
        (By.CSS_SELECTOR, ".card-body.text-center.p-5"), # Berdasarkan analisis gambar Anda
        (By.CSS_SELECTOR, "button[onclick*='presensi']"),
    ]
    ok = False
    for by, sel in btn_candidates:
        ok = try_click(driver, by, sel, attempts=4, delay=1.0, name_desc="Tombol Presensi Utama")
        if ok:
            break
    if not ok:
        raise RuntimeError("Tidak bisa klik tombol presensi utama.")

    # Tunggu popup konfirmasi
    time.sleep(2.5) # Tambahan jeda
    # tutup popup yang mungkin ikut muncul lagi
    close_guided_popups(driver, user, max_rounds=5)

    # Klik tombol konfirmasi di popup (tombol yang sama di dalam pop-up)
    ok2 = try_click(driver, By.XPATH, btn_xpath, attempts=5, delay=1.0, name_desc="Tombol Konfirmasi Presensi (Popup)")
    if not ok2:
        raise RuntimeError("Tidak bisa klik tombol konfirmasi presensi di popup.")

    time.sleep(5.0) # Jeda lebih lama untuk proses presensi
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
