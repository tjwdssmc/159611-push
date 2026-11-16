# -*- coding: utf-8 -*-
"""
159611 广发中证全指电力公用事业ETF · 每日战报推送(GitHub Actions版)
定价框架:DDM 股债利差 = 指数股息率 - 10Y国债收益率
持仓:成本 1.1063,2026-06-08 建仓,3000份
数据源:腾讯行情(qt.gtimg.cn)
推送:飞书群自定义机器人 webhook(从环境变量 FEISHU_WEBHOOK 读取)
"""
import os, sys, json, datetime, requests

# ============ 配置(每月手动改一次股息率基线) ============
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "159611_config.json")

DEFAULT_CONFIG = {
    "code": "sz159611",
    "name": "159611 电力ETF广发",
    "dividend_yield": 0.0279,
    "dividend_yield_date": "2026-08-27",
    "bond_10y": 0.0168,
    "bond_date": "2026-09-22",
    "yld_low": 0.0208,
    "yld_high": 0.0302,
    "spread_full": 0.020,
    "spread_add": 0.015,
    "spread_hold": 0.008,
    "cost": 1.1063,
    "buy_date": "2026-06-08",
    "shares": 3000,
    "target_yield_full": 0.033,
    "target_yield_add": 0.030,
    "target_yield_take": 0.022,
}

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    # webhook 优先从环境变量读(GitHub Secrets),其次从config读
    cfg["webhook"] = os.environ.get("FEISHU_WEBHOOK", cfg.get("webhook", ""))
    return cfg

def fetch_etf_price(cfg):
    r = requests.get("http://qt.gtimg.cn/q=sz159611", timeout=10)
    r.encoding = "gbk"
    parts = r.text.split("~")
    price = float(parts[3])
    prev = float(parts[4])
    return {
        "price": price,
        "pct": (price - prev) / prev * 100,
        "high": float(parts[33]),
        "low": float(parts[34]),
        "prev_close": prev,
        "time": parts[30],
    }

def fetch_bond_10y(cfg):
    return {
        "yield_10y": cfg.get("bond_10y", 0.0168),
        "date": cfg.get("bond_date", "2026-09-22"),
    }

def grade(spread, cfg):
    if spread >= cfg["spread_full"]: return "打满"
    if spread >= cfg["spread_add"]:  return "加仓"
    if spread >= cfg["spread_hold"]: return "持有"
    return "减仓"

def build_card(cfg, quote, bond, spread, rating):
    price = quote["price"]
    pct = quote["pct"]
    cost = cfg["cost"]
    pnl_pct = (price - cost) / cost
    div_per_unit = price * cfg["dividend_yield"]
    px_full = div_per_unit / cfg["target_yield_full"]
    px_add  = div_per_unit / cfg["target_yield_add"]
    px_take = div_per_unit / cfg["target_yield_take"]
    pctile = (cfg["dividend_yield"] - cfg["yld_low"]) / (cfg["yld_high"] - cfg["yld_low"])
    pnl_emoji = "📈" if pnl_pct >= 0 else "📉"
    day_emoji = "🔴" if pct > 0 else ("🟢" if pct < 0 else "⚪")

    lines = [
        f"**{cfg['name']} · 每日战报**",
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"{day_emoji} 现价 **{price:.3f}** 元  ({pct:+.2f}%)",
        f"{pnl_emoji} 成本 {cost:.4f} · 浮盈亏 **{pnl_pct*100:+.2f}%**",
        "",
        f"━━━ DDM 利差估值 ━━━",
        f"指数股息率(TTM) {cfg['dividend_yield']*100:.2f}%  (截至{cfg['dividend_yield_date']})",
        f"10Y国债 {bond['yield_10y']*100:.2f}%  ({bond['date']})",
        f"股债利差 **{spread*100:.2f}%**  ·  历史分位 {pctile*100:.0f}%",
        f"操作评级: **{rating}**",
        "",
        f"━━━ 关键价位 ━━━",
        f"打满价 {px_full:.3f}  (距现价 {(px_full-price)/price*100:+.1f}%)",
        f"加仓价 {px_add:.3f}  (距现价 {(px_add-price)/price*100:+.1f}%)",
        f"止盈价 {px_take:.3f}  (距现价 {(px_take-price)/price*100:+.1f}%)",
        "",
    ]
    if rating == "打满":
        lines.append("💡 利差≥2%,深度价值,可按计划打满")
    elif rating == "加仓":
        lines.append("💡 利差1.5~2%,偏便宜,逢低加仓")
    elif rating == "持有":
        lines.append("💡 利差0.8~1.5%,合理区间,持有不动")
    else:
        lines.append("⚠️ 利差<0.8%,偏贵,考虑减仓")

    if cfg.get("shares"):
        mv = price * cfg["shares"]
        pnl_amt = (price - cost) * cfg["shares"]
        lines.append(f"\n持仓市值 {mv:,.0f} 元 · 浮动盈亏 {pnl_amt:+,.0f} 元")

    # 国内惯例:涨红跌绿
    if pct > 0:
        header_color = "red"
    elif pct < 0:
        header_color = "green"
    else:
        header_color = "blue"

    return {"msg_type": "interactive", "card": {
        "config": {"wide_screen_mode": True},
        "header": {"template": header_color, "title": {"tag": "plain_text", "content": "159611 电力ETF 每日战报"}},
        "elements": [{"tag": "markdown", "content": "\n".join(lines)}]
    }}

def main():
    cfg = load_config()
    if not cfg["webhook"]:
        print("ERROR: 未配置 FEISHU_WEBHOOK 环境变量", file=sys.stderr); sys.exit(1)
    try:
        quote = fetch_etf_price(cfg)
        bond = fetch_bond_10y(cfg)
    except Exception as e:
        print(f"拉数据失败: {e}", file=sys.stderr); sys.exit(2)

    spread = cfg["dividend_yield"] - bond["yield_10y"]
    rating = grade(spread, cfg)
    card = build_card(cfg, quote, bond, spread, rating)

    r = requests.post(cfg["webhook"], json=card, timeout=10)
    print(f"推送: {r.status_code} {r.text[:200]}")
    print(f"评级: {rating}, 现价: {quote['price']}, 涨跌幅: {quote['pct']:+.2f}%")

if __name__ == "__main__":
    main()
