import subprocess
import time
import os
import sys
import requests
import threading
from pathlib import Path
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy

# Получить путь к Android SDK
ANDROID_HOME = os.getenv("ANDROID_HOME") or os.path.expanduser("~/Library/Android/sdk")
EMULATOR_PATH = os.path.join(ANDROID_HOME, "emulator", "emulator")

# Путь к ADB (для Windows с MEMU)
ADB_PATH = os.getenv("ADB_PATH") or "C:\\Program Files\\Microvirt\\MEmu\\adb.exe"
if not os.path.exists(ADB_PATH):
    # Пытаемся найти в Android SDK
    ADB_PATH = os.path.join(ANDROID_HOME, "platform-tools", "adb.exe")
if not os.path.exists(ADB_PATH):
    ADB_PATH = ADB_PATH  # Fallback на обычный adb из PATH

# MEMU device ID (автоопределение)
MEMU_DEVICE = os.getenv("MEMU_DEVICE")
if not MEMU_DEVICE:
    try:
        # Пробуем найти через adb devices
        # ADB_PATH уже определен выше
        res = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True)
        # Ищем первый попавшийся 127.0.0.1:2xxxx
        import re
        match = re.search(r"(127\.0\.0\.1:2\d{4})\s+device", res.stdout)
        if match:
            MEMU_DEVICE = match.group(1)
            print(f"✓ Автоматически найден MEmu девайс: {MEMU_DEVICE}")
    except Exception:
        pass

if not MEMU_DEVICE:
    MEMU_DEVICE = "127.0.0.1:21503"  # Дефолт (индекс 0)

USE_MEMU = os.getenv("USE_MEMU", "true").lower() in ["true", "1", "yes"]


def start_emulator(avd_name: str, port: int = 5554, show_gui: bool = False):
    """Запустить эмулятор Android или вернуть MEMU device ID"""
    if USE_MEMU:
        print(f"✓ Используется MEMU: {MEMU_DEVICE}")
        return MEMU_DEVICE
    
    if not os.path.exists(EMULATOR_PATH):
        raise FileNotFoundError(f"Emulator not found at {EMULATOR_PATH}. Please install Android SDK.")
    
    device_name = f"emulator-{port}"
    
    # Проверить не запущен ли уже эмулятор
    result = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True)
    if f"{device_name}\tdevice" in result.stdout:
        print(f"✓ Эмулятор {device_name} уже запущен, переиспользую")
        return device_name
    
    print(f"🚀 Запускаю эмулятор {avd_name} на порту {port}...")
    
    cmd = [
        EMULATOR_PATH,
        "-avd", avd_name,
        "-port", str(port),
        "-gpu", "swiftshader_indirect",  # Software rendering
        "-no-snapshot-load",
        "-no-boot-anim"
    ]
    
    if not show_gui:
        cmd.append("-no-window")
        print(f"  (запуск без GUI)")
    else:
        print(f"  (запуск с GUI окном)")
    
    # Запустить в отдельной сессии чтобы не убивался при завершении скрипта
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    print(f"✓ Эмулятор {avd_name} запущен на порту {port}")
    print("⏳ Ожидание полной загрузки эмулятора (макс 20 сек)...")
    
    # Ждем, пока эмулятор подключится к adb (макс 20 секунд)
    max_attempts = 10  # 10 попыток по 2 секунды = 20 секунд
    for i in range(max_attempts):
        try:
            result = subprocess.run(
                [ADB_PATH, "-s", device_name, "shell", "getprop", "sys.boot_completed"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and "1" in result.stdout:
                print(f"✓ Эмулятор полностью загружен")
                return device_name
        except subprocess.TimeoutExpired:
            pass
        
        time.sleep(2)
        print(f"  Попытка {i+1}/{max_attempts}...")
    
    # Если эмулятор не поднялся за 20 секунд - выбрасываем исключение
    print("❌ Эмулятор не поднялся за 20 секунд")
    raise Exception("Emulator failed to start in 20 seconds")


def install_accessibility_service(device_name: str):
    """Установить и включить Accessibility Service"""
    print("\n🔧 Устанавливаю Accessibility Service...")
    
    # Установка APK
    result = subprocess.run(
        [ADB_PATH, "-s", device_name, "install", "-r", "wa_clicker.apk"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✓ WA Clicker APK установлен")
    else:
        print(f"⚠️  Ошибка установки WA Clicker: {result.stderr}")
        return False
    
    # Автоматически включаем сервис
    print("⏳ Включаю Accessibility Service...")
    
    # Получаем текущий список enabled services
    result = subprocess.run([
        ADB_PATH, "-s", device_name, "shell", "settings", "get", "secure",
        "enabled_accessibility_services"
    ], capture_output=True, text=True)
    
    current_services = result.stdout.strip()
    if current_services and current_services != "null":
        new_services = current_services + ":com.wa.clicker/com.wa.clicker.WAClickerService"
    else:
        new_services = "com.wa.clicker/com.wa.clicker.WAClickerService"
    
    subprocess.run([
        ADB_PATH, "-s", device_name, "shell", "settings", "put", "secure",
        "enabled_accessibility_services", new_services
    ], capture_output=True)
    
    subprocess.run([
        ADB_PATH, "-s", device_name, "shell", "settings", "put", "secure",
        "accessibility_enabled", "1"
    ], capture_output=True)
    
    print("✓ Accessibility Service включен в настройках")
    
    # ТРИГГЕР: Открываем настройки Accessibility чтобы сервис реально запустился
    print("🔄 Триггерю запуск сервиса через настройки...")
    subprocess.run([
        ADB_PATH, "-s", device_name, "shell", "am", "start",
        "-a", "android.settings.ACCESSIBILITY_SETTINGS"
    ], capture_output=True)
    time.sleep(2)
    
    # Закрываем настройки
    subprocess.run([
        ADB_PATH, "-s", device_name, "shell", "input", "keyevent", "KEYCODE_HOME"
    ], capture_output=True)
    time.sleep(1)
    
    print("✓ Accessibility Service должен быть активен")
    return True







def install_whatsapp(device_name: str):
    """Установить WhatsApp APK на эмулятор"""
    apk_path = "whatsapp.apk"  # Путь к APK файлу
    subprocess.run([ADB_PATH, "-s", device_name, "install", apk_path], check=True)
    print(f"✓ WhatsApp установлен на {device_name}")


def open_whatsapp(device_name: str):
    """Открыть WhatsApp приложение"""
    try:
        subprocess.run(
            [ADB_PATH, "-s", device_name, "shell", "am", "start", "-n", "com.whatsapp/.Main"],
            check=True,
        )
        print(f"✓ WhatsApp открыт на {device_name}")
        time.sleep(5)  # Ждем, пока приложение загрузится
    except subprocess.CalledProcessError as e:
        print(f"✗ Ошибка при открытии WhatsApp: {e}")
        raise


def connect_appium(device_name: str, appium_port: int = 4723):
    """Подключиться к эмулятору через Appium"""
    # Проверяем что девайс online перед подключением
    print(f"⏳ Проверяю статус {device_name}...")
    for attempt in range(5):
        result = subprocess.run(
            [ADB_PATH, "devices"],
            capture_output=True,
            text=True
        )
        
        if f"{device_name}\tdevice" in result.stdout:
            print(f"✓ Девайс {device_name} online")
            break
        
        if f"{device_name}\toffline" in result.stdout or device_name not in result.stdout:
            print(f"  ⚠️  Девайс offline, пытаюсь восстановить соединение ({attempt+1}/5)...")
            # Перезапускаем ADB сервер
            subprocess.run([ADB_PATH, "kill-server"], capture_output=True)
            time.sleep(2)
            subprocess.run([ADB_PATH, "start-server"], capture_output=True)
            time.sleep(3)
        else:
            break
    
    # Дополнительная задержка перед подключением Appium
    time.sleep(2)
    
    # Очищаем логи перед подключением (помогает UiAutomator2 запуститься быстрее)
    subprocess.run(
        [ADB_PATH, "-s", device_name, "logcat", "-c"],
        capture_output=True
    )
    time.sleep(1)
    
    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "deviceName": device_name,
        "udid": device_name,
        "appPackage": "com.android.settings",  # Подключаемся к настройкам, а не к WA
        "appActivity": ".Settings",
        "autoLaunch": False,  # Не запускать настройки принудительно
        "appWaitActivity": "*",
        "noReset": True,
        "fullReset": False,
        "newCommandTimeout": 1200,
    }
    
    # Пробуем подключиться несколько раз
    max_retries = 3
    for retry in range(max_retries):
        try:
            driver = webdriver.Remote(f"http://localhost:{appium_port}", caps)
            print(f"✓ Appium подключен к {device_name}")
            return driver
        except Exception as e:
            if retry < max_retries - 1:
                print(f"❌ Ошибка подключения Appium (попытка {retry + 1}/{max_retries}): {e}")
                print(f"⏳ Жду 10 сек и пробую еще раз...")
                time.sleep(10)
                
                # Очищаем логи
                subprocess.run(
                    [ADB_PATH, "-s", device_name, "logcat", "-c"],
                    capture_output=True
                )
                time.sleep(2)
            else:
                # Последняя попытка - выбрасываем ошибку
                print(f"❌ Не удалось подключиться к Appium после {max_retries} попыток")
                raise


def click_agree_button(driver):
    """Кликнуть по кнопке 'Согласиться и продолжить' (или AGREE AND CONTINUE)"""
    try:
        print("⏳ Жду загрузки экрана (2 сек)...")
        time.sleep(2)

        print("⏳ Ищем кнопку согласия (polling до 15 сек)...")
        max_attempts = 30  # 30 попыток по 0.5 сек = 15 секунд
        agree_btn = None

        for attempt in range(max_attempts):
            selectors = [
                'new UiSelector().text("Принять и продолжить").clickable(true)',
                'new UiSelector().text("AGREE AND CONTINUE").clickable(true)',
                'new UiSelector().textContains("риня").clickable(true)',
                'new UiSelector().textContains("AGREE").clickable(true)',
                # Часто у кнопки бывает ресурс id
                'new UiSelector().resourceId("com.whatsapp:id/eula_accept").clickable(true)',
            ]
            for sel in selectors:
                try:
                    agree_btn = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, sel)
                    print(f"✓ Найдено по селектору: {sel}")
                    break
                except Exception:
                    continue
            if agree_btn:
                break
            if attempt % 10 == 0 and attempt > 0:
                print(f"  ⏳ Попытка {attempt}/{max_attempts}...")
            time.sleep(0.5)

        if agree_btn:
            agree_btn.click()
            print("✓ Нажата кнопка согласия")
            time.sleep(2)
        else:
            # Сохраняем page source для дебага
            print("⚠️  Кнопка не найдена, сохраняю page source...")
            try:
                with open("agree_screen.xml", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print("✓ Page source сохранён в agree_screen.xml")
            except Exception as save_err:
                print(f"⚠️ Не удалось сохранить page source: {save_err}")
            
            # Фолбэк: кликаем внизу по центру (там обычно кнопка)
            print("⚠️  Жму по координатам снизу экрана")
            size = driver.get_window_size()
            x = size["width"] // 2
            y = int(size["height"] * 0.9)
            print(f"   Клик по ({x}, {y})")
            driver.tap([(x, y)])
            time.sleep(2)
    except Exception as e:
        print(f"✗ Ошибка: {e}")


def enter_phone_number(driver, phone_number: str):
    """Ввести номер телефона"""
    try:
        # Даём время на загрузку экрана
        print("⏳ Жду загрузки экрана ввода номера (3 сек)...")
        time.sleep(3)
        
        # Найти оба поля ввода
        print("⏳ Ищем поля ввода номера...")
        edit_texts = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.EditText")
        
        if len(edit_texts) >= 2:
            # Первое поле = код страны
            print("✓ Нашли оба поля")
            country_code_input = edit_texts[0]
            phone_input = edit_texts[1]
            
            # Очистить и ввести код страны (для России)
            country_code_input.clear()
            country_code_input.send_keys("7")
            print("✓ Код страны 7 введен")
            time.sleep(1)
            
            # Очистить и ввести номер без кода страны
            phone_input.clear()
            phone_without_country = phone_number.lstrip('+').lstrip('7')  # Убрать +7
            phone_input.send_keys(phone_without_country)
            print(f"✓ Номер {phone_without_country} введен")
            time.sleep(1)
            return True
        else:
            print(f"✗ Найдено только {len(edit_texts)} поле(й), ожидалось 2")
            
            # Сохраняем page source для дебага
            print("⚠️  Сохраняю page source...")
            try:
                with open("phone_screen.xml", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print("✓ Page source сохранён в phone_screen.xml")
            except:
                pass
            
            return False
    except Exception as e:
        print(f"✗ Ошибка при вводе номера: {e}")
        return False


def redirect_calls_to_sip(phone_number: str):
    """Перенаправить входящие звонки на SIP через MTT API"""
    print(f"\n📞 Настраиваю перенаправление звонков для {phone_number}...")
    
    # MTT API параметры
    MTT_USERNAME = "ip_ivanchin"
    MTT_PASSWORD = "s13jgSxHpQ"
    CLIENT_ID = "110028011"
    ASTERISK_SIP_ID = "883140005582687"
    
    # Формируем номер для MTT (без +)
    mtt_phone = phone_number.lstrip('+')
    
    data = {
        "id": "1",
        "jsonrpc": "2.0",
        "method": "SetReserveStruct",
        "params": {
            "sip_id": mtt_phone,
            "redirect_type": 1,
            "masking": "N",
            "controlCallStruct": [
                {
                    "I_FOLLOW_ORDER": 1,
                    "PERIOD": "Always",
                    "PERIOD_DESCRIPTION": "Always",
                    "TIMEOUT": 40,
                    "ACTIVE": "Y",
                    "NAME": ASTERISK_SIP_ID,
                    "REDIRECT_NUMBER": ASTERISK_SIP_ID,
                }
            ],
        },
    }
    
    try:
        response = requests.post(
            "https://api.mtt.ru/ipcr/",
            json=data,
            auth=(MTT_USERNAME, MTT_PASSWORD),
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        print(f"✓ Звонки с {mtt_phone} перенаправлены на {ASTERISK_SIP_ID}")
        print(f"📋 Ответ MTT API: {result}")
        
        return result
    
    except requests.exceptions.RequestException as e:
        print(f"✗ Ошибка MTT API: {e}")
        return None


def wait_for_voice_call_code(phone_number: str, timeout: int = 120):
    """Ждать звонок от WhatsApp и получить код верификации"""
    print(f"\n📞 Ожидаю звонок от WhatsApp на {phone_number}...")
    print(f"⏳ Таймаут: {timeout} секунд")
    
    # Формируем номер (без +)
    phone = phone_number.lstrip('+')
    
    try:
        response = requests.post(
            "http://92.51.23.204:8000/api/wait-call",
            json={
                "phone_number": phone,
                "timeout": timeout
            },
            timeout=timeout + 10  # Даём запасное время для HTTP таймаута
        )
        response.raise_for_status()
        
        result = response.json()
        print(f"\n✅ Получен ответ от wait-call API:")
        print(f"📋 {result}")
        
        return result
    
    except requests.exceptions.RequestException as e:
        print(f"\n✗ Ошибка wait-call API: {e}")
        return None


def click_next_button(driver, device_name: str, phone_number: str):
    """Кликнуть по кнопке 'Далее' используя Appium"""
    try:
        print("⏳ Нажимаю Next через Appium...")
        
        # Ждём загрузки экрана
        print("   Жду загрузки экрана (3 сек)...")
        time.sleep(3)
        
        # Попытка 1: Ищем кнопку "Next" по тексту
        print("   Ищу кнопку 'Next'...")
        try:
            next_btn = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Next").clickable(true)')
            next_btn.click()
            print("✓ Нажата кнопка 'Next'")
            time.sleep(2)
        except:
            print("   Кнопка 'Next' не найдена, попытка 2...")
            # Попытка 2: По ID
            try:
                next_btn = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.whatsapp:id/registration_submit").clickable(true)')
                next_btn.click()
                print("✓ Нажата кнопка по ID")
                time.sleep(2)
            except Exception as e:
                print(f"   Кнопка не найдена: {e}")
                print("   Пропускаю...")
        
        # Ждём экрана с "Connecting" и появления диалога Yes/Да (polling до 20 сек)
        print("\n⏳ Жду 'Connecting...' и диалог подтверждения (до 20 сек)...")
        yes_clicked = False
        for i in range(40):  # 40 * 0.5s = 20s
            source = driver.page_source
            if "Connecting" in source:
                if i % 6 == 0 and i > 0:
                    print("  ⏳ Всё ещё 'Connecting...'")
            # Пытаемся найти и кликнуть Yes/Да
            yes_btn = None
            yes_selectors = [
                'new UiSelector().text("Yes").clickable(true)',
                'new UiSelector().text("Да").clickable(true)',
                'new UiSelector().textContains("Yes").clickable(true)',
                'new UiSelector().textContains("Да").clickable(true)',
                'new UiSelector().resourceId("android:id/button1").clickable(true)',
            ]
            for sel in yes_selectors:
                try:
                    yes_btn = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, sel)
                    print(f"✓ Найдена кнопка по селектору: {sel}")
                    break
                except Exception:
                    continue
            if yes_btn:
                yes_btn.click()
                yes_clicked = True
                print("✓ Нажата кнопка подтверждения")
                time.sleep(3)
                break
            time.sleep(0.5)
        if not yes_clicked:
            print("⚠️  Кнопка 'Yes'/'Да' не найдена за 20 сек")
            try:
                with open("yes_wait_screen.xml", "w", encoding="utf-8") as f:
                    f.write(source)
                print("✓ Сохранил yes_wait_screen.xml для анализа")
            except Exception:
                pass
        
        # Ждём экрана с кнопкой "Verify another way"
        print("\n⏳ Жду экрана с разрешениями (макс 10 сек)...")
        time.sleep(2)
        
        # Ищем и кликаем "Verify another way"
        print("⏳ Ищу кнопку 'Verify another way'...")
        verify_btn = None
        verify_selectors = [
            'new UiSelector().text("Verify another way").clickable(true)',
            'new UiSelector().text("Подтвердить другим способом").clickable(true)',
            'new UiSelector().textContains("Verify").clickable(true)',
            'new UiSelector().textContains("другим способом").clickable(true)',
            'new UiSelector().resourceId("com.whatsapp:id/secondary_button").clickable(true)',
        ]
        for sel in verify_selectors:
            try:
                verify_btn = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, sel)
                print(f"✓ Найдена кнопка по селектору: {sel}")
                break
            except Exception:
                continue
        if verify_btn:
            verify_btn.click()
            print("✓ Нажата кнопка 'Verify another way'")
            time.sleep(3)
        else:
            print("⚠️  Кнопка 'Verify another way/Подтвердить другим способом' не найдена")
        
        # Выбираем "Аудиозвонок" по индексам name/checkbox и жмём через MEmu adb
        print("\n⏳ Ищу 'Аудиозвонок' и тапаю по чекбоксу (adb)...")
        try:
            names = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.whatsapp:id/reg_method_name")')
            boxes = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.whatsapp:id/reg_method_checkbox")')
            target_idx = None
            for idx, el in enumerate(names):
                try:
                    txt = el.text
                except Exception:
                    txt = ""
                print(f"[{idx}] reg_method_name='{txt}'")
                if txt.strip() == "Аудиозвонок":
                    target_idx = idx
            if target_idx is not None and target_idx < len(boxes):
                rect = boxes[target_idx].rect
                tap_x = rect["x"] + rect["width"] // 2
                tap_y = rect["y"] + rect["height"] // 2
                adb_cmd = os.getenv("ADB_PATH") or r"C:\Program Files\Microvirt\MEmu\adb.exe"
                subprocess.run([adb_cmd, "-s", device_name, "shell", "input", "tap", str(tap_x), str(tap_y)], check=True)
                print(f"✓ adb tap 'Аудиозвонок' @ ({tap_x},{tap_y}) через {adb_cmd}")
                time.sleep(3)  # даём время зафиксировать выбор перед Continue
            else:
                print("⚠️ 'Аудиозвонок' не найден среди reg_method_name")
        except Exception as e:
            print(f"⚠️  Не удалось выбрать 'Аудиозвонок': {e}")
        
        # Нажимаем CONTINUE
        print("\n⏳ Ищу кнопку 'CONTINUE' / 'Продолжить'...")
        cont_btn = None
        cont_selectors = [
            'new UiSelector().resourceId("com.whatsapp:id/continue_button").clickable(true)',
            'new UiSelector().text("ПРОДОЛЖИТЬ").clickable(true)',
            'new UiSelector().text("Продолжить").clickable(true)',
            'new UiSelector().text("CONTINUE").clickable(true)',
            'new UiSelector().textContains("CONTINUE").clickable(true)',
            'new UiSelector().textContains("родолж").clickable(true)',
        ]
        for sel in cont_selectors:
            try:
                cont_btn = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, sel)
                print(f"✓ Найдена кнопка по селектору: {sel}")
                break
            except Exception:
                continue
        if cont_btn:
            cont_btn.click()
            print("✓ Нажата кнопка 'CONTINUE/Продолжить'")
            time.sleep(3)
        else:
            print("⚠️  Кнопка 'CONTINUE/Продолжить' не найдена")
        
        # Ждём код верификации
        print("\n⏳ Ожидаю звонок и код верификации...")
        call_result = wait_for_voice_call_code(phone_number, timeout=120)
        
        if call_result and call_result.get('status') == 'success':
            code = call_result.get('code')
            print(f"\n✅ Звонок получен! Код: {code}")
            
            # Вводим код через Appium
            print(f"\n⌨️  Ввожу код {code}...")
            time.sleep(2)
            
            try:
                code_input = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.whatsapp:id/verify_sms_code_input")')
                code_input.send_keys(code)
                print(f"✅ Код {code} введён")
                time.sleep(3)
            except:
                print("⚠️  Поле ввода кода не найдено")
            
            print("\n🎉 Регистрация завершена!")
        else:
            print("\n⚠️ Не удалось получить звонок")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"✗ Ошибка в click_next_button: {error_msg}")
        return False


def get_page_source(driver):
    """Получить исходный код страницы"""
    return driver.page_source


def print_page_dump(driver):
    """Вывести информацию о всех элементах на странице"""
    try:
        source = driver.page_source
        # Сохранить в файл для анализа
        with open("page_source.xml", "w") as f:
            f.write(source)
        print("\n✓ Page source сохранен в page_source.xml")
        print(f"✓ Размер: {len(source)} символов")
        
        # Вывести первые элементы с текстом
        import re
        texts = re.findall(r'text="([^"]+)"', source)
        buttons = re.findall(r'resource-id="([^"]*button[^"]*)"', source, re.IGNORECASE)
        print(f"\n✓ Найдено текстов: {len(set(texts))}")
        print(f"✓ Примеры текстов: {set(texts)}")
        print(f"\n✓ Найдено кнопок: {buttons}")
    except Exception as e:
        print(f"Ошибка при получении page source: {e}")


def main():
    phone_number = "79810890170"
    avd_name = "Pixel_4_API_26"
    port = 5554
    device_name = MEMU_DEVICE if USE_MEMU else f"emulator-{port}"
    max_retries = 3
    attempt = 0
    success = False
    emulator_recreated = False  # Флаг: пересоздан ли эмулятор
    
    # Проверяем нужно ли показывать GUI (для дебага)
    show_gui = os.getenv("SHOW_GUI", "false").lower() in ["true", "1", "yes"]
    if show_gui:
        print("🖥️  GUI режим включен (SHOW_GUI=true)")
    
    if USE_MEMU:
        print(f"📱 Режим MEMU активирован, используется: {MEMU_DEVICE}")
        max_retries = 1  # Для MEMU достаточно одной попытки
    
    while attempt < max_retries:
        attempt += 1
        print(f"\n{'=' * 70}")
        print(f"ПОПЫТКА {attempt}/{max_retries}")
        print(f"{'=' * 70}")
        
        try:
            # 1. Запустить эмулятор
            device_name = start_emulator(avd_name, port=port, show_gui=show_gui)
            
            # 2. Сбросить данные WhatsApp (вместо переустановки)
            print("🔄 Сбрасываю данные WhatsApp...")
            subprocess.run([ADB_PATH, "-s", device_name, "shell", "pm", "clear", "com.whatsapp"], capture_output=True)
            print("✓ Данные сброшены")
            
            # 4. Подключиться через Appium (к Settings, без запуска WA)
            # Примечание: connect_appium уже поправлен на com.android.settings
            driver = connect_appium(device_name)
            
            
            # 4.2 Запустить WhatsApp через драйвер
            print("📱 Запускаю WhatsApp...")
            driver.activate_app("com.whatsapp")
            time.sleep(5)
            
            # 5. Кликнуть "Согласиться"
            click_agree_button(driver)
            
            # 6. Ввести номер телефона
            enter_phone_number(driver, phone_number)
            
            # 7. Настроить перенаправление звонков на SIP
            redirect_calls_to_sip(phone_number)
            
            # 8. Нажать "Далее" и пройти регистрацию через Appium
            click_next_button(driver, device_name, phone_number)
            
            # Если добрались сюда - успех!
            success = True
            break
            
        except Exception as e:
            error_msg = str(e)
            print(f"\n❌ Ошибка на попытке {attempt}: {error_msg}")
            
            # Для MEMU не пересоздаём, просто выходим
            if USE_MEMU:
                print("❌ MEMU требует ручного перезапуска. Завершаю.")
                break
            
            # Проверяем была ли это блокировка от WhatsApp ИЛИ эмулятор не поднялся
            if "WhatsApp blocked login" in error_msg or "Emulator failed to start" in error_msg:
                if "WhatsApp blocked login" in error_msg:
                    print("🔄 Обнаружена блокировка WhatsApp. Пересоздаю эмулятор и выхожу...")
                    
                    # Убиваем текущий эмулятор
                    print(f"\n🔪 Убиваю эмулятор на порту {port}...")
                    subprocess.run(
                        [ADB_PATH, "-s", device_name, "emu", "kill"],
                        capture_output=True,
                        timeout=10
                    )
                    time.sleep(2)
                    
                    # Убиваем процесс если еще жив
                    subprocess.run(
                        ["pkill", "-f", f"emulator.*-port {port}"],
                        capture_output=True
                    )
                    time.sleep(2)
                    
                    # Запускаем пересоздание эмулятора
                    print(f"🏗️  Пересоздаю эмулятор с нуля...")
                    
                    # Получаем абсолютный путь к скрипту пересоздания
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    recreate_script = os.path.join(script_dir, "recreate_emulator.py")
                    
                    if not os.path.exists(recreate_script):
                        print(f"❌ Скрипт пересоздания не найден: {recreate_script}")
                        break
                    
                    print(f"   Вызываю: {sys.executable} {recreate_script}")
                    recreate_cmd = [
                        sys.executable,
                        recreate_script,
                        str(port),
                        avd_name
                    ]
                    
                    result = subprocess.run(recreate_cmd, cwd=script_dir)
                    print(f"   Результат: return code = {result.returncode}")
                    
                    if result.returncode == 0:
                        print(f"✅ Эмулятор пересоздан. Выхожу.")
                    else:
                        print(f"❌ Не удалось пересоздать эмулятор (exit code: {result.returncode})")
                    break
                    
                elif "Emulator failed to start" in error_msg:
                    print("🔄 Эмулятор не поднялся. Пересоздаю эмулятор...")
                    
                    # Пересоздаем ТОЛЬКО ОДИН РАЗ
                    if not emulator_recreated and attempt < max_retries:
                        # Убиваем текущий эмулятор
                        print(f"\n🔪 Убиваю эмулятор на порту {port}...")
                        subprocess.run(
                            [ADB_PATH, "-s", device_name, "emu", "kill"],
                            capture_output=True,
                            timeout=10
                        )
                        time.sleep(2)
                        
                        # Убиваем процесс если еще жив
                        subprocess.run(
                            ["pkill", "-f", f"emulator.*-port {port}"],
                            capture_output=True
                        )
                        time.sleep(2)
                        
                        # Запускаем пересоздание эмулятора
                        print(f"🏗️  Пересоздаю эмулятор с нуля...")
                        
                        # Получаем абсолютный путь к скрипту пересоздания
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        recreate_script = os.path.join(script_dir, "recreate_emulator.py")
                        
                        if not os.path.exists(recreate_script):
                            print(f"❌ Скрипт пересоздания не найден: {recreate_script}")
                            break
                        
                        print(f"   Вызываю: {sys.executable} {recreate_script}")
                        recreate_cmd = [
                            sys.executable,
                            recreate_script,
                            str(port),
                            avd_name
                        ]
                        
                        result = subprocess.run(recreate_cmd, cwd=script_dir)
                        print(f"   Результат: return code = {result.returncode}")
                        
                        if result.returncode == 0:
                            print(f"✅ Эмулятор пересоздан, переходу на следующую попытку...")
                            emulator_recreated = True  # Отмечаем что пересоздали
                            time.sleep(3)
                            continue
                        else:
                            print(f"❌ Не удалось пересоздать эмулятор (exit code: {result.returncode})")
                            break
                    else:
                        # Либо уже пересоздали, либо нет больше попыток
                        if emulator_recreated:
                            print(f"❌ Эмулятор уже был пересоздан, но блокировка осталась. Завершаю.")
                        else:
                            print(f"❌ Исчерпаны все попытки ({max_retries})")
                        break
            else:
                # Для других ошибок - просто выходим
                print(f"✗ Критическая ошибка (не блокировка): {error_msg}")
                break
    
    # Финальный вывод
    print(f"\n{'=' * 70}")
    if success:
        print("✅ УСПЕШНО! Регистрация завершена!")
    else:
        print("❌ РЕГИСТРАЦИЯ НЕ УДАЛАСЬ")
    print(f"{'=' * 70}")
    
    return success


if __name__ == "__main__":
    main()

