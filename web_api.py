
from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
from werkzeug.utils import secure_filename
import tempfile
import os
import sqlite3
from main import DoxagonEnterpriseManager
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# Doxagon sistemi
doxagon = DoxagonEnterpriseManager()

# Basit HTML arayüzü
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Doxagon Enterprise - Belge Yönetim Sistemi</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: #2c3e50; color: white; padding: 20px; text-align: center; margin-bottom: 30px; border-radius: 10px; }
        .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .upload-area { border: 2px dashed #3498db; padding: 40px; text-align: center; border-radius: 10px; background: #ecf0f1; }
        .btn { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin: 5px; }
        .btn:hover { background: #2980b9; }
        .btn-danger { background: #e74c3c; }
        .btn-danger:hover { background: #c0392b; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        .results { margin-top: 20px; }
        .document-item { background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #3498db; }
        .tabs { display: flex; background: #34495e; border-radius: 10px 10px 0 0; }
        .tab { padding: 15px 25px; color: white; cursor: pointer; border: none; background: transparent; }
        .tab.active { background: #3498db; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; }
        .login-form { max-width: 400px; margin: 50px auto; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏢 Doxagon Enterprise</h1>
            <p>Gelişmiş Belge ve Arşiv Yönetim Sistemi</p>
        </div>

        <!-- Giriş Formu -->
        <div id="loginSection" class="card login-form">
            <h2>🔐 Sisteme Giriş</h2>
            <div class="form-group">
                <label>Kullanıcı Adı:</label>
                <input type="text" id="username" value="admin" placeholder="Kullanıcı adınızı girin">
            </div>
            <div class="form-group">
                <label>Şifre:</label>
                <input type="password" id="password" value="admin123" placeholder="Şifrenizi girin">
            </div>
            <button class="btn" onclick="login()">Giriş Yap</button>
        </div>

        <!-- Ana Panel -->
        <div id="mainPanel" style="display: none;">
            <div class="tabs">
                <button class="tab active" onclick="showTab('upload')">📤 Belge Yükle</button>
                <button class="tab" onclick="showTab('search')">🔍 Ara</button>
                <button class="tab" onclick="showTab('documents')">📁 Belgelerim</button>
                <button class="tab" onclick="showTab('stats')">📊 İstatistikler</button>
                <button class="tab" onclick="showTab('share')">🔗 Paylaşım</button>
            </div>

            <!-- Yükleme Sekmesi -->
            <div id="uploadTab" class="tab-content active card">
                <h3>📤 Belge Yükleme</h3>
                <div class="upload-area">
                    <p>📁 Dosyaları buraya sürükleyin veya seçin</p>
                    <input type="file" id="fileInput" multiple style="margin-top: 20px;">
                </div>
                
                <div class="form-group">
                    <label>📂 Kategori:</label>
                    <select id="category">
                        <option value="">Otomatik Sınıflandırma</option>
                        <option value="Fatura">Fatura</option>
                        <option value="Sözleşme">Sözleşme</option>
                        <option value="Yasal">Yasal</option>
                        <option value="Muhasebe">Muhasebe</option>
                        <option value="İnsan Kaynakları">İnsan Kaynakları</option>
                        <option value="Genel">Genel</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>📝 Açıklama:</label>
                    <textarea id="description" placeholder="Belge hakkında açıklama..."></textarea>
                </div>
                
                <div class="form-group">
                    <label>🏷️ Etiketler (virgülle ayırın):</label>
                    <input type="text" id="tags" placeholder="etiket1, etiket2, etiket3">
                </div>
                
                <div class="form-group">
                    <label>🔒 Gizlilik Düzeyi:</label>
                    <select id="confidentiality">
                        <option value="Normal">Normal</option>
                        <option value="Gizli">Gizli</option>
                        <option value="Çok Gizli">Çok Gizli</option>
                    </select>
                </div>
                
                <button class="btn" onclick="uploadFiles()">📤 Yükle</button>
            </div>

            <!-- Arama Sekmesi -->
            <div id="searchTab" class="tab-content card">
                <h3>🔍 Belge Arama</h3>
                <div class="form-group">
                    <label>Arama Terimi:</label>
                    <input type="text" id="searchQuery" placeholder="Belge adı, içerik veya açıklama...">
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                    <div class="form-group">
                        <label>📂 Kategori:</label>
                        <select id="searchCategory">
                            <option value="">Tümü</option>
                            <option value="Fatura">Fatura</option>
                            <option value="Sözleşme">Sözleşme</option>
                            <option value="Yasal">Yasal</option>
                            <option value="Muhasebe">Muhasebe</option>
                            <option value="İnsan Kaynakları">İnsan Kaynakları</option>
                            <option value="Genel">Genel</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>🔒 Gizlilik:</label>
                        <select id="searchConfidentiality">
                            <option value="">Tümü</option>
                            <option value="Normal">Normal</option>
                            <option value="Gizli">Gizli</option>
                            <option value="Çok Gizli">Çok Gizli</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>📅 Başlangıç Tarihi:</label>
                        <input type="date" id="searchDateFrom">
                    </div>
                    
                    <div class="form-group">
                        <label>📅 Bitiş Tarihi:</label>
                        <input type="date" id="searchDateTo">
                    </div>
                </div>
                
                <button class="btn" onclick="searchDocuments()">🔍 Ara</button>
                
                <div id="searchResults" class="results"></div>
            </div>

            <!-- Belgelerim Sekmesi -->
            <div id="documentsTab" class="tab-content card">
                <h3>📁 Belgelerim</h3>
                <button class="btn" onclick="loadMyDocuments()">🔄 Yenile</button>
                <div id="myDocuments" class="results"></div>
            </div>

            <!-- İstatistikler Sekmesi -->
            <div id="statsTab" class="tab-content card">
                <h3>📊 Sistem İstatistikleri</h3>
                <button class="btn" onclick="loadStatistics()">🔄 Yenile</button>
                <div id="statisticsContent"></div>
            </div>

            <!-- Paylaşım Sekmesi -->
            <div id="shareTab" class="tab-content card">
                <h3>🔗 Paylaşım Linki Oluştur</h3>
                <div class="form-group">
                    <label>📋 Belge ID:</label>
                    <input type="text" id="shareDocumentId" placeholder="Paylaşılacak belgenin ID'si">
                </div>
                
                <div class="form-group">
                    <label>⏰ Geçerlilik Süresi:</label>
                    <select id="shareExpires">
                        <option value="1">1 Saat</option>
                        <option value="24">24 Saat</option>
                        <option value="168">7 Gün</option>
                        <option value="720">30 Gün</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>🔒 Şifre (isteğe bağlı):</label>
                    <input type="password" id="sharePassword" placeholder="Paylaşım şifresi">
                </div>
                
                <div class="form-group">
                    <label>📥 Maksimum İndirme (boş = sınırsız):</label>
                    <input type="number" id="shareMaxDownloads" placeholder="Örn: 5">
                </div>
                
                <button class="btn" onclick="createShareLink()">🔗 Paylaşım Linki Oluştur</button>
                
                <div id="shareResult" style="margin-top: 20px;"></div>
            </div>
        </div>
    </div>

    <script>
        let currentUser = null;

        function login() {
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    currentUser = data.user;
                    document.getElementById('loginSection').style.display = 'none';
                    document.getElementById('mainPanel').style.display = 'block';
                    alert('✅ Giriş başarılı! Hoş geldiniz ' + data.user.username);
                } else {
                    alert('❌ ' + data.message);
                }
            })
            .catch(error => {
                console.error('Hata:', error);
                alert('❌ Giriş hatası!');
            });
        }

        function showTab(tabName) {
            // Tüm sekmeleri gizle
            const contents = document.querySelectorAll('.tab-content');
            contents.forEach(content => content.classList.remove('active'));
            
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => tab.classList.remove('active'));
            
            // Seçilen sekmeyi göster
            document.getElementById(tabName + 'Tab').classList.add('active');
            event.target.classList.add('active');
        }

        function uploadFiles() {
            const fileInput = document.getElementById('fileInput');
            const files = fileInput.files;
            
            if (files.length === 0) {
                alert('❌ Lütfen dosya seçin!');
                return;
            }
            
            const formData = new FormData();
            for (let file of files) {
                formData.append('files', file);
            }
            
            formData.append('category', document.getElementById('category').value);
            formData.append('description', document.getElementById('description').value);
            formData.append('tags', document.getElementById('tags').value);
            formData.append('confidentiality', document.getElementById('confidentiality').value);
            
            fetch('/api/documents/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ ' + data.message);
                    // Formu temizle
                    fileInput.value = '';
                    document.getElementById('description').value = '';
                    document.getElementById('tags').value = '';
                } else {
                    alert('❌ ' + data.message);
                }
            })
            .catch(error => {
                console.error('Hata:', error);
                alert('❌ Yükleme hatası!');
            });
        }

        function searchDocuments() {
            const query = document.getElementById('searchQuery').value;
            const filters = {
                category: document.getElementById('searchCategory').value,
                confidentiality: document.getElementById('searchConfidentiality').value,
                date_from: document.getElementById('searchDateFrom').value,
                date_to: document.getElementById('searchDateTo').value
            };
            
            fetch('/api/documents/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, filters })
            })
            .then(response => response.json())
            .then(data => {
                const resultsDiv = document.getElementById('searchResults');
                if (data.success) {
                    let html = `<h4>🔍 ${data.results.total} sonuç bulundu</h4>`;
                    
                    data.results.documents.forEach(doc => {
                        html += `
                            <div class="document-item">
                                <h5>📄 ${doc.original_name}</h5>
                                <p><strong>📋 ID:</strong> ${doc.id}</p>
                                <p><strong>📂 Kategori:</strong> ${doc.category}</p>
                                <p><strong>💾 Boyut:</strong> ${formatFileSize(doc.file_size)}</p>
                                <p><strong>📅 Tarih:</strong> ${doc.created_at.substring(0, 10)}</p>
                                <p><strong>👤 Yükleyen:</strong> ${doc.uploaded_by_name}</p>
                                ${doc.description ? `<p><strong>📝 Açıklama:</strong> ${doc.description}</p>` : ''}
                                ${doc.tags.length > 0 ? `<p><strong>🏷️ Etiketler:</strong> ${doc.tags.join(', ')}</p>` : ''}
                                <button class="btn" onclick="downloadDocument('${doc.id}')">📥 İndir</button>
                                <button class="btn" onclick="copyToShare('${doc.id}')">🔗 Paylaş</button>
                            </div>
                        `;
                    });
                    
                    resultsDiv.innerHTML = html;
                } else {
                    resultsDiv.innerHTML = `<p>❌ ${data.message}</p>`;
                }
            })
            .catch(error => {
                console.error('Hata:', error);
                document.getElementById('searchResults').innerHTML = '<p>❌ Arama hatası!</p>';
            });
        }

        function loadMyDocuments() {
            fetch('/api/documents/my-documents')
            .then(response => response.json())
            .then(data => {
                const docsDiv = document.getElementById('myDocuments');
                if (data.success) {
                    let html = `<h4>📁 ${data.results.total} belgeniz var</h4>`;
                    
                    data.results.documents.forEach(doc => {
                        html += `
                            <div class="document-item">
                                <h5>📄 ${doc.original_name}</h5>
                                <p><strong>📋 ID:</strong> ${doc.id}</p>
                                <p><strong>📂 Kategori:</strong> ${doc.category}</p>
                                <p><strong>💾 Boyut:</strong> ${formatFileSize(doc.file_size)}</p>
                                <p><strong>📅 Tarih:</strong> ${doc.created_at.substring(0, 10)}</p>
                                <p><strong>🔒 Gizlilik:</strong> ${doc.confidentiality}</p>
                                <button class="btn" onclick="downloadDocument('${doc.id}')">📥 İndir</button>
                                <button class="btn" onclick="copyToShare('${doc.id}')">🔗 Paylaş</button>
                            </div>
                        `;
                    });
                    
                    docsDiv.innerHTML = html;
                } else {
                    docsDiv.innerHTML = `<p>❌ ${data.message}</p>`;
                }
            });
        }

        function loadStatistics() {
            fetch('/api/statistics')
            .then(response => response.json())
            .then(data => {
                const statsDiv = document.getElementById('statisticsContent');
                if (data.success) {
                    const stats = data.statistics;
                    
                    let html = `
                        <div class="stats-grid">
                            <div class="stat-card">
                                <h3>📄 ${stats.total_documents}</h3>
                                <p>Toplam Belge</p>
                            </div>
                            <div class="stat-card">
                                <h3>💾 ${stats.total_size_formatted}</h3>
                                <p>Toplam Boyut</p>
                            </div>
                        </div>
                        
                        <h4>📂 Kategori Dağılımı:</h4>
                        <div class="results">
                    `;
                    
                    stats.categories.forEach(([category, count, size]) => {
                        html += `
                            <div class="document-item">
                                <strong>${category}:</strong> ${count} belge (${formatFileSize(size || 0)})
                            </div>
                        `;
                    });
                    
                    html += '</div>';
                    statsDiv.innerHTML = html;
                } else {
                    statsDiv.innerHTML = `<p>❌ ${data.message}</p>`;
                }
            });
        }

        function createShareLink() {
            const documentId = document.getElementById('shareDocumentId').value;
            const expiresHours = document.getElementById('shareExpires').value;
            const password = document.getElementById('sharePassword').value;
            const maxDownloads = document.getElementById('shareMaxDownloads').value;
            
            if (!documentId) {
                alert('❌ Belge ID gerekli!');
                return;
            }
            
            fetch('/api/share/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    document_id: documentId,
                    expires_hours: parseInt(expiresHours),
                    password: password || null,
                    max_downloads: maxDownloads ? parseInt(maxDownloads) : null
                })
            })
            .then(response => response.json())
            .then(data => {
                const resultDiv = document.getElementById('shareResult');
                if (data.success) {
                    resultDiv.innerHTML = `
                        <div class="card" style="background: #d4edda; color: #155724; border: 1px solid #c3e6cb;">
                            <h4>✅ Paylaşım linki oluşturuldu!</h4>
                            <p><strong>🔗 Link:</strong> <a href="${data.share_url}" target="_blank">${data.share_url}</a></p>
                            <button class="btn" onclick="copyToClipboard('${data.share_url}')">📋 Kopyala</button>
                        </div>
                    `;
                } else {
                    resultDiv.innerHTML = `<p style="color: red;">❌ ${data.message}</p>`;
                }
            });
        }

        function downloadDocument(documentId) {
            window.open(`/api/documents/${documentId}/download`, '_blank');
        }

        function copyToShare(documentId) {
            document.getElementById('shareDocumentId').value = documentId;
            showTab('share');
        }

        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                alert('✅ Link panoya kopyalandı!');
            });
        }

        function formatFileSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
            return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
        }

        // Sayfa yüklendiğinde
        document.addEventListener('DOMContentLoaded', function() {
            // Auto-login için (geliştirme amaçlı)
            // login();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Ana sayfa"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """Kullanıcı girişi"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if doxagon.authenticate_user(username, password):
        return jsonify({
            'success': True,
            'message': 'Giriş başarılı',
            'user': doxagon.current_user
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Geçersiz kullanıcı adı veya şifre'
        }), 401

@app.route('/api/documents/upload', methods=['POST'])
def api_upload():
    """Belge yükleme"""
    if not doxagon.current_user:
        return jsonify({'success': False, 'message': 'Oturum açmanız gerekiyor'}), 401
    
    files = request.files.getlist('files')
    category = request.form.get('category') or None
    description = request.form.get('description', '')
    tags_str = request.form.get('tags', '')
    confidentiality = request.form.get('confidentiality', 'Normal')
    
    tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()] if tags_str else []
    
    uploaded_docs = []
    errors = []
    
    for file in files:
        if file and file.filename:
            # Geçici dosyaya kaydet
            filename = secure_filename(file.filename)
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            file.save(temp_path)
            
            try:
                doc_id = doxagon.upload_document(
                    temp_path, category, tags, description, 
                    confidentiality=confidentiality
                )
                if doc_id:
                    uploaded_docs.append({'filename': filename, 'id': doc_id})
                else:
                    errors.append(f"{filename}: Yükleme başarısız")
            except Exception as e:
                errors.append(f"{filename}: {str(e)}")
            finally:
                # Geçici dosyayı sil
                try:
                    os.remove(temp_path)
                except:
                    pass
    
    if uploaded_docs:
        message = f"{len(uploaded_docs)} belge başarıyla yüklendi"
        if errors:
            message += f", {len(errors)} hatası var"
        
        return jsonify({
            'success': True,
            'message': message,
            'uploaded': uploaded_docs,
            'errors': errors
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Hiçbir belge yüklenemedi',
            'errors': errors
        }), 400

@app.route('/api/documents/search', methods=['POST'])
def api_search():
    """Belge arama"""
    if not doxagon.current_user:
        return jsonify({'success': False, 'message': 'Oturum açmanız gerekiyor'}), 401
    
    data = request.get_json()
    query = data.get('query', '')
    filters = data.get('filters', {})
    page = data.get('page', 1)
    per_page = data.get('per_page', 20)
    
    # Boş filtreleri temizle
    cleaned_filters = {k: v for k, v in filters.items() if v}
    
    try:
        results = doxagon.search_documents(query, cleaned_filters, page, per_page)
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Arama hatası: {str(e)}'
        }), 500

@app.route('/api/documents/my-documents')
def api_my_documents():
    """Kullanıcının belgeleri"""
    if not doxagon.current_user:
        return jsonify({'success': False, 'message': 'Oturum açmanız gerekiyor'}), 401
    
    try:
        results = doxagon.search_documents("", {"uploaded_by": doxagon.current_user['id']})
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Belge listesi alınamadı: {str(e)}'
        }), 500

@app.route('/api/documents/<document_id>/download')
def api_download(document_id):
    """Belge indirme"""
    if not doxagon.current_user:
        return jsonify({'success': False, 'message': 'Oturum açmanız gerekiyor'}), 401
    
    try:
        import sqlite3
        with sqlite3.connect(doxagon.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT file_path, original_name FROM documents 
                WHERE id = ? AND organization_id = ? AND is_active = 1
            ''', (document_id, doxagon.current_user['organization_id']))
            
            result = cursor.fetchone()
            if result:
                file_path, original_name = result
                
                # Erişim logla
                doxagon.log_action("DOWNLOAD", "document", document_id, f"Belge indirildi: {original_name}")
                
                return send_file(file_path, as_attachment=True, download_name=original_name)
            else:
                return jsonify({'success': False, 'message': 'Belge bulunamadı'}), 404
                
    except Exception as e:
        return jsonify({'success': False, 'message': f'İndirme hatası: {str(e)}'}), 500

@app.route('/api/share/create', methods=['POST'])
def api_create_share():
    """Paylaşım linki oluştur"""
    if not doxagon.current_user:
        return jsonify({'success': False, 'message': 'Oturum açmanız gerekiyor'}), 401
    
    data = request.get_json()
    document_id = data.get('document_id')
    expires_hours = data.get('expires_hours', 24)
    password = data.get('password')
    max_downloads = data.get('max_downloads')
    
    try:
        share_url = doxagon.create_share_link(document_id, expires_hours, password, max_downloads)
        if share_url:
            return jsonify({
                'success': True,
                'share_url': share_url,
                'message': 'Paylaşım linki oluşturuldu'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Paylaşım linki oluşturulamadı'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Paylaşım hatası: {str(e)}'
        }), 500

@app.route('/api/statistics')
def api_statistics():
    """Sistem istatistikleri"""
    if not doxagon.current_user:
        return jsonify({'success': False, 'message': 'Oturum açmanız gerekiyor'}), 401
    
    try:
        stats = doxagon.get_statistics()
        return jsonify({
            'success': True,
            'statistics': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'İstatistik hatası: {str(e)}'
        }), 500

@app.route('/share/<token>')
def public_share(token):
    """Paylaşım linki ile belge erişimi"""
    try:
        import sqlite3
        with sqlite3.connect(doxagon.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sl.*, d.original_name, d.file_path
                FROM share_links sl
                JOIN documents d ON sl.document_id = d.id
                WHERE sl.token = ? AND sl.is_active = 1
            ''', (token,))
            
            share = cursor.fetchone()
            if not share:
                return jsonify({'error': 'Geçersiz paylaşım linki'}), 404
            
            # Süre kontrolü
            expires_at = datetime.fromisoformat(share[4])
            if datetime.now() > expires_at:
                return jsonify({'error': 'Paylaşım linkinin süresi dolmuş'}), 410
            
            # İndirme sayısı kontrolü
            if share[6] and share[7] >= share[6]:
                return jsonify({'error': 'Maksimum indirme sayısına ulaşıldı'}), 410
            
            # Şifre kontrolü (basit - gerçek uygulamada form gösterilmeli)
            if share[5]:  # password_hash var
                return jsonify({'error': 'Bu paylaşım şifre korumalı'}), 403
            
            # İndirme sayısını artır
            cursor.execute('''
                UPDATE share_links SET download_count = download_count + 1 
                WHERE id = ?
            ''', (share[0],))
            conn.commit()
            
            # Dosyayı gönder
            return send_file(share[11], as_attachment=True, download_name=share[10])
            
    except Exception as e:
        return jsonify({'error': f'Paylaşım hatası: {str(e)}'}), 500

if __name__ == '__main__':
    # İlk kurulum kontrolü
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
    
    print("\n🌐 Doxagon Enterprise Web Arayüzü")
    print("=" * 50)
    print("🔗 Web Arayüzü: http://localhost:5000")
    print("📊 API Endpoint: http://localhost:5000/api")
    print("👤 Demo Giriş: admin / admin123")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
