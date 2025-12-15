import subprocess
import time
import os
import sys
import re
import requests
import threading
from pathlib import Path

# ==========================================
# КОНФИГУРАЦИЯ
# ==========================================

# Путь к ADB (для Windows с MEMU)
ADB_PATH = os.getenv("ADB_PATH") or r"C:\Program Files\Microvirt\MEmu\adb.exe"

# ==========================================
# ADB CONTROLLER (ЗАМЕНА APPIUM)
# ==========================================

class ADBController:
    def __init__(self, device_name):
        self.device_name = device_name
        self.adb = ADB_PATH

    def run_shell(self, cmd, timeout=10):
        """Выполнить shell команду"""
        full_cmd = [self.adb, "-s", self.device_name, "shell"] + cmd.split()
        try:
            return subprocess.run(full_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"⚠️ Timeout команды: {cmd}")
            return None

    def tap(self, x, y):
        """Клик по координатам"""
        self.run_shell(f"input tap {x} {y}")

    def text(self, text):
        """Ввод текста"""
        # Экранирование пробелов и спецсимволов для ADB
        escaped_text = text.replace(" ", "%s").replace("'", r"\'")
        self.run_shell(f"input text {escaped_text}")

    def keyevent(self, keycode):
        """Нажатие кнопки (66=ENTER, 67=BACKSPACE, 3=HOME)"""
        self.run_shell(f"input keyevent {keycode}")

    def get_ui_dump(self):
        """Получить XML текущего экрана через uiautomator"""
        remote_dump = "/data/local/tmp/window_dump.xml"
        
        # 1. Создаем дамп на устройстве
        # Иногда uiautomator падает, поэтому пробуем пару раз
        for _ in range(2):
            res = self.run_shell(f"uiautomator dump {remote_dump}", timeout=15)
            if res and "UI hierchary dumped to" in res.stdout:
                break
            time.sleep(1)

        # 2. Читаем файл прямо через cat (быстрее, чем pull)
        res = self.run_shell(f"cat {remote_dump}", timeout=5)
        if res and res.stdout:
            return res.stdout
        return ""

    def find_element(self, text=None, resource_id=None, class_name=None, index=0):
        """
        Ищет элемент в XML дампе.
        Возвращает словарь {x, y, bounds} или None.
        """
        xml = self.get_ui_dump()
        if not xml:
            return None

        # Формируем паттерн поиска
        # Пример: <node index="0" text="AGREE" resource-id="id" ... bounds="[0,0][100,100]" />
        
        # Простой парсинг регулярками (быстрее lxml для простых задач)
        # Ищем все ноды
        nodes = re.findall(r'<node [^>]*>', xml)
        
        matches = []
        for node in nodes:
            # Проверяем условия
            if text and text.lower() not in node.lower():
                continue
            if resource_id and resource_id not in node:
                continue
            if class_name and class_name not in node:
                continue
            
            # Если совпало, достаем координаты
            bounds_match = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node)
            if bounds_match:
                x1, y1, x2, y2 = map(int, bounds_match.groups())
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                matches.append({'x': center_x, 'y': center_y, 'raw': node})

        if len(matches) > index:
            return matches[index]
        return None

    def click_element(self, text=None, resource_id=None, timeout=10):
        """Ждет элемент и кликает по нему"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            el = self.find_element(text=text, resource_id=resource_id)
            if el:
                print(f"✓ Клик по '{text or resource_id}' ({el['x']}, {el['y']})")
                self.tap(el['x'], el['y'])
                return True
            time.sleep(1)
        print(f"⚠️ Элемент '{text or resource_id}' не найден за {timeout} сек")
        return False

    def wait_for_element(self, text=None, resource_id=None, class_name=None, timeout=20):
        """Ждет появления элемента"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            el = self.find_element(text=text, resource_id=resource_id, class_name=class_name)
            if el:
                return True
            time.sleep(1)
        return False

# ==========================================
# ЛОГИКА WHATSAPP
# ==========================================

def setup_proxydroid(adb: ADBController):
    """Настройка ProxyDroid (Без Appium!)"""
    print("\n🌍 Настраиваю ProxyDroid...")
    
    # 1. Заливаем конфиг
    local_conf = "proxydroid_prefs.xml"
    if os.path.exists(local_conf):
        print("📂 Загружаю конфиг...")
        adb.run_shell("am force-stop org.proxydroid")
        subprocess.run([ADB_PATH, "-s", adb.device_name, "push", local_conf, "/data/data/org.proxydroid/shared_prefs/org.proxydroid_preferences.xml"], capture_output=True)
        adb.run_shell("chmod 777 /data/data/org.proxydroid/shared_prefs/org.proxydroid_preferences.xml")
    
    # 2. Запускаем приложение (GUI), чтобы точно триггернуть запрос прав
    adb.run_shell("am start -n org.proxydroid/.MainActivity")
    time.sleep(3)

    # 2.1 Запускаем сервис (на всякий случай)
    adb.run_shell("am startservice -n org.proxydroid/.ProxyDroidService")
    adb.run_shell("am broadcast -a org.proxydroid.intent.action.START")
    time.sleep(2)
    
    # 3. Обработка диалогов (Хорошо -> Grant)
    print("🕵️ Проверяю диалоги прав...")
    
    # Кнопка "Хорошо" / "OK" в первом диалоге
    if adb.click_element(text="Хорошо", timeout=5) or adb.click_element(text="OK", timeout=1):
        time.sleep(1)
    
    # Кнопка "Grant" / "Разрешить" (Root)
    # Ищем по разным словам
    for txt in ["Grant", "Allow", "Разрешить", "Предоставить"]:
        if adb.click_element(text=txt, timeout=2):
            break

    print("✓ ProxyDroid настроен (надеюсь)")

def register_whatsapp(adb: ADBController, phone_number: str):
    """Регистрация WhatsApp на чистом ADB"""
    print(f"\n📱 Начинаю регистрацию номера {phone_number}...")
    
    # 1. Запуск WhatsApp
    adb.run_shell("am start -n com.whatsapp/.Main")
    time.sleep(3)
    
    # 2. Кнопка "Принять и продолжить"
    print("⏳ Ищу кнопку согласия...")
    if not adb.click_element(resource_id="com.whatsapp:id/eula_accept", timeout=10):
        # Фолбэк по тексту
        if not adb.click_element(text="AGREE", timeout=2):
             print("⚠️ Кнопка согласия не найдена! Пробую тапнуть в низ экрана.")
             adb.tap(360, 1150) # Примерно низ экрана 720x1280
    
    # 3. Ввод номера
    print("⏳ Ввожу номер...")
    if not adb.wait_for_element(class_name="android.widget.EditText", timeout=10):
        print("❌ Поля ввода не найдены")
        return False
    
    # Находим поля. Обычно [0] - код страны, [1] - телефон
    # Но find_element возвращает одно. Нужно найти все.
    # Для простоты используем логику:
    # 1. Тапаем в левое поле (код)
    # 2. Чистим
    # 3. Пишем код
    # 4. Тапаем в правое (телефон)
    # 5. Пишем телефон
    
    # Получаем координаты полей через дамп
    cc_field = adb.find_element(class_name="android.widget.EditText", index=0)
    phone_field = adb.find_element(class_name="android.widget.EditText", index=1)
    
    if cc_field and phone_field:
        # Вводим код страны (7)
        print("   Ввожу код страны...")
        adb.tap(cc_field['x'], cc_field['y'])
        time.sleep(0.5)
        # Очищаем (несколько раз Backspace)
        for _ in range(5): adb.keyevent(67)
        adb.text("7")
        
        # Вводим номер
        print("   Ввожу телефон...")
        adb.tap(phone_field['x'], phone_field['y'])
        time.sleep(0.5)
        phone_clean = phone_number.replace("+7", "").replace("7", "", 1) if phone_number.startswith("7") or phone_number.startswith("+7") else phone_number
        adb.text(phone_clean)
        time.sleep(1)
    else:
        print("❌ Не удалось найти координаты полей ввода")
        return False

    # 4. Жмем NEXT
    print("⏳ Жму 'Next'...")
    if not adb.click_element(text="Далее", timeout=5):
        adb.click_element(text="Next", timeout=1)
        # Фолбэк по ID
        adb.click_element(resource_id="com.whatsapp:id/registration_submit", timeout=1)
    
    # 5. Обработка "Connecting..." и "Yes"
    print("⏳ Жду 'Connecting' и подтверждение...")
    # Ждем пока Connecting уйдет (просто ждем кнопку Yes/Switch)
    # Ищем кнопку "Yes" / "OK" / "Да" в диалоге подтверждения
    confirmed = False
    for _ in range(20):
        if adb.click_element(text="Yes", timeout=1) or \
           adb.click_element(text="Да", timeout=0.5) or \
           adb.click_element(text="OK", timeout=0.5) or \
           adb.click_element(resource_id="android:id/button1", timeout=0.5):
            confirmed = True
            print("✓ Подтвердил номер")
            break
        time.sleep(1)
        
    if not confirmed:
        print("⚠️ Не удалось подтвердить номер (диалог не появился или пропущен)")

    # 5.1 Настраиваем переадресацию (пока WA думает)
    redirect_calls_to_sip(phone_number)

    # 6. Verify another way
    print("⏳ Ищу 'Verify another way'...")
    time.sleep(2) # Даем время анимации
    
    # Сначала проверим, не просит ли он доступ к SMS (иногда бывает)
    adb.click_element(text="Not now", timeout=1)
    adb.click_element(text="Не сейчас", timeout=0.5)

    if adb.click_element(text="Подтвердить другим способом", timeout=10) or \
       adb.click_element(text="Verify another way", timeout=2) or \
       adb.click_element(text="другим способом", timeout=1):
        print("✓ Выбрал другой способ")
        time.sleep(1)
        
        # 7. Выбираем Call Me
        print("⏳ Выбираем 'Call Me'...")
        if adb.click_element(text="Call me", timeout=5) or \
           adb.click_element(text="Позвонить", timeout=1) or \
           adb.click_element(text="Аудиозвонок", timeout=1):
            print("✓ Запрошен звонок (выбран пункт)")
            time.sleep(1)
            # Жмем "Продолжить" (если есть кнопка)
            # Иногда это радиобаттон и нужна кнопка внизу
            if adb.click_element(text="Continue", timeout=2) or \
               adb.click_element(text="Продолжить", timeout=1) or \
               adb.click_element(resource_id="com.whatsapp:id/continue_button", timeout=1):
                print("✓ Нажата кнопка 'Продолжить'")
        else:
            print("⚠️ Кнопка звонка не найдена (возможно, таймер?)")
    else:
        print("⚠️ Кнопка 'Verify another way' не найдена (возможно, сразу перешло к коду)")

    # 8. Ждем звонка
    print("\n📞 Ожидание звонка и ввод кода...")
    # Тут вызываем API ожидания звонка
    call_result = wait_for_voice_call_code(phone_number)
    
    if call_result and call_result.get('status') == 'success':
        code = str(call_result.get('code'))
        print(f"✅ Код получен: {code}")
        
        # Ввод кода
        # Обычно фокус уже стоит, но лучше найти поле
        # Поле ввода кода часто разбито на 6 полей или одно скрытое
        # Пробуем просто ввести текст
        adb.text(code)
        print("⌨️ Код введен")
        
        # 9. Финализация (Ввод имени)
        print("\n⏳ Жду экран ввода имени (до 40 сек)...")
        if adb.wait_for_element(resource_id="com.whatsapp:id/registration_name", timeout=40) or \
           adb.wait_for_element(text="Type your name here", timeout=1) or \
           adb.wait_for_element(text="Введите ваше имя", timeout=1):
            
            print("✓ Экран ввода имени найден")
            time.sleep(1)
            
            # Клик в поле (на всякий случай)
            adb.click_element(resource_id="com.whatsapp:id/registration_name", timeout=2)
            
            # Ввод имени
            adb.text("Alex")
            print("✓ Имя 'Alex' введено")
            adb.keyevent(66) # ENTER (скрыть клаву / подтвердить)
            time.sleep(1)
            
            # Жмем Далее
            if adb.click_element(text="Next", timeout=5) or \
               adb.click_element(text="Далее", timeout=1) or \
               adb.click_element(resource_id="com.whatsapp:id/register_name_accept", timeout=1):
                print("✓ Нажато 'Далее'")
                time.sleep(5)
                return True
            else:
                print("⚠️ Кнопка 'Далее' не найдена")
        else:
            print("⚠️ Экран ввода имени не появился за 40 сек")

        return True
    else:
        print("❌ Звонок не прошел")
        return False

# ==========================================
# API МЕТОДЫ
# ==========================================

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
        return result
    
    except requests.exceptions.RequestException as e:
        print(f"✗ Ошибка MTT API: {e}")
        return None

def wait_for_voice_call_code(phone_number: str, timeout=120):
    """API запрос (копия из старого скрипта)"""
    print(f"⏳ Жду звонок на {phone_number} ({timeout} сек)...")
    phone = phone_number.lstrip('+')
    try:
        response = requests.post(
            "http://92.51.23.204:8000/api/wait-call",
            json={"phone_number": phone, "timeout": timeout},
            timeout=timeout + 10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"✗ Ошибка API: {e}")
        return None

# ==========================================
# MAIN
# ==========================================

def main():
    phone_number = "79820910433"
    
    # 1. Определяем девайс (MEmu)
    print("🔍 Ищем MEmu девайс...")
    res = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True)
    
    device_name = None
    # Ищем 127.0.0.1:2xxxx
    match = re.search(r"(127\.0\.0\.1:2\d{4})\s+device", res.stdout)
    if match:
        device_name = match.group(1)
        print(f"✓ Найден девайс: {device_name}")
    else:
        # Дефолт для первого инстанса
        device_name = "127.0.0.1:21503"
        print(f"⚠️ Девайс не найден в списке, пробую дефолт: {device_name}")
        # Пытаемся подключиться
        subprocess.run([ADB_PATH, "connect", device_name], capture_output=True)

    # Инициализация контроллера
    adb = ADBController(device_name)
    
    # 2. Очистка и подготовка
    print("🧹 Очистка...")
    adb.run_shell("pm clear com.whatsapp")
    
    # 3. Настройка прокси
    # setup_proxydroid(adb)
    
    # 4. Регистрация
    register_whatsapp(adb, phone_number)
    
    print("\n🏁 Скрипт завершен")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Прервано пользователем")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
