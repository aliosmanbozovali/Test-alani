
import os
import shutil
import json
from datetime import datetime
from pathlib import Path
import re
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

class FileManager:
    def __init__(self, base_directory="files"):
        self.base_directory = Path(base_directory)
        self.base_directory.mkdir(exist_ok=True)
        self.metadata_file = self.base_directory / "metadata.json"
        self.load_metadata()
    
    def load_metadata(self):
        """Metadata dosyasını yükle"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}
    
    def save_metadata(self):
        """Metadata dosyasını kaydet"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
    
    def add_file(self, file_path, category="Genel", tags=None, description="", use_smart_naming=False):
        """Dosya ekle ve kategorize et"""
        if not os.path.exists(file_path):
            print(f"Hata: {file_path} bulunamadı!")
            return False
        
        # Aynı dosyanın zaten eklenip eklenmediğini kontrol et
        file_size = os.path.getsize(file_path)
        original_name = Path(file_path).name
        
        for existing_id, existing_info in self.metadata.items():
            if (existing_info.get("original_path") == file_path or 
                (existing_info.get("file_size") == file_size and 
                 Path(existing_info.get("original_path", "")).name == original_name)):
                print(f"⚠️  Bu dosya zaten mevcut: {existing_info['original_name']} ({existing_info['category']} kategorisinde)")
                return False
        
        if use_smart_naming:
            print("🤖 İçerik analiz ediliyor...")
            smart_name = self.generate_smart_name(file_path)
            file_name = smart_name
            print(f"💡 Önerilen ad: {smart_name}")
        else:
            file_name = Path(file_path).name
        
        category_dir = self.base_directory / category
        category_dir.mkdir(exist_ok=True)
        
        destination = category_dir / file_name
        
        # Aynı isimli dosya varsa numaralandır
        counter = 1
        original_destination = destination
        while destination.exists():
            name_stem = original_destination.stem
            suffix = original_destination.suffix
            destination = category_dir / f"{name_stem}_{counter}{suffix}"
            counter += 1
        
        # Dosyayı kopyala
        shutil.copy2(file_path, destination)
        
        # Metadata kaydet
        file_id = str(destination.relative_to(self.base_directory))
        self.metadata[file_id] = {
            "original_name": destination.name,
            "original_path": file_path,
            "category": category,
            "tags": tags or [],
            "description": description,
            "added_date": datetime.now().isoformat(),
            "file_size": os.path.getsize(destination)
        }
        
        self.save_metadata()
        print(f"✅ Dosya başarıyla eklendi: {file_id}")
        return True
    
    def create_category(self, category_name):
        """Yeni kategori oluştur"""
        category_dir = self.base_directory / category_name
        category_dir.mkdir(exist_ok=True)
        print(f"✅ Kategori oluşturuldu: {category_name}")
    
    def list_files(self, category=None):
        """Dosyaları listele"""
        print("\n📁 DOSYA LİSTESİ")
        print("-" * 50)
        
        for file_id, info in self.metadata.items():
            if category is None or info["category"] == category:
                print(f"📄 {info['original_name']}")
                print(f"   Kategori: {info['category']}")
                print(f"   Boyut: {self.format_size(info['file_size'])}")
                print(f"   Tarih: {info['added_date'][:10]}")
                if info["tags"]:
                    print(f"   Etiketler: {', '.join(info['tags'])}")
                if info["description"]:
                    print(f"   Açıklama: {info['description']}")
                print()
    
    def search_files(self, query):
        """Dosyalarda arama yap"""
        results = []
        query_lower = query.lower()
        
        for file_id, info in self.metadata.items():
            # İsim, kategori, etiket ve açıklamada ara
            if (query_lower in info["original_name"].lower() or
                query_lower in info["category"].lower() or
                query_lower in info["description"].lower() or
                any(query_lower in tag.lower() for tag in info["tags"])):
                results.append((file_id, info))
        
        print(f"\n🔍 '{query}' için {len(results)} sonuç bulundu:")
        print("-" * 50)
        
        for file_id, info in results:
            print(f"📄 {info['original_name']} ({info['category']})")
    
    def list_categories(self):
        """Kategorileri listele"""
        categories = set(info["category"] for info in self.metadata.values())
        print("\n📂 KATEGORİLER:")
        for category in sorted(categories):
            count = sum(1 for info in self.metadata.values() if info["category"] == category)
            print(f"  {category} ({count} dosya)")
    
    def delete_file(self, file_name):
        """Dosyayı sil"""
        for file_id, info in self.metadata.items():
            if info["original_name"] == file_name:
                file_path = self.base_directory / file_id
                if file_path.exists():
                    os.remove(file_path)
                del self.metadata[file_id]
                self.save_metadata()
                print(f"✅ Dosya silindi: {file_name}")
                return True
        
        print(f"❌ Dosya bulunamadı: {file_name}")
        return False
    
    def extract_content(self, file_path):
        """Dosya içeriğinden metin çıkar"""
        try:
            file_ext = Path(file_path).suffix.lower()
            
            # Metin dosyaları
            if file_ext in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()[:500]  # İlk 500 karakter
            
            # PDF dosyaları
            elif file_ext == '.pdf' and PDF_AVAILABLE:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in reader.pages[:3]:  # İlk 3 sayfa
                        text += page.extract_text()
                    return text[:500]
            
            # Word dosyaları
            elif file_ext in ['.docx', '.doc'] and DOCX_AVAILABLE:
                doc = docx.Document(file_path)
                text = ""
                for paragraph in doc.paragraphs[:10]:  # İlk 10 paragraf
                    text += paragraph.text + " "
                return text[:500]
            
            # Resim dosyaları (OCR)
            elif file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff'] and OCR_AVAILABLE:
                image = Image.open(file_path)
                text = pytesseract.image_to_string(image, lang='tur+eng')
                return text[:500]
                
        except Exception as e:
            print(f"İçerik çıkarma hatası: {e}")
            
        return ""
    
    def generate_smart_name(self, file_path, content=""):
        """İçeriğe göre akıllı dosya adı üret"""
        original_name = Path(file_path).stem
        extension = Path(file_path).suffix
        
        if not content:
            content = self.extract_content(file_path)
        
        if content:
            # Metni temizle ve anlamlı kelimeleri al
            words = re.findall(r'\b[a-zA-ZğüşıöçĞÜŞİÖÇ]+\b', content)
            meaningful_words = [w for w in words if len(w) > 2 and w.lower() not in 
                              ['the', 'and', 'bir', 'ile', 'için', 'olan', 'var', 'this', 'that']]
            
            if meaningful_words:
                # İlk 3-4 anlamlı kelimeyi al
                smart_name = "_".join(meaningful_words[:4])
                # Uzun isimleri kısalt
                if len(smart_name) > 30:
                    smart_name = smart_name[:30]
                
                # Tarih ekle
                date_str = datetime.now().strftime("%Y%m%d")
                return f"{smart_name}_{date_str}{extension}"
        
        # İçerik bulunamazsa orijinal ad + tarih
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        return f"{original_name}_{date_str}{extension}"
    
    def format_size(self, size_bytes):
        """Dosya boyutunu formatla"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/(1024**2):.1f} MB"
        else:
            return f"{size_bytes/(1024**3):.1f} GB"

def main():
    fm = FileManager()
    
    print("🗂️  DOSYALAMA PROGRAMI")
    print("=" * 30)
    
    while True:
        print("\n📋 MENÜ:")
        print("1. Dosya ekle")
        print("2. Dosyaları listele")
        print("3. Kategorileri görüntüle")
        print("4. Dosya ara")
        print("5. Kategori oluştur")
        print("6. Dosya sil")
        print("7. Toplu dosya işleme")
        print("8. Çıkış")
        
        choice = input("\nSeçiminiz (1-7): ").strip()
        
        if choice == "1":
            file_path = input("Dosya yolu: ").strip()
            category = input("Kategori (varsayılan: Genel): ").strip() or "Genel"
            description = input("Açıklama (opsiyonel): ").strip()
            tags_input = input("Etiketler (virgülle ayırın): ").strip()
            tags = [tag.strip() for tag in tags_input.split(",")] if tags_input else []
            
            smart_naming = input("İçeriğe göre otomatik adlandır? (e/h): ").strip().lower() == 'e'
            
            fm.add_file(file_path, category, tags, description, smart_naming)
        
        elif choice == "2":
            category = input("Kategori (tümü için boş bırakın): ").strip() or None
            fm.list_files(category)
        
        elif choice == "3":
            fm.list_categories()
        
        elif choice == "4":
            query = input("Arama terimi: ").strip()
            if query:
                fm.search_files(query)
        
        elif choice == "5":
            category_name = input("Kategori adı: ").strip()
            if category_name:
                fm.create_category(category_name)
        
        elif choice == "6":
            file_name = input("Silinecek dosya adı: ").strip()
            if file_name:
                fm.delete_file(file_name)
        
        elif choice == "7":
            folder_path = input("İşlenecek klasör yolu: ").strip()
            if not os.path.exists(folder_path):
                print("❌ Klasör bulunamadı!")
                continue
            
            category = input("Kategori (varsayılan: Genel): ").strip() or "Genel"
            smart_naming = input("Tüm dosyalar için akıllı adlandırma? (e/h): ").strip().lower() == 'e'
            
            print(f"\n🔄 {folder_path} klasöründeki dosyalar işleniyor...")
            
            processed = 0
            for file_path in Path(folder_path).iterdir():
                if file_path.is_file():
                    try:
                        fm.add_file(str(file_path), category, [], "", smart_naming)
                        processed += 1
                    except Exception as e:
                        print(f"❌ {file_path.name} işlenemedi: {e}")
            
            print(f"✅ {processed} dosya başarıyla işlendi!")
        
        elif choice == "8":
            print("👋 Görüşürüz!")
            break
        
        else:
            print("❌ Geçersiz seçim!")

if __name__ == "__main__":
    main()
