import sys, math, subprocess, random
sys.path.insert(0, __file__.rsplit('/',1)[0])
from PIL import Image, ImageDraw, ImageFilter
from gen2 import Cv, F, FB, FM, ease, S, W, H, FPS, ball as ball_
from funny import kid, banner, endcard
P="/tmp/claude-0/x1/pages/"
DUR=18.0

def rr(d,box,r,fill): d.rounded_rectangle(box,r,fill=fill)
def cover(img,w,h):
    img=img.convert("RGB"); s=max(w/img.width,h/img.height)
    img=img.resize((int(img.width*s)+1,int(img.height*s)+1),Image.LANCZOS)
    x=(img.width-w)//2; y=(img.height-h)//2; return img.crop((x,y,x+w,y+h))
def fnt(p,s): return F(p,s)

def page():
    im=Image.new("RGB",(W,H),(15,15,15)); d=ImageDraw.Draw(im)
    # top bar
    d.text((60,120),"<",font=fnt(FB,60),fill=(240,240,240))
    d.text((150,128),"DASHX Cricket Tennis Ball",font=fnt(FB,34),fill=(240,240,240))
    # banner
    bx0,by0,bx1,by1=40,230,1040,560
    ban=Image.new("RGB",(bx1-bx0,by1-by0)); bd=ImageDraw.Draw(ban)
    for y in range(ban.height):
        k=y/ban.height; bd.line([(0,y),(ban.width,y)],fill=(int(20+30*k),int(20+10*k),int(40+20*k)))
    pk=Image.open(P+"gallery-11.jpg").convert("RGB"); pk.thumbnail((260,300)); ban.paste(pk,(ban.width-pk.width-40,(ban.height-pk.height)//2))
    ps=cover(Image.open(P+"pack-studio.jpg"),300,300); ban.paste(ps,(ban.width-pk.width-360,15))
    bd.text((40,45),"DASHX",font=fnt(FB,100),fill=(255,210,50))
    bd.text((46,200),"Cricket Tennis Ball",font=fnt(FB,32),fill=(255,255,255))
    m=Image.new("L",ban.size,0); ImageDraw.Draw(m).rounded_rectangle([0,0,ban.width-1,ban.height-1],30,fill=255)
    im.paste(ban,(bx0,by0),m)
    # profile pic
    lg=cover(Image.open(P+"dashx-logo.jpg"),230,230); m=Image.new("L",(230,230),0); ImageDraw.Draw(m).ellipse([0,0,229,229],fill=255)
    im.paste(lg,(60,610),m)
    d.text((320,630),"DASHX Cricket Tennis Ball",font=fnt(FB,36),fill=(255,255,255))
    d.text((320,690),"by Nav Durga Sports",font=fnt(FM,30),fill=(170,170,170))
    rr(d,(320,755,640,835),40,(245,245,245)); d.text((480,795),"Subscribe",font=fnt(FB,32),fill=(15,15,15),anchor="mm")
    # tabs
    for i,tb in enumerate(["Home","Videos","Shorts","Playlists"]):
        d.text((60+i*240,890),tb,font=fnt(FB if i==2 else FM,32),fill=(255,255,255) if i==2 else (160,160,160))
    d.line([(540,945),(700,945)],fill=(255,255,255),width=5); d.line([(0,950),(W,950)],fill=(50,50,50),width=2)
    # shorts grid
    th=["/tmp/tts/f5_7.jpg","/tmp/tts/f4_9.0.jpg","/tmp/tts/f3_10.5.jpg"]
    for i,f in enumerate(th):
        try: t=cover(Image.open(f),320,560)
        except Exception: t=Image.new("RGB",(320,560),(60,60,60))
        m=Image.new("L",t.size,0); ImageDraw.Draw(m).rounded_rectangle([0,0,319,559],18,fill=255)
        im.paste(t,(30+i*345,990),m)
    for i,tt in enumerate(["Meerut Boys Entry","Ball Kho Gayi!","Last Ball 6 Run"]):
        d.text((40+i*345,1570),tt,font=fnt(FB,24),fill=(240,240,240))
    return im

def dust_layer():
    random.seed(7)
    im=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(im)
    d.rectangle([0,180,W,1640],fill=(120,105,85,225))
    for _ in range(2600):
        x=random.randint(0,W); y=random.randint(180,1640); r=random.randint(2,9); g=random.randint(70,150)
        d.ellipse([x-r,y-r,x+r,y+r],fill=(g,g-10,g-25,random.randint(120,230)))
    for (cx,cy) in ((40,200),(1040,200),(1040,1600)):  # cobwebs
        for a in range(0,90,15):
            ang=math.radians(a+ (0 if cx<500 else 90) + (0 if cy<500 else 180))
            d.line([(cx,cy),(cx+math.cos(ang)*260,cy+math.sin(ang)*260)],fill=(230,230,230,200),width=3)
        for rad in (70,140,210): d.arc([cx-rad,cy-rad,cx+rad,cy+rad],0,360,fill=(230,230,230,160),width=2)
    return im.filter(ImageFilter.GaussianBlur(1.2))

def path_at(t):
    # cloth position over time, returns (x,y) or None
    if t<2.6: return None
    if t<5.6:  # banner zigzag
        u=(t-2.6)/3.0; row=int(u*3); f=(u*3)%1; f=f if row%2==0 else 1-f
        return (90+f*900,290+row*110)
    if t<7.0:  # profile + name
        u=(t-5.6)/1.4; a=u*2*math.pi*1.5
        return (420+math.cos(a)*330,740+math.sin(a)*110)
    if t<10.6:  # shorts grid zigzag
        u=(t-7.0)/3.6; row=int(u*4); f=(u*4)%1; f=f if row%2==0 else 1-f
        return (90+f*900,1020+row*160)
    return None

def main(out):
    pg=page().resize((int(W*S),int(H*S)),Image.LANCZOS).convert("RGBA")
    dust=dust_layer().resize(pg.size,Image.LANCZOS)
    mask=Image.new("L",pg.size,255); md=ImageDraw.Draw(mask)
    tmp=out+".silent.mp4"
    p=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","image2pipe","-framerate",str(FPS),"-i","-","-c:v","libx264","-pix_fmt","yuv420p","-crf","19","-t",str(DUR),tmp],stdin=subprocess.PIPE)
    prev=None; spark=[]
    for n in range(int(FPS*DUR)):
        t=n/FPS
        q=path_at(t)
        if q:
            pts=[q] if prev is None else [(prev[0]+(q[0]-prev[0])*k/6,prev[1]+(q[1]-prev[1])*k/6) for k in range(7)]
            for (x,y) in pts: md.ellipse([(x-120)*S,(y-95)*S,(x+120)*S,(y+95)*S],fill=0)
            if n%2==0: spark.append((q[0]+random.uniform(-80,80),q[1]+random.uniform(-60,60),t))
        prev=q
        if 10.6<=t<10.7: md.rectangle([0,0,pg.size[0],pg.size[1]],fill=0)
        im=pg.copy()
        dl=dust.copy(); a=dl.getchannel("A"); a=Image.composite(a,Image.new("L",a.size,0),mask); dl.putalpha(a)
        im.alpha_composite(dl); c=Cv(im)
        # sparkles
        for (sx,sy,st) in spark:
            u=t-st
            if 0<=u<0.8:
                s=(1-u/0.8)*26
                c.poly([(sx,sy-s),(sx+s*0.25,sy-s*0.25),(sx+s,sy),(sx+s*0.25,sy+s*0.25),(sx,sy+s),(sx-s*0.25,sy+s*0.25),(sx-s,sy),(sx-s*0.25,sy-s*0.25)],(255,240,150))
        # big final shine
        if 10.6<=t<12.6:
            u=t-10.6
            for i in range(10):
                sx=100+i*95; sy=300+((i*373)%1200); s=24+18*abs(math.sin(u*6+i))
                c.poly([(sx,sy-s),(sx+s*0.25,sy-s*0.25),(sx+s,sy),(sx+s*0.25,sy+s*0.25),(sx,sy+s),(sx-s*0.25,sy+s*0.25),(sx-s,sy),(sx-s*0.25,sy-s*0.25)],(255,240,150))
            c.rect(140,1660,940,1790,(0,0,0,170),40); c.text(540,1680,"CHAMAK GAYA!",F(FB,80),(255,210,50),min(1,u/0.3))
        # kid with stretchy arm
        kx,kgy=880,1915
        if q or t<2.6 or t>=10.6:
            cx,cy=(q if q else ((700,1500) if t<2.6 else (760,1480)))
            hands,_=kid(c,kx,kgy,(220,50,60),"happy" if t<10.6 else "laugh",0.35,-0.35,k=1.25,t=t,skin=1)
            shx,shy=kx+26*1.25,kgy-195*1.25+5
            c.line([(shx,shy),(cx,cy)],(232,185,140),22); c.line([(shx,shy),(shx+(cx-shx)*0.18,shy+(cy-shy)*0.18)],(220,50,60),30)
            wob=math.sin(t*30)*8
            c.rect(cx-70+wob,cy-50,cx+70+wob,cy+50,(250,250,250),18); c.rect(cx-70+wob,cy-50,cx+70+wob,cy-30,(80,160,240),10)
            c.ell(cx,cy,20,fill=(232,185,140))
        banner(c,t,0.2,2.6,"DIWALI KI SAFAI",74)
        # diyas at bottom
        for i,dx in enumerate((90,250,410)):
            fl=8*math.sin(t*12+i)
            c.ell(dx,1880,60,22,fill=(190,90,30)); c.poly([(dx,1830-26+fl),(dx+14,1860),(dx-14,1860)],(255,190,60))
        endcard(c,im,t,12.6,"Flipkart aur Amazon par!","Link description me.")
        im.convert("RGB").resize((W,H),Image.LANCZOS).save(p.stdin,"JPEG",quality=92)
    p.stdin.close(); p.wait()
    a=out+".m4a"
    fc=f"anoisesrc=c=pink:r=44100:a=0.04:d={DUR},lowpass=f=900,afade=t=out:st={DUR-0.6}:d=0.6"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-filter_complex",fc,"-t",str(DUR),"-c:a","aac","-b:a","128k",a],check=True)
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",tmp,"-i",a,"-c:v","copy","-c:a","copy","-shortest",out],check=True)
if __name__=="__main__": main(sys.argv[1])
