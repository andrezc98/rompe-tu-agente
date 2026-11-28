import os, re, sys, pathlib
LEAD, TAIL, END_TAIL = 0.4, 0.2, 1.6   # voice starts 0.4s into a scene; 0.6s breath between scenes
EXTRA = {"flagged": 0.6, "intro": 0.5, **({"attack": 0.4} if os.environ.get("EXTRA_ATTACK") else {})}  # beats after the punchline and the opening question
proj = pathlib.Path(sys.argv[1]); idx = proj / "index.html"; h = idx.read_text()
scenes = [s for s in re.findall(r'<div id="(\w+)" data-composition-id="\w+" data-composition-src', h) if s != 'avatar']
voice = {m[0]: float(m[1]) for m in re.findall(r'<audio id="vo-(\w+)"[^>]*data-duration="([\d.]+)"', h)}
t = 0.0
for i, s in enumerate(scenes):
    d = round(LEAD + voice[s] + (END_TAIL if i == len(scenes) - 1 else TAIL) + EXTRA.get(s, 0), 2)
    h = re.sub(rf'(<div id="{s}" [^>]*?data-start=")[\d.]+(" data-duration=")[\d.]+', rf'\g<1>{round(t,2)}\g<2>{d}', h)
    h = re.sub(rf'(<audio id="vo-{s}"[^>]*?data-start=")[\d.]+', rf'\g<1>{round(t+LEAD,2)}', h)
    comp = proj / f"compositions/{s}.html"; c = comp.read_text()
    c = re.sub(rf'(#{s}-stage", \{{ scale: 1 \}}, \{{ scale: 1.025, transformOrigin: "50% 40%", duration: )[\d.]+', rf'\g<1>{d}', c)
    cues = [float(x) for x in re.findall(r':\s*([\d.]+)', re.search(r'const C = \{([^}]*)\}', c).group(1))]
    if max(cues) + 0.6 >= d:
        raise SystemExit(f"{s}: last cue {max(cues)} s is too close to the scene end {d} s")
    comp.write_text(c); print(s, round(t, 2), d); t += d
h = re.sub(r'(<div id="avatar" [^>]*?data-duration=")[\d.]+', rf'\g<1>{round(t,2)}', h)
h = re.sub(r'(data-composition-id="main" data-start="0" data-duration=")[\d.]+', rf'\g<1>{round(t,2)}', h)
idx.write_text(h); print("total", round(t, 2))
