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
        r = requests.post(url, data=data, timeout=10)
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

def get_trend_projection(closes, days=10):
    """Lineer regresyon ile 10 günlük fiyat projeksiyonu"""
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

def get_bist_analysis():
    symbols = [
        "ASELS.IS","THYAO.IS","GARAN.IS","AKBNK.IS","EREGL.IS",
        "BIMAS.IS","KCHOL.IS","SAHOL.IS","SISE.IS","TUPRS.IS",
        "TOASO.IS","FROTO.IS","PGSUS.IS","TAVHL.IS","VESTL.IS",
        "ARCLK.IS","KOZAL.IS","KRDMD.IS","PETKM.IS","TCELL.IS",
        "YKBNK.IS","HALKB.IS","VAKBN.IS","ISCTR.IS","ENKAI.IS",
        "ODAS.IS","EKGYO.IS","LOGO.IS","NETAS.IS","SMART.IS"
    ]

    alim_firsati = []
    yukselenler = []

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
            closes = [c for c in quotes.get("close", []) if c is not None]
            highs  = [c for c in quotes.get("high",  []) if c is not None]
            lows   = [c for c in quotes.get("low",   []) if c is not None]

            if len(closes) < 22:
                continue

            price_now = closes[-1]

            # 1 aylık bant (~22 işlem günü)
            closes_1m = closes[-22:]
            highs_1m  = highs[-22:]  if len(highs)  >= 22 else highs
            lows_1m   = lows[-22:]   if len(lows)   >= 22 else lows
            high_1m = round(max(highs_1m), 2)
            low_1m  = round(min(lows_1m), 2)
            pct_1m  = round(((price_now - closes[-22]) / closes[-22]) * 100, 1)

            # 3 aylık bant (tüm veri)
            high_3m = round(max(highs), 2)
            low_3m  = round(min(lows), 2)
            pct_3m  = round(((price_now - closes[0]) / closes[0]) * 100, 1)

            # 10 günlük projeksiyon
            proj_price, proj_pct = get_trend_projection(closes)

            # RSI
            rsi = get_rsi(closes)

            # Son 3 gün değişimi (toparlanma tespiti)
            change_3d = ((price_now - closes[-4]) / closes[-4]) * 100 if len(closes) >= 4 else 0

            name = symbol.replace(".IS", "")

            stock = {
                "symbol": name,
                "price_now": round(price_now, 2),
                "high_1m": high_1m, "low_1m": low_1m, "pct_1m": pct_1m,
                "high_3m": high_3m, "low_3m": low_3m, "pct_3m": pct_3m,
                "proj_price": proj_price, "proj_pct": proj_pct,
                "rsi": rsi,
                "change_3d": round(change_3d, 2),
            }

            if rsi and rsi < 45 and change_3d > 1.5:
                alim_firsati.append(stock)

            if pct_1m > 10 and change_3d > 0:
                yukselenler.append(stock)

            time.sleep(0.3)
        except Exception as e:
            print(f"{symbol} hatası: {e}")

    return alim_firsati, yukselenler

def get_tefas_funds():
    fund_codes = ["AFT","AKS","GAH","TTE","IPJ","YAE","MAH","GAF","HAS","IYH"]
    fund_results = []
    end_date = datetime.now().strftime("%d.%m.%Y")
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
            high_1m = round(max(prices[-22:]), 4) if len(prices) >= 22 else round(max(prices), 4)
            low_1m  = round(min(prices[-22:]), 4) if len(prices) >= 22 else round(min(prices), 4)
            pct_1m  = round(((price_now - price_1m) / price_1m) * 100, 1)

            high_3m = round(max(prices), 4)
            low_3m  = round(min(prices), 4)
            pct_3m  = round(((price_now - prices[0]) / prices[0]) * 100, 1)

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

    return sorted(fund_results, key=lambda x: x["pct_1m"], reverse=True)

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

def fmt_stock(s):
    proj_emoji = "📈" if s["proj_pct"] and s["proj_pct"] > 0 else "📉"
    msg  = f"💰 Bugün: <b>{s['price_now']} ₺</b>\n"
    msg += f"📅 1 Aylık bant: {s['low_1m']} ₺ – {s['high_1m']} ₺  (%{s['pct_1m']:+.1f})\n"
    msg += f"📅 3 Aylık bant: {s['low_3m']} ₺ – {s['high_3m']} ₺  (%{s['pct_3m']:+.1f})\n"
    if s["proj_price"]:
        msg += f"{proj_emoji} 10 Gün Beklenti: ~{s['proj_price']} ₺  (%{s['proj_pct']:+.1f})\n"
    if s.get("rsi"):
        msg += f"🔍 RSI: {s['rsi']}\n"
    return msg

def fmt_fund(f):
    proj_emoji = "📈" if f["proj_pct"] and f["proj_pct"] > 0 else "📉"
    msg  = f"💰 Bugün: <b>{f['price_now']} ₺</b>\n"
    msg += f"📅 1 Aylık bant: {f['low_1m']} ₺ – {f['high_1m']} ₺  (%{f['pct_1m']:+.1f})\n"
    msg += f"📅 3 Aylık bant: {f['low_3m']} ₺ – {f['high_3m']} ₺  (%{f['pct_3m']:+.1f})\n"
    if f["proj_price"]:
        msg += f"{proj_emoji} 10 Gün Beklenti: ~{f['proj_price']} ₺  (%{f['proj_pct']:+.1f})\n"
    return msg

def build_report(alim_firsati, yukselenler, funds, ipos):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    msg = f"📊 <b>BORSA TARAYICI RAPORU</b>\n🕐 {now}\n━━━━━━━━━━━━━━━━━━\n\n"

    if alim_firsati:
        msg += "🎯 <b>ALIM FIRSATLARI</b>\n<i>(RSI düşük + toparlanma başladı)</i>\n\n"
        for s in sorted(alim_firsati, key=lambda x: x["rsi"])[:5]:
            msg += f"🟡 <b>{s['symbol']}</b>\n"
            msg += fmt_stock(s)
            msg += "\n"

    if yukselenler:
        msg += "🚀 <b>GÜÇLÜ MOMENTUM</b>\n<i>(1 ayda güçlü yükseliş)</i>\n\n"
        for s in sorted(yukselenler, key=lambda x: x["pct_1m"], reverse=True)[:5]:
            msg += f"🟢 <b>{s['symbol']}</b>\n"
            msg += fmt_stock(s)
            msg += "\n"

    if funds:
        msg += "💼 <b>EN İYİ TEFAS FONLARI</b>\n\n"
        for f in funds[:5]:
            emoji = "🟢" if f["pct_1m"] > 0 else "🔴"
            msg += f"{emoji} <b>{f['code']}</b>\n"
            msg += fmt_fund(f)
            msg += "\n"

    if ipos:
        msg += "🆕 <b>YAKLAŞAN HALKA ARZLAR</b>\n"
        for ipo in ipos:
            msg += f"📌 <b>{ipo['company']}</b> — {ipo['date']}\n"
        msg += "\n"

    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += "⚠️ <i>Bu rapor bilgi amaçlıdır, yatırım tavsiyesi değildir.</i>"
    return msg

def main():
    print("📡 Veri çekiliyor...")
    alim_firsati, yukselenler = get_bist_analysis()
    print(f"✅ Alım fırsatı: {len(alim_firsati)} | Momentum: {len(yukselenler)}")
    funds = get_tefas_funds()
    print(f"✅ {len(funds)} fon verisi alındı")
    ipos = get_upcoming_ipos()
    print(f"✅ {len(ipos)} halka arz bulundu")
    report = build_report(alim_firsati, yukselenler, funds, ipos)
    success = send_telegram(report)
    print("✅ Telegram mesajı gönderildi!" if success else "❌ Gönderilemedi!")

if __name__ == "__main__":
    main()
