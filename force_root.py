import os
import glob

# Путь к папке с конфигами MEmu (обычно в Documents или Program Files)
# Попробуем найти через MEMU_PATH
MEMU_DIR = r"C:\Program Files\Microvirt\MEmu"
MEMU_VMS_DIR = r"C:\Program Files\Microvirt\MEmu\MemuHyperv VMs" # Проверим этот путь, или стандартный

def find_memu_vms():
    # Попробуем найти папку VMs
    candidates = [
        r"C:\Program Files\Microvirt\MEmu\MemuHyperv VMs",
        r"D:\Program Files\Microvirt\MEmu\MemuHyperv VMs",
        os.path.expanduser("~\\Documents\\MEmu Hyperv VMs"),
        os.path.expanduser("~\\MEmu Hyperv VMs")
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def enable_root_in_file(filepath):
    print(f"🔧 Обрабатываю: {filepath}")
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        new_lines = []
        changed = False
        for line in lines:
            # Ищем enable_root или root_mode
            if 'enable_root' in line:
                if 'value="1"' not in line:
                    line = line.replace('value="0"', 'value="1"')
                    changed = True
                    print("  ✓ enable_root -> 1")
            elif 'root_mode' in line:
                if 'value="1"' not in line:
                    line = line.replace('value="0"', 'value="1"')
                    changed = True
                    print("  ✓ root_mode -> 1")
            elif 'is_root' in line: # иногда так
                 if 'value="1"' not in line:
                    line = line.replace('value="0"', 'value="1"')
                    changed = True
                    print("  ✓ is_root -> 1")
            
            new_lines.append(line)
            
        if changed:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print("✅ Файл обновлен!")
        else:
            print("  (Root уже включен или параметр не найден)")
            
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")

def main():
    vms_dir = find_memu_vms()
    if not vms_dir:
        print("❌ Не нашел папку с VM конфигами MEmu.")
        return

    print(f"📂 Папка VM: {vms_dir}")
    
    # Ищем .memu файлы
    configs = glob.glob(os.path.join(vms_dir, "**", "*.memu"), recursive=True)
    if not configs:
        # Попробуем старый формат .xml в корне
        configs = glob.glob(os.path.join(vms_dir, "*.memu"))
    
    print(f"Найдено конфигов: {len(configs)}")
    for conf in configs:
        enable_root_in_file(conf)

if __name__ == "__main__":
    main()
