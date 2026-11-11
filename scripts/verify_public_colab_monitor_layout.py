"""実計測値から生成した表示のPC・モバイル・ダーク表示を検証する。"""
import argparse
import json
from pathlib import Path
import re
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
content = (args.output / "preview.html").read_text(encoding="utf-8")
checks = []

def luminance(css_color):
    channels = [int(value) / 255 for value in re.findall(r"\d+", css_color)[:3]]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="msedge", headless=True)
    try:
        for width, theme in ((1280, "light"), (390, "light"), (320, "light"), (390, "dark")):
            page = browser.new_page(viewport={"width": width, "height": 700}, color_scheme=theme)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content(content, wait_until="load")
            assert not errors, errors
            assert page.get_by_role("region", name="ランタイムの使用状況").count() == 1
            assert page.get_by_text("停止済み", exact=False).count() > 0
            assert page.locator(".gm-monitor-card").count() >= 3
            bounds = page.evaluate('''() => ({
                document: document.documentElement.scrollWidth,
                viewport: innerWidth,
                cards: [...document.querySelectorAll('.gm-monitor-card')].map(element => {
                    const rect = element.getBoundingClientRect();
                    const style = getComputedStyle(element);
                    return {left: rect.left, right: rect.right, scroll: element.scrollWidth, width: element.clientWidth,
                        text: style.color, background: style.backgroundColor};
                })
            })''')
            assert bounds["document"] <= width, bounds
            assert all(card["left"] >= 0 and card["right"] <= width and card["scroll"] <= card["width"] for card in bounds["cards"]), bounds
            for card in bounds["cards"]:
                values = sorted((luminance(card["text"]), luminance(card["background"])))
                assert (values[1] + 0.05) / (values[0] + 0.05) >= 4.5, card
            page.screenshot(path=str(args.output / f"monitor-{width}-{theme}.png"), full_page=True)
            checks.append({"width": width, "theme": theme, "passed": True, "page_errors": len(errors)})
            page.close()
    finally:
        browser.close()
(args.output / "layout.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
print("PC・390px・320px・ダーク表示の4条件で、表示と画面内配置を確認しました。")
