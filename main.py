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

# MEMU device ID (замени на свой если другой инстанс)
MEMU_DEVICE = os.getenv("MEMU_DEVICE", "127.0.0.1:21613")
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
        "appPackage": "com.whatsapp",
        "appActivity": ".Main",
        "noReset": True,
        "fullReset": False,
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
    """Кликнуть по кнопке 'Согласиться и продолжить'"""
    try:
        # Нажать OK на диалоге про ROM (координаты из page_source: [472,1260][648,1392])
        print("⏳ Нажимаем OK на диалоге про ROM...")
        driver.tap([(560, 1326)])  # Центр кнопки OK
        time.sleep(2)
        
        # Теперь должна быть кнопка "AGREE AND CONTINUE"
        print("⏳ Ищем кнопку AGREE AND CONTINUE...")
        agree_btn = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("AGREE AND CONTINUE").clickable(true)')
        agree_btn.click()
        print("✓ Нажата кнопка 'AGREE AND CONTINUE'")
        time.sleep(2)
    except Exception as e:
        print(f"✗ Ошибка: {e}")


def enter_phone_number(driver, phone_number: str):
    """Ввести номер телефона"""
    try:
        # Сначала нажать Allow на диалоге про уведомления (обязательно есть)
        print("⏳ Ищу диалог про уведомления (polling до 10 сек)...")
        max_attempts = 20  # 20 попыток по 0.5 сек = 10 секунд
        allow_found = False
        
        for attempt in range(max_attempts):
            try:
                allow_btn = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Allow").clickable(true)')
                print(f"✓ Диалог найден на попытке {attempt + 1}, нажимаю Allow...")
                time.sleep(0.5)  # Небольшая задержка перед кликом
                allow_btn.click()
                print("✓ Нажата кнопка 'Allow'")
                time.sleep(2)
                allow_found = True
                break
            except:
                if attempt % 5 == 0 and attempt > 0:
                    print(f"  ⏳ Попытка {attempt}/{max_attempts}...")
                time.sleep(0.5)
        
        if not allow_found:
            raise Exception("Диалог про уведомления не появился за 10 секунд")
        
        # Найти оба поля ввода
        print("⏳ Ищем поля ввода...")
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
    """Кликнуть по кнопке 'Далее' используя Accessibility Service"""
    try:
        print("⏳ Нажимаю Next через Accessibility Service...")
        
        # ВАЖНО! Закрываем Appium драйвер чтобы не мешал Accessibility Service
        print("   Закрываю Appium драйвер...")
        driver.quit()
        
        # Ждем чтобы Accessibility Service получил доступ к UI
        print("   Жду восстановления Accessibility Service...")
        time.sleep(5)
        
        # Попытка 1: По тексту
        print("   Клик по тексту 'Next'...")
        subprocess.run([
            ADB_PATH, "-s", device_name, "shell", "am", "broadcast",
            "-a", "com.wa.clicker.CLICK",
            "--es", "find_by", "text",
            "--es", "value", "Next",
            "-n", "com.wa.clicker/.CommandReceiver"
        ], capture_output=True)
        # time.sleep(3)
        
        # # Попытка 2: По ID
        # print("   Попытка 2: Клик по ID...")
        # subprocess.run([
        #     ADB_PATH, "-s", device_name, "shell", "am", "broadcast",
        #     "-a", "com.wa.clicker.CLICK",
        #     "--es", "find_by", "id",
        #     "--es", "value", "com.whatsapp:id/registration_submit",
        #     "-n", "com.wa.clicker/.CommandReceiver"
        # ], capture_output=True)
        # time.sleep(3)
        
        # # Попытка 3: По координатам
        # print("   Попытка 3: Клик по координатам...")
        # subprocess.run([
        #     ADB_PATH, "-s", device_name, "shell", "am", "broadcast",
        #     "-a", "com.wa.clicker.CLICK",
        #     "--es", "find_by", "coordinates",
        #     "--es", "value", "540,2148",
        #     "-n", "com.wa.clicker/.CommandReceiver"
        # ], capture_output=True)
        # time.sleep(3)
        
        print("✓ Команды отправлены в Accessibility Service")
        
        # Даем время для загрузки экрана "Connecting..."
        print("\n⏳ Жду загрузки экрана (2 сек)...")
        time.sleep(2)
        
        # Ждем окончания "Connecting..." и появления диалога с Yes
        print("⏳ Жду окончания 'Connecting...' и появления диалога (опрос каждые 0.5 сек)...")
        max_wait = 20  # Максимум 20 секунд
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            # Используем exec-out для прямого вывода XML, с fallback на file-based метод
            try:
                dump_result = subprocess.run(
                    [ADB_PATH, "-s", device_name, "exec-out", "uiautomator", "dump", "/dev/tty"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            except subprocess.TimeoutExpired:
                print("  ⚠️ exec-out timeout, пробую через файл...")
                # Fallback: dump в файл и читаем
                try:
                    subprocess.run(
                        [ADB_PATH, "-s", device_name, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"],
                        capture_output=True,
                        timeout=10
                    )
                    dump_result = subprocess.run(
                        [ADB_PATH, "-s", device_name, "shell", "cat", "/sdcard/window_dump.xml"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                except subprocess.TimeoutExpired:
                    print("  ⚠️ И файловый метод timeout, пропускаю итерацию...")
                    time.sleep(1)
                    continue
            
            if dump_result.returncode == 0:
                # Если видим "Connecting" - показываем статус и продолжаем ждать
                if 'text="Connecting"' in dump_result.stdout:
                    print("  ⏳ Экран 'Connecting...' активен...")
                    time.sleep(0.5)
                    continue
                
                # Если "Connecting" нет и появился диалог с Yes - выходим
                # Ищем по resource-id как в дампе: android:id/button1
                if 'resource-id="android:id/button1"' in dump_result.stdout and 'text="Yes"' in dump_result.stdout:
                    print(f"✓ Connecting завершён, диалог появился (прождали {time.time() - start_time:.1f}с)")
                    break
            
            time.sleep(0.5)
        
        # Кликаем "Yes" для подтверждения номера
        print("⏳ Кликаю Yes для подтверждения номера...")
        subprocess.run([
            ADB_PATH, "-s", device_name, "shell", "am", "broadcast",
            "-a", "com.wa.clicker.CLICK",
            "--es", "find_by", "text",
            "--es", "value", "Yes",
            "-n", "com.wa.clicker/.CommandReceiver"
        ], capture_output=True)
        
        print("✓ Нажата кнопка Yes")
        
        # Ждем экран с разрешениями (15 секунд)
        print("\n⏳ Жду экран с разрешениями (4 сек)...")
        time.sleep(4)
        
        # Кликаем "Verify another way" по resource-id
        print("⏳ Кликаю 'Verify another way'...")
        subprocess.run([
            ADB_PATH, "-s", device_name, "shell", "am", "broadcast",
            "-a", "com.wa.clicker.CLICK",
            "--es", "find_by", "id",
            "--es", "value", "com.whatsapp:id/secondary_button",
            "-n", "com.wa.clicker/.CommandReceiver"
        ], capture_output=True)
        
        print("✓ Нажата кнопка 'Verify another way'")
        time.sleep(3)
        
        # Выбираем "Voice call" через ADB tap
        # Voice call LinearLayout: bounds="[44,1827][1036,1950]", центр: (540, 1889)
        print("\n⏳ Выбираю Voice call...")
        subprocess.run([
            ADB_PATH, "-s", device_name, "shell", "input", "tap", "540", "1889"
        ], capture_output=True)
        
        print("✓ Voice call выбран")
        time.sleep(2)
        
        # Нажимаем кнопку CONTINUE
        print("\n⏳ Нажимаю CONTINUE...")
        subprocess.run([
            ADB_PATH, "-s", device_name, "shell", "am", "broadcast",
            "-a", "com.wa.clicker.CLICK",
            "--es", "find_by", "id",
            "--es", "value", "com.whatsapp:id/continue_button",
            "-n", "com.wa.clicker/.CommandReceiver"
        ], capture_output=True)
        
        print("✓ CONTINUE нажат")
        
        # СРАЗУ запускаем ожидание звонка в отдельном потоке (чтобы не пропустить)
        call_result_container = {}
        
        def wait_for_call():
            call_result_container['result'] = wait_for_voice_call_code(phone_number, timeout=120)
        
        call_thread = threading.Thread(target=wait_for_call)
        call_thread.start()
        print("✓ Запущено ожидание звонка в фоне")
        
        # Ждем пока пройдет загрузчик "Requesting a call..."
        print("\n⏳ Жду окончания загрузчика 'Requesting a call...' (опрос каждые 0.5 сек, макс 15 сек)...")
        time.sleep(1)  # Даем загрузчику появиться
        max_wait = 15
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            dump_result = subprocess.run(
                [ADB_PATH, "-s", device_name, "exec-out", "uiautomator", "dump", "/dev/tty"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if dump_result.returncode == 0:
                # Проверяем на ошибку "Login not available"
                if 'text="Login not available right now"' in dump_result.stdout:
                    print("\n❌ ОШИБКА: WhatsApp заблокировал вход!")
                    print("❌ 'Login not available right now'")
                    print("❌ For security reasons, we can't log you in right now.")
                    raise Exception("WhatsApp blocked login - 'Login not available right now'")
                
                # Если видим загрузчик - продолжаем ждать
                if 'Requesting a call' in dump_result.stdout:
                    print("  ⏳ Загрузчик 'Requesting a call...' активен...")
                    time.sleep(0.5)
                    continue
                
                # Если загрузчик прошел и появился экран ввода кода - выходим
                if 'Verifying your number' in dump_result.stdout or 'Enter the 6-digit code' in dump_result.stdout:
                    print(f"✓ Загрузчик завершён (прождали {time.time() - start_time:.1f}с)")
                    break
            
            time.sleep(0.5)
        
        # Ждём результата от потока с ожиданием звонка
        print("\n⏳ Ожидаю результат от wait-call API...")
        call_thread.join()
        call_result = call_result_container.get('result')
        
        if call_result and call_result.get('status') == 'success':
            code = call_result.get('code')
            print(f"\n✅ Звонок получен! Код: {code}")
            
            # Вводим код через Accessibility Service
            print(f"\n⌨️  Ввожу код {code} через Accessibility Service...")
            time.sleep(2)  # Ждём загрузки экрана ввода кода
            
            subprocess.run([
                ADB_PATH, "-s", device_name, "shell", "am", "broadcast",
                "-a", "com.wa.clicker.TYPE_TEXT",
                "--es", "find_by", "id",
                "--es", "value", "com.whatsapp:id/verify_sms_code_input",
                "--es", "text", code,
                "-n", "com.wa.clicker/.CommandReceiver"
            ], capture_output=True)
            
            print(f"✅ Код {code} введён")
            
            # Даем время на загрузку экрана "Verifying..."
            print("\n⏳ Жду загрузки экрана Verifying (1 сек)...")
            time.sleep(1)
            
            # Ждём пока появится следующий экран (опрос каждые 0.5 сек)
            print("⏳ Жду появления следующего экрана после Verifying (опрос каждые 0.5 сек, макс 30 сек)...")
            max_wait = 30
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                # Используем exec-out для прямого вывода XML
                dump_result = subprocess.run(
                    [ADB_PATH, "-s", device_name, "exec-out", "uiautomator", "dump", "/dev/tty"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if dump_result.returncode == 0:
                    # Если появился следующий экран (NOT NOW или разрешения) - выходим
                    if 'text="NOT NOW"' in dump_result.stdout or 'text="Allow WhatsApp"' in dump_result.stdout:
                        print(f"✓ Verifying завершён, следующий экран появился (прождали {time.time() - start_time:.1f}с)")
                        break
                    
                    # Если видим "Verifying" - показываем статус
                    if 'text="Verifying"' in dump_result.stdout or 'Verifying' in dump_result.stdout:
                        print("  ⏳ Экран 'Verifying...' активен...")
                
                time.sleep(0.5)
            
            # Дополнительная задержка после завершения верификации
            print("⏳ Дополнительная задержка (3 сек)...")
            time.sleep(5)
            
            # Диалог 1: Нажимаем "NOT NOW" на диалоге разрешений (Contacts)
            print("\n⏳ Закрываю диалог разрешений (NOT NOW)...")
            subprocess.run([
                ADB_PATH, "-s", device_name, "shell", "input", "tap", "502", "1490"
            ], capture_output=True)
            time.sleep(7)
            
            # Диалог 2: Нажимаем "CANCEL" на диалоге восстановления резервной копии
            print("⏳ Закрываю диалог восстановления резервной копии (CANCEL)...")
            subprocess.run([
                ADB_PATH, "-s", device_name, "shell", "input", "tap", "504", "1465"
            ], capture_output=True)
            time.sleep(7)
            
            # Ввод имени профиля
            print("\n⏳ Ввожу имя профиля...")
            subprocess.run([
                ADB_PATH, "-s", device_name, "shell", "input", "tap", "518", "1054"
            ], capture_output=True)
            time.sleep(3)
            
            subprocess.run(
                f'adb -s {device_name} shell input text "John Smith"',
                shell=True,
                capture_output=True
            )
            
            print("✅ Имя введено")
            time.sleep(7)
            
            # Нажимаем Next на экране Profile info
            print("\n⏳ Нажимаю Next на экране Profile info...")
            subprocess.run([
                ADB_PATH, "-s", device_name, "shell", "am", "broadcast",
                "-a", "com.wa.clicker.CLICK",
                "--es", "find_by", "text",
                "--es", "value", "Next",
                "-n", "com.wa.clicker/.CommandReceiver"
            ], capture_output=True)
            
            print("✓ Next нажат")
            time.sleep(7)
            
            # Нажимаем Skip на экране Add your email
            print("\n⏳ Нажимаю Skip на экране Add your email...")
            subprocess.run([
                ADB_PATH, "-s", device_name, "shell", "am", "broadcast",
                "-a", "com.wa.clicker.CLICK",
                "--es", "find_by", "text",
                "--es", "value", "Skip",
                "-n", "com.wa.clicker/.CommandReceiver"
            ], capture_output=True)
            
            print("✓ Skip нажат")
            
            # Ждём готовности пользователя
            input("\n⏸  Нажми Enter когда будешь готов искать код (после манипуляций в ТГ)...")
            
            # Ждём появления чата с кодом верификации на главном экране
            print("\n⏳ Ищу сообщение с кодом (опрос каждую секунду, макс 60 сек)...")
            max_wait = 60
            start_time = time.time()
            found_code = None
            
            while time.time() - start_time < max_wait:
                # Дампим в файл и читаем (так надежнее чем exec-out)
                try:
                    subprocess.run(
                        [ADB_PATH, "-s", device_name, "shell", "uiautomator", "dump", "/sdcard/check.xml"],
                        capture_output=True,
                        timeout=10
                    )
                    
                    dump_result = subprocess.run(
                        [ADB_PATH, "-s", device_name, "shell", "cat", "/sdcard/check.xml"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                except subprocess.TimeoutExpired:
                    print("  ⚠️ uiautomator timeout, пропускаю итерацию...")
                    time.sleep(1)
                    continue
                
                if dump_result.returncode == 0:
                    # Ищем текст с кодом подтверждения (в русском или английском)
                    if 'код подтверждения' in dump_result.stdout or 'verification code' in dump_result.stdout:
                        # Извлекаем код (5 или 6 цифр)
                        code_match = re.search(r'(\d{5,6})', dump_result.stdout)
                        if code_match:
                            found_code = code_match.group(1)
                            print(f"\n🎉 КОД НАЙДЕН: {found_code}")
                            print(f"✓ Прождали {time.time() - start_time:.1f}с")
                            break
                        else:
                            print("  ⏳ Нашел сообщение, но нет цифр")
                    else:
                        elapsed = time.time() - start_time
                        print(f"  ⏳ Прождали {elapsed:.1f}с, сообщение еще не пришло...")
                
                time.sleep(1)
            else:
                print(f"\n❌ Код не появился за {max_wait} сек")
            
            if found_code:
                print(f"\n✅ Финальный код верификации: {found_code}")
            
            print("\n🎉 Регистрация WhatsApp завершена!")
            
            # Удаляем WhatsApp для чистого следующего запуска
            print("\n⏳ Удаляю WhatsApp...")
            subprocess.run([
                ADB_PATH, "-s", device_name, "uninstall", "com.whatsapp"
            ], capture_output=True)
            print("✓ WhatsApp удален")
            
        else:
            print("\n⚠️ Не удалось получить звонок")
            
            # Удаляем WhatsApp даже при ошибке
            print("\n⏳ Удаляю WhatsApp...")
            subprocess.run([
                ADB_PATH, "-s", device_name, "uninstall", "com.whatsapp"
            ], capture_output=True)
            print("✓ WhatsApp удален")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"✗ Ошибка в click_next_button: {error_msg}")
        
        # Если это ошибка блокировки - перебрасываем её для обработки в main()
        if "WhatsApp blocked login" in error_msg:
            raise
        
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
    phone_number = "79820079022"
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
            
            # 2. Установить Accessibility Service (СНАЧАЛА!)
            if not install_accessibility_service(device_name):
                print("⚠️  Accessibility Service не установлен, но продолжаю...")
            
            # 3. Удалить старый WhatsApp и переустановить
            print("\n🔄 Удаляю старый WhatsApp...")
            subprocess.run([
                ADB_PATH, "-s", device_name, "uninstall", "com.whatsapp"
            ], capture_output=True)
            print("✓ WhatsApp удален")
            time.sleep(1)
            
            print("📱 Устанавливаю WhatsApp...")
            install_whatsapp(device_name)
            print("✓ WhatsApp установлен")
            
            # 4. Открыть WhatsApp
            open_whatsapp(device_name)
            
            # 5. Подключиться через Appium
            driver = connect_appium(device_name)
            
            # 6. Кликнуть "Согласиться"
            click_agree_button(device_name)
            
            # 7. Ввести номер телефона
            enter_phone_number(driver, phone_number)
            
            # 8. Настроить перенаправление звонков на SIP
            redirect_calls_to_sip(phone_number)
            
            # 9. Нажать "Далее" через Accessibility Service
            # (driver.quit() вызывается внутри click_next_button)
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

