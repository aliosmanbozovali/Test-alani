
import os
import shutil
import json
from datetime import datetime
from pathlib import Path

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
    
    def add_file(self, file_path, category="Genel", tags=None, description=""):
        """Dosya ekle ve kategorize et"""
        if not os.path.exists(file_path):
            print(f"Hata: {file_path} bulunamadı!")
            return False
        
        file_name = Path(file_path).name
        category_dir = self.base_directory / category
        category_dir.mkdir(exist_ok=True)
        
        destination = category_dir / file_name
        
        # Dosyayı kopyala
        shutil.copy2(file_path, destination)
        
        # Metadata kaydet
        file_id = str(destination.relative_to(self.base_directory))
        self.metadata[file_id] = {
            "original_name": file_name,
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
        print("7. Çıkış")
        
        choice = input("\nSeçiminiz (1-7): ").strip()
        
        if choice == "1":
            file_path = input("Dosya yolu: ").strip()
            category = input("Kategori (varsayılan: Genel): ").strip() or "Genel"
            description = input("Açıklama (opsiyonel): ").strip()
            tags_input = input("Etiketler (virgülle ayırın): ").strip()
            tags = [tag.strip() for tag in tags_input.split(",")] if tags_input else []
            
            fm.add_file(file_path, category, tags, description)
        
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
            print("👋 Görüşürüz!")
            break
        
        else:
            print("❌ Geçersiz seçim!")

if __name__ == "__main__":
    main()
