
import os
import shutil
import json
from datetime import datetime
from pathlib import Path
import re
import hashlib
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

class DoxagonArchiveManager:
    def __init__(self, base_directory="archive"):
        self.base_directory = Path(base_directory)
        self.base_directory.mkdir(exist_ok=True)
        self.metadata_file = self.base_directory / "archive_metadata.json"
        self.config_file = self.base_directory / "system_config.json"
        self.load_metadata()
        self.load_config()
    
    def load_metadata(self):
        """Arşiv metadata dosyasını yükle"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}
    
    def save_metadata(self):
        """Arşiv metadata dosyasını kaydet"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
    
    def load_config(self):
        """Sistem konfigürasyonunu yükle"""
        default_config = {
            "retention_policies": {
                "Yasal": 7,  # 7 yıl
                "Muhasebe": 10,  # 10 yıl
                "İnsan Kaynakları": 5,  # 5 yıl
                "Genel": 3  # 3 yıl
            },
            "auto_classification": True,
            "version_control": True,
            "audit_trail": True
        }
        
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = default_config
            self.save_config()
    
    def save_config(self):
        """Sistem konfigürasyonunu kaydet"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def calculate_file_hash(self, file_path):
        """Dosyanın SHA-256 hash değerini hesapla"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def classify_document_type(self, file_path, content=""):
        """Belge türünü otomatik olarak sınıflandır"""
        if not content:
            content = self.extract_content(file_path).lower()
        
        # Yasal belgeler
        if any(word in content for word in ['sözleşme', 'anlaşma', 'mahkeme', 'dava', 'yasal', 'kanun']):
            return "Yasal"
        
        # Muhasebe belgeleri
        elif any(word in content for word in ['fatura', 'makbuz', 'gelir', 'gider', 'vergi', 'kdv']):
            return "Muhasebe"
        
        # İnsan Kaynakları
        elif any(word in content for word in ['personel', 'çalışan', 'maaş', 'bordro', 'işe alım']):
            return "İnsan Kaynakları"
        
        # Teknik dökümanlar
        elif any(word in content for word in ['api', 'kod', 'geliştirme', 'test', 'proje']):
            return "Teknik"
        
        return "Genel"
    
    def archive_document(self, file_path, category=None, tags=None, description="", 
                        document_type=None, confidentiality="Normal", version="1.0"):
        """Belgeyi arşivle"""
        if not os.path.exists(file_path):
            print(f"❌ Hata: {file_path} bulunamadı!")
            return False
        
        # Dosya hash kontrolü (kopya kontrolü)
        file_hash = self.calculate_file_hash(file_path)
        for existing_id, existing_info in self.metadata.items():
            if existing_info.get("file_hash") == file_hash:
                print(f"⚠️  Bu belge zaten arşivde: {existing_info['original_name']}")
                return False
        
        # Otomatik sınıflandırma
        if self.config.get("auto_classification", True) and category is None:
            content = self.extract_content(file_path)
            category = self.classify_document_type(file_path, content)
            print(f"🤖 Otomatik sınıflandırma: {category}")
        
        if document_type is None:
            document_type = self.classify_document_type(file_path)
        
        category = category or "Genel"
        
        # Kategori dizini oluştur
        category_dir = self.base_directory / category
        category_dir.mkdir(exist_ok=True)
        
        # Dosya adı ve hedef yol
        file_name = Path(file_path).name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_name = f"{timestamp}_{file_name}"
        destination = category_dir / archived_name
        
        # Dosyayı kopyala
        shutil.copy2(file_path, destination)
        
        # Retention date hesapla
        retention_years = self.config["retention_policies"].get(document_type, 3)
        retention_date = datetime.now().replace(year=datetime.now().year + retention_years)
        
        # Metadata kaydet
        file_id = str(destination.relative_to(self.base_directory))
        self.metadata[file_id] = {
            "original_name": file_name,
            "archived_name": archived_name,
            "original_path": file_path,
            "category": category,
            "document_type": document_type,
            "tags": tags or [],
            "description": description,
            "confidentiality": confidentiality,
            "version": version,
            "archived_date": datetime.now().isoformat(),
            "retention_date": retention_date.isoformat(),
            "file_size": os.path.getsize(destination),
            "file_hash": file_hash,
            "archived_by": "sistem",  # Kullanıcı sistemi eklenebilir
            "access_count": 0,
            "last_accessed": None
        }
        
        self.save_metadata()
        print(f"✅ Belge başarıyla arşivlendi: {file_id}")
        print(f"📋 Saklama süresi: {retention_date.strftime('%Y-%m-%d')} tarihine kadar")
        return True
    
    def search_documents(self, query, filters=None):
        """Gelişmiş belge arama"""
        results = []
        query_lower = query.lower()
        filters = filters or {}
        
        for file_id, info in self.metadata.items():
            # Temel arama
            matches = (
                query_lower in info["original_name"].lower() or
                query_lower in info["category"].lower() or
                query_lower in info["description"].lower() or
                query_lower in info.get("document_type", "").lower() or
                any(query_lower in tag.lower() for tag in info["tags"])
            )
            
            # Filtreler
            if matches:
                # Kategori filtresi
                if filters.get("category") and info["category"] != filters["category"]:
                    continue
                
                # Belge türü filtresi
                if filters.get("document_type") and info.get("document_type") != filters["document_type"]:
                    continue
                
                # Gizlilik filtresi
                if filters.get("confidentiality") and info.get("confidentiality") != filters["confidentiality"]:
                    continue
                
                # Tarih aralığı filtresi
                if filters.get("date_from"):
                    archived_date = datetime.fromisoformat(info["archived_date"])
                    if archived_date < datetime.fromisoformat(filters["date_from"]):
                        continue
                
                if filters.get("date_to"):
                    archived_date = datetime.fromisoformat(info["archived_date"])
                    if archived_date > datetime.fromisoformat(filters["date_to"]):
                        continue
                
                results.append((file_id, info))
        
        return results
    
    def list_documents(self, category=None, show_expired=False):
        """Belgeleri listele"""
        print("\n📁 ARŞİV BELGELERİ")
        print("=" * 70)
        
        current_date = datetime.now()
        
        for file_id, info in self.metadata.items():
            if category and info["category"] != category:
                continue
            
            # Saklama süresi kontrolü
            retention_date = datetime.fromisoformat(info["retention_date"])
            is_expired = current_date > retention_date
            
            if not show_expired and is_expired:
                continue
            
            # Durumu belirle
            status = "🔴 Süresi Dolmuş" if is_expired else "🟢 Aktif"
            
            print(f"📄 {info['original_name']}")
            print(f"   ID: {file_id}")
            print(f"   Kategori: {info['category']}")
            print(f"   Belge Türü: {info.get('document_type', 'Belirtilmemiş')}")
            print(f"   Gizlilik: {info.get('confidentiality', 'Normal')}")
            print(f"   Durum: {status}")
            print(f"   Boyut: {self.format_size(info['file_size'])}")
            print(f"   Arşivlenme: {info['archived_date'][:10]}")
            print(f"   Saklama Bitiş: {info['retention_date'][:10]}")
            print(f"   Erişim Sayısı: {info.get('access_count', 0)}")
            if info["tags"]:
                print(f"   Etiketler: {', '.join(info['tags'])}")
            if info["description"]:
                print(f"   Açıklama: {info['description']}")
            print()
    
    def access_document(self, file_id):
        """Belgeye erişim sağla ve kayıt tut"""
        if file_id not in self.metadata:
            print(f"❌ Belge bulunamadı: {file_id}")
            return False
        
        file_path = self.base_directory / file_id
        if not file_path.exists():
            print(f"❌ Fiziksel dosya bulunamadı: {file_path}")
            return False
        
        # Erişim kaydı tut
        self.metadata[file_id]["access_count"] = self.metadata[file_id].get("access_count", 0) + 1
        self.metadata[file_id]["last_accessed"] = datetime.now().isoformat()
        self.save_metadata()
        
        print(f"✅ Belgeye erişim sağlandı: {self.metadata[file_id]['original_name']}")
        print(f"📁 Dosya konumu: {file_path}")
        return str(file_path)
    
    def retention_management(self):
        """Saklama süresi yönetimi"""
        current_date = datetime.now()
        expired_docs = []
        warning_docs = []
        
        for file_id, info in self.metadata.items():
            retention_date = datetime.fromisoformat(info["retention_date"])
            days_remaining = (retention_date - current_date).days
            
            if days_remaining < 0:
                expired_docs.append((file_id, info))
            elif days_remaining < 30:  # 30 gün kala uyarı
                warning_docs.append((file_id, info, days_remaining))
        
        print("\n⏰ SAKLAMA SÜRESİ YÖNETİMİ")
        print("=" * 50)
        
        if expired_docs:
            print(f"\n🔴 Süresi Dolmuş Belgeler ({len(expired_docs)}):")
            for file_id, info in expired_docs:
                print(f"  • {info['original_name']} - {info['category']}")
        
        if warning_docs:
            print(f"\n🟡 Yakında Süresi Dolacak Belgeler ({len(warning_docs)}):")
            for file_id, info, days in warning_docs:
                print(f"  • {info['original_name']} - {days} gün kaldı")
        
        if not expired_docs and not warning_docs:
            print("✅ Tüm belgeler geçerli saklama süresi içinde")
        
        return expired_docs, warning_docs
    
    def archive_statistics(self):
        """Arşiv istatistikleri"""
        total_docs = len(self.metadata)
        categories = {}
        doc_types = {}
        total_size = 0
        
        for info in self.metadata.values():
            # Kategori istatistikleri
            categories[info["category"]] = categories.get(info["category"], 0) + 1
            
            # Belge türü istatistikleri
            doc_type = info.get("document_type", "Belirtilmemiş")
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
            
            # Toplam boyut
            total_size += info["file_size"]
        
        print("\n📊 ARŞİV İSTATİSTİKLERİ")
        print("=" * 50)
        print(f"Toplam Belge Sayısı: {total_docs}")
        print(f"Toplam Boyut: {self.format_size(total_size)}")
        
        print("\n📂 Kategoriler:")
        for category, count in sorted(categories.items()):
            print(f"  {category}: {count} belge")
        
        print("\n📋 Belge Türleri:")
        for doc_type, count in sorted(doc_types.items()):
            print(f"  {doc_type}: {count} belge")
    
    def extract_content(self, file_path):
        """Dosya içeriğinden metin çıkar"""
        try:
            file_ext = Path(file_path).suffix.lower()
            
            # Metin dosyaları
            if file_ext in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()[:1000]  # İlk 1000 karakter
            
            # PDF dosyaları
            elif file_ext == '.pdf' and PDF_AVAILABLE:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in reader.pages[:3]:  # İlk 3 sayfa
                        text += page.extract_text()
                    return text[:1000]
            
            # Word dosyaları
            elif file_ext in ['.docx', '.doc'] and DOCX_AVAILABLE:
                doc = docx.Document(file_path)
                text = ""
                for paragraph in doc.paragraphs[:20]:  # İlk 20 paragraf
                    text += paragraph.text + " "
                return text[:1000]
            
            # Resim dosyaları (OCR)
            elif file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff'] and OCR_AVAILABLE:
                image = Image.open(file_path)
                text = pytesseract.image_to_string(image, lang='tur+eng')
                return text[:1000]
                
        except Exception as e:
            print(f"İçerik çıkarma hatası: {e}")
            
        return ""
    
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
    archive = DoxagonArchiveManager()
    
    print("📚 DOXAGON - BELGE VE ARŞİV YÖNETİM SİSTEMİ")
    print("=" * 50)
    
    while True:
        print("\n📋 ANA MENÜ:")
        print("1. Belge Arşivle")
        print("2. Belgeleri Listele")
        print("3. Belge Ara")
        print("4. Belgeye Erişim")
        print("5. Saklama Süresi Yönetimi")
        print("6. Arşiv İstatistikleri")
        print("7. Sistem Ayarları")
        print("8. Toplu Arşivleme")
        print("9. Çıkış")
        
        choice = input("\nSeçiminiz (1-9): ").strip()
        
        if choice == "1":
            file_path = input("Belge yolu: ").strip()
            category = input("Kategori (otomatik sınıflandırma için boş): ").strip() or None
            description = input("Açıklama: ").strip()
            tags_input = input("Etiketler (virgülle ayırın): ").strip()
            tags = [tag.strip() for tag in tags_input.split(",")] if tags_input else []
            
            print("\nGizlilik Düzeyi:")
            print("1. Normal")
            print("2. Gizli")
            print("3. Çok Gizli")
            conf_choice = input("Seçim (1-3): ").strip()
            confidentiality = {"1": "Normal", "2": "Gizli", "3": "Çok Gizli"}.get(conf_choice, "Normal")
            
            archive.archive_document(file_path, category, tags, description, confidentiality=confidentiality)
        
        elif choice == "2":
            category = input("Kategori (tümü için boş): ").strip() or None
            show_expired = input("Süresi dolmuş belgeleri göster? (e/h): ").strip().lower() == 'e'
            archive.list_documents(category, show_expired)
        
        elif choice == "3":
            query = input("Arama terimi: ").strip()
            if query:
                print("\n🔍 Gelişmiş Filtreler (boş bırakabilirsiniz):")
                filters = {}
                
                category_filter = input("Kategori: ").strip()
                if category_filter:
                    filters["category"] = category_filter
                
                type_filter = input("Belge türü: ").strip()
                if type_filter:
                    filters["document_type"] = type_filter
                
                results = archive.search_documents(query, filters)
                
                print(f"\n🔍 '{query}' için {len(results)} sonuç bulundu:")
                print("-" * 60)
                
                for file_id, info in results:
                    print(f"📄 {info['original_name']}")
                    print(f"   ID: {file_id}")
                    print(f"   Kategori: {info['category']}")
                    print(f"   Tarih: {info['archived_date'][:10]}")
                    print()
        
        elif choice == "4":
            file_id = input("Belge ID: ").strip()
            if file_id:
                archive.access_document(file_id)
        
        elif choice == "5":
            archive.retention_management()
        
        elif choice == "6":
            archive.archive_statistics()
        
        elif choice == "7":
            print("\n⚙️ SİSTEM AYARLARI")
            print("1. Saklama Süreleri")
            print("2. Otomatik Sınıflandırma")
            
            setting_choice = input("Ayar seçimi: ").strip()
            
            if setting_choice == "1":
                print("\nMevcut Saklama Süreleri:")
                for doc_type, years in archive.config["retention_policies"].items():
                    print(f"  {doc_type}: {years} yıl")
                
                doc_type = input("\nDeğiştirilecek belge türü: ").strip()
                if doc_type in archive.config["retention_policies"]:
                    years = input(f"{doc_type} için yeni süre (yıl): ").strip()
                    try:
                        archive.config["retention_policies"][doc_type] = int(years)
                        archive.save_config()
                        print("✅ Ayar güncellendi")
                    except ValueError:
                        print("❌ Geçersiz değer")
            
            elif setting_choice == "2":
                current = archive.config.get("auto_classification", True)
                print(f"\nOtomatik sınıflandırma şu anda: {'Açık' if current else 'Kapalı'}")
                toggle = input("Durumu değiştir? (e/h): ").strip().lower() == 'e'
                if toggle:
                    archive.config["auto_classification"] = not current
                    archive.save_config()
                    print("✅ Ayar güncellendi")
        
        elif choice == "8":
            folder_path = input("Arşivlenecek klasör yolu: ").strip()
            if not os.path.exists(folder_path):
                print("❌ Klasör bulunamadı!")
                continue
            
            category = input("Kategori (otomatik sınıflandırma için boş): ").strip() or None
            
            print(f"\n🔄 {folder_path} klasöründeki belgeler arşivleniyor...")
            
            processed = 0
            for file_path in Path(folder_path).iterdir():
                if file_path.is_file():
                    try:
                        archive.archive_document(str(file_path), category)
                        processed += 1
                    except Exception as e:
                        print(f"❌ {file_path.name} arşivlenemedi: {e}")
            
            print(f"✅ {processed} belge başarıyla arşivlendi!")
        
        elif choice == "9":
            print("👋 Doxagon Arşiv Sistemi kapatılıyor...")
            break
        
        else:
            print("❌ Geçersiz seçim!")

if __name__ == "__main__":
    main()
