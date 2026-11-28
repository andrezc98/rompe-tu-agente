"""Dark -> light theme for every scene composition (not the avatar). Single pass, so mapped colors are never re-mapped."""
import re, sys, pathlib
MAP = {"#0b0f14": "#ffffff", "#0d1220": "#f6f8fb", "#05080c": "#f6f8fa", "#121821": "#ffffff", "#1d2633": "#eaeef2",
       "#263040": "#d0d7de", "#2f3b4d": "#c4ccd6", "#3a4352": "#afb8c1", "#2a1c1f": "#fff1f1", "#5a2d33": "#f3b7bd",
       "#5c4a1c": "#e9c977", "#e6edf3": "#1f2328", "#c9d1d9": "#32383f", "#9da7b3": "#57606a", "#7d8590": "#6e7781",
       "#f0b429": "#9a6700", "#3fb950": "#1a7f37", "#ff6b6b": "#cf222e", "#ff9b9b": "#a40e26", "#a78bfa": "#8250df",
       "#c4b5fd": "#6639ba", "#22d3ee": "#0e7490", "#67e8f9": "#0e7490", "rgba(255,255,255,.055)": "rgba(31,35,40,.08)"}
pat = re.compile("|".join(re.escape(k) for k in MAP), re.I)
for f in sorted(pathlib.Path(sys.argv[1], "compositions").glob("*.html")):
    if f.stem == "avatar": continue
    c = f.read_text(); c2 = pat.sub(lambda m: MAP[m.group(0).lower()], c)
    f.write_text(c2); print(f.stem, len(pat.findall(c)))
