# 📱 Antigravity Mobile App (v2)

Aplikasi mobile berbasis **React Native (Expo + TypeScript)** yang terhubung langsung ke **Google Antigravity & Gemini API** di komputer lokal Anda.

---

## 🌟 Fitur Utama

1. **💬 Chat Interaktif & Streaming**:
   - Respon agen mengalir secara realtime (*streaming response*).
   - **Stop Button**: Tombol kirim berubah otomatis menjadi tombol stop (merah) untuk membatalkan proses jika respon terlalu panjang.
   - **Thinking Process (CoT)**: Kotak akordeon pemikiran agen (*chain-of-thought*) yang bisa dilipat/dibuka layaknya Antigravity Desktop.

2. **⚙️ Kontrol Model & Thinking Effort**:
   - Pemilihan model: **Gemini 2.5 Flash** (Cepat & Hemat) dan **Gemini 2.5 Pro** (Penalaran & Koding Mendalam).
   - Penyetelan *Thinking Effort*: `None`, `Low`, `Medium`, `High`.

3. **📂 History Chat & Manajemen Sesi**:
   - Riwayat obrolan tersimpan rapi di SQLite lokal.
   - Buat sesi baru (*New Chat*), ganti sesi, dan hapus percakapan.

4. **⚡ Automations & Notifikasi Realtime**:
   - Daftarkan tugas otomatisasi berulang (*interval* menit atau jadwal *cron*).
   - PC mengeksekusi tugas di background dan mengirimkan **Notifikasi Realtime (WebSocket)** langsung ke layar HP Anda.

5. **📁 PC File Explorer & Mobile Code Editor**:
   - Jelajahi folder proyek PC (`MY-PR/`).
   - Buka file kode, baca isi file, edit langsung di HP, dan simpan kembali ke harddisk PC Anda.

---

## 🚀 Panduan Menjalankan Sistem

### Langkah 1: Setup Backend (Python)

1. Buka terminal di folder backend:
   ```bash
   cd "C:\Users\bobby\OneDrive\Documents\MY-PR\MOBILE-APP\backend"
   ```

2. Buka file `.env` dan masukkan kredensial:
   - **Jika menggunakan 9router (Rekomendasi)**:
     ```env
     USE_9ROUTER=true
     NINEROUTER_BASE_URL=https://api.9router.com/v1
     NINEROUTER_API_KEY=masukkan_api_key_9router_anda
     ```
   - **Jika langsung menggunakan Google AI Studio**:
     ```env
     USE_9ROUTER=false
     GEMINI_API_KEY=AIzaSy...masukkan_kunci_anda_disini
     ```

3. Install dependensi:
   ```bash
   py -m pip install -r requirements.txt
   ```

4. Jalankan server:
   ```bash
   py main.py
   ```
   *Server akan berjalan di `http://0.0.0.0:8000`.*

---

### Langkah 2: Buat Tunneling Agar HP Bisa Akses (Opsional jika beda WiFi / Pakai 4G)

Buka terminal baru di laptop dan jalankan **ngrok**:
```bash
npx ngrok http 8000
```
Salin URL publik yang muncul (contoh: `https://a1b2-c3d4.ngrok-free.app`).

---

### Langkah 3: Setup Frontend Mobile (React Native / Expo)

1. Buka terminal di folder mobile:
   ```bash
   cd "C:\Users\bobby\OneDrive\Documents\MY-PR\MOBILE-APP\mobile"
   ```

2. Install dependensi Node.js:
   ```bash
   npm install
   ```

3. Jalankan Expo:
   ```bash
   npx expo start
   ```

4. **Buka di HP Anda**:
   - Download aplikasi **Expo Go** di Play Store (Android) atau App Store (iOS).
   - Scan **QR Code** yang muncul di terminal laptop menggunakan aplikasi Expo Go.
   - Di aplikasi mobile, buka menu drawer ➔ ketuk **⚙️ URL Backend** ➔ masukkan URL backend Anda:
     - Jika pakai WiFi sama: `http://192.168.x.x:8000`
     - Jika pakai ngrok / beda jaringan: `https://a1b2-c3d4.ngrok-free.app`
     - Jika pakai Android Emulator: `http://10.0.2.2:8000`
