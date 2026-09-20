"""HTML slide templates for the EquiVision Basics daily post.

Every slide is a 1080x1350 (4:5) page. `build_slide_html` turns one slide dict from
queue/posts.json into a complete HTML document. Text supports light markup:
    [[word]]  -> highlighted in the brand's light blue (bold)
    **word**  -> bold white
"""
import html
import re

HANDLE = "@equivisionbasics"
BRAND = "EQUIVISION BASICS"

CSS = """
@font-face{font-family:'Poppins';font-weight:400;src:url('__FONTS__/Poppins-Regular.ttf')}
@font-face{font-family:'Poppins';font-weight:500;src:url('__FONTS__/Poppins-Medium.ttf')}
@font-face{font-family:'Poppins';font-weight:600;src:url('__FONTS__/Poppins-Bold.ttf')}
@font-face{font-family:'Poppins';font-weight:700;src:url('__FONTS__/Poppins-Bold.ttf')}
:root{--bg:#0d1015;--panel:#161b23;--panel2:#1b212b;--ice:#7ec8e8;--ice2:#b5e3f5;--silver:#d5dde5;--muted:#8b99a8}
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1350px;font-family:'Poppins',sans-serif;background:var(--bg);color:#fff;position:relative;overflow:hidden}
.bg{position:absolute;inset:0;background:
 radial-gradient(900px 700px at 90% 5%,rgba(126,200,232,.20),transparent 60%),
 radial-gradient(800px 800px at 0% 100%,rgba(126,200,232,.10),transparent 62%),
 linear-gradient(180deg,#10141b,#0a0d12)}
.rings{position:absolute;right:-260px;top:-260px;width:760px;height:760px;opacity:.38}
.top{position:absolute;left:72px;right:72px;top:64px;display:flex;align-items:center;gap:22px}
.top img{width:88px;height:88px;border-radius:50%}
.top span{letter-spacing:.24em;font-size:23px;color:var(--silver);font-weight:500}
.foot{position:absolute;left:72px;right:72px;bottom:58px;display:flex;justify-content:space-between;align-items:center;font-size:24px;color:var(--muted);font-weight:500}
.foot b{color:var(--ice);font-weight:600}
.label{display:inline-block;font-size:26px;font-weight:600;letter-spacing:.2em;color:var(--ice);margin-bottom:26px;text-transform:uppercase}
.wrap{position:absolute;left:72px;right:72px;top:210px}
h1{font-weight:700;line-height:1.12}
.ice{color:var(--ice);font-weight:700}
.panel{background:linear-gradient(180deg,var(--panel2),var(--panel));border:2px solid rgba(126,200,232,.22);border-radius:36px}
.note{font-size:24px;color:var(--muted);line-height:1.4}
.abs{position:absolute;left:72px;right:72px}
"""

RINGS = """<svg class="rings" viewBox="0 0 760 760" fill="none" stroke="#7ec8e8">
<circle cx="380" cy="380" r="150" stroke-width="10" opacity=".9"/><circle cx="380" cy="380" r="205" stroke-width="3" opacity=".6"/>
<circle cx="380" cy="380" r="270" stroke-width="2" opacity=".35"/><circle cx="380" cy="380" r="340" stroke-width="2" opacity=".2"/></svg>"""

# Shrinks any element marked class="fit" until it fits its box (data-maxh / data-maxw in px)
FIT_JS = """
<script>
document.fonts.ready.then(function(){
  document.querySelectorAll('.fit').forEach(function(el){
    var maxh = parseFloat(el.dataset.maxh||0), maxw = parseFloat(el.dataset.maxw||0);
    var size = parseFloat(getComputedStyle(el).fontSize), min = parseFloat(el.dataset.min||34);
    function over(){ return (maxh && el.scrollHeight>maxh) || (maxw && el.scrollWidth>maxw); }
    while(over() && size>min){ size-=2; el.style.fontSize=size+'px'; }
  });
  document.querySelectorAll('text.fs').forEach(function(t){
    var mw = parseFloat(t.dataset.maxw||240), size = parseFloat(t.getAttribute('font-size'));
    while(t.getComputedTextLength()>mw && size>16){ size-=1; t.setAttribute('font-size',size); }
  });
  document.body.setAttribute('data-ready','1');
});
</script>
"""


def esc(s):
    return html.escape(str(s), quote=False)


def mk(s):
    """Escape then apply [[ice]] and **bold** markup."""
    s = esc(s)
    s = re.sub(r"\[\[(.+?)\]\]", r'<span class="ice">\1</span>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return s


def plain(s):
    """Remove markup for SVG text."""
    return esc(re.sub(r"\[\[(.+?)\]\]|\*\*(.+?)\*\*", lambda m: m.group(1) or m.group(2), str(s)))


# ---------------------------------------------------------------- icons (100x100 box, centred)
ICONS = {
    "person": '<circle cx="0" cy="-18" r="17"/><path d="M-34 38Q-34 6 0 6Q34 6 34 38Z"/>',
    "store": '<path d="M-42 -8L-32 -38H32L42 -8Z"/><path d="M-30 -2H30V36H-30Z" opacity=".85"/><rect x="-8" y="10" width="16" height="26" fill="#0d1015"/>',
    "bank": '<path d="M-44 -14L0 -42L44 -14Z"/><rect x="-32" y="-6" width="14" height="36"/><rect x="-7" y="-6" width="14" height="36"/><rect x="18" y="-6" width="14" height="36"/><rect x="-44" y="32" width="88" height="9"/>',
    "gift": '<rect x="-38" y="-8" width="76" height="46" rx="5"/><rect x="-44" y="-28" width="88" height="20" rx="5"/><rect x="-7" y="-28" width="14" height="66" fill="#7ec8e8"/><path d="M0 -28C-24 -58 -48 -36 -24 -28ZM0 -28C24 -58 48 -36 24 -28Z"/>',
    "coins": '<ellipse cx="0" cy="24" rx="38" ry="13"/><ellipse cx="0" cy="6" rx="38" ry="13" fill="#b5e3f5"/><ellipse cx="0" cy="-12" rx="38" ry="13"/><ellipse cx="0" cy="-12" rx="24" ry="7" fill="none" stroke="#6b7c8a" stroke-width="3"/>',
    "basket": '<path d="M-42 -4H42L32 38H-32Z"/><path d="M-24 -4L-12 -34H12L24 -4" fill="none" stroke="#d5dde5" stroke-width="7" stroke-linejoin="round"/><path d="M-12 8V28M0 8V28M12 8V28" stroke="#0d1015" stroke-width="5" stroke-linecap="round"/>',
    "tag": '<path d="M-42 4L-6 -32H38V12L2 48Z" transform="translate(0 -6)"/><circle cx="18" cy="-24" r="7" fill="#0d1015"/>',
    "chart": '<rect x="-38" y="6" width="20" height="34" rx="3"/><rect x="-10" y="-14" width="20" height="54" rx="3" fill="#b5e3f5"/><rect x="18" y="-38" width="20" height="78" rx="3"/>',
    "pie": '<path d="M-4 4L-4 -40A40 40 0 1 0 36 4Z"/><path d="M4 -4L4 -40A40 40 0 0 1 40 -4Z" fill="#7ec8e8"/>',
    "shield": '<path d="M0 -44L34 -30V0C34 24 18 38 0 46C-18 38 -34 24 -34 0V-30Z"/><path d="M-14 2L-4 12L16 -12" fill="none" stroke="#0d1015" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>',
    "clock": '<circle r="40" fill="none" stroke="#d5dde5" stroke-width="8"/><path d="M0 -22V0L18 12" fill="none" stroke="#d5dde5" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>',
    "doc": '<path d="M-30 -42H12L34 -20V42H-30Z"/><path d="M-16 -2H20M-16 12H20M-16 26H6" stroke="#0d1015" stroke-width="6" stroke-linecap="round"/>',
    "arrowup": '<path d="M-36 24L-8 -4L8 12L36 -22" fill="none" stroke="#d5dde5" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/><path d="M14 -28H40V-2" fill="none" stroke="#d5dde5" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>',
    "arrowdown": '<path d="M-36 -22L-8 6L8 -10L36 24" fill="none" stroke="#d5dde5" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/><path d="M14 30H40V4" fill="none" stroke="#d5dde5" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>',
    "house": '<path d="M-44 -2L0 -40L44 -2H32V38H-32V-2Z"/><rect x="-9" y="12" width="18" height="26" fill="#0d1015"/>',
    "wallet": '<rect x="-42" y="-24" width="84" height="58" rx="10"/><rect x="10" y="-6" width="38" height="22" rx="8" fill="#7ec8e8"/><circle cx="26" cy="5" r="4" fill="#0d1015"/>',
    "plant": '<path d="M0 40V-4" stroke="#d5dde5" stroke-width="7" stroke-linecap="round"/><path d="M0 8C-30 8 -38 -14 -36 -30C-10 -30 0 -16 0 8Z"/><path d="M0 -6C26 -6 36 -26 34 -42C10 -42 0 -28 0 -6Z" fill="#b5e3f5"/>',
    "percent": '<circle cx="-20" cy="-20" r="13"/><circle cx="20" cy="20" r="13"/><path d="M28 -34L-28 34" stroke="#d5dde5" stroke-width="8" stroke-linecap="round"/>',
    "cart": '<path d="M-44 -34H-30L-18 20H32L40 -16H-24" fill="none" stroke="#d5dde5" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/><circle cx="-10" cy="36" r="7"/><circle cx="26" cy="36" r="7"/>',
    "scale": '<path d="M0 -40V36M-24 36H24" stroke="#d5dde5" stroke-width="7" stroke-linecap="round"/><path d="M-40 -22H40" stroke="#d5dde5" stroke-width="7" stroke-linecap="round"/><path d="M-40 -22L-54 6H-26Z"/><path d="M40 -22L26 6H54Z"/>',
}


def icon(name, scale=1.0, fill="#d5dde5"):
    body = ICONS.get(name, ICONS["coins"])
    return f'<g transform="scale({scale})" fill="{fill}">{body}</g>'


# ---------------------------------------------------------------- cover art (1080 x 590, bleeds off the bottom)
def art_card(a):
    return """
 <defs>
  <linearGradient id="c1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#dbe6ee"/><stop offset=".45" stop-color="#8fbfd6"/><stop offset="1" stop-color="#3b6f8c"/></linearGradient>
  <linearGradient id="c2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2b3644"/><stop offset="1" stop-color="#151b24"/></linearGradient>
  <linearGradient id="chip" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f2f5f7"/><stop offset="1" stop-color="#9aa9b6"/></linearGradient>
 </defs>
 <g transform="translate(560 330) rotate(-16)" opacity=".95"><rect x="-330" y="-190" width="700" height="420" rx="44" fill="url(#c2)" stroke="#7ec8e8" stroke-opacity=".35" stroke-width="3"/></g>
 <g transform="translate(470 300) rotate(-8)">
   <rect x="-360" y="-215" width="760" height="460" rx="48" fill="url(#c1)"/>
   <rect x="-360" y="-215" width="760" height="460" rx="48" fill="none" stroke="#ffffff" stroke-opacity=".55" stroke-width="3"/>
   <rect x="-300" y="-140" width="96" height="74" rx="14" fill="url(#chip)"/>
   <path d="M-300 -103H-204M-252 -140V-66" stroke="#6b7c8a" stroke-width="3"/>
   <text x="-300" y="120" font-family="Poppins" font-weight="600" font-size="54" fill="#0d1a24" letter-spacing="8">0000  0000  0000</text>
   <text x="-300" y="190" font-family="Poppins" font-weight="500" font-size="30" fill="#0d1a24" letter-spacing="5">EQUIVISION BASICS</text>
   <g transform="translate(300 170)"><circle r="34" fill="#0d1a24" opacity=".85"/><circle cx="34" r="34" fill="#7ec8e8" opacity=".9"/></g>
 </g>"""


def art_coins(a):
    defs = """<defs><linearGradient id="cg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#8fa2b2"/><stop offset=".5" stop-color="#eef3f7"/><stop offset="1" stop-color="#7f93a4"/></linearGradient>
    <linearGradient id="ct" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f4f8fb"/><stop offset="1" stop-color="#9fd3ea"/></linearGradient></defs>"""
    out = [defs]
    for cx, n in ((250, 4), (540, 8), (830, 5)):
        base = 560
        for i in range(n):
            y = base - i * 30
            out.append(f'<rect x="{cx-115}" y="{y-30}" width="230" height="34" fill="url(#cg)"/>')
            out.append(f'<ellipse cx="{cx}" cy="{y+4}" rx="115" ry="34" fill="url(#cg)"/>')
        top = base - (n - 1) * 30 - 30
        out.append(f'<ellipse cx="{cx}" cy="{top}" rx="115" ry="34" fill="url(#ct)"/>')
        out.append(f'<ellipse cx="{cx}" cy="{top}" rx="78" ry="20" fill="none" stroke="#6b7c8a" stroke-width="4"/>')
    out.append('<g transform="translate(540 110) rotate(-10)"><circle r="92" fill="url(#ct)" stroke="#fff" stroke-opacity=".6" stroke-width="4"/><circle r="70" fill="none" stroke="#6b7c8a" stroke-width="5"/>'
               '<text y="26" text-anchor="middle" font-family="Poppins" font-weight="700" font-size="84" fill="#3b6f8c">$</text></g>')
    return "".join(out)


def art_tag(a):
    t1 = plain(a.get("text1", "$4.00"))
    t2 = plain(a.get("text2", "$4.20"))
    return f"""
 <defs><linearGradient id="t1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2b3644"/><stop offset="1" stop-color="#151b24"/></linearGradient>
 <linearGradient id="t2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#dbe6ee"/><stop offset=".5" stop-color="#8fbfd6"/><stop offset="1" stop-color="#3b6f8c"/></linearGradient></defs>
 <g transform="translate(270 300) rotate(-14)">
   <path d="M-260 0L-150 -170H250Q290 -170 290 -130V130Q290 170 250 170H-150Z" fill="url(#t1)" stroke="#7ec8e8" stroke-opacity=".4" stroke-width="3"/>
   <circle cx="-150" cy="0" r="24" fill="#0d1015" stroke="#7ec8e8" stroke-opacity=".4" stroke-width="3"/>
   <text x="10" y="32" text-anchor="middle" font-family="Poppins" font-weight="600" font-size="96" fill="#8b99a8">{t1}</text>
   <line x1="-90" y1="14" x2="110" y2="14" stroke="#e5766c" stroke-width="9" stroke-linecap="round"/>
 </g>
 <g transform="translate(700 380) rotate(9)">
   <path d="M-300 0L-180 -190H290Q340 -190 340 -140V140Q340 190 290 190H-180Z" fill="url(#t2)"/>
   <path d="M-300 0L-180 -190H290Q340 -190 340 -140V140Q340 190 290 190H-180Z" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="3"/>
   <circle cx="-180" cy="0" r="28" fill="#0d1a24" opacity=".85"/>
   <text x="40" y="42" text-anchor="middle" font-family="Poppins" font-weight="700" font-size="128" fill="#0d1a24">{t2}</text>
 </g>
 <g transform="translate(900 120)"><circle r="58" fill="#0d1a24" stroke="#7ec8e8" stroke-width="4"/><path d="M0 22V-24M-20 -6L0 -26L20 -6" fill="none" stroke="#7ec8e8" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/></g>"""


def art_chart(a):
    pts = a.get("points") or [[80, 470], [230, 430], [330, 452], [470, 350], [590, 380], [720, 250], [850, 270], [1000, 130]]
    line = " ".join(f"{x},{y}" for x, y in pts)
    area = f"M{pts[0][0]},590 L" + " L".join(f"{x},{y}" for x, y in pts) + f" L{pts[-1][0]},590 Z"
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="11" fill="#0d1015" stroke="#7ec8e8" stroke-width="5"/>' for x, y in pts[1:-1:2])
    lx, ly = pts[-1]
    grid = "".join(f'<line x1="60" y1="{y}" x2="1020" y2="{y}" stroke="#7ec8e8" stroke-opacity=".12" stroke-width="2"/>' for y in (130, 230, 330, 430, 530))
    return f"""
 <defs><linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7ec8e8" stop-opacity=".45"/><stop offset="1" stop-color="#7ec8e8" stop-opacity="0"/></linearGradient>
 <linearGradient id="ln" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#8fbfd6"/><stop offset="1" stop-color="#ffffff"/></linearGradient></defs>
 {grid}
 <path d="{area}" fill="url(#ar)"/>
 <polyline points="{line}" fill="none" stroke="url(#ln)" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
 {dots}
 <circle cx="{lx}" cy="{ly}" r="20" fill="#7ec8e8"/><circle cx="{lx}" cy="{ly}" r="34" fill="none" stroke="#7ec8e8" stroke-opacity=".5" stroke-width="4"/>"""


def art_pie(a):
    import math
    cols = ["#dbe6ee", "#8fd3f0", "#4b8fb0", "#2f5f7a", "#b5c1cc"]
    vals = a.get("values") or [30, 25, 20, 15, 10]
    tot = float(sum(vals))
    cx, cy, R = 540, 300, 240
    ang = -math.pi / 2
    out = ['<defs><filter id="sh"><feDropShadow dx="0" dy="14" stdDeviation="14" flood-color="#000" flood-opacity=".5"/></filter></defs><g filter="url(#sh)">']
    for i, v in enumerate(vals):
        a2 = ang + 2 * math.pi * v / tot
        mid = (ang + a2) / 2
        ox, oy = math.cos(mid) * 10, math.sin(mid) * 10
        x1, y1 = cx + ox + R * math.cos(ang), cy + oy + R * math.sin(ang)
        x2, y2 = cx + ox + R * math.cos(a2), cy + oy + R * math.sin(a2)
        large = 1 if (a2 - ang) > math.pi else 0
        out.append(f'<path d="M{cx+ox},{cy+oy} L{x1:.1f},{y1:.1f} A{R},{R} 0 {large} 1 {x2:.1f},{y2:.1f} Z" fill="{cols[i % len(cols)]}" stroke="#0d1015" stroke-width="6"/>')
        ang = a2
    out.append("</g>")
    out.append(f'<circle cx="{cx}" cy="{cy}" r="96" fill="#0d1015"/><circle cx="{cx}" cy="{cy}" r="96" fill="none" stroke="#7ec8e8" stroke-opacity=".5" stroke-width="4"/>')
    out.append(f'<g transform="translate({cx} {cy})">{icon("shield", 1.3, "#7ec8e8")}</g>')
    return "".join(out)


def art_growth(a):
    out = ['<defs><linearGradient id="gc" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f4f8fb"/><stop offset="1" stop-color="#7ec8e8"/></linearGradient></defs>']
    out.append('<path d="M60 520 C 300 500, 560 420, 1000 120" fill="none" stroke="#7ec8e8" stroke-opacity=".35" stroke-width="6" stroke-dasharray="4 16" stroke-linecap="round"/>')
    steps = [(120, 490, 44), (270, 470, 58), (430, 430, 76), (610, 360, 98), (820, 250, 128)]
    for i, (x, y, r) in enumerate(steps):
        out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#gc)" stroke="#fff" stroke-opacity=".6" stroke-width="3"/>')
        out.append(f'<text x="{x}" y="{y + r*0.32:.0f}" text-anchor="middle" font-family="Poppins" font-weight="700" font-size="{int(r*0.95)}" fill="#3b6f8c">$</text>')
    out.append('<g transform="translate(985 110)"><circle r="54" fill="#0d1a24" stroke="#7ec8e8" stroke-width="4"/><path d="M-20 12L-2 -6L10 6L26 -16" fill="none" stroke="#7ec8e8" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/></g>')
    return "".join(out)


def art_doc(a):
    title = plain(a.get("title", "BOND"))
    return f"""
 <defs><linearGradient id="pp" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e6eef4"/><stop offset="1" stop-color="#9dbfd2"/></linearGradient></defs>
 <g transform="translate(520 330) rotate(-6)">
   <rect x="-400" y="-230" width="800" height="520" rx="30" fill="url(#pp)"/>
   <rect x="-370" y="-200" width="740" height="460" rx="18" fill="none" stroke="#3b6f8c" stroke-width="4" stroke-dasharray="2 10" stroke-linecap="round"/>
   <text x="0" y="-100" text-anchor="middle" font-family="Poppins" font-weight="700" font-size="90" fill="#0d1a24" letter-spacing="12">{title}</text>
   <path d="M-260 -40H260M-260 0H260M-260 40H120" stroke="#3b6f8c" stroke-opacity=".6" stroke-width="6" stroke-linecap="round"/>
   <g transform="translate(250 170)"><circle r="70" fill="#0d1a24"/><circle r="56" fill="none" stroke="#7ec8e8" stroke-width="4"/><g transform="scale(.9)" fill="#7ec8e8">{ICONS['shield']}</g></g>
   <text x="-300" y="190" font-family="Poppins" font-weight="600" font-size="34" fill="#0d1a24" letter-spacing="6">EQUIVISION BASICS</text>
 </g>"""


ARTS = {"card": art_card, "coins": art_coins, "tag": art_tag, "chart": art_chart, "pie": art_pie, "growth": art_growth, "doc": art_doc}


# ---------------------------------------------------------------- slide builders
def s_cover(s, ctx):
    art = s.get("art", "coins")
    if isinstance(art, str):
        art = {"kind": art}
    art_svg = ARTS.get(art.get("kind", "coins"), art_coins)(art)
    tag = s.get("tagline", ["Explained in plain English.", "No finance degree needed."])
    l1 = mk(tag[0]) if tag else ""
    l2 = mk(tag[1]) if len(tag) > 1 else ""
    return f"""
<div class="wrap" style="top:250px">
  <div style="display:inline-block;padding:14px 30px;border:2px solid rgba(126,200,232,.6);border-radius:999px;font-size:26px;letter-spacing:.22em;color:var(--ice);font-weight:600">{esc(s.get('kicker', 'TERM OF THE DAY'))}</div>
  <div style="height:300px;display:flex;align-items:center"><h1 class="fit" data-maxw="936" data-min="90" style="font-size:270px;white-space:nowrap;letter-spacing:-.02em;background:linear-gradient(90deg,#ffffff,#8fd3f0);-webkit-background-clip:text;color:transparent;line-height:1.15;padding-bottom:10px">{esc(s['term'])}</h1></div>
  <p style="font-size:44px;line-height:1.35;color:var(--silver);margin-top:0">{l1}<br><span style="color:var(--muted)">{l2}</span></p>
</div>
<svg style="position:absolute;left:0;top:725px" width="1080" height="520" viewBox="0 0 1080 590" preserveAspectRatio="xMidYMin meet">{art_svg}</svg>"""


def s_definition(s, ctx):
    v = s.get("visual", {})
    L, R = v.get("left", {}), v.get("right", {})
    arc = plain(v.get("arcText", "a promise to pay back"))
    mid = plain(v.get("midText", "time passes"))
    return f"""
<div class="wrap">
  <div class="label">{esc(s.get('label', 'IN ONE SENTENCE'))}</div>
  <h1 class="fit" data-maxh="470" data-min="56" style="font-size:88px">{mk(s['headline'])}</h1>
</div>
<div class="panel" style="position:absolute;left:72px;right:72px;top:790px;height:360px">
 <svg width="936" height="360" viewBox="0 0 936 360">
  <defs><marker id="ar" markerUnits="userSpaceOnUse" markerWidth="26" markerHeight="26" refX="20" refY="13" orient="auto"><path d="M0 2L24 13L0 24Z" fill="#7ec8e8"/></marker></defs>
  <path d="M170 140 C 340 40, 600 40, 758 128" stroke="#7ec8e8" stroke-width="5" stroke-dasharray="4 14" stroke-linecap="round" fill="none" marker-end="url(#ar)"/>
  <text class="fs" data-maxw="600" x="468" y="52" text-anchor="middle" font-family="Poppins" font-weight="600" font-size="30" fill="#b5e3f5">{arc}</text>
  <circle cx="130" cy="190" r="62" fill="#0d1015" stroke="#7ec8e8" stroke-width="4"/>
  <circle cx="806" cy="190" r="62" fill="#0d1015" stroke="#7ec8e8" stroke-width="4"/>
  <g transform="translate(130 190)">{icon(L.get('icon', 'gift'), 0.85)}</g>
  <g transform="translate(806 190)">{icon(R.get('icon', 'coins'), 0.85)}</g>
  <text class="fs" data-maxw="232" x="130" y="300" text-anchor="middle" font-family="Poppins" font-weight="700" font-size="34" fill="#fff">{plain(L.get('title', 'TODAY'))}</text>
  <text class="fs" data-maxw="232" x="130" y="336" text-anchor="middle" font-family="Poppins" font-size="26" fill="#8b99a8">{plain(L.get('sub', ''))}</text>
  <text class="fs" data-maxw="232" x="806" y="300" text-anchor="middle" font-family="Poppins" font-weight="700" font-size="34" fill="#fff">{plain(R.get('title', 'LATER'))}</text>
  <text class="fs" data-maxw="232" x="806" y="336" text-anchor="middle" font-family="Poppins" font-size="26" fill="#8b99a8">{plain(R.get('sub', ''))}</text>
  <path d="M250 190H686" stroke="#3a4656" stroke-width="3" stroke-dasharray="2 12" stroke-linecap="round"/>
  <text class="fs" data-maxw="380" x="468" y="205" text-anchor="middle" font-family="Poppins" font-weight="500" font-size="26" fill="#8b99a8">{mid}</text>
 </svg>
</div>
<div class="abs" style="top:1180px;font-size:30px;color:var(--silver);text-align:center">{mk(s.get('footer', "It's all built on [[trust]]."))}</div>"""


def s_steps(s, ctx):
    steps = s["steps"]
    n = len(steps)
    h = 190 if n <= 3 else 142
    gap = 20 if n <= 3 else 18
    total = n * h + (n - 1) * gap
    start = 510 if n == 3 else (510 + (3 * 190 + 40 - total) // 2 if n < 3 else 500)
    cs = 118 if h == 190 else 92
    ts, ss = (40, 27) if h == 190 else (33, 24)
    isz = 80 if h == 190 else 62
    rows = []
    for i, st in enumerate(steps):
        y = start + i * (h + gap)
        rows.append(f"""<div class="panel" style="position:absolute;left:72px;right:72px;top:{y}px;height:{h}px;display:flex;align-items:center;gap:34px;padding:0 36px">
 <div style="width:{cs}px;height:{cs}px;flex:none;border-radius:50%;background:#0d1015;border:3px solid #7ec8e8;display:flex;align-items:center;justify-content:center">
  <svg width="{isz}" height="{isz}" viewBox="-50 -50 100 100">{icon(st.get('icon', 'coins'))}</svg></div>
 <div><div style="font-size:24px;letter-spacing:.2em;color:var(--ice);font-weight:600">STEP {i+1}</div>
 <div style="font-size:{ts}px;font-weight:700;line-height:1.2;margin-top:2px">{mk(st['title'])}</div>
 <div style="font-size:{ss}px;color:var(--muted);margin-top:4px">{mk(st.get('sub', ''))}</div></div></div>""")
    closing = s.get("closing")
    close_html = f'<div class="abs" style="top:1150px;text-align:center;font-size:36px;color:var(--silver)">{mk(closing)}</div>' if closing else ""
    return f"""<div class="wrap">
  <div class="label">{esc(s.get('label', 'EVERYDAY EXAMPLE'))}</div>
  <h1 class="fit" data-maxh="230" data-min="48" style="font-size:68px">{mk(s['headline'])}</h1>
</div>{''.join(rows)}{close_html}"""


def s_compare(s, ctx):
    c = s["chart"]
    bars = c["bars"]
    maxtot = max(b["value"] + b.get("extra", 0) for b in bars)
    scale = 300.0 / maxtot
    base_y = 420
    xs = [110, 546]
    out = []
    for i, b in enumerate(bars[:2]):
        x = xs[i]
        bh = b["value"] * scale
        eh = max(b.get("extra", 0) * scale, 12) if b.get("extra") else 0
        out.append(f'<rect x="{x}" y="{base_y-bh:.1f}" width="280" height="{bh:.1f}" rx="14" fill="#d5dde5"/>')
        if eh:
            top = base_y - bh - eh
            out.append(f'<rect x="{x}" y="{top:.1f}" width="280" height="{eh:.1f}" rx="10" fill="#7ec8e8"/>')
            out.append(f'<text class="fs" data-maxw="300" x="{x+140}" y="{top-14:.1f}" text-anchor="middle" font-family="Poppins" font-weight="700" font-size="36" fill="#7ec8e8">{plain(b.get("extraText", ""))}</text>')
        out.append(f'<text x="{x+140}" y="{base_y-bh/2+22:.1f}" text-anchor="middle" font-family="Poppins" font-weight="700" font-size="60" fill="#0d1015">{plain(b.get("text", ""))}</text>')
        out.append(f'<text class="fs" data-maxw="400" x="{x+140}" y="466" text-anchor="middle" font-family="Poppins" font-weight="500" font-size="27" fill="#b5c1cc">{plain(b.get("label", ""))}</text>')
    return f"""
<div class="wrap">
  <div class="label">{esc(s.get('label', 'THE CATCH'))}</div>
  <h1 class="fit" data-maxh="130" data-min="56" style="font-size:88px">{mk(s['headline'])}</h1>
  <p class="fit" data-maxh="110" data-min="30" style="font-size:38px;line-height:1.4;color:var(--silver);margin-top:22px">{mk(s.get('sub', ''))}</p>
</div>
<div class="panel" style="position:absolute;left:72px;right:72px;top:640px;height:500px">
 <svg width="936" height="500" viewBox="0 0 936 500">
  <line x1="60" y1="420" x2="876" y2="420" stroke="#3a4656" stroke-width="3"/>
  {''.join(out)}
  <path d="M410 250H500" stroke="#7ec8e8" stroke-width="5" stroke-linecap="round"/><path d="M482 232L504 250L482 268" stroke="#7ec8e8" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <text class="fs" data-maxw="800" x="468" y="60" text-anchor="middle" font-family="Poppins" font-weight="600" font-size="30" fill="#b5e3f5">{plain(c.get('title', ''))}</text>
 </svg>
</div>
<div class="abs note" style="top:1170px">{esc(s.get('note', ''))}</div>"""


def s_points(s, ctx):
    g = s.get("gauge")
    rows = s.get("rows", [])
    parts = []
    if g:
        import math
        ang = -90 + 180 * float(g.get("needle", 0.75))
        c_l, c_r = ("#6fd3a0", "#e5766c") if g.get("reverse") else ("#e5766c", "#6fd3a0")
        parts.append(f"""<div class="panel" style="position:absolute;left:72px;right:72px;top:560px;height:350px">
 <svg width="936" height="350" viewBox="0 0 936 350">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{c_l}"/><stop offset=".5" stop-color="#f0c05a"/><stop offset="1" stop-color="{c_r}"/></linearGradient></defs>
  <path d="M238 280 A230 230 0 0 1 698 280" stroke="url(#g)" stroke-width="44" fill="none" stroke-linecap="round"/>
  <g transform="translate(468 280) rotate({ang:.1f})"><path d="M-9 0L0 -190L9 0Z" fill="#fff"/></g>
  <circle cx="468" cy="280" r="26" fill="#0d1015" stroke="#fff" stroke-width="6"/>
  <text x="238" y="332" text-anchor="middle" font-family="Poppins" font-weight="600" font-size="28" fill="{c_l}">{plain(g.get('left', 'Low'))}</text>
  <text x="698" y="332" text-anchor="middle" font-family="Poppins" font-weight="600" font-size="28" fill="{c_r}">{plain(g.get('right', 'Great'))}</text>
 </svg></div>""")
        row_top, row_h, row_gap = 940, 100, 20
    else:
        row_top, row_h, row_gap = 620, 150, 24
    for i, r in enumerate(rows[:3]):
        up = r.get("dir", "up") == "up"
        col, arrow = ("#6fd3a0", "&#8593;") if up else ("#e5766c", "&#8595;")
        if r.get("mark"):
            col, arrow = "#7ec8e8", esc(r["mark"])
        y = row_top + i * (row_h + row_gap)
        fs = 33 if g else 38
        long_mark = bool(r.get("mark")) and len(str(r["mark"])) > 2
        mark_fs = 28 if long_mark else 52
        mark_w = 120 if long_mark else 0
        mark_ls = "letter-spacing:.08em;" if long_mark else ""
        parts.append(f"""<div class="panel" style="position:absolute;left:72px;right:72px;top:{y}px;height:{row_h}px;display:flex;align-items:center;padding:0 40px;gap:26px;font-size:{fs}px;line-height:1.25"><b style="color:{col};font-size:{mark_fs}px;min-width:{mark_w}px;{mark_ls}">{arrow}</b><span>{mk(r['text'])}</span></div>""")
    note_top = 1185 if g else 1180
    return f"""<div class="wrap">
  <div class="label">{esc(s.get('label', 'WHY IT MATTERS'))}</div>
  <h1 class="fit" data-maxh="200" data-min="52" style="font-size:76px">{mk(s['headline'])}</h1>
  <p class="fit" data-maxh="{'50' if g else '110'}" data-min="28" style="font-size:34px;line-height:1.4;color:var(--silver);margin-top:20px">{mk(s.get('sub', ''))}</p>
</div>{''.join(parts)}
<div class="abs note" style="top:{note_top}px">{esc(s.get('note', ''))}</div>"""


def s_recap(s, ctx):
    checks = s.get("checks", [])
    ys = [600, 700, 800]
    rows = "".join(f"""<div class="abs" style="top:{ys[i]}px;display:flex;align-items:center;gap:28px;font-size:36px;line-height:1.25">
 <div style="width:60px;height:60px;flex:none;border-radius:50%;background:#7ec8e8;display:flex;align-items:center;justify-content:center"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#0d1a24" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5l5 5L20 6.5"/></svg></div>
 <span>{mk(c)}</span></div>""" for i, c in enumerate(checks[:3]))
    return f"""<div class="wrap">
  <div class="label">{esc(s.get('label', 'REMEMBER'))}</div>
  <h1 class="fit" data-maxw="936" data-min="60" style="font-size:116px;white-space:nowrap;letter-spacing:-.02em;background:linear-gradient(90deg,#ffffff,#8fd3f0);-webkit-background-clip:text;color:transparent;line-height:1.1">{esc(s['title'])}</h1>
  <p class="fit" data-maxh="110" data-min="30" style="font-size:40px;line-height:1.35;color:var(--silver);margin-top:18px">{mk(s.get('sub', ''))}</p>
</div>{rows}
<div class="panel" style="position:absolute;left:72px;right:72px;top:920px;height:230px;display:flex;align-items:center;gap:36px;padding:0 40px">
  <img src='{ctx['logo']}' style="width:140px;height:140px;border-radius:50%">
  <div><div style="font-size:40px;font-weight:700;line-height:1.2">New term every day</div>
  <div style="font-size:30px;color:var(--ice);font-weight:600;margin-top:6px">Follow {HANDLE}</div>
  <div style="font-size:26px;color:var(--muted);margin-top:4px">Save this post for later</div></div></div>
<div class="abs note" style="top:1180px">Educational content only. Not financial advice.</div>"""


BUILDERS = {"cover": s_cover, "definition": s_definition, "steps": s_steps, "compare": s_compare, "points": s_points, "recap": s_recap}


def build_slide_html(slide, index, total, ctx):
    """ctx: {'logo': data-uri, 'fonts': file:// url of the fonts dir}"""
    kind = slide["type"]
    if kind not in BUILDERS:
        raise ValueError(f"unknown slide type: {kind}")
    body = BUILDERS[kind](slide, ctx)
    if kind == "cover":
        foot_l, foot_r = "", "<span>Swipe &nbsp;&rarr;</span>"
    elif index == total:
        foot_l, foot_r = HANDLE, f"<span><b>{index}</b> / {total}</span>"
    else:
        foot_l, foot_r = HANDLE, f"<span><b>{index}</b> / {total} &nbsp;&rarr;</span>"
    css = CSS.replace("__FONTS__", ctx["fonts"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>
<div class="bg"></div>{RINGS}
<div class="top"><img src="{ctx['logo']}"><span>{BRAND}</span></div>
{body}
<div class="foot"><span>{foot_l}</span>{foot_r}</div>{FIT_JS}</body></html>"""
