"""Intro/outro scenes + lip-synced drawn avatar for a HyperFrames project.
usage: build_av.py <project dir> <en|es> scenes   -> writes intro/outro, hosts in index.html
       build_av.py <project dir> <en|es> avatar   -> writes compositions/avatar.html from final audio starts
"""
import json, math, random, re, subprocess, sys, pathlib, array

proj, lang, step = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
SCR = pathlib.Path(__file__).parent
FPS = 30

if not (SCR / "lucide/package/icons").is_dir():
    raise SystemExit(f"missing Lucide icons: put lucide-static's package/ folder at {SCR / 'lucide/package'}")
missing = [f"s{n}.wav" for n in range(9) if not (proj / f"assets/voice/s{n}.wav").exists()]
if missing:
    raise SystemExit(f"missing voice takes in assets/voice/: {missing} (regenerate from narration/ with ElevenLabs)")


def lucide(name, color, size, sw=2):
    svg = (SCR / f"lucide/package/icons/{name}.svg").read_text()
    inner = re.search(r"<svg[^>]*>(.*?)</svg>", svg, re.S).group(1)
    inner = re.sub(r"<!--.*?-->", "", inner, flags=re.S).strip()
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{inner}</svg>')


def words(n):
    d = json.loads((proj / f"narration/words/s{n}.json").read_text())
    w = d if isinstance(d, list) else d.get("words", d.get("segments"))
    return [(x.get("text", x.get("word")).strip(), x["start"]) for x in w]


LEAD = 0.4
T = {
    "en": dict(q1="Can an AI agent find the hole in your agent,", q2="before an attacker does?",
               sub="I tried it on my own talk demo.", kicker="A question first",
               title="Let the agent review you.", i1="It found my mistakes", i2="Then it checked my fix",
               link="Code + write-up", thanks="Thanks for watching!", built="Built with",
               k_i1="found", k_i2="then", k_link="the", k_thanks="thanks", k_sub="i"),
    "es": dict(q1="¿Puede un agente de IA encontrar el agujero en tu agente,", q2="antes que un atacante?",
               sub="Lo probé con la demo de mi charla.", kicker="Primero, una pregunta",
               title="Deja que la IA revise tu trabajo.", i1="Encontró mis errores", i2="Después revisó mi arreglo",
               link="Código + informe", thanks="¡Gracias por ver!", built="Hecho con",
               k_i1="encontró", k_i2="después", k_link="el", k_thanks="gracias", k_sub="lo"),
}[lang]

BASE_CSS = """
    #root { position: absolute; inset: 0; background: #0d1220; color: #e6edf3; font-family: "Inter"; overflow: hidden; }
    .bg { position: absolute; inset: 0; background: radial-gradient(1100px 760px at 22% 50%, rgba(240,180,41,.20), transparent 70%), radial-gradient(1000px 760px at 92% 10%, rgba(167,139,250,.20), transparent 70%), #0d1220; }
    .dots { position: absolute; inset: 0; background-image: radial-gradient(rgba(255,255,255,.055) 1.5px, transparent 1.5px); background-size: 36px 36px; }
    .ic { display: inline-block; vertical-align: -0.14em; flex: none; }
    .pill { display: inline-flex; align-items: center; gap: 14px; padding: 12px 24px; border-radius: 999px; background: rgba(240,180,41,.14); border: 1px solid rgba(240,180,41,.45); font: 700 28px "Inter"; letter-spacing: .2em; text-transform: uppercase; color: #f0b429; }
"""


def first_time(ws, key, after=0.0):
    for w, t in ws:
        if t >= after and re.sub(r"[^\wáéíóú]", "", w.lower()) == key:
            return t
    raise KeyError(key)


def intro():
    ws = words(0)
    q1, q2 = T["q1"].split(), T["q2"].split()
    assert len(ws) >= len(q1) + len(q2), (len(ws), q1 + q2)
    spans = "".join(f'<span id="i-w{i}" class="w">{w}</span> ' for i, w in enumerate(q1))
    spans2 = "".join(f'<span id="i-w{i + len(q1)}" class="w">{w}</span> ' for i, w in enumerate(q2))
    times = [round(LEAD + t, 2) for _, t in ws[: len(q1) + len(q2)]]
    sub_t = round(LEAD + first_time(ws, T["k_sub"], ws[len(q1) + len(q2) - 1][1]), 2)
    return f"""<template>
  <style>{BASE_CSS}
    .i-kicker {{ position: absolute; left: 900px; top: 220px; }}
    .i-q {{ position: absolute; left: 900px; top: 320px; width: 880px; font: 800 72px/1.12 "Inter"; letter-spacing: -.02em; }}
    .i-q .acc {{ color: #f0b429; }}
    .i-sub {{ position: absolute; left: 900px; top: 780px; width: 880px; font: 500 36px/1.3 "Inter"; color: #9da7b3; display: flex; align-items: center; gap: 16px; }}
  </style>
  <div id="root" data-composition-id="intro" data-width="1920" data-height="1080">
    <div class="bg"></div><div class="dots"></div>
    <div id="intro-stage" style="position:absolute;inset:0">
      <div id="i-kicker" class="i-kicker pill">{lucide("message-circle-question", "#f0b429", 30)}{T["kicker"]}</div>
      <div id="i-q" class="i-q">{spans}<span class="acc">{spans2}</span></div>
      <div id="i-sub" class="i-sub">{lucide("file-text", "#9da7b3", 34)}{T["sub"]}</div>
    </div>
  </div>
  <script>
    const C = {{ q: {times[0]}, sub: {sub_t} }};
    const W = {json.dumps(times)};
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo("#i-kicker", {{ opacity: 0, y: 12 }}, {{ opacity: 1, y: 0, duration: 0.4 }}, 0);
    W.forEach((t, i) => tl.fromTo("#i-w" + i, {{ opacity: 0, y: 18 }}, {{ opacity: 1, y: 0, duration: 0.25, ease: "power3.out" }}, t - 0.05));
    tl.fromTo("#i-sub", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, C.sub);
    tl.fromTo("#intro-stage", {{ scale: 1 }}, {{ scale: 1.025, transformOrigin: "50% 40%", duration: 8.0, ease: "none" }}, 0); // slow push
    window.__timelines["intro"] = tl;
  </script>
</template>
"""


def outro():
    ws = words(8)
    t = lambda k, a=0.0: round(LEAD + first_time(ws, k, a), 2)
    ti1 = t(T["k_i1"]); ti2 = t(T["k_i2"], ti1 - LEAD); tl_ = t(T["k_link"], ti2 - LEAD); tth = t(T["k_thanks"], tl_ - LEAD)
    aws = lambda k: f'<img class="aws" src="assets/aws/{k}.svg" width="40" height="40" alt="" style="border-radius:6px;flex:none">'
    return f"""<template>
  <style>{BASE_CSS}
    .o-title {{ position: absolute; left: 860px; top: 200px; width: 1000px; font: 900 76px/1.05 "Inter"; letter-spacing: -.03em; background: linear-gradient(90deg, #e6edf3 0%, #f0b429 60%, #3fb950 100%); -webkit-background-clip: text; background-clip: text; color: transparent; }}
    .o-item {{ position: absolute; left: 900px; width: 880px; font: 600 40px "Inter"; display: flex; align-items: center; gap: 18px; }}
    #o-i1 {{ top: 430px; }} #o-i2 {{ top: 510px; }}
    .o-link {{ position: absolute; left: 900px; top: 620px; width: 880px; background: #121821; border: 1px solid #263040; border-radius: 16px; padding: 22px 28px; }}
    .o-link .l {{ font: 600 28px "Inter"; color: #9da7b3; display: flex; align-items: center; gap: 12px; }}
    .o-link .u {{ font: 500 28px "JetBrains Mono"; color: #e6edf3; margin-top: 8px; }}
    .o-built {{ position: absolute; left: 900px; top: 820px; display: flex; align-items: center; gap: 18px; font: 500 28px "Inter"; color: #9da7b3; }}
    .o-thanks {{ position: absolute; left: 900px; top: 900px; font: 800 48px "Inter"; color: #f0b429; display: flex; align-items: center; gap: 16px; }}
  </style>
  <div id="root" data-composition-id="outro" data-width="1920" data-height="1080">
    <div class="bg"></div><div class="dots"></div>
    <div id="outro-stage" style="position:absolute;inset:0">
      <div id="o-title" class="o-title">{T["title"]}</div>
      <div id="o-i1" class="o-item">{lucide("scan-search", "#f0b429", 44)}{T["i1"]}</div>
      <div id="o-i2" class="o-item">{lucide("shield-check", "#3fb950", 44)}{T["i2"]}</div>
      <div id="o-link" class="o-link"><div class="l">{lucide("git-branch", "#9da7b3", 30)}{T["link"]} · branch war-review</div><div class="u">github.com/andrezc98/rompe-tu-agente</div></div>
      <div id="o-built" class="o-built">{T["built"]} {aws("wa")} Agent Toolkit · {aws("bedrock")} Amazon Bedrock · Strands Evals</div>
      <div id="o-thanks" class="o-thanks">{lucide("heart", "#f0b429", 44, 2.4)}{T["thanks"]}</div>
    </div>
  </div>
  <script>
    const C = {{ title: 0.3, i1: {ti1}, i2: {ti2}, link: {tl_}, thanks: {tth} }};
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo("#o-title", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }}, C.title);
    tl.fromTo("#o-i1", {{ opacity: 0, x: -24 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: "power3.out" }}, C.i1);
    tl.fromTo("#o-i2", {{ opacity: 0, x: -24 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: "power3.out" }}, C.i2);
    tl.fromTo(["#o-link", "#o-built"], {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: 0.5, stagger: 0.3, ease: "power3.out" }}, C.link);
    tl.fromTo("#o-thanks", {{ opacity: 0, scale: 0.85 }}, {{ opacity: 1, scale: 1, duration: 0.4, ease: "back.out(2.5)" }}, C.thanks);
    tl.fromTo("#outro-stage", {{ scale: 1 }}, {{ scale: 1.025, transformOrigin: "50% 40%", duration: 12.0, ease: "none" }}, 0); // slow push
    window.__timelines["outro"] = tl;
  </script>
</template>
"""


def scenes():
    (proj / "compositions/intro.html").write_text(intro())
    (proj / "compositions/outro.html").write_text(outro())
    h = (proj / "index.html").read_text()
    host = lambda i: (f'<div id="{i}" data-composition-id="{i}" data-composition-src="compositions/{i}.html" data-start="0" '
                      f'data-duration="1" data-track-index="1" data-track-kind="graphics" data-width="1920" data-height="1080"></div>')
    aud = lambda i, n: f'<audio id="vo-{i}" class="clip" src="assets/voice/s{n}.wav" data-start="0" data-duration="{dur(n)}" data-track-index="2" data-volume="1"></audio>'
    if 'id="intro"' not in h:
        h = h.replace('      <div id="hook"', f'      {host("intro")}\n      <div id="hook"', 1)
        h = h.replace('      <audio id="vo-hook"', f'      {aud("intro", 0)}\n      <audio id="vo-hook"', 1)
    if 'id="outro"' not in h:
        last_div = list(re.finditer(r'      <div id="\w+" data-composition-id="\w+" data-composition-src[^\n]*\n', h))[-1]
        h = h[: last_div.end()] + f"      {host('outro')}\n" + h[last_div.end():]
        h = h.replace("    </div>\n    <script>", f"      {aud('outro', 8)}\n    </div>\n    <script>", 1)
    if 'id="avatar"' not in h:
        h = h.replace("    </div>\n    <script>",
                      '      <div id="avatar" data-composition-id="avatar" data-composition-src="compositions/avatar.html" data-start="0" '
                      'data-duration="1" data-track-index="3" data-track-kind="graphics" data-width="1920" data-height="1080" '
                      'data-layout-allow-overlap style="z-index:10"></div>\n    </div>\n    <script>', 1)
    (proj / "index.html").write_text(h)


def dur(n):
    return round(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                                str(proj / f"assets/voice/s{n}.wav")]).decode()), 2)


def envelope(wav):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"])
    a = array.array("h", raw); hop = 16000 // FPS
    db, zc = [], []
    for i in range(0, len(a) - hop, hop):
        fr = a[i:i + hop]
        rms = math.sqrt(sum(x * x for x in fr) / hop) + 1e-6
        db.append(20 * math.log10(rms / 32768))
        zc.append(sum(1 for j in range(1, hop) if (fr[j] >= 0) != (fr[j - 1] >= 0)) / hop)
    ref = sorted(db)[int(len(db) * 0.95)]
    o, w, prev = [], [], 0.0
    for d, z in zip(db, zc):
        x = max(0.0, min(1.0, (d - (ref - 26)) / 26)) ** 1.2
        x = x if x > 0.08 else 0.0
        prev = max(x, prev * 0.5) * 0.6 + x * 0.4   # quick attack, short release: lips close between syllables
        o.append(round(prev * 99)); w.append(round(max(0.0, min(1.0, (z - 0.04) / 0.2)) * 99))
    return o, w


def avatar():
    h = (proj / "index.html").read_text()
    total = float(re.search(r'data-composition-id="main" data-start="0" data-duration="([\d.]+)"', h).group(1))
    n = int(total * FPS) + 2
    O, Wd = [0] * n, [0] * n
    for src, st in re.findall(r'<audio id="vo-\w+" class="clip" src="(assets/voice/s\d\.wav)" data-start="([\d.]+)"', h):
        o, w = envelope(proj / src); f0 = round(float(st) * FPS)
        for i, (a, b) in enumerate(zip(o, w)):
            if f0 + i < n: O[f0 + i], Wd[f0 + i] = a, b
    intro_end = float(re.search(r'<div id="intro" [^>]*?data-duration="([\d.]+)"', h).group(1))
    outro_st = float(re.search(r'<div id="outro" [^>]*?data-start="([\d.]+)"', h).group(1))
    rnd = random.Random(7); blinks, t = [], 1.2
    while t < total:
        blinks.append(round(t, 2))
        if rnd.random() < 0.18: blinks.append(round(t + 0.32, 2))
        t += rnd.uniform(2.4, 5.0)
    import os
    svg = AVATAR_SVG_MALE if os.environ.get('AVATAR') == 'male' else AVATAR_SVG
    html = f"""<template>
  <style>
    #root {{ position: absolute; inset: 0; overflow: hidden; pointer-events: none; }}
    #av {{ position: absolute; left: 230px; top: 250px; width: 560px; height: 560px; }}
    #av svg {{ width: 100%; height: 100%; overflow: visible; }}
  </style>
  <div id="root" data-composition-id="avatar" data-width="1920" data-height="1080">
    <div id="av">{svg}</div>
  </div>
  <script>
    // mouth open (O) and width (W) per frame, 0-99, from the narration wavs at their timeline starts
    const O = {json.dumps(O, separators=(",", ":"))};
    const WD = {json.dumps(Wd, separators=(",", ":"))};
    const B = {json.dumps(blinks)};
    const FPS = {FPS}, TOTAL = {total};
    const $ = (s) => document.querySelector(s);
    const mouth = $("#av-mouth"), smile = $("#av-smile"), eyes = $("#av-eyes"), head = $("#av-head"), hb = $("#av-hb"), ring = $("#av-ring"), brows = $("#av-brows");
    const avg = (i) => {{ let s = 0; for (let k = -6; k <= 0; k++) s += O[Math.max(0, i + k)] || 0; return s / 7 / 99; }};
    const draw = (t) => {{
      const i = Math.min(O.length - 1, Math.max(0, Math.round(t * FPS)));
      const o = O[i] / 99, w = WD[i] / 99, e = avg(i);
      const rx = 8 + w * 2.5 - o * 1.2, dep = 1 + o * (document.querySelector('#av-teeth') ? 7.5 : 11);   // D-shaped mouth: flat upper lip, rounded lower
      mouth.setAttribute("d", `M${{(100 - rx).toFixed(2)}} 120 Q100 ${{(119 - o).toFixed(2)}} ${{(100 + rx).toFixed(2)}} 120 Q100 ${{(120 + dep).toFixed(2)}} ${{(100 - rx).toFixed(2)}} 120 Z`);
      // teeth fade in only once the mouth is properly open
      const tclip = $("#av-mclip-p"), teeth = $("#av-teeth");
      if (teeth) {{  // one smile-shaped mouth: closed = thin smile line, opening drops the lower lip
        const sx = 10 + w * 1.5 - o * 1.0, top = 122 - o * 3, bot = 124 + o * 8;
        mouth.setAttribute("d", `M${{(100 - sx).toFixed(2)}} 118.6 Q100 ${{top.toFixed(2)}} ${{(100 + sx).toFixed(2)}} 118.6 Q100 ${{bot.toFixed(2)}} ${{(100 - sx).toFixed(2)}} 118.6 Z`);
        smile.setAttribute("opacity", 0);
      }}
      if (teeth) {{ tclip.setAttribute("d", mouth.getAttribute("d")); teeth.setAttribute("height", (1.2 + o * 3).toFixed(2)); teeth.setAttribute("opacity", Math.max(0, Math.min(1, (o - 0.25) / 0.2)).toFixed(2)); }}
      smile.setAttribute("opacity", Math.max(0, 1 - o * 2.2).toFixed(2));
      let s = 1;
      for (const b of B) {{ const d = t - b; if (d >= 0 && d < 0.22) {{ s = 0.1 + 0.9 * Math.min(1, Math.abs(d - 0.1) / 0.1); break; }} }}
      eyes.setAttribute("transform", `translate(0 93) scale(1 ${{s.toFixed(3)}}) translate(0 -93)`);
      const rot = 1.6 * Math.sin(t * 2 * Math.PI / 5.3) + 1.4 * e * Math.sin(t * 2 * Math.PI / 1.9);
      const hy = -2.2 * e + 0.8 * Math.sin(t * 2 * Math.PI / 3.7);
      const tr = `translate(0 ${{hy.toFixed(2)}}) rotate(${{rot.toFixed(2)}} 100 130)`;
      head.setAttribute("transform", tr); hb.setAttribute("transform", tr);
      brows.setAttribute("transform", `translate(0 ${{(-2.4 * Math.max(0, o - 0.55)).toFixed(2)}})`);
      ring.setAttribute("opacity", (0.35 + 0.65 * e).toFixed(2));
    }};
    const tl = gsap.timeline({{ paused: true }});
    const p = {{ t: 0 }};
    tl.fromTo(p, {{ t: 0 }}, {{ t: TOTAL, duration: TOTAL, ease: "none", onUpdate: () => draw(p.t) }}, 0);
    tl.fromTo("#av", {{ scale: 0.92 }}, {{ scale: 1, duration: 0.6, ease: "back.out(2)" }}, 0);
    // big presenter in the intro, corner bubble for the scenes, big again for the close
    const CORNER = {{ x: 1800 - 510, y: 985 - 530, scale: 0.286 }};  // 160px bubble clear of the scene content
    tl.to("#av", {{ x: CORNER.x, y: CORNER.y, scale: CORNER.scale, duration: 0.9, ease: "power3.inOut" }}, {round(intro_end - 0.45, 2)});
    tl.to("#av", {{ x: 0, y: 0, scale: 1, duration: 0.9, ease: "power3.inOut" }}, {round(outro_st - 0.45, 2)});
    window.__timelines["avatar"] = tl;
  </script>
</template>
"""
    (proj / "compositions/avatar.html").write_text(html)
    print("avatar", total, "frames", n, "blinks", len(blinks), "intro_end", intro_end, "outro", outro_st)


# drawn presenter, 200x200 viewBox; ids driven by the timeline: av-head, av-hb, av-eyes, av-brows, av-mouth, av-smile, av-ring
AVATAR_SVG = """<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <clipPath id="av-clip"><circle cx="100" cy="100" r="95"/></clipPath>
    <radialGradient id="av-bg" cx="50%" cy="38%" r="70%"><stop offset="0" stop-color="#34407a"/><stop offset="1" stop-color="#151b33"/></radialGradient>
  </defs>
  <circle cx="100" cy="100" r="99" fill="#0d1220"/>
  <g clip-path="url(#av-clip)">
    <rect width="200" height="200" fill="url(#av-bg)"/>
    <g id="av-hb"><path d="M50 100 C44 52 70 30 100 30 C130 30 156 52 150 100 L156 168 L44 168 Z" fill="#2b1a14"/></g>
    <rect x="89" y="126" width="22" height="28" rx="6" fill="#d39a78"/>
    <path d="M26 205 C30 164 62 148 100 148 C138 148 170 164 174 205 Z" fill="#7c3aed"/>
    <path d="M86 149 L100 166 L114 149 Z" fill="#d39a78"/>
    <path d="M70 152 C76 176 84 190 86 205 M130 152 C124 176 116 190 114 205" stroke="#6526cf" stroke-width="3" fill="none"/>
    <circle cx="134" cy="178" r="6" fill="#f0b429"/>
    <g id="av-head">
      <ellipse cx="63" cy="100" rx="6" ry="9" fill="#e2a885"/><ellipse cx="137" cy="100" rx="6" ry="9" fill="#e2a885"/>
      <ellipse cx="100" cy="96" rx="37" ry="44" fill="#eab38f"/>
      <path d="M61 92 C58 52 84 40 104 41 C128 42 144 60 140 90 C130 72 114 63 97 61 C88 74 74 84 61 92 Z" fill="#3a2419"/>
      <g id="av-brows" stroke="#3a2419" stroke-width="3" fill="none" stroke-linecap="round"><path d="M76 81 Q84 76 92 80"/><path d="M108 80 Q116 76 124 81"/></g>
      <g id="av-eyes"><ellipse cx="84" cy="93" rx="4.8" ry="5.8" fill="#1e1b2e"/><circle cx="85.8" cy="91" r="1.6" fill="#fff"/><ellipse cx="116" cy="93" rx="4.8" ry="5.8" fill="#1e1b2e"/><circle cx="117.8" cy="91" r="1.6" fill="#fff"/></g>
      <path d="M100 99 Q97 108 101.5 110" stroke="#c98a6a" stroke-width="2" fill="none" stroke-linecap="round"/>
      <circle cx="75" cy="109" r="6" fill="#f08a8a" opacity=".35"/><circle cx="125" cy="109" r="6" fill="#f08a8a" opacity=".35"/>
      <path id="av-mouth" d="M91 120 Q100 119 109 120 Q100 121 91 120 Z" fill="#5a1f2b" stroke="#b5485a" stroke-width="1.6" stroke-linejoin="round"/>
      <path id="av-smile" d="M90 119.5 Q100 126 110 119.5" stroke="#b5485a" stroke-width="3" fill="none" stroke-linecap="round"/>
      <path d="M62 98 C56 14 144 14 138 98" stroke="#aab4c3" stroke-width="3.2" fill="none"/>
      <path d="M64 104 Q68 124 86 127" stroke="#aab4c3" stroke-width="2.6" fill="none" stroke-linecap="round"/><circle cx="87" cy="127" r="3.2" fill="#f0b429"/>
    </g>
  </g>
  <circle id="av-ring" cx="100" cy="100" r="97" fill="none" stroke="#f0b429" stroke-width="3"/>
</svg>"""


# male presenter modelled on the speaker's photo: short dark hair, black rectangular glasses, full face, light stubble, white tee with dark shoulder stripes
AVATAR_SVG_MALE = """<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <clipPath id="av-clip"><circle cx="100" cy="100" r="95"/></clipPath>
    <radialGradient id="av-bg" cx="50%" cy="38%" r="70%"><stop offset="0" stop-color="#e3edff"/><stop offset="1" stop-color="#b9cdf3"/></radialGradient>
  </defs>
  <circle cx="100" cy="100" r="99" fill="#ffffff"/>
  <g clip-path="url(#av-clip)">
    <rect width="200" height="200" fill="url(#av-bg)"/>
    <g id="av-hb"><path d="M61 84 C58 50 78 31 100 31 C124 31 143 50 139 84 Z" fill="#1f1a17"/></g>
    <path d="M87 124 L113 124 L115 150 L85 150 Z" fill="#b9825c"/><path d="M87 136 Q100 142 113 136" stroke="#a06f4e" stroke-width="2" fill="none" opacity=".5"/>
    <path d="M2 205 L5 176 C7 160 22 152 52 148 L84 144 L116 144 L148 148 C178 152 193 160 195 176 L198 205 Z" fill="#26324d"/><path d="M38 205 L42 170 M162 205 L158 170" stroke="#1b253b" stroke-width="2.4" fill="none"/><path d="M84 145 L116 145 L108 205 L92 205 Z" fill="#ffffff"/><path d="M84 144 L64 156 L76 164 L66 172 L90 205 L95 205 Z" fill="#1b253b" stroke="#3b4c72" stroke-width="1.4" stroke-linejoin="round"/><path d="M116 144 L136 156 L124 164 L134 172 L110 205 L105 205 Z" fill="#1b253b" stroke="#3b4c72" stroke-width="1.4" stroke-linejoin="round"/><path d="M140 182 L152 180 L150 186 Z" fill="#9a6700"/>
    <path d="M86 146 Q100 156 114 146" fill="none" stroke="#c4ccd6" stroke-width="3"/>
    
    <g id="av-head">
      <ellipse cx="61" cy="100" rx="6.5" ry="9.5" fill="#c48a63"/><ellipse cx="139" cy="100" rx="6.5" ry="9.5" fill="#c48a63"/>
      <path d="M62 94 C62 62 80 48 100 48 C120 48 138 62 138 94 C138 110 134 122 126 131 C118 139 109 142 100 142 C91 142 82 139 74 131 C66 122 62 110 62 94 Z" fill="#cf9a72"/>
      <path d="M72 118 C78 132 88 141 100 141 C112 141 122 132 128 118 C121 127 111 131 100 131 C89 131 79 127 72 118 Z" fill="#8c6650" opacity=".14"/><path d="M66 112 C70 124 76 131 84 136" stroke="#b9825c" stroke-width="2" fill="none" opacity=".5"/><path d="M134 112 C130 124 124 131 116 136" stroke="#b9825c" stroke-width="2" fill="none" opacity=".5"/>
      <path d="M86 113 Q100 109 114 113" stroke="#8c6650" stroke-width="2.4" fill="none" opacity=".18" stroke-linecap="round"/>
      <path d="M61 86 C58 56 74 34 100 33 C126 32 142 54 139 86 C138 74 136 66 133 60 C124 54 108 53 96 54 C82 55 70 62 64 74 C61 80 59 85 58 90 Z" fill="#1f1a17"/>
      <path d="M70 58 C76 36 106 26 130 40 C138 45 140 52 138 58 C130 48 118 44 106 45 C94 46 82 50 70 58 Z" fill="#2b231f"/><path d="M96 46 C104 36 118 33 128 38" stroke="#3a302a" stroke-width="2.4" fill="none" stroke-linecap="round"/>
      <g id="av-brows" stroke="#1f1a17" stroke-width="4.2" fill="none" stroke-linecap="round"><path d="M72 80 Q81 76 91 79"/><path d="M109 79 Q119 76 128 80"/></g>
      <g id="av-eyes"><ellipse cx="82" cy="93" rx="3.6" ry="4" fill="#1e1b2e"/><circle cx="83.2" cy="91.8" r="1.1" fill="#fff"/><ellipse cx="118" cy="93" rx="3.6" ry="4" fill="#1e1b2e"/><circle cx="119.2" cy="91.8" r="1.1" fill="#fff"/></g>
      <g fill="none" stroke-linecap="round" stroke-linejoin="round">
        <path d="M69 88 L62 90 M131 88 L138 90" stroke="#b8bec8" stroke-width="2.4"/>
        <rect x="68" y="84" width="28" height="18" rx="4" stroke="#14161a" stroke-width="3.6"/>
        <rect x="104" y="84" width="28" height="18" rx="4" stroke="#14161a" stroke-width="3.6"/>
        <path d="M96 90 Q100 87 104 90" stroke="#14161a" stroke-width="3"/>
      </g>
      <path d="M100 98 Q95 108 99 111 Q103 112 107 109" stroke="#a8714f" stroke-width="2.2" fill="none" stroke-linecap="round"/>
      <path id="av-mouth" d="M90 120 Q100 119 110 120 Q100 121 90 120 Z" fill="#4a1a22" stroke="#9a4a52" stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round"/>
      <clipPath id="av-mclip"><path id="av-mclip-p" d="M90 120 Q100 119 110 120 Q100 121 90 120 Z"/></clipPath><rect id="av-teeth" x="86" y="117" width="28" height="0" fill="#ffffff" clip-path="url(#av-mclip)"/>
      <path id="av-smile" d="M88 118.5 Q100 127 112 118.5" stroke="#8f3b45" stroke-width="3" fill="none" stroke-linecap="round"/>
      <ellipse cx="60" cy="101" rx="4.5" ry="6.5" fill="#3d444d"/>
      <path d="M62 106 Q66 124 84 128" stroke="#57606a" stroke-width="2.6" fill="none" stroke-linecap="round"/><circle cx="85" cy="128" r="3.2" fill="#9a6700"/>
    </g>
  </g>
  <circle id="av-ring" cx="100" cy="100" r="97" fill="none" stroke="#9a6700" stroke-width="3"/>
</svg>"""

{"scenes": scenes, "avatar": avatar}[step]()
