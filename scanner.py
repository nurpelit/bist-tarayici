import requests
from datetime import datetime, timedelta
import os
import time

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=data, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram hatası: {e}")
        return False

def get_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)

def get_macd(closes):
    """MACD sinyal hesapla"""
    if len(closes) < 26:
        return None, None
    def ema(data, period):
        k = 2 / (period + 1)
        ema_val = data[0]
        for price in data[1:]:
            ema_val = price * k + ema_val * (1 - k)
        return ema_val
    ema12 = ema(closes[-26:], 12)
    ema26 = ema(closes[-26:], 26)
    macd = ema12 - ema26
    return round(macd, 4), round(ema12, 4)

def get_trend_projection(closes, days=10):
    if len(closes) < 10:
        return None, None
    last = closes[-10:]
    n = len(last)
    x_mean = (n - 1) / 2
    y_mean = sum(last) / n
    num = sum((i - x_mean) * (last[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den != 0 else 0
    projected_price = closes[-1] + slope * days
    projected_pct = ((projected_price - closes[-1]) / closes[-1]) * 100
    return round(projected_price, 2), round(projected_pct, 1)

def calc_score(rsi, pct_1m, pct_1w, change_3d, proj_pct, macd, volume_ratio):
    """
    Borsa uzmanı gibi çoklu kriter puanlama (max 100)
    """
    score = 0

    # RSI (30-50 arası ideal alım bölgesi) — max 25 puan
    if rsi:
        if 30 <= rsi <= 45:
            score += 25  # aşırı satım + toparlanma
        elif 45 < rsi <= 55:
            score += 18
        elif 55 < rsi <= 65:
            score += 10
        elif rsi < 30:
            score += 15  # çok aşırı satım, dikkatli

    # 10 günlük projeksiyon — max 25 puan
    if proj_pct:
        if proj_pct > 8:
            score += 25
        elif proj_pct > 5:
            score += 20
        elif proj_pct > 3:
            score += 15
        elif proj_pct > 1:
            score += 8
        elif proj_pct > 0:
            score += 3

    # Son 3 gün toparlanma — max 20 puan
    if change_3d > 4:
        score += 20
    elif change_3d > 2:
        score += 15
    elif change_3d > 1:
        score += 10
    elif change_3d > 0:
        score += 5

    # 1 haftalık momentum — max 15 puan
    if pct_1w > 5:
        score += 15
    elif pct_1w > 3:
        score += 10
    elif pct_1w > 1:
        score += 7
    elif pct_1w > 0:
        score += 3

    # MACD pozitif mi — max 10 puan
    if macd and macd > 0:
        score += 10
    elif macd and macd > -0.5:
        score += 5

    # Hacim artışı — max 5 puan
    if volume_ratio and volume_ratio > 1.5:
        score += 5
    elif volume_ratio and volume_ratio > 1.2:
        score += 3

    return min(score, 100)

def get_signal_label(score):
    if score >= 80:
        return "🔥 ÇOK GÜÇLÜ"
    elif score >= 65:
        return "💪 GÜÇLÜ"
    elif score >= 50:
        return "✅ ORTA"
    else:
        return "⚠️ ZAYIF"

def get_bist_analysis():
    # Geniş hisse listesi — BIST'in en aktif hisseleri
    symbols = [
        "ASELS.IS","THYAO.IS","GARAN.IS","AKBNK.IS","EREGL.IS",
        "BIMAS.IS","KCHOL.IS","SAHOL.IS","SISE.IS","TUPRS.IS",
        "TOASO.IS","FROTO.IS","PGSUS.IS","TAVHL.IS","VESTL.IS",
        "ARCLK.IS","KOZAL.IS","KRDMD.IS","PETKM.IS","TCELL.IS",
        "YKBNK.IS","HALKB.IS","VAKBN.IS","ISCTR.IS","ENKAI.IS",
        "ODAS.IS","EKGYO.IS","LOGO.IS","NETAS.IS","SMART.IS",
        "GUBRF.IS","CIMSA.IS","AKCNS.IS","BRISA.IS","DOHOL.IS",
        "TKFEN.IS","SOKM.IS","ULKER.IS","MGROS.IS","BIZIM.IS",
        "ALARK.IS","SASA.IS","ISDMR.IS","KORDS.IS","TTKOM.IS",
        "AEFES.IS","CCOLA.IS","MAVI.IS","ADEL.IS","KTLEV.IS"
    ]

    candidates = []

    for symbol in symbols:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=3mo&interval=1d"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            chart = data.get("chart", {}).get("result", [])
            if not chart:
                continue

            quotes = chart[0].get("indicators", {}).get("quote", [{}])[0]
            closes  = [c for c in quotes.get("close",  []) if c is not None]
            highs   = [c for c in quotes.get("high",   []) if c is not None]
            lows    = [c for c in quotes.get("low",    []) if c is not None]
            volumes = [c for c in quotes.get("volume", []) if c is not None]

            if len(closes) < 22:
                continue

            price_now = closes[-1]

            # Fiyat bantları
            high_1m = round(max(highs[-22:]),  2) if len(highs)  >= 22 else round(max(highs),  2)
            low_1m  = round(min(lows[-22:]),   2) if len(lows)   >= 22 else round(min(lows),   2)
            high_3m = round(max(highs), 2)
            low_3m  = round(min(lows),  2)

            pct_1m = round(((price_now - closes[-22]) / closes[-22]) * 100, 1)
            pct_3m = round(((price_now - closes[0])   / closes[0])   * 100, 1)
            pct_1w = round(((price_now - closes[-6])  / closes[-6])  * 100, 1) if len(closes) >= 6 else 0
            change_3d = round(((price_now - closes[-4]) / closes[-4]) * 100, 2) if len(closes) >= 4 else 0

            # Teknik göstergeler
            rsi = get_rsi(closes)
            macd, _ = get_macd(closes)
            proj_price, proj_pct = get_trend_projection(closes)

            # Hacim oranı (son 5 gün vs önceki 20 gün)
            volume_ratio = None
            if len(volumes) >= 25:
                avg_recent = sum(volumes[-5:]) / 5
                avg_old = sum(volumes[-25:-5]) / 20
                volume_ratio = round(avg_recent / avg_old, 2) if avg_old > 0 else None

            # Puanlama
            score = calc_score(rsi, pct_1m, pct_1w, change_3d, proj_pct, macd, volume_ratio)

            # Sadece pozitif projeksiyon olan ve makul RSI'lı hisseleri al
            if proj_pct and proj_pct > 0 and rsi and rsi < 70:
                candidates.append({
                    "symbol": symbol.replace(".IS", ""),
                    "price_now": round(price_now, 2),
                    "high_1m": high_1m, "low_1m": low_1m, "pct_1m": pct_1m,
                    "high_3m": high_3m, "low_3m": low_3m, "pct_3m": pct_3m,
                    "pct_1w": pct_1w,
                    "proj_price": proj_price, "proj_pct": proj_pct,
                    "rsi": rsi, "macd": macd,
                    "volume_ratio": volume_ratio,
                    "change_3d": change_3d,
                    "score": score,
                })

            time.sleep(0.3)
        except Exception as e:
            print(f"{symbol} hatası: {e}")

    # En yüksek puanlı 10 hisse
    return sorted(candidates, key=lambda x: x["score"], reverse=True)[:10]

def get_tefas_funds():
    fund_codes = ["AFT","AKS","GAH","TTE","IPJ","YAE","MAH","GAF","HAS","IYH",
                  "ATA","MAC","YAS","TI2","GBF"]
    fund_results = []
    end_date   = datetime.now().strftime("%d.%m.%Y")
    start_date = (datetime.now() - timedelta(days=90)).strftime("%d.%m.%Y")

    for code in fund_codes:
        try:
            url = "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://www.tefas.gov.tr/"
            }
            payload = f"fontip=YAT&bastarih={start_date}&bittarih={end_date}&fonkod={code}"
            r = requests.post(url, headers=headers, data=payload, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            rows = data.get("data", [])
            if len(rows) < 10:
                continue

            prices = [float(row.get("FIYAT", 0)) for row in reversed(rows) if row.get("FIYAT")]
            if len(prices) < 10:
                continue

            price_now = prices[-1]
            price_1m  = prices[-22] if len(prices) >= 22 else prices[0]
            high_1m   = round(max(prices[-22:]), 4) if len(prices) >= 22 else round(max(prices), 4)
            low_1m    = round(min(prices[-22:]), 4) if len(prices) >= 22 else round(min(prices), 4)
            pct_1m    = round(((price_now - price_1m) / price_1m) * 100, 1)
            high_3m   = round(max(prices), 4)
            low_3m    = round(min(prices), 4)
            pct_3m    = round(((price_now - prices[0]) / prices[0]) * 100, 1)
            proj_price, proj_pct = get_trend_projection(prices)

            fund_results.append({
                "code": code,
                "price_now": round(price_now, 4),
                "high_1m": high_1m, "low_1m": low_1m, "pct_1m": pct_1m,
                "high_3m": high_3m, "low_3m": low_3m, "pct_3m": pct_3m,
                "proj_price": proj_price, "proj_pct": proj_pct,
            })
        except Exception as e:
            print(f"Fon {code} hatası: {e}")

    return sorted(fund_results, key=lambda x: x["pct_1m"], reverse=True)[:5]

def get_upcoming_ipos():
    try:
        url = "https://www.kap.org.tr/tr/api/disclosureQuery"
        headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
        payload = {
            "fromDate": datetime.now().strftime("%Y-%m-%d"),
            "toDate": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "disclosureClass": "FR"
        }
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return [{"company": i.get("companyName",""), "date": i.get("publishDate","")[:10]} for i in data[:5]]
    except Exception as e:
        print(f"KAP hatası: {e}")
    return []

def build_report(top10, funds, ipos):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    msg = f"📊 <b>BORSA TARAYICI — UZMAN ANALİZ</b>\n"
    msg += f"🕐 {now}\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"
    msg += "🏆 <b>EN İYİ 10 ALIM FIRSATI</b>\n"
    msg += "<i>(Çoklu teknik kritere göre puanlandı)</i>\n\n"

    for i, s in enumerate(top10, 1):
        label = get_signal_label(s["score"])
        proj_emoji = "📈" if s["proj_pct"] > 0 else "📉"
        msg += f"<b>{i}. {s['symbol']}</b> — {label} ({s['score']}/100)\n"
        msg += f"💰 Bugün: <b>{s['price_now']} ₺</b>\n"
        msg += f"📅 1 Aylık bant: {s['low_1m']} ₺ – {s['high_1m']} ₺  (%{s['pct_1m']:+.1f})\n"
        msg += f"📅 3 Aylık bant: {s['low_3m']} ₺ – {s['high_3m']} ₺  (%{s['pct_3m']:+.1f})\n"
        msg += f"{proj_emoji} 10 Gün Beklenti: ~{s['proj_price']} ₺  (%{s['proj_pct']:+.1f})\n"
        msg += f"🔍 RSI: {s['rsi']}"
        if s['volume_ratio']:
            msg += f" | Hacim: x{s['volume_ratio']}"
        msg += "\n\n"

    if funds:
        msg += "━━━━━━━━━━━━━━━━━━\n"
        msg += "💼 <b>EN İYİ TEFAS FONLARI</b>\n\n"
        for f in funds:
            emoji = "🟢" if f["pct_1m"] > 0 else "🔴"
            proj_emoji = "📈" if f["proj_pct"] and f["proj_pct"] > 0 else "📉"
            msg += f"{emoji} <b>{f['code']}</b> — {f['price_now']} ₺\n"
            msg += f"📅 1 Aylık: {f['low_1m']} ₺ – {f['high_1m']} ₺  (%{f['pct_1m']:+.1f})\n"
            msg += f"📅 3 Aylık: {f['low_3m']} ₺ – {f['high_3m']} ₺  (%{f['pct_3m']:+.1f})\n"
            if f["proj_price"]:
                msg += f"{proj_emoji} 10 Gün: ~{f['proj_price']} ₺  (%{f['proj_pct']:+.1f})\n"
            msg += "\n"

    if ipos:
        msg += "━━━━━━━━━━━━━━━━━━\n"
        msg += "🆕 <b>YAKLAŞAN HALKA ARZLAR</b>\n"
        for ipo in ipos:
            msg += f"📌 <b>{ipo['company']}</b> — {ipo['date']}\n"
        msg += "\n"

    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += "⚠️ <i>Teknik analize dayalı bilgi amaçlıdır.\nYatırım tavsiyesi değildir, karar size aittir.</i>"
    return msg

def main():
    print("📡 Veri çekiliyor... (50 hisse taranıyor)")
    top10 = get_bist_analysis()
    print(f"✅ En iyi {len(top10)} hisse seçildi")
    funds = get_tefas_funds()
    print(f"✅ {len(funds)} fon verisi alındı")
    ipos = get_upcoming_ipos()
    print(f"✅ {len(ipos)} halka arz bulundu")
    report = build_report(top10, funds, ipos)
    success = send_telegram(report)
    print("✅ Telegram mesajı gönderildi!" if success else "❌ Gönderilemedi!")

if __name__ == "__main__":
    main()
