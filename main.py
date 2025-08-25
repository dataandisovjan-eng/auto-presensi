import os
import time
import logging
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, WebDriverException, ElementClickInterceptedException
)

# =============================
# LOGGING & ARTIFACTS
# =============================
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"presensi_{ts}.log"
ART_DIR = Path("artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_filename, encoding="utf-8"), logging.StreamHandler()],
    datefmt="%Y-%m-%d %H:%M:%S",
)

def save_debug(driver, prefix):
    """Simpan screenshot + HTML untuk debugging."""
    t = datetime.now().strftime("%Y%m%d_%H%M%S")
    png = ART_DIR / f"{prefix}_{t}.png"
    html = ART_DIR / f"{prefix}_{t}.html"
    try:
        driver.save_screenshot(str(png))
        with open(html, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logging.warning(f"📸 Screenshot disimpan: {png.name}")
        logging.warning(f"📝 HTML halaman disimpan: {html.name}")
    except Exception as e:
        logging.warning(f"⚠️ Gagal simpan debug: {e}")

# =============================
# DRIVER
# =============================
def setup_driver():
    logging.info("⚙️ Mengatur driver...")
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
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
# UTIL
# =============================
def js_click(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.2)
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)

def dismiss_onboarding_if_any(driver):
    """Hilangkan pop-up pengumuman/intro (Next/Finish) tanpa menyentuh modal presensi."""
    try:
        # Coba klik Next berkali-kali
        for _ in range(6):
            next_btns = driver.find_elements(
                By.XPATH,
                "//*[contains(translate(.,'NEXT','next'),'next') or contains(.,'Selanjutnya')]"
            )
            found = False
            for b in next_btns:
                if b.is_displayed():
                    try:
                        js_click(driver, b)
                        found = True
                        time.sleep(0.6)
                        break
                    except Exception:
                        pass
            if not found:
                break

        # Coba Finish
        finish_btns = driver.find_elements(
            By.XPATH,
            "//*[contains(translate(.,'FINISH','finish'),'finish') or contains(.,'Selesai')]"
        )
        for b in finish_btns:
            if b.is_displayed():
                try:
                    js_click(driver, b)
                    time.sleep(0.6)
                    break
                except Exception:
                    pass
    except Exception:
        pass

def hard_clear_blocking_modals(driver):
    """Buang modal pengumuman/backdrop yang menutup klik (bukan modal presensi)."""
    try:
        driver.execute_script("""
            // hapus backdrop
            document.querySelectorAll('.modal-backdrop').forEach(e=>e.remove());
            // hapus modal umum (announcement) yang bukan popup presensi
            document.querySelectorAll('.modal.show, .modal.fade.show, #announcement').forEach(m=>{
                const txt = m.innerText || '';
                if (!/Klik\\s+Disini\\s+Untuk\\s+Presensi/i.test(txt)) {
                    m.remove();
                }
            });
        """)
        logging.info("❎ Modal pengumuman/backdrop dihapus dengan JS.")
    except Exception:
        pass

def wait_visible_modal(driver, timeout=10):
    """Tunggu ada modal/overlay terlihat."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(@class,'modal') and contains(@class,'show')]"))
        )
        return True
    except TimeoutException:
        return False

def extract_status_text(driver):
    """Ambil status ringkas (Sudah Check In/Out atau Belum)."""
    try:
        # Ambil blok dashboard yang memuat status
        blocks = driver.find_elements(By.XPATH, "//*[contains(.,'Sudah Check In') or contains(.,'Sudah Check Out') or contains(.,'Belum Check In') or contains(.,'Belum Check Out')]")
        combined = " | ".join([b.text for b in blocks if b.is_displayed()])
        return combined.strip() if combined else None
    except Exception:
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
        login_btn = driver.find_element(By.XPATH, "//button[contains(.,'Login') or @type='submit']")
        js_click(driver, login_btn)
        logging.info("🔐 Login dikirim.")
        return True
    except Exception as e:
        logging.error(f"❌ Gagal login: {e}")
        save_debug(driver, "login_error")
        return False

# =============================
# PRESENSI
# =============================
def open_presensi(driver):
    """Klik tombol/tautan menuju presensi di dashboard."""
    wait = WebDriverWait(driver, 20)
    dismiss_onboarding_if_any(driver)
    hard_clear_blocking_modals(driver)

    # Cari anchor/btn yang mengarah ke presensi
    candidates = [
        "//a[contains(@href,'/presensi')]",
        "//a[contains(.,'Presensi')]",
        "//button[contains(.,'Presensi')]",
        "//*[contains(@class,'btn') and contains(.,'Presensi')]",
        "//*[contains(.,'Klik Disini Untuk Presensi')]/ancestor::a | //*[contains(.,'Klik Disini Untuk Presensi')]/ancestor::button"
    ]
    for xp in candidates:
        try:
            el = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
            js_click(driver, el)
            logging.info("✅ Klik: Tombol Presensi Utama.")
            return True
        except TimeoutException:
            continue
        except ElementClickInterceptedException:
            hard_clear_blocking_modals(driver)
            try:
                el = driver.find_element(By.XPATH, xp)
                js_click(driver, el)
                logging.info("✅ Klik: Tombol Presensi Utama (setelah clear overlay).")
                return True
            except Exception:
                continue

    save_debug(driver, "presensi_btn_missing")
    logging.error("❌ Tombol presensi utama tidak ditemukan.")
    return False

def click_popup_presensi(driver, attempt):
    """
    Klik tombol oranye 'Klik Disini Untuk Presensi' DI DALAM MODAL.
    Kembalikan True jika klik berhasil (modal di-close / status berubah),
    False jika tombol tidak ditemukan/klik gagal.
    """
    # Tunggu modal muncul sebentar
    modal_ready = wait_visible_modal(driver, timeout=6)
    if not modal_ready:
        # Kadang modal muncul tapi tanpa class 'show'—tetap coba cari tombol spesifik di DOM
        pass

    # Selector khusus di dalam modal
    selectors = [
        # tombol di dalam modal
        "//*[contains(@class,'modal') and contains(@class,'show')]//*[self::a or self::button][contains(normalize-space(.), 'Klik Disini Untuk Presensi')]",
        # fallback: tombol warning di modal
        "//*[contains(@class,'modal') and contains(@class,'show')]//*[self::a or self::button][contains(@class,'btn') and contains(@class,'btn-warning')]",
        # fallback umum: apapun yang bertuliskan frasa target
        "//*[self::a or self::button][contains(normalize-space(.), 'Klik Disini Untuk Presensi')]",
    ]

    for sel in selectors:
        btns = driver.find_elements(By.XPATH, sel)
        for b in btns:
            if not b.is_displayed():
                continue
            try:
                js_click(driver, b)
                logging.info(f"🖱️ Klik tombol popup presensi (percobaan {attempt}).")
                time.sleep(1.5)
                return True
            except Exception:
                continue

    logging.warning(f"⚠️ Popup presensi tidak muncul/btn tidak bisa diklik (percobaan {attempt}).")
    save_debug(driver, f"popup_missing_attempt{attempt}")
    return False

def await_status(driver, target_phrase, timeout=15):
    """Pantau sampai status mengandung target_phrase (Sudah Check In/Out)."""
    end = time.time() + timeout
    last_seen = None
    while time.time() < end:
        st = extract_status_text(driver)
        if st:
            last_seen = st
            if target_phrase.lower() in st.lower():
                return True, st
        time.sleep(1.0)
    return False, last_seen

def do_presensi(driver, mode):
    """
    Alur:
    1) buka tombol presensi utama (dashboard)
    2) klik tombol popup di modal
    3) cek perubahan status
    4) retry sampai 3×
    """
    # 1) buka presensi dari dashboard
    if not open_presensi(driver):
        return False

    # Tentukan target status
    target_phrase = "Sudah Check Out" if mode == "check_out" else "Sudah Check In"

    # 2-4) tiga percobaan klik di dalam modal
    success = False
    for attempt in range(1, 4):
        # Pastikan modal onboarding tidak menghalangi
        hard_clear_blocking_modals(driver)

        if not click_popup_presensi(driver, attempt):
            # Kalau tombol belum ada, coba klik ulang presensi utama (kadang perlu 2x)
            open_presensi(driver)

        ok, current = await_status(driver, target_phrase, timeout=12)
        if ok:
            logging.info(f"🎉 Presensi {mode} berhasil! Status: {current or target_phrase}")
            success = True
            break
        else:
            logging.warning("⚠️ Tidak menemukan indikator keberhasilan. Simpan eviden & coba lagi...")
            save_debug(driver, f"status_not_updated_attempt{attempt}")

    if not success:
        logging.error(f"❌ Presensi {mode} gagal setelah 3 percobaan.")
    return success

# =============================
# MAIN
# =============================
if __name__ == "__main__":
    # MODE: check_in / check_out (default check_out agar bisa dites sore)
    mode = os.environ.get("MODE", "check_out").strip().lower()
    if mode not in ("check_in", "check_out"):
        mode = "check_out"

    # Secrets utama + fallback agar fleksibel
    username = os.environ.get("USER1_USERNAME") or os.environ.get("USER1")
    password = os.environ.get("USER1_PASSWORD") or os.environ.get("PASS1")

    if not username or not password:
        logging.error("❌ Username/Password tidak ditemukan di secrets untuk USER1!")
        raise SystemExit(1)

    logging.info(f"⏰ Mulai proses presensi untuk USER1 (mode: {mode})...")
    driver = setup_driver()
    if not driver:
        raise SystemExit(1)

    try:
        if not login(driver, username, password):
            raise SystemExit(1)

        # Bersihkan pop-up onboarding yang mengganggu klik dashboard,
        # TAPI jangan hapus modal presensi saat sudah dibuka.
        dismiss_onboarding_if_any(driver)
        hard_clear_blocking_modals(driver)

        ok = do_presensi(driver, mode)
        if not ok:
            raise SystemExit(1)
    finally:
        try:
            driver.quit()
        except Exception:
            pass
