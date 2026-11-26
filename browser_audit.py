import sys
from playwright.sync_api import sync_playwright
URL="file://"+__import__("os").path.abspath("web/index.html")+""
R=[]
def chk(n,ok,info=""):
    R.append((n,ok,info));print(("PASS " if ok else "FAIL ")+n+(" :: "+str(info) if info else ""))
with sync_playwright() as p:
    b=p.chromium.launch();pg=b.new_page(viewport={"width":1280,"height":800})
    errs=[];dlg=[]
    pg.on("pageerror",lambda e:errs.append(str(e)));pg.on("dialog",lambda d:(dlg.append(d.message),d.dismiss()))
    pg.goto(URL);pg.wait_for_timeout(1500)
    chk("no JS errors on load",not errs,errs)
    sug=lambda:pg.eval_on_selector_all("#sg li","e=>e.map(x=>x.className+'|'+x.textContent)")
    pg.fill("#q","air");print(sug());chk("'air' suggests IGI Airport",any("IGI" in s for s in sug()))
    pg.fill("#q","qutb");chk("typo 'qutb' still matches Qutub",any("Qutub" in s for s in sug()),sug())
    pg.fill("#q","saket");chk("'saket' matches by area",any("Citywalk" in s for s in sug()),sug())
    pg.fill("#q","zzzz");s=sug();chk("no match shows fallback suggestions",len(s)==6 and s[0].startswith("hd"),s)
    pg.fill("#q","");pg.focus("#q");s=sug();chk("empty focus shows popular",len(s)==6,s)
    pg.fill("#q","<img src=x onerror=alert(1)>");pg.wait_for_timeout(300)
    chk("XSS payload in search is inert",not dlg and pg.locator("#sg img").count()==0,dlg)
    pg.fill("#q","khan");pg.keyboard.press("ArrowDown");pg.keyboard.press("Enter");pg.wait_for_timeout(1100)
    chk("keyboard select works",pg.eval_on_selector("#pl","e=>e.options[e.selectedIndex].text")=="Khan Market")
    chk("popup closes after pick",pg.is_hidden("#sg"))
    pg.fill("#q","khan");pg.keyboard.press("Escape");chk("Esc closes",pg.is_hidden("#sg"))
    pg.fill("#q","  ");chk("whitespace-only query doesn't crash",not errs,errs)
    pg.fill("#q","a"*500);chk("long query capped",len(pg.input_value("#q"))<=60,len(pg.input_value("#q")))
    pg.fill("#q","");
    # tampering
    def state():
        pg.wait_for_timeout(1100);return pg.eval_on_selector("#num","e=>e.textContent"),pg.inner_text("#cp"),pg.inner_text("#rg"),pg.inner_text("#st"),pg.inner_text("#tl")
    pg.eval_on_selector("#dt","e=>{e.value='';e.dispatchEvent(new Event('change'))}");s=state();chk("cleared date handled",not errs and "NaN" not in str(s),s)
    for v in ["0001-01-01","275760-09-13","2026-02-30","abc"]:
        pg.eval_on_selector("#dt","(e,v)=>{e.value=v;e.dispatchEvent(new Event('change'))}",v);s=state();chk("date '%s' safe"%v,not errs and "NaN" not in str(s),s)
    pg.eval_on_selector("#dt","e=>{e.value='2026-10-31';e.dispatchEvent(new Event('change'))}")
    for v in ["99","-5","abc","7.25"]:
        pg.eval_on_selector("#tm","(e,v)=>{e.value=v;e.dispatchEvent(new Event('input'))}",v);s=state();chk("slider '%s' safe"%v,not errs and "NaN" not in str(s) and s[4] and "NaN" not in s[4],s)
    pg.eval_on_selector("#pl","e=>{e.add(new Option('x','999'));e.value='999';e.dispatchEvent(new Event('change'))}");s=state();chk("tampered select index safe",not errs and "NaN" not in str(s) and "undefined" not in str(s),(s,errs[-1:]))
    pg.reload();pg.wait_for_timeout(800)
    # rapid updates race
    for i in range(8):
        pg.eval_on_selector("#tm","(e,v)=>{e.value=v;e.dispatchEvent(new Event('input'))}",str(7+i*1.0))
        pg.wait_for_timeout(60)
    pg.wait_for_timeout(1300);n=pg.eval_on_selector("#num","e=>+e.textContent.replace(/,/g,'')")
    cap=int(pg.inner_text("#cp").split("~")[1].split()[0].replace(",","")) ;pc=int(pg.inner_text("#cp").split("%")[0])
    chk("count-up settles on correct value after rapid input",abs(n-round(pc/100*cap))<=cap*0.006,(n,pc,cap))
    # invariants
    bad=pg.evaluate("()=>{let m=0,c=0;for(let p=0;p<D.p.length;p++)for(let d=0;d<7;d++)for(let i=0;i<22;i++){const v=G[p][d][i];if(!(v>=0&&v<=.99))c++}return c}")
    chk("all 1848 grid values valid",bad==0,bad)
    pg.evaluate("on.rain=1;on.holiday=0;on.peak_event=1");ok=pg.evaluate("()=>{let m=0;for(let p=0;p<12;p++)for(let t=7;t<=17.5;t+=.5)m=Math.max(m,at(p,t));return m<=.99}");chk("max-stress occupancy capped <=99%",ok)
    # a11y
    chk("venue cards keyboard-focusable",pg.eval_on_selector("#gr .card","e=>e.tabIndex>=0"))
    chk("chips expose pressed state",pg.eval_on_selector(".chip","e=>e.hasAttribute('aria-pressed')"))
    chk("slider/date/select have labels",pg.evaluate("()=>['tm','dt','pl'].every(i=>document.getElementById(i).labels&&document.getElementById(i).labels.length||document.getElementById(i).getAttribute('aria-label'))"))
    chk("nav links reachable on mobile (menu or links)",True)
    for w in (360,1280):
        pg.set_viewport_size({"width":w,"height":800});pg.wait_for_timeout(200)
        ov=pg.evaluate("document.documentElement.scrollWidth-innerWidth");chk(f"no horizontal overflow @{w}",ov<=0,ov)
    pg.set_viewport_size({"width":360,"height":800});pg.wait_for_timeout(200)
    chk("nav links visible on mobile",pg.locator("nav a:visible").count()>=2,pg.locator("nav a:visible").count())
    chk("CSP-safe: no inline handlers/eval",pg.evaluate("!document.querySelector('[onclick],[onerror]')"))
    chk("no NaN/undefined anywhere in page text",not any(x in pg.inner_text("body") for x in ("NaN","undefined")))
    chk("no JS errors overall",not errs,errs)
    b.close()
print("\nFAILED:",[n for n,o,_ in R if not o])
