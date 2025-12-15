import subprocess
import os
import sys
import re
import time

# Путь к memuc.exe (CLI для управления MEmu)
# Обычно лежит там же, где и MEmu.exe
MEMUC_PATH = r"C:\Program Files\Microvirt\MEmu\memuc.exe"

def run_memuc(args):
    """Запуск команды memuc и возврат вывода"""
    if not os.path.exists(MEMUC_PATH):
        print(f"❌ Ошибка: не найден memuc.exe по пути: {MEMUC_PATH}")
        sys.exit(1)
        
    cmd = [MEMUC_PATH] + args
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    return result.stdout.strip()

def main():
    print("🚀 Создаю новый инстанс MEmu...")

    # 1. Создаем Android 9.0 64-bit (код версии 96)
    # Коды: 51=Android 5, 71=Android 7 (32), 76=Android 7 (64), 96=Android 9 (64)
    output = run_memuc(["create", "96"])
    
    # Парсим индекс из ответа "SUCCESS: create vm finished. index: 5"
    match = re.search(r"index:\s*(\d+)", output)
    if not match:
        print(f"❌ Не удалось создать инстанс. Вывод: {output}")
        return

    index = int(match.group(1))
    print(f"✓ Инстанс создан. Индекс: {index}")

    # 2. Настраиваем производительность (2 CPU, 1536 RAM)
    print("⚙️  Настраиваю CPU/RAM...")
    run_memuc(["setconfigex", "-i", str(index), "cpus", "2"])
    run_memuc(["setconfigex", "-i", str(index), "memory", "1536"])

    # 3. Настраиваем разрешение (720x1280, 240dpi, Mobile)
    print("⚙️  Настраиваю экран...")
    run_memuc(["setconfigex", "-i", str(index), "is_custom_resolution", "1"])
    run_memuc(["setconfigex", "-i", str(index), "resolution_width", "720"])
    run_memuc(["setconfigex", "-i", str(index), "resolution_height", "1280"])
    run_memuc(["setconfigex", "-i", str(index), "v_dpi", "240"])

    # 4. Настраиваем рендер (DirectX) и Root
    # graphics_render_mode: 0 = OpenGL, 1 = DirectX
    print("⚙️  Включаю DirectX и Root...")
    run_memuc(["setconfigex", "-i", str(index), "graphics_render_mode", "1"])
    run_memuc(["setconfigex", "-i", str(index), "is_root_mode", "1"])
    run_memuc(["setconfigex", "-i", str(index), "root_mode", "1"])

    # 5. Запускаем (один раз)
    print(f"▶️  Запускаю инстанс {index}...")
    run_memuc(["start", "-i", str(index)])
    
    # 6. Вычисляем ADB порт
    # Базовый порт 21503, шаг 10. Индекс 0 -> 21503, Индекс 1 -> 21513
    adb_port = 21503 + (index * 10)
    device_name = f"127.0.0.1:{adb_port}"


    # 7. Устанавливаем ProxyDroid
    apk_proxy = "proxydroid.apk"
    if os.path.exists(apk_proxy):
        print(f"🌍 Устанавливаю {apk_proxy}...")
        run_memuc(["installapp", "-i", str(index), os.path.abspath(apk_proxy)])
        print(f"✓ ProxyDroid установлен")
    else:
        print(f"⚠️  Файл {apk_proxy} не найден")

    # 8. Устанавливаем WhatsApp
    apk_wa = "whatsapp.apk"
    if os.path.exists(apk_wa):
        print(f"📱 Устанавливаю {apk_wa}...")
        run_memuc(["installapp", "-i", str(index), os.path.abspath(apk_wa)])
        print(f"✓ WhatsApp установлен")
    else:
        print(f"⚠️  Файл {apk_wa} не найден, пропуск установки WhatsApp")

    # 9. Настраиваем ProxyDroid (Config + Start)
    print("🌍 Настраиваю конфиг ProxyDroid...")
    ADB_PATH = r"C:\Program Files\Microvirt\MEmu\adb.exe" # Или из env
    local_conf = "proxydroid_prefs.xml"
    remote_conf = "/data/data/org.proxydroid/shared_prefs/org.proxydroid_preferences.xml"
    
    # Ждем загрузки
    print("⏳ Жду загрузки Android (10 сек)...")
    time.sleep(10)

    if os.path.exists(local_conf):
        try:
            # Force stop
            subprocess.run([ADB_PATH, "-s", device_name, "shell", "am", "force-stop", "org.proxydroid"], capture_output=True)
            # Push config
            subprocess.run([ADB_PATH, "-s", device_name, "push", local_conf, remote_conf], check=True)
            # Permissions
            subprocess.run([ADB_PATH, "-s", device_name, "shell", "chmod", "777", remote_conf], check=True)
            print("✓ Конфиг ProxyDroid загружен")
            
            # Не запускаем приложение здесь, сделаем это в main.py через Appium (для обработки диалогов Root)
            # subprocess.run([ADB_PATH, "-s", device_name, "shell", "monkey", "-p", "org.proxydroid", "1"], capture_output=True)
            
        except Exception as e:
             print(f"⚠️ Ошибка настройки ProxyDroid: {e}")
    else:
        print(f"⚠️ Файл {local_conf} не найден, пропускаю настройку")

    print("\n" + "="*40)
    print(f"✅ Готово! Новый девайс запущен.")
    print("="*40)
    # Вывод в формате, готовом для вставки в main.py
    print(f'MEMU_DEVICE = "{device_name}"')
    print("="*40)

if __name__ == "__main__":
    main()

