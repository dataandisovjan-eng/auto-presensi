import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

BASE_URL = "https://dani.perhutani.co.id"

# === Credentials (dibaca dari GitHub Secrets / env) ===
NPK = os.getenv("NPK")
PASSWORD = os.getenv("PASSWORD")

# === Lokasi Dummy (default jika env tidak ada) ===
def _normalize_coord(s, limit):
    try:
        v = float(str(s).replace(",", "."))
        if abs(v) > limit:  # misal -7177347 -> -7.177347
            v = v / 1_000_000.0
        return v
    except Exception:
        return 0.0

LAT = _normalize_coord(os.getenv("LAT") or "-7.177347", 90)
LON = _normalize_coord(os.getenv("LON") or "111.874487", 180)
TS = int(time.time() * 1000)

def setup_driver():
    chrome_opts = Options()
    chrome_opts.add_argument("--headless=new")  # hapus baris ini kalau mau lihat browser
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--window-size=1920,1080")
    chrome_opts.add_argument("--user-data-dir=./chrome-profile")
    chrome_opts.add_experimental_option(
        "prefs",
        {
            "profile.default_content_setting_values.geolocation": 1,
            "profile.managed_default_content_settings.geolocation": 1,
        },
    )

    driver = webdriver.Chrome(options=chrome_opts)
    driver.set_page_load_timeout(120)

    # Grant izin lokasi
    driver.execute_cdp_cmd(
        "Browser.grantPermissions",
        {"origin": BASE_URL, "permissions": ["geolocation"]},
    )
    driver.execute_cdp_cmd(
        "Emulation.setGeolocationOverride",
        {"latitude": LAT, "longitude": LON, "accuracy": 5},
    )

    # Stub API geolocation agar success callback selalu terpanggil
    geoloc_js = f"""
        Object.defineProperty(navigator, 'geolocation', {{
          value: {{
            getCurrentPosition: function(success, error, opts) {{
              success({{
                coords: {{
                  latitude: {LAT},
                  longitude: {LON},
                  accuracy: 5
                }},
                timestamp: {TS}
              }});
            }},
            watchPosition: function(success, error, opts) {{
              var id = Math.floor(Math.random()*10000);
              success({{
                coords: {{
                  latitude: {LAT},
                  longitude: {LON},
                  accuracy: 5
                }},
                timestamp: {TS}
              }});
              return id;
            }},
            clearWatch: function(id) {{}}
          }},
          configurable: true
        }});
    """
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": geoloc_js})
    print(f"🌍 Lokasi dummy aktif: lat={LAT}, lon={LON}")
    return driver

def safe_wait_click(driver, locators, timeout=20):
    """Coba beberapa locator sampai berhasil klik"""
    for by, value, desc in locators:
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            try:
                el.click()
            except WebDriverException:
                driver.execute_script("arguments[0].click();", el)
            print(f"✅ Klik: {desc}")
            return True
        except Exception:
            continue
    return False

def switch_into_iframe_if_needed(driver):
    """Masuk ke iframe jika tombol ada di dalamnya"""
    driver.switch_to.default_content()
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for fr in frames:
        try:
            driver.switch_to.frame(fr)
            if "klik" in driver.page_source.lower():
                print("ℹ️ Masuk ke iframe presensi")
                return True
            driver.switch_to.default_content()
        except Exception:
            driver.switch_to.default_content()
    return False

def main():
    driver = setup_driver()
    t0 = datetime.now()
    try:
        driver.get(f"{BASE_URL}/login")

        # Login
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='NPK']"))
        ).send_keys(NPK)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
        ).send_keys(PASSWORD)

        safe_wait_click(driver, [(By.XPATH, "//button[contains(.,'Login')]", "login")], timeout=20)

        # Lewati wizard (Next/Finish)
        for _ in range(4):
            if not safe_wait_click(driver, [(By.XPATH, "//button[contains(.,'Next')]", "next")], timeout=3):
                safe_wait_click(driver, [(By.XPATH, "//button[contains(.,'Finish')]", "finish")], timeout=3)

        # Masuk menu presensi
        if not safe_wait_click(driver, [(By.XPATH, "//a[contains(@href,'/presensi')]", "menu-presensi")], timeout=15):
            driver.get(f"{BASE_URL}/presensi")

        time.sleep(2)
        switch_into_iframe_if_needed(driver)

        # Lokator tombol presensi
        tombol_locators = [
            (By.XPATH, "//button[contains(.,'Klik Disini')]", "btn-presensi"),
            (By.XPATH, "//a[contains(.,'Klik Disini')]", "a-presensi"),
            (By.XPATH, "//div[contains(.,'Klik Disini')]", "div-presensi"),
        ]

        if safe_wait_click(driver, tombol_locators, timeout=30):
            print("✅ Tombol presensi berhasil diklik")
        else:
            print("❌ Tombol presensi tidak ditemukan")
            return

        # Verifikasi hasil
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(.,'berhasil')]"))
            )
            print("🎉 Presensi BERHASIL!")
        except TimeoutException:
            print("⚠️ Tidak ada notifikasi sukses, cek dashboard manual")

    except Exception as e:
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f"page_source_{ts_str}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        driver.save_screenshot(f"screenshot_{ts_str}.png")
        print(f"❌ Error: {e}\n🧩 Debug disimpan: page_source_{ts_str}.html & screenshot_{ts_str}.png")
    finally:
        dur = (datetime.now() - t0).total_seconds()
        print(f"⏱️ Durasi: {dur:.1f}s")
        driver.quit()

if __name__ == "__main__":
    main()
