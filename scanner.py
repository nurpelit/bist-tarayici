import requests
import json
from datetime import datetime, timedelta
import os

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

def get_bist_top_movers():
    symbols = [
        "ASELS.IS","THYAO.IS","GARAN.IS","AKBNK.IS","EREGL.IS",
        "BIMAS.IS","KCHOL.IS","SAHOL.IS","SISE.IS","TUPRS.IS",
        "TOASO.IS","FROTO.IS","PGSUS.IS","TAVHL.IS","VESTL.IS",
        "ARCLK.IS","KOZAL.IS","KRDMD.IS","PETKM.IS","TCELL.IS",
        "YKBNK.IS","HALKB.IS","VAKBN.IS","ISCTR.IS","ENKAI.IS"
    ]
    results = []
    for symbol in symbols:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1mo&interval=1d"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            chart = data.get("chart", {}).get("result", [])
            if not chart:
                continue
            closes = chart[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
            closes = [c for c in closes if c is not None]
            if len(closes) < 2:
                continue
            price_now = closes[-1]
            price_month_ago = closes[0]
            change_1m = ((price_now - price_month_ago) / price_month_ago) * 100
            change_1d = ((closes[-1] - closes[-2]) / closes[-2]) * 100 if len(closes) >= 2 else 0
            results.append({
                "symbol": symbol.replace(".IS", ""),
                "price": round(price_now, 2),
                "change_1d": round(change_1d, 2),
                "change_1m": round(change_1m, 2),
            })
        except Exception as e:
            print(f"{symbol} hatası: {e}")
    return results

def get_tefas_funds():
    fund_codes = ["AFT","AKS","GAH","TTE","IPJ","YAE","MAH","GAF"]
    fund_results = []
    end_date = datetime.now().strftime("%d.%m.%Y")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%d.%m.%Y")
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
            if len(rows) < 2:
                continue
            price_start = float(rows[-1].get("FIYAT", 0))
            price_end = float(rows[0].get("FIYAT", 0))
            if price_start == 0:
                continue
            change_1m = ((price_end - price_start) / price_start) * 100
            fund_results.append({
                "code": code,
                "price": round(price_end, 4),
                "change_1m": round(change_1m, 2)
            })
        except Exception as e:
            print(f"Fon {code} hatası: {e}")
    return fund_results

def build_report(stocks, funds):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    top_stocks = sorted(stocks, key=lambda x: x["change_1m"], reverse=True)[:5]
    worst_stocks = sorted(stocks, key=lambda x: x["change_1m"])[:3]
    top_funds = sorted(funds, key=lambda x: x["change_1m"], reverse=True)[:5]

    msg = f"📊 <b>BORSA TARAYICI RAPORU</b>\n🕐 {now}\n━━━━━━━━━━━━━━━━━━\n\n"
    msg += "🚀 <b>EN ÇOK YÜKSELEN HİSSELER (1 Ay)</b>\n"
    for s in top_stocks:
        emoji = "🟢" if s["change_1m"] > 0 else "🔴"
        msg += f"{emoji} <b>{s['symbol']}</b>: {s['price']} ₺ | Aylık: %{s['change_1m']:+.1f} | Günlük: %{s['change_1d']:+.1f}\n"
    msg += "\n📉 <b>EN ÇOK DÜŞENLER (1 Ay)</b>\n"
    for s in worst_stocks:
        msg += f"🔴 <b>{s['symbol']}</b>: {s['price']} ₺ | Aylık: %{s['change_1m']:+.1f}\n"
    if top_funds:
        msg += "\n💰 <b>EN İYİ TEFAS FONLARI (1 Ay)</b>\n"
        for f in top_funds:
            emoji = "🟢" if f["change_1m"] > 0 else "🔴"
            msg += f"{emoji} <b>{f['code']}</b>: {f['price']} ₺ | %{f['change_1m']:+.1f}\n"
    msg += "\n━━━━━━━━━━━━━━━━━━\n⚠️ <i>Bu rapor bilgi amaçlıdır, yatırım tavsiyesi değildir.</i>"
    return msg

def main():
    print("📡 Veri çekiliyor...")
    stocks = get_bist_top_movers()
    print(f"✅ {len(stocks)} hisse verisi alındı")
    funds = get_tefas_funds()
    print(f"✅ {len(funds)} fon verisi alındı")
    if not stocks and not funds:
        send_telegram("⚠️ Veri çekilemedi, lütfen kontrol edin.")
        return
    report = build_report(stocks, funds)
    success = send_telegram(report)
    print("✅ Telegram mesajı gönderildi!" if success else "❌ Gönderilemedi!")

if __name__ == "__main__":
    main()
