import html as _html, json, re

THEMES=[("#67ddff","#9f8cff","#071124"),("#ffcc66","#ff8da1","#140a18"),("#72f2a7","#67ddff","#07160f"),("#b99cff","#ff8da1","#100a22")]

def esc(x): return _html.escape(str(x or ""))
def pct(h,p): return int(h*p)
def aspect_size(aspect, res_map, aspect_map, resolution):
    ar_w, ar_h = aspect_map.get(aspect,(9,16)); h=res_map.get(resolution,1080); w=int(h*ar_w/ar_h/2)*2; return w,h

def _chips(items):
    return "".join([f"<span>{esc(i)}</span>" for i in (items or [])[:4]])

def _base_css(w,h):
    return f"""
*{{box-sizing:border-box}}html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;background:#050713;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#fff}}#root{{position:relative;width:{w}px;height:{h}px;overflow:hidden;background:#050713}}.bg{{position:absolute;inset:0;background:radial-gradient(circle at 18% 18%,var(--a),transparent 32%),radial-gradient(circle at 86% 22%,var(--b),transparent 28%),linear-gradient(145deg,var(--c),#050713 68%);filter:saturate(1.18)}}.grid{{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.055) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.055) 1px,transparent 1px);background-size:{pct(h,.055)}px {pct(h,.055)}px;mask-image:radial-gradient(circle at 50% 45%,#000 0%,transparent 78%);opacity:.56}}.brand{{position:absolute;top:{pct(h,.035)}px;left:{pct(h,.04)}px;font-size:{pct(h,.015)}px;letter-spacing:4px;font-weight:950;color:#67ddff}}.scene-no{{position:absolute;top:{pct(h,.035)}px;right:{pct(h,.04)}px;font-size:{pct(h,.013)}px;color:rgba(255,255,255,.62);font-weight:800}}.headline{{position:absolute;left:{pct(h,.052)}px;right:{pct(h,.052)}px;top:{pct(h,.11)}px;font-size:{pct(h,.036)}px;line-height:1.08;font-weight:950;text-shadow:0 3px 24px #000}}.copy{{position:absolute;left:{pct(h,.052)}px;right:{pct(h,.052)}px;bottom:{pct(h,.09)}px;padding:{pct(h,.025)}px;border-radius:{pct(h,.03)}px;background:linear-gradient(135deg,rgba(255,255,255,.16),rgba(255,255,255,.07));border:1px solid rgba(255,255,255,.22);backdrop-filter:blur(16px);font-size:{pct(h,.023)}px;line-height:1.34;font-weight:780;text-shadow:0 2px 14px rgba(0,0,0,.72)}}.chips{{position:absolute;left:{pct(h,.052)}px;right:{pct(h,.052)}px;top:{pct(h,.24)}px;display:flex;gap:{pct(h,.01)}px;flex-wrap:wrap}}.chips span{{padding:{pct(h,.008)}px {pct(h,.014)}px;border-radius:999px;background:rgba(103,221,255,.14);border:1px solid rgba(103,221,255,.35);font-size:{pct(h,.013)}px;font-weight:900;color:#9beeff;text-transform:uppercase;letter-spacing:1px}}.card{{position:absolute;border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.10);backdrop-filter:blur(12px);border-radius:{pct(h,.03)}px;box-shadow:0 {pct(h,.022)}px {pct(h,.06)}px rgba(0,0,0,.35)}}.big-num{{font-size:{pct(h,.08)}px;font-weight:1000;line-height:.95;background:linear-gradient(135deg,var(--a),var(--b));-webkit-background-clip:text;color:transparent}}.muted{{color:rgba(255,255,255,.72)}}.asset-img{{position:absolute;right:{pct(h,.055)}px;top:{pct(h,.25)}px;width:{int(w*.36)}px;height:{pct(h,.28)}px;object-fit:cover;border-radius:{pct(h,.03)}px;border:1px solid rgba(255,255,255,.25);box-shadow:0 {pct(h,.025)}px {pct(h,.07)}px rgba(0,0,0,.45)}}
"""

def _wrap(scene, body, w, h, idx=0, title=""):
    a,b,c=THEMES[idx%len(THEMES)]
    dur=float(scene.get("duration") or 5)
    data=json.dumps({"id":scene.get("id"),"duration":dur,"visual_type":scene.get("visual_type"),"motion_preset":scene.get("motion_preset")},ensure_ascii=False)
    return f"""<!doctype html><html lang='vi'><head><meta charset='UTF-8'/><meta name='viewport' content='width={w},height={h}'/><script src='https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js'></script><style>:root{{--a:{a};--b:{b};--c:{c}}}{_base_css(w,h)}</style></head><body><div id='root' data-composition-id='scene' data-start='0' data-duration='{dur}' data-width='{w}' data-height='{h}' data-scene='{esc(data)}'><div class='bg'></div><div class='grid'></div><div class='brand'>AI WORLD</div><div class='scene-no'>SCENE {int(scene.get('order',idx))+1:02d}</div>{body}</div><script>const tl=gsap.timeline({{paused:true}});tl.from('.brand,.scene-no',{{opacity:0,y:-12,duration:.45}},0);tl.from('.headline',{{opacity:0,y:28,duration:.7,ease:'power3.out'}},.15);tl.from('.chips span',{{opacity:0,y:12,stagger:.08,duration:.35}},.45);tl.from('.card,.copy,.asset-img',{{opacity:0,y:30,scale:.97,duration:.65,ease:'power3.out'}},.55);tl.to('.bg',{{scale:1.08,xPercent:2,duration:{dur},ease:'none'}},0);window.__timelines={{scene:tl}};window.seekTo=function(t){{tl.seek(t)}};tl.play(0);</script></body></html>"""

def render_kinetic_quote(scene, ctx):
    w,h=ctx['w'],ctx['h']; text=esc(scene.get('text')); head=esc(scene.get('headline')); chips=_chips(scene.get('keywords'))
    body=f"<div class='headline'>{head}</div><div class='chips'>{chips}</div><div class='card' style='left:{pct(h,.065)}px;right:{pct(h,.065)}px;top:{pct(h,.34)}px;bottom:{pct(h,.25)}px;display:grid;place-items:center;padding:{pct(h,.035)}px;font-size:{pct(h,.036)}px;font-weight:950;line-height:1.16;text-align:center'><span style='position:absolute;left:{pct(h,.025)}px;top:{pct(h,.005)}px;font-size:{pct(h,.14)}px;color:rgba(255,255,255,.13)'>“</span>{text[:420]}</div>"
    return _wrap(scene,body,w,h,ctx.get('idx',0),ctx.get('title',''))

def render_data_card(scene, ctx):
    w,h=ctx['w'],ctx['h']; nums=scene.get('numbers') or ['01']; kws=scene.get('keywords') or []; head=esc(scene.get('headline'))
    cards=[]
    for i,n in enumerate(nums[:3]):
        label=esc(kws[i] if i < len(kws) else 'số liệu chính')
        cards.append(f"<div class='card' style='position:relative;padding:{pct(h,.025)}px;min-height:{pct(h,.13)}px'><div class='big-num'>{esc(n)}</div><div class='muted' style='font-size:{pct(h,.017)}px;font-weight:850'>{label}</div></div>")
    body=f"<div class='headline'>{head}</div><div style='position:absolute;left:{pct(h,.06)}px;right:{pct(h,.06)}px;top:{pct(h,.28)}px;display:grid;grid-template-columns:repeat(1,1fr);gap:{pct(h,.018)}px'>{''.join(cards)}</div><div class='copy'>{esc(scene.get('text'))[:360]}</div>"
    return _wrap(scene,body,w,h,ctx.get('idx',0),ctx.get('title',''))

def render_process_flow(scene, ctx):
    w,h=ctx['w'],ctx['h']; text=scene.get('text') or ''; parts=[p.strip() for p in re.split(r'(?:;|→|->|\.\s+)', text) if p.strip()][:4] or [text[:80]]
    blocks=[]
    for i,p in enumerate(parts):
        blocks.append(f"<div class='card' style='position:relative;padding:{pct(h,.02)}px;font-size:{pct(h,.018)}px;font-weight:850;min-height:{pct(h,.105)}px'><b style='color:#67ddff'>0{i+1}</b><br>{esc(p)[:96]}</div>")
        if i < len(parts)-1:
            blocks.append(f"<div style='height:{pct(h,.035)}px;text-align:center;color:#67ddff;font-size:{pct(h,.028)}px'>↓</div>")
    body=f"<div class='headline'>{esc(scene.get('headline'))}</div><div style='position:absolute;left:{pct(h,.07)}px;right:{pct(h,.07)}px;top:{pct(h,.27)}px'>{''.join(blocks)}</div>"
    return _wrap(scene,body,w,h,ctx.get('idx',0),ctx.get('title',''))

def render_takeaway(scene, ctx):
    w,h=ctx['w'],ctx['h']; kws=scene.get('keywords') or []
    bullets=''.join([f"<li>{esc(k).title()}</li>" for k in kws[:4]])
    body=f"<div class='headline'>Kết luận: {esc(scene.get('headline'))}</div><div class='card' style='left:{pct(h,.07)}px;right:{pct(h,.07)}px;top:{pct(h,.31)}px;padding:{pct(h,.035)}px'><div style='font-size:{pct(h,.025)}px;font-weight:950;margin-bottom:{pct(h,.02)}px;color:#9beeff'>Bài học rút ra</div><ul style='font-size:{pct(h,.022)}px;line-height:1.55;font-weight:850;margin-left:{pct(h,.025)}px'>{bullets}</ul></div><div class='copy'>{esc(scene.get('text'))[:340]}</div>"
    return _wrap(scene,body,w,h,ctx.get('idx',0),ctx.get('title',''))

def render_image_card(scene, ctx):
    w,h=ctx['w'],ctx['h']; img=scene.get('image') or (scene.get('assets') or {}).get('article_image')
    img_tag=f"<img class='asset-img' src='{esc(img)}'>" if img else ""
    body=f"<div class='headline'>{esc(scene.get('headline'))}</div>{img_tag}<div class='chips'>{_chips(scene.get('keywords'))}</div><div class='copy' style='right:{int(w*.43)}px'>{esc(scene.get('text'))[:340]}</div>"
    return _wrap(scene,body,w,h,ctx.get('idx',0),ctx.get('title',''))

RENDERERS={"kinetic_quote":render_kinetic_quote,"data_card":render_data_card,"process_flow":render_process_flow,"takeaway":render_takeaway,"image_card":render_image_card}

def render_scene_html(scene, aspect='doc', title='', aspect_map=None, res_map=None, resolution='hd', idx=0):
    aspect_map=aspect_map or {'doc':(9,16)}; res_map=res_map or {'hd':720,'fhd':1080}
    w,h=aspect_size(aspect,res_map,aspect_map,resolution)
    ctx={'w':w,'h':h,'idx':idx,'title':title}
    r=RENDERERS.get(scene.get('visual_type') or 'kinetic_quote', render_kinetic_quote)
    return r(scene,ctx)
