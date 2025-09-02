
import zipfile
import os
from pathlib import Path

def create_project_zip():
    """DocuMaster HBA Pro projesini ZIP olarak paketler"""
    
    # ZIP dosyası adı
    zip_filename = "DocuMaster_HBA_Pro.zip"
    
    # Dahil edilecek dosyalar ve klasörler
    include_files = [
        'main.py',
        'web_api.py', 
        'pyproject.toml',
        '.replit',
        'generated-icon.png',
        'doxagon.db'
    ]
    
    include_folders = [
        'archive',
        'doxagon_storage',
        'files'
    ]
    
    # Hariç tutulacak dosyalar
    exclude_patterns = [
        '__pycache__',
        '.git',
        'uv.lock',
        '.gitignore'
    ]
    
    print("📦 DocuMaster HBA Pro ZIP paketi oluşturuluyor...")
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        
        # Ana dosyaları ekle
        for file in include_files:
            if os.path.exists(file):
                zipf.write(file)
                print(f"✅ {file} eklendi")
        
        # Klasörleri ekle
        for folder in include_folders:
            if os.path.exists(folder):
                for root, dirs, files in os.walk(folder):
                    # Hariç tutulan klasörleri atla
                    dirs[:] = [d for d in dirs if not any(pattern in d for pattern in exclude_patterns)]
                    
                    for file in files:
                        # Hariç tutulan dosyaları atla
                        if not any(pattern in file for pattern in exclude_patterns):
                            file_path = os.path.join(root, file)
                            arcname = file_path
                            zipf.write(file_path, arcname)
                            print(f"✅ {file_path} eklendi")
        
        # README dosyası ekle
        readme_content = """# DocuMaster HBA Pro - Belge Yönetim Sistemi

## Kurulum

1. Python 3.11+ yükleyin
2. Gerekli paketleri yükleyin:
   ```
   pip install flask flask-cors pillow pypdf2 pytesseract python-docx werkzeug
   ```
3. Sistemi başlatın:
   ```
   python web_api.py
   ```
4. Tarayıcıda açın: http://localhost:5000

## Giriş Bilgileri
- Kullanıcı: admin
- Şifre: admin123

## Özellikler
- Belge yükleme ve yönetimi
- Kategori bazlı organizasyon
- Arama ve filtreleme
- Paylaşım linkleri
- Önizleme desteği
- Audit log sistemi
"""
        zipf.writestr("README.md", readme_content)
        print("✅ README.md eklendi")
    
    print(f"\n🎉 ZIP paketi hazır: {zip_filename}")
    print(f"📊 Dosya boyutu: {os.path.getsize(zip_filename) / (1024*1024):.2f} MB")
    
    return zip_filename

if __name__ == "__main__":
    create_project_zip()
