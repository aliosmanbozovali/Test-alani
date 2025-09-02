import os
import shutil
import json
from datetime import datetime, timedelta
from pathlib import Path
import re
import hashlib
import uuid
import sqlite3
from typing import Optional, List, Dict, Any
import base64
import secrets
import smtplib
try:
    from email.mime.text import MIMEText as MimeText
    from email.mime.multipart import MIMEMultipart as MimeMultipart
    EMAIL_AVAILABLE = True
except ImportError:
    # Email özellikleri devre dışı
    class DummyMime:
        def __init__(self, *args, **kwargs):
            pass
    MimeText = DummyMime
    MimeMultipart = DummyMime
    EMAIL_AVAILABLE = False

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

try:
    import requests
    WEB_AVAILABLE = True
except ImportError:
    WEB_AVAILABLE = False

class DatabaseManager:
    def __init__(self, db_path="doxagon.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Veritabanı tablolarını oluştur"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Kullanıcılar tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'viewer',
                    organization_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    two_factor_enabled BOOLEAN DEFAULT 0,
                    two_factor_secret TEXT
                )
            ''')

            # Organizasyonlar tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS organizations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    plan TEXT DEFAULT 'free',
                    storage_quota_gb INTEGER DEFAULT 5,
                    user_quota INTEGER DEFAULT 10,
                    document_quota INTEGER DEFAULT 1000,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')

            # Belgeler tablosu (genişletilmiş)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    current_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    mime_type TEXT,
                    category TEXT,
                    document_type TEXT,
                    organization_id TEXT,
                    uploaded_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT,
                    confidentiality TEXT DEFAULT 'Normal',
                    retention_date TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    thumbnail_path TEXT,
                    ocr_text TEXT,
                    ai_classification TEXT,
                    FOREIGN KEY (organization_id) REFERENCES organizations(id),
                    FOREIGN KEY (uploaded_by) REFERENCES users(id)
                )
            ''')

            # Belge versiyonları tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS document_versions (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    change_notes TEXT,
                    is_current BOOLEAN DEFAULT 0,
                    FOREIGN KEY (document_id) REFERENCES documents(id),
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )
            ''')

            # Metadata tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS document_metadata (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    data_type TEXT DEFAULT 'string',
                    is_required BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                )
            ''')

            # Etiketler tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    color TEXT DEFAULT '#007bff',
                    organization_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations(id)
                )
            ''')

            # Belge-etiket ilişki tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS document_tags (
                    document_id TEXT,
                    tag_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (document_id, tag_id),
                    FOREIGN KEY (document_id) REFERENCES documents(id),
                    FOREIGN KEY (tag_id) REFERENCES tags(id)
                )
            ''')

            # Paylaşım linkleri tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS share_links (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    created_by TEXT,
                    expires_at TIMESTAMP,
                    password_hash TEXT,
                    max_downloads INTEGER,
                    download_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id),
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )
            ''')

            # Hatırlatıcılar tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    reminder_date TIMESTAMP NOT NULL,
                    repeat_interval TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # Audit log tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # İş akışları tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    current_step INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id),
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )
            ''')

            # İş akışı adımları tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflow_steps (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    step_name TEXT NOT NULL,
                    assigned_to TEXT,
                    status TEXT DEFAULT 'pending',
                    completed_at TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id),
                    FOREIGN KEY (assigned_to) REFERENCES users(id)
                )
            ''')

            conn.commit()

class DoxagonEnterpriseManager:
    def __init__(self, base_directory="doxagon_storage"):
        self.base_directory = Path(base_directory)
        self.base_directory.mkdir(exist_ok=True)

        # Alt dizinler
        self.uploads_dir = self.base_directory / "uploads"
        self.uploads_dir.mkdir(exist_ok=True)

        self.thumbnails_dir = self.base_directory / "thumbnails"
        self.thumbnails_dir.mkdir(exist_ok=True)

        self.temp_dir = self.base_directory / "temp"
        self.temp_dir.mkdir(exist_ok=True)

        # Veritabanı yöneticisi
        self.db = DatabaseManager()

        # Konfigürasyon
        self.config = self.load_config()

        # Mevcut kullanıcı (basit auth için)
        self.current_user = None
        self.current_org = None

    def load_config(self):
        """Sistem konfigürasyonunu yükle"""
        config_file = self.base_directory / "enterprise_config.json"
        default_config = {
            "storage": {
                "type": "local",  # local, s3, minio
                "encryption_enabled": True,
                "max_file_size_mb": 100,
                "allowed_extensions": [
                    ".pdf", ".doc", ".docx", ".xls", ".xlsx", 
                    ".ppt", ".pptx", ".txt", ".jpg", ".jpeg", 
                    ".png", ".gif", ".bmp", ".tiff"
                ]
            },
            "ocr": {
                "enabled": OCR_AVAILABLE,
                "languages": ["tur", "eng"],
                "auto_ocr": True
            },
            "ai": {
                "classification_enabled": False,
                "api_key": None,
                "model": "gpt-3.5-turbo"
            },
            "security": {
                "session_timeout_hours": 8,
                "max_login_attempts": 5,
                "password_min_length": 8,
                "require_2fa": False
            },
            "notifications": {
                "email_enabled": False,
                "smtp_server": None,
                "smtp_port": 587,
                "smtp_username": None,
                "smtp_password": None
            },
            "retention": {
                "default_years": 7,
                "policies": {
                    "Yasal": 10,
                    "Muhasebe": 10,
                    "İnsan Kaynakları": 5,
                    "Sözleşme": 7,
                    "Fatura": 10
                }
            }
        }

        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                # Varsayılan değerleri güncelle
                self.deep_update(default_config, loaded_config)

        self.save_config(default_config)
        return default_config

    def deep_update(self, base_dict, update_dict):
        """Derinlemesine sözlük güncelleme"""
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict:
                self.deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    def save_config(self, config=None):
        """Konfigürasyonu kaydet"""
        if config is None:
            config = self.config

        config_file = self.base_directory / "enterprise_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def create_organization(self, name: str, plan: str = "free") -> str:
        """Yeni organizasyon oluştur"""
        org_id = str(uuid.uuid4())

        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO organizations (id, name, plan)
                VALUES (?, ?, ?)
            ''', (org_id, name, plan))
            conn.commit()

        return org_id

    def create_user(self, username: str, email: str, password: str, 
                   role: str = "viewer", organization_id: str = None) -> str:
        """Yeni kullanıcı oluştur"""
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (id, username, email, password_hash, role, organization_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, email, password_hash, role, organization_id))
            conn.commit()

        return user_id

    def authenticate_user(self, username: str, password: str) -> bool:
        """Kullanıcı doğrulama"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.*, o.name as org_name 
                FROM users u 
                LEFT JOIN organizations o ON u.organization_id = o.id
                WHERE u.username = ? AND u.password_hash = ? AND u.is_active = 1
            ''', (username, password_hash))

            user = cursor.fetchone()
            if user:
                self.current_user = {
                    'id': user[0],
                    'username': user[1],
                    'email': user[2],
                    'role': user[4],
                    'organization_id': user[5],
                    'organization_name': user[10] if user[10] else 'Bireysel'
                }
                return True

        return False

    def calculate_file_hash(self, file_path: Path) -> str:
        """Dosyanın SHA-256 hash değerini hesapla"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def create_thumbnail(self, file_path: Path, document_id: str) -> Optional[str]:
        """Belge thumbnail'i oluştur"""
        try:
            file_ext = file_path.suffix.lower()
            thumbnail_path = self.thumbnails_dir / f"{document_id}_thumb.jpg"

            if file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff']:
                # Resim dosyaları için thumbnail
                with Image.open(file_path) as img:
                    img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                    img.convert('RGB').save(thumbnail_path, 'JPEG', quality=85)
                return str(thumbnail_path)

            elif file_ext == '.pdf' and PDF_AVAILABLE:
                # PDF için ilk sayfa thumbnail'i
                # Bu özellik için pdf2image kütüphanesi gerekli
                # Şimdilik basit bir placeholder
                return None

        except Exception as e:
            print(f"Thumbnail oluşturma hatası: {e}")

        return None

    def extract_text_content(self, file_path: Path) -> str:
        """Dosyadan metin içeriği çıkar"""
        try:
            file_ext = file_path.suffix.lower()

            # Metin dosyaları
            if file_ext in ['.txt', '.md']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()

            # PDF dosyaları
            elif file_ext == '.pdf' and PDF_AVAILABLE:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                    return text

            # Word dosyaları
            elif file_ext in ['.docx'] and DOCX_AVAILABLE:
                doc = docx.Document(file_path)
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                return text

            # Resim dosyaları (OCR)
            elif file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff'] and OCR_AVAILABLE:
                if self.config['ocr']['enabled']:
                    image = Image.open(file_path)
                    languages = '+'.join(self.config['ocr']['languages'])
                    text = pytesseract.image_to_string(image, lang=languages)
                    return text

        except Exception as e:
            print(f"Metin çıkarma hatası: {e}")

        return ""

    def classify_document_ai(self, content: str, filename: str) -> str:
        """AI ile belge sınıflandırma"""
        if not self.config['ai']['classification_enabled']:
            return self.classify_document_rules(content, filename)

        # Basit kural tabanlı sınıflandırma
        return self.classify_document_rules(content, filename)

    def classify_document_rules(self, content: str, filename: str) -> str:
        """Kural tabanlı belge sınıflandırma"""
        content_lower = content.lower()
        filename_lower = filename.lower()

        # Fatura tespiti
        if any(word in content_lower for word in ['fatura', 'invoice', 'kdv', 'vergi', 'tutar']):
            return "Fatura"

        # Sözleşme tespiti
        elif any(word in content_lower for word in ['sözleşme', 'contract', 'anlaşma', 'agreement']):
            return "Sözleşme"

        # Kimlik belgesi tespiti
        elif any(word in content_lower for word in ['kimlik', 'nüfus', 'tc', 'passport', 'ehliyet']):
            return "Kimlik"

        # Yasal belge tespiti
        elif any(word in content_lower for word in ['mahkeme', 'dava', 'court', 'legal', 'hukuk']):
            return "Yasal"

        # Muhasebe belgesi
        elif any(word in content_lower for word in ['bilanço', 'gelir', 'gider', 'accounting']):
            return "Muhasebe"

        # Maaş bordrosu tespiti
        elif any(word in content_lower for word in ['lohn abrechnung', 'lohnabrechnung', 'maaş bordrosu', 'payroll', 'salary slip', 'bordro']):
            return "Lohn abrechnung"

        # Personel belgesi
        elif any(word in content_lower for word in ['personel', 'employee', 'maaş', 'işe alım']):
            return "İnsan Kaynakları"

        # Dosya adından çıkarım
        if 'fatura' in filename_lower or 'invoice' in filename_lower:
            return "Fatura"
        elif 'sozlesme' in filename_lower or 'contract' in filename_lower:
            return "Sözleşme"

        return "Genel"

    def upload_document(self, file_path: str, category: str = None, 
                       tags: List[str] = None, description: str = "", 
                       metadata: Dict[str, Any] = None, 
                       confidentiality: str = "Normal") -> Optional[str]:
        """Belge yükleme (versiyonlama ile)"""

        if not self.current_user:
            print("❌ Oturum açmanız gerekiyor!")
            return None

        source_path = Path(file_path)
        if not source_path.exists():
            print(f"❌ Dosya bulunamadı: {file_path}")
            return None

        # Dosya boyutu kontrolü
        file_size = source_path.stat().st_size
        max_size = self.config['storage']['max_file_size_mb'] * 1024 * 1024
        if file_size > max_size:
            print(f"❌ Dosya çok büyük! Maksimum: {self.config['storage']['max_file_size_mb']}MB")
            return None

        # Dosya türü kontrolü
        if source_path.suffix.lower() not in self.config['storage']['allowed_extensions']:
            print(f"❌ Desteklenmeyen dosya türü: {source_path.suffix}")
            return None

        # Hash hesapla ve duplikasyon kontrolü
        file_hash = self.calculate_file_hash(source_path)

        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, original_name FROM documents 
                WHERE file_hash = ? AND organization_id = ? AND is_active = 1
            ''', (file_hash, self.current_user['organization_id']))

            existing = cursor.fetchone()
            if existing:
                print(f"⚠️  Bu dosya zaten mevcut: {existing[1]}")
                return existing[0]

        # Belge ID oluştur
        document_id = str(uuid.uuid4())

        # Dosya yolu oluştur: uploads/{doc_id}/v1/
        doc_dir = self.uploads_dir / document_id / "v1"
        doc_dir.mkdir(parents=True, exist_ok=True)

        # Dosyayı kopyala
        dest_path = doc_dir / source_path.name
        shutil.copy2(source_path, dest_path)

        # İçerik çıkar
        text_content = self.extract_text_content(dest_path)

        # Otomatik sınıflandırma
        if not category:
            category = self.classify_document_ai(text_content, source_path.name)
            print(f"🤖 Otomatik sınıflandırma: {category}")

        # Thumbnail oluştur
        thumbnail_path = self.create_thumbnail(dest_path, document_id)

        # Saklama tarihi hesapla
        retention_years = self.config['retention']['policies'].get(
            category, self.config['retention']['default_years']
        )
        retention_date = datetime.now() + timedelta(days=retention_years * 365)

        # Veritabanına kaydet
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()

            # Ana belge kaydı
            cursor.execute('''
                INSERT INTO documents (
                    id, original_name, current_name, file_path, file_hash, 
                    file_size, mime_type, category, document_type, 
                    organization_id, uploaded_by, description, confidentiality,
                    retention_date, thumbnail_path, ocr_text, ai_classification
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                document_id, source_path.name, source_path.name, str(dest_path),
                file_hash, file_size, self.get_mime_type(source_path), category,
                category, self.current_user['organization_id'], self.current_user['id'],
                description, confidentiality, retention_date.isoformat(),
                thumbnail_path, text_content, category
            ))

            # Versiyon kaydı
            cursor.execute('''
                INSERT INTO document_versions (
                    id, document_id, version_number, file_path, file_hash,
                    file_size, created_by, is_current, change_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), document_id, 1, str(dest_path),
                file_hash, file_size, self.current_user['id'], True, "İlk versiyon"
            ))

            # Metadata kaydet
            if metadata:
                for key, value in metadata.items():
                    cursor.execute('''
                        INSERT INTO document_metadata (id, document_id, key, value)
                        VALUES (?, ?, ?, ?)
                    ''', (str(uuid.uuid4()), document_id, key, str(value)))

            # Etiketleri kaydet
            if tags:
                for tag_name in tags:
                    # Etiket var mı kontrol et
                    cursor.execute('''
                        SELECT id FROM tags WHERE name = ? AND organization_id = ?
                    ''', (tag_name, self.current_user['organization_id']))

                    tag_result = cursor.fetchone()
                    if tag_result:
                        tag_id = tag_result[0]
                    else:
                        # Yeni etiket oluştur
                        tag_id = str(uuid.uuid4())
                        cursor.execute('''
                            INSERT INTO tags (id, name, organization_id)
                            VALUES (?, ?, ?)
                        ''', (tag_id, tag_name, self.current_user['organization_id']))

                    # Belge-etiket ilişkisi
                    cursor.execute('''
                        INSERT OR IGNORE INTO document_tags (document_id, tag_id)
                        VALUES (?, ?)
                    ''', (document_id, tag_id))

            conn.commit()

        # Audit log
        self.log_action("CREATE", "document", document_id, f"Belge yüklendi: {source_path.name}")

        print(f"✅ Belge başarıyla yüklendi!")
        print(f"📄 Belge ID: {document_id}")
        print(f"📂 Kategori: {category}")
        print(f"💾 Boyut: {self.format_size(file_size)}")
        print(f"📅 Saklama Süresi: {retention_date.strftime('%Y-%m-%d')} tarihine kadar")

        return document_id

    def get_mime_type(self, file_path: Path) -> str:
        """Dosya MIME türünü belirle"""
        ext = file_path.suffix.lower()
        mime_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.txt': 'text/plain',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff'
        }
        return mime_types.get(ext, 'application/octet-stream')

    def create_new_version(self, document_id: str, new_file_path: str, 
                          change_notes: str = "") -> bool:
        """Belgenin yeni versiyonunu oluştur"""

        if not self.current_user:
            print("❌ Oturum açmanız gerekiyor!")
            return False

        source_path = Path(new_file_path)
        if not source_path.exists():
            print(f"❌ Dosya bulunamadı: {new_file_path}")
            return False

        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()

            # Belge var mı kontrol et
            cursor.execute('''
                SELECT original_name FROM documents 
                WHERE id = ? AND organization_id = ? AND is_active = 1
            ''', (document_id, self.current_user['organization_id']))

            doc = cursor.fetchone()
            if not doc:
                print("❌ Belge bulunamadı!")
                return False

            # Mevcut en yüksek versiyon numarasını bul
            cursor.execute('''
                SELECT MAX(version_number) FROM document_versions WHERE document_id = ?
            ''', (document_id,))

            max_version = cursor.fetchone()[0] or 0
            new_version = max_version + 1

            # Yeni versiyon dizini oluştur
            doc_dir = self.uploads_dir / document_id / f"v{new_version}"
            doc_dir.mkdir(parents=True, exist_ok=True)

            # Dosyayı kopyala
            dest_path = doc_dir / source_path.name
            shutil.copy2(source_path, dest_path)

            # Hash hesapla
            file_hash = self.calculate_file_hash(dest_path)
            file_size = dest_path.stat().st_size

            # Mevcut versiyonu deaktif et
            cursor.execute('''
                UPDATE document_versions SET is_current = 0 WHERE document_id = ?
            ''', (document_id,))

            # Yeni versiyon kaydı
            cursor.execute('''
                INSERT INTO document_versions (
                    id, document_id, version_number, file_path, file_hash,
                    file_size, created_by, is_current, change_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), document_id, new_version, str(dest_path),
                file_hash, file_size, self.current_user['id'], True, change_notes
            ))

            # Ana belge güncelle
            cursor.execute('''
                UPDATE documents SET 
                    current_name = ?, file_path = ?, file_hash = ?, 
                    file_size = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (source_path.name, str(dest_path), file_hash, file_size, document_id))

            conn.commit()

        self.log_action("UPDATE", "document", document_id, f"Yeni versiyon oluşturuldu: v{new_version}")

        print(f"✅ Belgenin v{new_version} versiyonu oluşturuldu!")
        return True

    def search_documents(self, query: str, filters: Dict[str, Any] = None, 
                        page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Gelişmiş belge arama"""

        if not self.current_user:
            return {"documents": [], "total": 0}

        filters = filters or {}
        offset = (page - 1) * per_page

        # Base query
        base_query = '''
            SELECT DISTINCT d.*, u.username as uploaded_by_name,
                   GROUP_CONCAT(t.name) as tag_names
            FROM documents d
            LEFT JOIN users u ON d.uploaded_by = u.id
            LEFT JOIN document_tags dt ON d.id = dt.document_id
            LEFT JOIN tags t ON dt.tag_id = t.id
            WHERE d.organization_id = ? AND d.is_active = 1
        '''

        params = [self.current_user['organization_id']]

        # Metin arama
        if query:
            base_query += ' AND (d.original_name LIKE ? OR d.description LIKE ? OR d.ocr_text LIKE ?)'
            search_term = f'%{query}%'
            params.extend([search_term, search_term, search_term])

        # Filtreler
        if filters.get('category'):
            base_query += ' AND d.category = ?'
            params.append(filters['category'])

        if filters.get('document_type'):
            base_query += ' AND d.document_type = ?'
            params.append(filters['document_type'])

        if filters.get('confidentiality'):
            base_query += ' AND d.confidentiality = ?'
            params.append(filters['confidentiality'])

        if filters.get('uploaded_by'):
            base_query += ' AND d.uploaded_by = ?'
            params.append(filters['uploaded_by'])

        if filters.get('date_from'):
            base_query += ' AND d.created_at >= ?'
            params.append(filters['date_from'])

        if filters.get('date_to'):
            base_query += ' AND d.created_at <= ?'
            params.append(filters['date_to'])

        if filters.get('tags'):
            tag_placeholders = ','.join(['?' for _ in filters['tags']])
            base_query += f' AND t.name IN ({tag_placeholders})'
            params.extend(filters['tags'])

        # Grup by ekle
        base_query += ' GROUP BY d.id'

        # Toplam sayı
        count_query = f"SELECT COUNT(*) FROM ({base_query})"

        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()

            # Toplam sayı
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Sayfalı sonuçlar
            base_query += ' ORDER BY d.created_at DESC LIMIT ? OFFSET ?'
            params.extend([per_page, offset])

            cursor.execute(base_query, params)
            results = cursor.fetchall()

            documents = []
            for row in results:
                documents.append({
                    'id': row[0],
                    'original_name': row[1],
                    'current_name': row[2],
                    'file_size': row[5],
                    'category': row[7],
                    'document_type': row[8],
                    'description': row[11],
                    'confidentiality': row[12],
                    'created_at': row[10],
                    'uploaded_by_name': row[19],
                    'tags': row[20].split(',') if row[20] else []
                })

        return {
            'documents': documents,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        }

    def create_share_link(self, document_id: str, expires_hours: int = 24, 
                         password: str = None, max_downloads: int = None) -> Optional[str]:
        """Paylaşım linki oluştur"""

        if not self.current_user:
            print("❌ Oturum açmanız gerekiyor!")
            return None

        # Belge var mı kontrol et
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT original_name FROM documents 
                WHERE id = ? AND organization_id = ? AND is_active = 1
            ''', (document_id, self.current_user['organization_id']))

            doc = cursor.fetchone()
            if not doc:
                print("❌ Belge bulunamadı!")
                return None

        # Token oluştur
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=expires_hours)
        password_hash = hashlib.sha256(password.encode()).hexdigest() if password else None

        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO share_links (
                    id, document_id, token, created_by, expires_at, 
                    password_hash, max_downloads
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), document_id, token, self.current_user['id'],
                expires_at.isoformat(), password_hash, max_downloads
            ))
            conn.commit()

        share_url = f"http://localhost:5000/share/{token}"

        self.log_action("CREATE", "share_link", document_id, f"Paylaşım linki oluşturuldu")

        print(f"✅ Paylaşım linki oluşturuldu!")
        print(f"🔗 Link: {share_url}")
        print(f"⏰ Geçerlilik: {expires_at.strftime('%Y-%m-%d %H:%M')} tarihine kadar")
        if password:
            print(f"🔒 Şifre korumalı")
        if max_downloads:
            print(f"📥 Maksimum indirme: {max_downloads}")

        return share_url

    def create_reminder(self, document_id: str, title: str, description: str,
                       reminder_date: datetime, repeat_interval: str = None) -> bool:
        """Hatırlatıcı oluştur"""

        if not self.current_user:
            print("❌ Oturum açmanız gerekiyor!")
            return False

        reminder_id = str(uuid.uuid4())

        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO reminders (
                    id, document_id, user_id, title, description,
                    reminder_date, repeat_interval
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                reminder_id, document_id, self.current_user['id'],
                title, description, reminder_date.isoformat(), repeat_interval
            ))
            conn.commit()

        print(f"✅ Hatırlatıcı oluşturuldu: {title}")
        return True

    def log_action(self, action: str, resource_type: str, resource_id: str, 
                   details: str = None) -> None:
        """Audit log kaydı"""

        if not self.current_user:
            return

        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO audit_logs (
                    id, user_id, action, resource_type, resource_id, details
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), self.current_user['id'], action,
                resource_type, resource_id, details
            ))
            conn.commit()

    def format_size(self, size_bytes: int) -> str:
        """Dosya boyutunu formatla"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/(1024**2):.1f} MB"
        else:
            return f"{size_bytes/(1024**3):.1f} GB"

    def get_statistics(self) -> Dict[str, Any]:
        """Sistem istatistikleri"""

        if not self.current_user:
            return {}

        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()

            # Temel istatistikler
            cursor.execute('''
                SELECT COUNT(*), SUM(file_size) FROM documents 
                WHERE organization_id = ? AND is_active = 1
            ''', (self.current_user['organization_id'],))

            total_docs, total_size = cursor.fetchone()
            total_size = total_size or 0

            # Kategori bazlı istatistikler
            cursor.execute('''
                SELECT category, COUNT(*), SUM(file_size) FROM documents 
                WHERE organization_id = ? AND is_active = 1
                GROUP BY category
            ''', (self.current_user['organization_id'],))

            categories = cursor.fetchall()

            # Son 7 günün istatistikleri
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor.execute('''
                SELECT DATE(created_at) as date, COUNT(*) FROM documents 
                WHERE organization_id = ? AND created_at >= ? AND is_active = 1
                GROUP BY DATE(created_at)
                ORDER BY date
            ''', (self.current_user['organization_id'], week_ago))

            daily_uploads = cursor.fetchall()

        return {
            'total_documents': total_docs,
            'total_size': total_size,
            'total_size_formatted': self.format_size(total_size),
            'categories': categories,
            'daily_uploads': daily_uploads
        }

def main():
    print("🏢 DOXAGON ENTERPRISE - BELGE YÖNETİM SİSTEMİ")
    print("=" * 60)

    # Sistem başlat
    doxagon = DoxagonEnterpriseManager()

    # Varsayılan organizasyon ve kullanıcı oluştur (ilk çalıştırmada)
    with sqlite3.connect(doxagon.db.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM organizations')
        if cursor.fetchone()[0] == 0:
            print("🔧 İlk kurulum yapılıyor...")

            # Varsayılan organizasyon
            org_id = doxagon.create_organization("Demo Organizasyon", "enterprise")

            # Admin kullanıcı
            admin_id = doxagon.create_user("admin", "admin@demo.com", "admin123", "admin", org_id)

            print("✅ Demo organizasyon ve admin kullanıcısı oluşturuldu")
            print("👤 Kullanıcı adı: admin")
            print("🔑 Şifre: admin123")

    # Giriş yap
    while not doxagon.current_user:
        print("\n🔐 GİRİŞ YAP")
        username = input("Kullanıcı adı: ").strip()
        password = input("Şifre: ").strip()

        if doxagon.authenticate_user(username, password):
            print(f"✅ Hoş geldiniz, {doxagon.current_user['username']}!")
            print(f"🏢 Organizasyon: {doxagon.current_user['organization_name']}")
        else:
            print("❌ Geçersiz kullanıcı adı veya şifre!")

    # Ana menü
    while True:
        print(f"\n📋 ANA MENÜ - {doxagon.current_user['organization_name']}")
        print("=" * 50)
        print("1. 📤 Belge Yükle")
        print("2. 🔍 Belge Ara")
        print("3. 📁 Belgelerim")
        print("4. 🔄 Yeni Versiyon Oluştur")
        print("5. 🔗 Paylaşım Linki Oluştur")
        print("6. ⏰ Hatırlatıcı Ekle")
        print("7. 📊 İstatistikler")
        print("8. ⚙️  Sistem Ayarları")
        print("9. 👥 Kullanıcı Yönetimi")
        print("10. 📋 Audit Logs")
        print("11. 🚪 Çıkış")

        choice = input("\nSeçiminiz (1-11): ").strip()

        if choice == "1":
            # Belge yükleme
            file_path = input("📁 Belge yolu: ").strip()
            if not file_path:
                continue

            category = input("📂 Kategori (otomatik için boş): ").strip() or None
            description = input("📝 Açıklama: ").strip()
            tags_input = input("🏷️  Etiketler (virgülle ayırın): ").strip()
            tags = [tag.strip() for tag in tags_input.split(",")] if tags_input else []

            print("\n🔒 Gizlilik Düzeyi:")
            print("1. Normal")
            print("2. Gizli") 
            print("3. Çok Gizli")
            conf_choice = input("Seçim (1-3): ").strip()
            confidentiality = {"1": "Normal", "2": "Gizli", "3": "Çok Gizli"}.get(conf_choice, "Normal")

            # Metadata ekle
            metadata = {}
            print("\n📋 Ek metadata eklemek ister misiniz? (e/h): ", end="")
            if input().strip().lower() == 'e':
                while True:
                    key = input("Anahtar (boş=bitir): ").strip()
                    if not key:
                        break
                    value = input(f"{key} değeri: ").strip()
                    metadata[key] = value

            doxagon.upload_document(file_path, category, tags, description, metadata, confidentiality)

        elif choice == "2":
            # Belge arama
            query = input("🔍 Arama terimi: ").strip()

            # Gelişmiş filtreler
            filters = {}
            print("\n📋 Filtreler (isteğe bağlı):")

            category_filter = input("📂 Kategori: ").strip()
            if category_filter:
                filters["category"] = category_filter

            type_filter = input("📄 Belge türü: ").strip()
            if type_filter:
                filters["document_type"] = type_filter

            conf_filter = input("🔒 Gizlilik (Normal/Gizli/Çok Gizli): ").strip()
            if conf_filter:
                filters["confidentiality"] = conf_filter

            date_from = input("📅 Başlangıç tarihi (YYYY-MM-DD): ").strip()
            if date_from:
                filters["date_from"] = date_from

            date_to = input("📅 Bitiş tarihi (YYYY-MM-DD): ").strip()
            if date_to:
                filters["date_to"] = date_to

            tags_filter = input("🏷️  Etiketler (virgülle ayırın): ").strip()
            if tags_filter:
                filters["tags"] = [tag.strip() for tag in tags_filter.split(",")]

            # Arama yap
            results = doxagon.search_documents(query, filters)

            print(f"\n🔍 '{query}' için {results['total']} sonuç bulundu:")
            print("=" * 60)

            for doc in results['documents']:
                print(f"📄 {doc['original_name']}")
                print(f"   📋 ID: {doc['id']}")
                print(f"   📂 Kategori: {doc['category']}")
                print(f"   💾 Boyut: {doxagon.format_size(doc['file_size'])}")
                print(f"   📅 Tarih: {doc['created_at'][:10]}")
                print(f"   👤 Yükleyen: {doc['uploaded_by_name']}")
                if doc['tags']:
                    print(f"   🏷️  Etiketler: {', '.join(doc['tags'])}")
                print()

        elif choice == "3":
            # Belgelerim
            results = doxagon.search_documents("", {"uploaded_by": doxagon.current_user['id']})

            print(f"\n📁 BELGELERİM ({results['total']} belge)")
            print("=" * 50)

            for doc in results['documents']:
                print(f"📄 {doc['original_name']}")
                print(f"   📋 ID: {doc['id']}")
                print(f"   📂 {doc['category']} | 💾 {doxagon.format_size(doc['file_size'])}")
                print(f"   📅 {doc['created_at'][:10]} | 🔒 {doc['confidentiality']}")
                print()

        elif choice == "4":
            # Yeni versiyon oluştur
            document_id = input("📋 Belge ID: ").strip()
            new_file_path = input("📁 Yeni dosya yolu: ").strip()
            change_notes = input("📝 Değişiklik notları: ").strip()

            if document_id and new_file_path:
                doxagon.create_new_version(document_id, new_file_path, change_notes)

        elif choice == "5":
            # Paylaşım linki
            document_id = input("📋 Belge ID: ").strip()
            if not document_id:
                continue

            print("\n⏰ Geçerlilik süresi:")
            print("1. 1 saat")
            print("2. 24 saat")
            print("3. 7 gün")
            print("4. 30 gün")
            print("5. Özel")

            expires_choice = input("Seçim (1-5): ").strip()
            expires_hours = {"1": 1, "2": 24, "3": 168, "4": 720}.get(expires_choice, 24)

            if expires_choice == "5":
                expires_hours = int(input("Saat cinsinden süre: ").strip() or "24")

            password = input("🔒 Şifre (isteğe bağlı): ").strip() or None
            max_downloads = input("📥 Maksimum indirme (boş=sınırsız): ").strip()
            max_downloads = int(max_downloads) if max_downloads else None

            doxagon.create_share_link(document_id, expires_hours, password, max_downloads)

        elif choice == "6":
            # Hatırlatıcı ekle
            document_id = input("📋 Belge ID: ").strip()
            title = input("📋 Hatırlatıcı başlığı: ").strip()
            description = input("📝 Açıklama: ").strip()

            reminder_date_str = input("📅 Hatırlatma tarihi (YYYY-MM-DD HH:MM): ").strip()
            try:
                reminder_date = datetime.strptime(reminder_date_str, "%Y-%m-%d %H:%M")

                print("🔄 Tekrar:")
                print("1. Tek seferlik")
                print("2. Günlük")
                print("3. Haftalık")
                print("4. Aylık")

                repeat_choice = input("Seçim (1-4): ").strip()
                repeat_interval = {"2": "daily", "3": "weekly", "4": "monthly"}.get(repeat_choice)

                doxagon.create_reminder(document_id, title, description, reminder_date, repeat_interval)
            except ValueError:
                print("❌ Geçersiz tarih formatı!")

        elif choice == "7":
            # İstatistikler
            stats = doxagon.get_statistics()

            print("\n📊 SİSTEM İSTATİSTİKLERİ")
            print("=" * 50)
            print(f"📄 Toplam Belge: {stats['total_documents']}")
            print(f"💾 Toplam Boyut: {stats['total_size_formatted']}")

            print("\n📂 Kategori Dağılımı:")
            for category, count, size in stats['categories']:
                print(f"  {category}: {count} belge ({doxagon.format_size(size or 0)})")

            if stats['daily_uploads']:
                print("\n📅 Son 7 Günün Yüklemeleri:")
                for date, count in stats['daily_uploads']:
                    print(f"  {date}: {count} belge")

        elif choice == "8":
            # Sistem ayarları
            print("\n⚙️ SİSTEM AYARLARI")
            print("1. Saklama Süreleri")
            print("2. OCR Ayarları")
            print("3. Güvenlik Ayarları")
            print("4. Bildirim Ayarları")

            setting_choice = input("Ayar seçimi: ").strip()

            if setting_choice == "1":
                print("\nMevcut Saklama Süreleri:")
                for doc_type, years in doxagon.config['retention']['policies'].items():
                    print(f"  {doc_type}: {years} yıl")

                doc_type = input("\nDeğiştirilecek belge türü: ").strip()
                if doc_type:
                    years = input(f"{doc_type} için yeni süre (yıl): ").strip()
                    try:
                        doxagon.config['retention']['policies'][doc_type] = int(years)
                        doxagon.save_config()
                        print("✅ Ayar güncellendi")
                    except ValueError:
                        print("❌ Geçersiz değer")

            elif setting_choice == "2":
                current = doxagon.config['ocr']['enabled']
                print(f"\nOCR şu anda: {'Açık' if current else 'Kapalı'}")
                toggle = input("Durumu değiştir? (e/h): ").strip().lower() == 'e'
                if toggle:
                    doxagon.config['ocr']['enabled'] = not current
                    doxagon.save_config()
                    print("✅ OCR ayarı güncellendi")

        elif choice == "9":
            # Kullanıcı yönetimi (sadece admin)
            if doxagon.current_user['role'] != 'admin':
                print("❌ Bu özellik için admin yetkisi gerekiyor!")
                continue

            print("\n👥 KULLANICI YÖNETİMİ")
            print("1. Yeni Kullanıcı Ekle")
            print("2. Kullanıcıları Listele")

            user_choice = input("Seçim: ").strip()

            if user_choice == "1":
                username = input("Kullanıcı adı: ").strip()
                email = input("E-posta: ").strip()
                password = input("Şifre: ").strip()

                print("Rol:")
                print("1. Viewer")
                print("2. Editor")  
                print("3. Admin")
                role_choice = input("Seçim (1-3): ").strip()
                role = {"1": "viewer", "2": "editor", "3": "admin"}.get(role_choice, "viewer")

                try:
                    user_id = doxagon.create_user(username, email, password, role, 
                                                 doxagon.current_user['organization_id'])
                    print(f"✅ Kullanıcı oluşturuldu: {username}")
                except Exception as e:
                    print(f"❌ Hata: {e}")

            elif user_choice == "2":
                with sqlite3.connect(doxagon.db.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT username, email, role, created_at, is_active
                        FROM users WHERE organization_id = ?
                    ''', (doxagon.current_user['organization_id'],))

                    users = cursor.fetchall()

                    print(f"\n👥 KULLANICILAR ({len(users)} kişi)")
                    print("-" * 60)
                    for user in users:
                        status = "🟢 Aktif" if user[4] else "🔴 Pasif"
                        print(f"👤 {user[0]} ({user[1]})")
                        print(f"   🎭 {user[2]} | 📅 {user[3][:10]} | {status}")
                        print()

        elif choice == "10":
            # Audit logs
            if doxagon.current_user['role'] not in ['admin', 'editor']:
                print("❌ Bu özellik için yetki gerekiyor!")
                continue

            print("\n📋 AUDIT LOGS (Son 50 kayıt)")
            print("=" * 70)

            with sqlite3.connect(doxagon.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.*, u.username 
                    FROM audit_logs a
                    LEFT JOIN users u ON a.user_id = u.id
                    ORDER BY a.created_at DESC LIMIT 50
                ''')

                logs = cursor.fetchall()

                for log in logs:
                    print(f"🕒 {log[7][:19]} | 👤 {log[8] or 'Sistem'}")
                    print(f"   📋 {log[2]} {log[3]} | 🆔 {log[4]}")
                    if log[5]:
                        print(f"   📝 {log[5]}")
                    print()

        elif choice == "11":
            print("👋 Doxagon Enterprise'dan çıkılıyor...")
            break

        else:
            print("❌ Geçersiz seçim!")

if __name__ == "__main__":
    main()