import sys, math, subprocess, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H,FPS,DUR,S=1080,1920,24,12,1.5
FB="/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FL="/usr/share/fonts/truetype/google-fonts/Poppins-Light.ttf"
FM="/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf"
_fc={}
def F(p,s):
    k=(p,int(s*S))
    if k not in _fc: _fc[k]=ImageFont.truetype(p,int(s*S))
    return _fc[k]
# sky_top, sky_bottom, grass, accent, jersey, night?
PAL=[((6,10,38),(54,34,110),(22,86,44),(255,200,40),(255,196,30),True),
     ((250,110,60),(255,206,130),(54,126,52),(255,255,255),(30,90,200),False),
     ((18,70,140),(130,200,245),(48,140,62),(255,226,60),(220,40,50),False),
     ((70,22,92),(236,104,124),(38,104,62),(255,240,150),(40,170,220),False),
     ((8,44,66),(44,128,150),(28,112,74),(255,160,60),(240,240,240),True)]
FACTS=[("Rubber core","+ felt cover"),("6.5 cm","ball diameter"),("90 g or 110 g","pick your weight"),
       ("Packs of 3, 6, 10, 12","pick your size"),("UPI or cash","on delivery"),("Made in Meerut","Uttar Pradesh")]
HOOK=["GULLY CRICKET TIME","ONE BALL. ONE SHOT.","READY TO PLAY?","SIX OR BOWLED?","LET'S PLAY","TENNIS BALL CRICKET"]
def lerp(a,b,t): return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))
def ease(x): x=max(0,min(1,x)); return x*x*(3-2*x)
def sc(v): return v*S
class Cv:
    def __init__(s,im): s.im=im; s.d=ImageDraw.Draw(im,"RGBA")
    def line(s,p,fill,w):
        (x1,y1),(x2,y2)=p; s.d.line([sc(x1),sc(y1),sc(x2),sc(y2)],fill=fill,width=int(sc(w)))
        r=sc(w)/2
        for x,y in p: s.d.ellipse([sc(x)-r,sc(y)-r,sc(x)+r,sc(y)+r],fill=fill)
    def _alpha(s,x0,y0,x1,y1,fn,fill):
        X0,Y0,X1,Y1=int(max(0,sc(x0)-2)),int(max(0,sc(y0)-2)),int(min(s.im.size[0],sc(x1)+2)),int(min(s.im.size[1],sc(y1)+2))
        if X1<=X0 or Y1<=Y0: return
        lay=Image.new("RGBA",(X1-X0,Y1-Y0),(0,0,0,0)); fn(ImageDraw.Draw(lay),X0,Y0,fill); s.im.alpha_composite(lay,(X0,Y0))
    def ell(s,cx,cy,rx,ry=None,fill=None,outline=None,w=0):
        ry=ry or rx
        if fill is not None and len(fill)==4 and fill[3]<255 and outline is None:
            if fill[3]<=0: return
            s._alpha(cx-rx,cy-ry,cx+rx,cy+ry,lambda d,X0,Y0,f:d.ellipse([sc(cx-rx)-X0,sc(cy-ry)-Y0,sc(cx+rx)-X0,sc(cy+ry)-Y0],fill=f),fill); return
        s.d.ellipse([sc(cx-rx),sc(cy-ry),sc(cx+rx),sc(cy+ry)],fill=fill,outline=outline,width=int(sc(w)))
    def poly(s,pts,fill): s.d.polygon([(sc(x),sc(y)) for x,y in pts],fill=fill)
    def rect(s,x1,y1,x2,y2,fill,r=0):
        if len(fill)==4 and fill[3]<255:
            if fill[3]<=0: return
            s._alpha(x1,y1,x2,y2,lambda d,X0,Y0,f:d.rounded_rectangle([sc(x1)-X0,sc(y1)-Y0,sc(x2)-X0,sc(y2)-Y0],radius=sc(r),fill=f),fill); return
        if r: s.d.rounded_rectangle([sc(x1),sc(y1),sc(x2),sc(y2)],radius=sc(r),fill=fill)
        else: s.d.rectangle([sc(x1),sc(y1),sc(x2),sc(y2)],fill=fill)
    def text(s,cx,y,t,font,fill,a=1.0):
        if a<=0.01: return
        w=s.d.textlength(t,font=font)/S
        lay=Image.new("RGBA",s.im.size,(0,0,0,0)); ld=ImageDraw.Draw(lay)
        ld.text((sc(cx-w/2),sc(y)),t,font=font,fill=tuple(fill)+(int(255*a),))
        s.im.alpha_composite(lay)
def bg_static(pal,seed):
    top,bot,gr,acc,jer,night=pal; rnd=random.Random(seed)
    im=Image.new("RGBA",(int(W*S),int(H*S))); c=Cv(im)
    for y in range(0,int(H*0.62),6):
        c.rect(0,y/S,W,y/S+6/S+1,lerp(top,bot,y/(H*0.62)))
    if night:
        for _ in range(90): c.ell(rnd.randint(0,W),rnd.randint(0,600),rnd.choice((1.2,1.8,2.5)),fill=(255,255,255,200))
        c.ell(900,370,46,fill=(250,248,225,255)); c.ell(918,360,41,fill=lerp(top,(40,40,90),0.5)+(255,))
    else:
        c.ell(860,370,62,fill=(255,250,210,255))
    # floodlights glow
    glow=Image.new("RGBA",im.size,(0,0,0,0)); gd=ImageDraw.Draw(glow)
    for x in (110,970):
        for r,a in ((240,40),(160,70),(90,120)): gd.ellipse([sc(x-r),sc(430-r),sc(x+r),sc(430+r)],fill=(255,250,220,a))
    glow=glow.filter(ImageFilter.GaussianBlur(sc(28))); im.alpha_composite(glow); c=Cv(im)
    for x in (110,970):
        c.rect(x-6,430,x+6,900,(60,60,70)); c.rect(x-48,400,x+48,452,(70,70,82),6)
        for i in range(-3,4): c.ell(x+i*13,426,5,fill=(255,255,235))
    # stadium wall + crowd
    c.rect(0,760,W,900,lerp(top,(0,0,0),0.55))
    cols=[(220,60,60),(240,200,60),(70,150,230),(240,240,240),(90,200,120),(230,120,40)]
    for row in range(4):
        for i in range(0,W,24):
            x=i+(row%2)*12+rnd.randint(-3,3); y=775+row*30
            cc=rnd.choice(cols); c.ell(x,y,9,fill=lerp(cc,(0,0,0),0.35+0.1*row)); c.rect(x-9,y+6,x+9,y+28,lerp(cc,(0,0,0),0.45+0.1*row),4)
    # grass with mowing stripes
    for i,x in enumerate(range(0,W,90)):
        c.rect(x,900,x+90,H,lerp(gr,(255,255,255),0.06) if i%2 else gr)
    c.rect(0,900,W,912,lerp(gr,(255,255,255),0.25))
    # boundary rope
    c.rect(0,896,W,904,(250,250,250))
    # pitch strip
    c.poly([(60,1190),(1020,1190),(1060,1290),(20,1290)],(196,170,120))
    c.poly([(60,1190),(1020,1190),(1030,1200),(50,1200)],(214,190,140))
    return im
def ball(c,x,y,rot,r=26):
    c.ell(x,y,r,fill=(222,44,44),outline=(255,255,255),w=2)
    a=rot
    for s_ in (-1,1):
        pts=[]
        for k in range(-5,6):
            u=k/5*0.9
            px=x+s_*r*0.62*math.cos(u*1.2)*math.cos(a)- r*0.0
            py=y+r*0.9*u
            pts.append((x+(s_*r*0.55*math.cos(u*1.3))*math.cos(a)+r*0.25*math.sin(a)*u, py))
        c.d.line([(sc(px),sc(py)) for px,py in pts],fill=(255,255,255,255),width=int(sc(2.5)))
def person(c,bx,gy,jer,skin=(245,205,165),helmet=True,pose=0.0,stance=1.0):
    leg=(235,235,240)
    c.line([(bx-10,gy-130),(bx-26*stance-pose*6,gy)],leg,18); c.line([(bx+10,gy-130),(bx+30*stance+pose*6,gy)],leg,18)
    c.rect(bx-26*stance-pose*6-14,gy-6,bx-26*stance-pose*6+14,gy+6,(40,40,40),3)
    c.rect(bx+30*stance+pose*6-14,gy-6,bx+30*stance+pose*6+14,gy+6,(40,40,40),3)
    c.line([(bx,gy-130),(bx,gy-235)],jer,50)
    c.ell(bx,gy-268,26,fill=skin)
    if helmet:
        c.d.pieslice([sc(bx-30),sc(gy-300),sc(bx+30),sc(gy-246)],180,360,fill=(30,60,140,255))
        c.line([(bx+26,gy-268),(bx+30,gy-246)],(180,190,200),4)
def draw(t,day,event,pal,hook,fact,bgi,parts,crowd_seed):
    top,bot,gr,acc,jer,night=pal
    im=bgi.copy(); c=Cv(im)
    GY=1230
    # crowd jump on six
    if event=="six" and 5.3<t<8:
        j=abs(math.sin((t-5.3)*9))*14*(1-ease((t-7)/1.0))
        c.rect(0,880-j,W,900,lerp(top,(0,0,0),0.55))
    # stumps
    ST=250
    fall=ease((t-5.45)/0.5) if event=="bowled" else 0
    if fall==0:
        for dx in (-26,0,26): c.line([(ST+dx,GY),(ST+dx,GY-165)],(244,226,180),12)
        c.line([(ST-20,GY-170),(ST-4,GY-170)],(255,255,255),7); c.line([(ST+4,GY-170),(ST+20,GY-170)],(255,255,255),7)
    else:
        for i,dx in enumerate((-26,0,26)):
            ang=fall*(0.5+0.35*i)*(1 if i!=1 else -1.3)
            x0=ST+dx+fall*(30+20*i); y0=GY-fall*10
            c.line([(x0,y0),(x0+math.sin(ang)*165,y0-math.cos(ang)*165)],(244,226,180),12)
        c.line([(ST-20+fall*140,GY-170-fall*120+fall*fall*200),(ST-4+fall*140,GY-170-fall*120+fall*fall*200)],(255,255,255),7)
    # keeper
    person(c,130,GY,(235,235,240),helmet=False,stance=0.7)
    # batter
    bx=410
    person(c,bx,GY,jer,helmet=True,pose=0.0,stance=1.0)
    c.line([(bx-10,GY-215),(bx+8,GY-185)],jer,22)
    start=4.5 if event=="six" else 4.95
    sw=ease((t-start)/0.55); ang=math.radians(-70+170*sw) if t<start+0.7 else math.radians(100+10*ease((t-start-0.7)/0.4))
    px,py=bx+8,GY-185; L=215
    tipx,tipy=px+math.sin(ang)*L,py+math.cos(ang)*L
    c.line([(px,py),(tipx,tipy)],(214,168,96),24); c.line([(px,py),(px-math.sin(ang)*30,py-math.cos(ang)*30)],(60,60,60),12)
    c.ell(px,py,14,fill=(245,205,165))
    # contact point at t=5.0 for six
    a5=math.radians(-70+170*ease((5.0-4.5)/0.55)); CX,CY=px+math.sin(a5)*L,py+math.cos(a5)*L
    # bowler run-up
    bwx=1040-ease((t-0.3)/1.7)*140 if t<2.0 else 900
    ph=math.sin(t*14) if t<2.0 else 0
    if t<2.2 and t>0.2:
        person(c,bwx,GY,(240,240,240),helmet=False,pose=ph*2,stance=1.0)
    if 0.2<t<2.0:
        c.line([(bwx,GY-215),(bwx+20,GY-250)],(245,205,165),16)
    elif 2.0<=t<2.3:
        r=ease((t-2.0)/0.3)*3.2; c.line([(bwx,GY-215),(bwx+math.sin(r)*-70,GY-215-math.cos(r)*70)],(245,205,165),16)
    # ball
    bpos=None; vis=False; rot=t*20
    if 2.0<=t<5.0:
        p=(t-2)/3; vis=True
        if p<0.55:
            q=p/0.55; bpos=(900-(900-640)*q, 960+(GY-30-960)*q*q)
        else:
            q=(p-0.55)/0.45
            if event=="six": bpos=(640-(640-CX)*q, (GY-30)+(CY-(GY-30))*math.sin(q*math.pi/2))
            else: bpos=(640-(640-260)*q, (GY-30)+(GY-110-(GY-30))*math.sin(q*math.pi/2)) # passes under bat toward stumps
    elif t>=5.0:
        if event=="six":
            q=(t-5.0)/2.0
            if q<1.1: vis=True; bpos=(CX+1000*q, CY-1700*q+1100*q*q)
        else:
            vis=t<6.4
            q=(t-5.0)/0.45
            if q<1: bpos=(260-(0), GY-110+ (0))
            else:
                bpos=(260+(t-5.45)*160, GY-30-abs(math.sin((t-5.45)*5))*90*max(0,1-(t-5.45)/1.2))
    if vis and bpos:
        bxp,byp=bpos
        sh=max(0.3,1-abs(GY-30-byp)/900)
        c.ell(bxp,GY+4,26*sh,7*sh,fill=(0,0,0,90))
        if t<5.0 or event=="six":
            for k in range(1,6):
                c.ell(bxp+(k*14 if t<5.0 else -k*10),byp+ (0 if t<5.0 else k*7),max(4,24-k*4),fill=(255,255,255,max(0,90-k*15)))
        ball(c,bxp,byp,rot)
    # particles
    for (vx,vy,col,sz) in parts:
        if event=="six" and t>5.0:
            u=t-5.0
            if u<2.4:
                x=CX+vx*u; y=CY+vy*u+420*u*u
                c.ell(x,y,sz,fill=col+(int(255*(1-u/2.4)),))
        elif event=="bowled" and t>5.45:
            u=t-5.45
            if u<1.2:
                x=ST+vx*u*0.45; y=GY-20+vy*u*0.3+300*u*u
                if y<GY: c.ell(x,y,sz*0.9,fill=(230,210,170,int(255*(1-u/1.2))))
    # top brand + hook
    c.rect(300,50,780,118,(0,0,0,110),34); c.text(540,62,"DASHX Cricket Tennis Ball",F(FM,30),(255,255,255))
    if t<4.2:
        a=ease(t/0.6)*(1-ease((t-3.5)/0.6)); c.text(540,150+(1-ease(t/0.6))*30,hook,F(FB,84),(255,255,255),a)
    if 5.1<t<7.6:
        pop=ease((t-5.1)/0.25); a=pop*(1-ease((t-7.0)/0.6)); word="SIX!" if event=="six" else "BOWLED!"
        sz=int(150+60*(1-pop)) if pop<1 else 190
        c.text(540,520,word,F(FB,sz),acc,a)
    # bottom panel facts
    if t>=7.3:
        a=ease((t-7.3)/0.5)*(1-ease((t-9.6)/0.4))
        c.rect(110,1420,970,1700,(0,0,0,int(150*a)),44)
        c.text(540,1460,fact[0],F(FB,92 if len(fact[0])<14 else 66),acc,a)
        c.text(540,1590,fact[1],F(FL,62),(255,255,255),a)
    # end card
    if t>=9.9:
        a=ease((t-9.9)/0.5)
        ov=Image.new("RGBA",im.size,(0,0,0,int(200*a))); im.alpha_composite(ov); c=Cv(im)
        c.text(540,560,"DASHX",F(FB,230),acc,a)
        c.text(540,840,"Cricket Tennis Balls",F(FM,68),(255,255,255),a)
        c.text(540,960,"Made in Meerut by Nav Durga Sports",F(FL,46),(255,255,255),a)
        by=1250-abs(math.sin((t-9.9)*4))*130*a
        ball(c,540,by,t*16,r=46)
        c.text(540,1420,"Link in bio",F(FB,66),acc,a)
    # flash on hit
    if 5.0<t<5.15:
        fl=Image.new("RGBA",im.size,(255,255,255,int(120*(1-(t-5.0)/0.15)))); im.alpha_composite(fl)
    # screen shake
    out=im.convert("RGB").resize((W,H),Image.LANCZOS)
    return out
def audio(path,event):
    cheer="1.0" if event=="six" else "0.6"
    fc=(f"anoisesrc=c=pink:r=44100:a=0.25:d=12,lowpass=f=1400,highpass=f=200,volume='if(between(t,5,7.8),{cheer}+1.6,0.7)':eval=frame[crowd];"
        "aevalsrc='if(gte(t,5),0.9*sin(2*PI*210*(t-5))*exp(-28*(t-5)),0)':s=44100:d=12[tock];"
        "aevalsrc='if(gte(t,3.65),0.8*sin(2*PI*85*(t-3.65))*exp(-30*(t-3.65)),0)':s=44100:d=12[thud];"
        "[crowd][tock][thud]amix=inputs=3:normalize=0,volume=0.9,afade=t=out:st=11.4:d=0.6")
    return fc
def main(day,out):
    rnd=random.Random(day*7+3)
    pal=PAL[day%len(PAL)]; event=["six","bowled"][day%2]; hook=HOOK[day%len(HOOK)]; fact=FACTS[day%len(FACTS)]
    bgi=bg_static(pal,day)
    parts=[]
    for _ in range(110):
        a=rnd.uniform(-2.8,-0.4) if event=="six" else rnd.uniform(-math.pi,0)
        v=rnd.uniform(200,700) if event=="six" else rnd.uniform(150,500)
        col=rnd.choice([(255,200,40),(255,255,255),(255,90,90),(90,200,255),(120,255,140)]) if event=="six" else (230,210,170)
        parts.append((math.cos(a)*v*(1.0 if event=="six" else 1),math.sin(a)*v,col,rnd.choice((6,8,10,13))))
    tmp=out+".silent.mp4"
    p=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","image2pipe","-framerate",str(FPS),"-i","-","-c:v","libx264","-pix_fmt","yuv420p","-crf","19","-t",str(DUR),tmp],stdin=subprocess.PIPE)
    for i in range(FPS*DUR):
        draw(i/FPS,day,event,pal,hook,fact,bgi,parts,day).save(p.stdin,"JPEG",quality=92)
    p.stdin.close(); p.wait()
    # build audio separately then mux
    a_path=out+".m4a"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-filter_complex",audio(out,event),"-t","12","-c:a","aac","-b:a","128k",a_path],check=True)
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",tmp,"-i",a_path,"-c:v","copy","-c:a","copy","-shortest",out],check=True)
if __name__=="__main__": main(int(sys.argv[1]),sys.argv[2])
