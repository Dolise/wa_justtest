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
    import sys
    count = 1
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            print("⚠️ Некорректное число, создаю 1 инстанс")
    
    print(f"🚀 Запускаю создание {count} инстансов MEmu...")
    
    for i in range(count):
        print(f"\n--- Инстанс {i+1} из {count} ---")
        create_one_instance()

def create_one_instance():
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
    # ...
    # 9.1 Сразу после создания пробуем включить ROOT принудительно через правку файла конфига
    # (потому что memuc иногда не включает)
    try:
        # Пытаемся найти папку с VM конфигами
        # Обычно: C:\Program Files\Microvirt\MEmu\MemuHyperv VMs\MEmu_{index}\MEmu_{index}.memu
        # Но у нас index может быть любым.
        # Проще найти папку VMs
        vms_dir = r"C:\Program Files\Microvirt\MEmu\MemuHyperv VMs"
        if not os.path.exists(vms_dir):
             # Попробуем альтернативу
             vms_dir = os.path.expanduser("~\\Documents\\MEmu Hyperv VMs")
        
        if os.path.exists(vms_dir):
             # Ищем файл конфига для нашего индекса
             # Папка может называться MEmu_{index} или просто лежать там
             # Попробуем найти файл MEmu_{index}.memu
             target_file = None
             import glob
             # Ищем рекурсивно
             print(f"🔎 Ищу конфиг MEmu_{index}.memu в {vms_dir}...")
             candidates = glob.glob(os.path.join(vms_dir, f"**", f"MEmu_{index}.memu"), recursive=True)
             if not candidates:
                 print(f"⚠️ Конфиг не найден рекурсивно. Пробую искать просто по имени папки...")
                 # Попробуем предсказать путь: MemuHyperv VMs\MEmu_{index}\MEmu_{index}.memu
                 predicted = os.path.join(vms_dir, f"MEmu_{index}", f"MEmu_{index}.memu")
                 if os.path.exists(predicted):
                     candidates = [predicted]
                 else:
                     print(f"⚠️ И по пути {predicted} тоже нет.")
             
             if candidates:
                 target_file = candidates[0]
                 print(f"🔧 Найден файл конфига: {target_file}")
                 
                 # Читаем и правим
                 with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
                     content = f.read()
                 
                 new_content = content
                 if 'enable_root" value="0"' in content:
                     new_content = new_content.replace('enable_root" value="0"', 'enable_root" value="1"')
                     print("  ✓ Исправлено: enable_root -> 1")
                 if 'root_mode" value="0"' in content:
                     new_content = new_content.replace('root_mode" value="0"', 'root_mode" value="1"')
                     print("  ✓ Исправлено: root_mode -> 1")
                 if 'is_root_mode" value="0"' in content:
                     new_content = new_content.replace('is_root_mode" value="0"', 'is_root_mode" value="1"')
                     print("  ✓ Исправлено: is_root_mode -> 1")
                     
                 if new_content != content:
                     with open(target_file, 'w', encoding='utf-8') as f:
                         f.write(new_content)
                     print("✅ Root включен принудительно в файле!")
                     
                     # Перезагружаем эмулятор чтобы применилось
                     print("🔄 Перезапускаю эмулятор для применения Root...")
                     run_memuc(["stop", "-i", str(index)])
                     time.sleep(2)
                     run_memuc(["start", "-i", str(index)])
                     time.sleep(5)
                 else:
                     print("  (Root уже включен в файле)")
    except Exception as e:
        print(f"⚠️ Ошибка принудительного включения Root: {e}")

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

if __name__ == "__main__":
    main()

