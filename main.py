import os
import time
import math
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains

BASE_URL = "https://dani.perhutani.co.id"

NPK = os.getenv("NPK") or "180108011"
PASSWORD = os.getenv("PASSWORD") or "syahputra18"

# Anda bisa set env LAT, LON di GitHub Actions. Bila tidak, pakai default.
LAT = os.getenv("LAT") or "-7.177347"
LON = os.getenv("LON") or "111.874487"

def _normalize_coord(s, limit):
    """Terima string angka, kalau > limit (mis. 90/180) diasumsikan dalam mikro-derajat, dibagi 1e6."""
    try:
        v = float(str(s).replace(",", "."))
        if abs(v) > limit:
            # contoh: -7177347 -> -7.177347
            v = v / 1_000_000.0
        return v
    except Exception:
        return 0.0

lat = _normalize_coord(LAT, 90)
lon = _normalize_coord(LON, 180)

ts = int(time.time() * 1000)  # ms

def setup_driver():
    chrome_opts = Options()
    chrome_opts.add_argument("--headless=new")  # boleh dicoba non-headless jika butuh debug
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--window-size=1920,1080")
    # profil persisten opsional (berguna kalau situs simpan sesi)
    chrome_opts.add_argument("--user-data-dir=./chrome-profile")
    chrome_opts.add_experimental_option(
        "prefs",
        {
            "profile.default_content_setting_values.geolocation": 1,  # allow
            "profile.managed_default_content_settings.geolocation": 1,
        },
    )
    driver = webdriver.Chrome(options=chrome_opts)
    driver.set_page_load_timeout(120)

    # Grant permission + set geolocation via CDP
    driver.execute_cdp_cmd(
        "Browser.grantPermissions",
        {"origin": BASE_URL, "permissions": ["geolocation"]},
    )
    driver.execute_cdp_cmd(
        "Emulation.setGeolocationOverride",
        {"latitude": lat, "longitude": lon, "accuracy": 5},
    )

    # Fallback override API (kalau halaman mengandalkan getCurrentPosition/manual check)
    geoloc_override_js = f"""
        Object.defineProperty(navigator, 'geolocation', {{
          value: {{
            getCurrentPosition: function(success, error, opts) {{
              setTimeout(function(){{
                success({{
                  coords: {{
                    latitude: {lat},
                    longitude: {lon},
                    accuracy: 5,
                    altitude: null,
                    altitudeAccuracy: null,
                    heading: null,
                    speed: null
                  }},
                  timestamp: {ts}
                }});
              }}, 150);
            }},
            watchPosition: function(success, error, opts) {{
              var id = Math.floor(Math.random()*10000);
              setTimeout(function(){{
                success({{
                  coords: {{
                    latitude: {lat},
                    longitude: {lon},
                    accuracy: 5,
                    altitude: null,
                    altitudeAccuracy: null,
                    heading: null,
                    speed: null
                  }},
                  timestamp: {ts}
                }});
              }}, 300);
              return id;
            }},
            clearWatch: function(id) {{}}
          }},
          configurable: true
        }});
    """
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": geoloc_override_js})
    return driver

def safe_wait_click(driver, locators, timeout=20):
    """Coba beberapa locator sampai dapat element clickable. Kembalikan element."""
    last_err = None
    for by, value, desc in locators:
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            try:
                el.click()
            except WebDriverException:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(0.2)
                try:
                    el.click()
                except WebDriverException:
                    driver.execute_script("arguments[0].click();", el)
            return el, desc
        except Exception as e:
            last_err = e
    raise TimeoutException(f"Gagal menemukan elemen: {last_err}")

def switch_into_iframe_if_needed(driver, iframe_hints=("presensi", "absen", "presence", "frame")):
    """Masuk ke iframe yang relevan bila tombol berada di dalam iframe."""
    driver.switch_to.default_content()
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for idx, fr in enumerate(frames):
        try:
            name = (fr.get_attribute("name") or "") + " " + (fr.get_attribute("id") or "")
            src = fr.get_attribute("src") or ""
            if any(h in name.lower() or h in src.lower() for h in iframe_hints):
                driver.switch_to.frame(fr)
                return True
        except Exception:
            continue
    # kalau tidak ada hint, tes satu per satu
    for fr in driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(fr)
            if len(driver.find_elements(By.XPATH, "//*")) > 0:
                # kalau berhasil masuk, kembali dulu
                driver.switch_to.default_content()
        except Exception:
            driver.switch_to.default_content()
    return False

def main():
    driver = setup_driver()
    t0 = datetime.now()
    try:
        print(f"🌍 Using geolocation lat={lat}, lon={lon}")
        driver.get(f"{BASE_URL}/login")

        # Login
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='NPK']"))).send_keys(NPK)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))).send_keys(PASSWORD)
        safe_wait_click(
            driver,
            [
                (By.XPATH, "//button[contains(.,'Login')]","login-btn"),
                (By.CSS_SELECTOR, "button[type='submit']","login-submit"),
            ],
            timeout=20
        )

        # Wizard setelah login (Next/Finish bisa dinamis)
        try:
            for _ in range(4):
                # coba Next
                try:
                    safe_wait_click(driver, [(By.XPATH, "//button[contains(translate(., 'NEXT', 'next'),'next')]", "next-btn")], timeout=5)
                    time.sleep(0.4)
                    continue
                except Exception:
                    pass
                # coba Finish
                try:
                    safe_wait_click(driver, [(By.XPATH, "//button[contains(translate(., 'FINISH', 'finish'),'finish')]", "finish-btn")], timeout=5)
                    time.sleep(0.4)
                    break
                except Exception:
                    break
        except Exception:
            pass

        # Menuju halaman presensi
        try:
            # link langsung
            safe_wait_click(
                driver,
                [
                    (By.XPATH, "//a[contains(@href,'/presensi')]", "menu-presensi-link"),
                    (By.XPATH, "//a[contains(translate(., 'PRESENSI','presensi'),'presensi')]", "menu-presensi-text"),
                ],
                timeout=20
            )
        except Exception:
            # fallback buka langsung
            driver.get(f"{BASE_URL}/presensi")

        # Tunggu konten siap & posisi terkirim
        time.sleep(1.0)
        WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.XPATH, "//*"))
        )

        # Kalau tombol ada di iframe/modal, masuk dulu
        switched = switch_into_iframe_if_needed(driver)

        # Locator tombol “Klik Disini Untuk Presensi”
        tombol_locators = [
            # teks penuh & pendek, berbagai elemen
            (By.XPATH, "//button[contains(translate(., 'KLIK DISINI UNTUK PRESENSI','klik disini untuk presensi'),'klik disini untuk presensi')]", "btn-full-text"),
            (By.XPATH, "//a[contains(translate(., 'KLIK DISINI UNTUK PRESENSI','klik disini untuk presensi'),'klik disini untuk presensi')]", "a-full-text"),
            (By.XPATH, "//div[contains(translate(., 'KLIK DISINI UNTUK PRESENSI','klik disini untuk presensi'),'klik disini untuk presensi')]", "div-full-text"),
            (By.XPATH, "//button[contains(translate(., 'KLIK DISINI','klik disini'),'klik disini')]", "btn-short-text"),
            (By.XPATH, "//a[contains(translate(., 'KLIK DISINI','klik disini'),'klik disini')]", "a-short-text"),
            (By.XPATH, "//div[contains(translate(., 'KLIK DISINI','klik disini'),'klik disini')]", "div-short-text"),
            # tombol oranye (sering pakai .btn-warning / .btn-orange)
            (By.CSS_SELECTOR, "button.btn-warning, a.btn-warning, .btn.btn-warning", "btn-warning"),
            (By.CSS_SELECTOR, ".btn-orange, .btn-warning.bg-warning", "btn-orange"),
        ]

        # Tunggu sinyal lokasi muncul di UI (jika ada indikator)
        # Tidak wajib: banyak situs memunculkan koordinat atau badge 'Lokasi terdeteksi'
        # Kita beri jeda kecil untuk proses geolokasi di frontend
        time.sleep(1.0)

        el, how = safe_wait_click(driver, tombol_locators, timeout=30)
        print(f"✅ Menekan tombol presensi via: {how}")

        # Konfirmasi hasil
        # Cari teks sukses umum
        success_markers = [
            "//div[contains(translate(., 'BERHASIL','berhasil'),'berhasil')]",
            "//div[contains(translate(., 'SUKSES','sukses'),'sukses')]",
            "//div[contains(translate(., 'TERKIRIM','terkirim'),'terkirim')]",
            "//div[contains(translate(., 'PRESENSI','presensi'),'presensi') and contains(translate(., 'BERHASIL','berhasil'),'berhasil')]",
        ]
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "|".join(success_markers)))
            )
            print("🎉 Presensi terdeteksi BERHASIL di UI.")
        except TimeoutException:
            print("ℹ️ Tidak menemukan pesan sukses eksplisit. Cek dashboard/riwayat presensi untuk memastikan.")

    except Exception as e:
        # dump bantuan debug
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            with open(f"page_source_{ts_str}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            driver.save_screenshot(f"screenshot_{ts_str}.png")
            print(f"🧩 Dump disimpan: page_source_{ts_str}.html & screenshot_{ts_str}.png")
        except Exception:
            pass
        raise
    finally:
        dur = (datetime.now() - t0).total_seconds()
        print(f"⏱️ Durasi: {dur:.1f}s")
        driver.quit()

if __name__ == "__main__":
    main()
