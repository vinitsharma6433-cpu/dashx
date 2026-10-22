import sys, math, subprocess, random
sys.path.insert(0, __file__.rsplit('/',1)[0])
from PIL import Image
from gen2 import Cv, F, FB, FL, FM, ease, lerp, S, W, H, FPS, ball as ball_
GY=1440
SKIN=[(245,205,165),(232,185,140),(210,160,115)]
def bgs():
    im=Image.new("RGBA",(int(W*S),int(H*S))); c=Cv(im)
    for y in range(0,1180,6): c.rect(0,y,W,y+7,lerp((255,196,110),(255,236,190),y/1180))
    c.ell(900,260,80,fill=(255,250,215,255))
    for (x,y,r) in ((200,300,60),(260,290,80),(330,305,55),(640,420,50),(700,410,70),(760,425,50)): c.ell(x,y,r,fill=(255,255,255,235))
    hs=[(-20,640,300,(240,150,130)),(290,570,260,(150,200,230)),(540,660,280,(250,220,140)),(810,600,290,(170,215,160))]
    for x,y,w,col in hs:
        c.rect(x,y,x+w,1180,col); c.rect(x,y-18,x+w,y+6,lerp(col,(0,0,0),0.25))
        for wx in (x+40,x+w-120):
            for wy in (y+50,y+200):
                if wy+80<1160: c.rect(wx,wy,wx+80,wy+86,(255,255,255)); c.rect(wx+4,wy+4,wx+76,wy+82,(120,170,210)); c.line([(wx+40,wy),(wx+40,wy+86)],(255,255,255),5)
        c.rect(x+w/2-36,1050,x+w/2+36,1180,lerp(col,(0,0,0),0.4),6)
    c.rect(0,1180,W,H,(120,120,128)); c.rect(0,1180,W,1230,(190,190,196)); c.rect(0,1230,W,1240,(90,90,98))
    for i in range(0,W,90): c.rect(i,1180,i+4,1230,(165,165,172))
    for i in range(0,W,160): c.rect(i,1740,i+90,1758,(235,235,235))
    c.line([(60,1620),(1020,1620)],(105,105,112),4)
    return im
def face(c,x,y,r,kind,t=0):
    ex=r*0.36; ey=y-r*0.05
    if kind in("happy","smug"):
        c.ell(x-ex,ey,r*0.11,fill=(30,30,30)); c.ell(x+ex,ey,r*0.11,fill=(30,30,30))
        c.d.arc([c.sx(x-r*0.4),c.sx(y+r*0.0),c.sx(x+r*0.4),c.sx(y+r*0.5)],10,170,fill=(120,40,40,255),width=int(c.sx(r*0.09)))
    elif kind=="angry":
        c.ell(x-ex,ey,r*0.11,fill=(30,30,30)); c.ell(x+ex,ey,r*0.11,fill=(30,30,30))
        c.line([(x-ex-r*0.2,ey-r*0.32),(x-ex+r*0.2,ey-r*0.16)],(40,20,20),r*0.1); c.line([(x+ex+r*0.2,ey-r*0.32),(x+ex-r*0.2,ey-r*0.16)],(40,20,20),r*0.1)
        c.d.arc([c.sx(x-r*0.3),c.sx(y+r*0.25),c.sx(x+r*0.3),c.sx(y+r*0.65)],200,340,fill=(120,40,40,255),width=int(c.sx(r*0.09)))
        c.ell(x-r*0.62,y+r*0.15,r*0.14,fill=(255,120,110,160)); c.ell(x+r*0.62,y+r*0.15,r*0.14,fill=(255,120,110,160))
    elif kind=="shock":
        c.ell(x-ex,ey,r*0.2,fill=(255,255,255),outline=(40,40,40),w=1.5); c.ell(x+ex,ey,r*0.2,fill=(255,255,255),outline=(40,40,40),w=1.5)
        c.ell(x-ex,ey,r*0.07,fill=(30,30,30)); c.ell(x+ex,ey,r*0.07,fill=(30,30,30)); c.ell(x,y+r*0.4,r*0.16,r*0.22,fill=(110,30,30))
    elif kind=="laugh":
        for s in(-1,1): c.d.arc([c.sx(x+s*ex-r*0.18),c.sx(ey-r*0.1),c.sx(x+s*ex+r*0.18),c.sx(ey+r*0.2)],200,340,fill=(30,30,30,255),width=int(c.sx(r*0.08)))
        c.d.pieslice([c.sx(x-r*0.4),c.sx(y+r*0.0),c.sx(x+r*0.4),c.sx(y+r*0.6)],0,180,fill=(130,30,40,255))
    elif kind=="cry":
        for s in(-1,1):
            c.d.arc([c.sx(x+s*ex-r*0.18),c.sx(ey-r*0.1),c.sx(x+s*ex+r*0.18),c.sx(ey+r*0.2)],200,340,fill=(30,30,30,255),width=int(c.sx(r*0.08)))
            for k in range(3): c.ell(x+s*(ex+r*0.18),ey+r*0.2+((t*5+k*0.34)%1)*r*0.9,r*0.07,r*0.11,fill=(90,170,255,230))
        c.ell(x,y+r*0.45,r*0.2,r*0.14,fill=(110,30,30))
    elif kind=="serious":
        c.ell(x-ex,ey,r*0.1,fill=(30,30,30)); c.ell(x+ex,ey,r*0.1,fill=(30,30,30)); c.line([(x-r*0.25,y+r*0.45),(x+r*0.25,y+r*0.45)],(110,40,40),r*0.09)
    elif kind=="sad":
        c.ell(x-ex,ey,r*0.1,fill=(30,30,30)); c.ell(x+ex,ey,r*0.1,fill=(30,30,30))
        c.d.arc([c.sx(x-r*0.3),c.sx(y+r*0.3),c.sx(x+r*0.3),c.sx(y+r*0.7)],200,340,fill=(110,40,40,255),width=int(c.sx(r*0.09)))
Cv.sx=lambda s,v: v*S
def kid(c,x,gy,shirt,fc="happy",aL=0.35,aR=-0.35,k=1.6,acc=None,hop=0,skin=0,t=0,tilt=0,hold=None):
    gy=gy-hop; sk=SKIN[skin%3]; leg=(60,70,110)
    hipy=gy-95*k; shy=gy-195*k; hy=gy-252*k; r=44*k
    c.line([(x-18*k,hipy),(x-26*k,gy)],leg,22*k); c.line([(x+18*k,hipy),(x+26*k,gy)],leg,22*k)
    c.rect(x-44*k,gy-2,x-8*k,gy+10*k,(40,40,40),4); c.rect(x+8*k,gy-2,x+44*k,gy+10*k,(40,40,40),4)
    c.line([(x,hipy),(x+tilt,shy)],shirt,58*k)
    c.text(x+tilt,(hipy+shy)/2-9*k,"DASHX",F(FB,14*k),(255,255,255),0.9)
    hands=[]
    for a,sgn in((aL,-1),(aR,1)):
        sx=x+tilt+sgn*26*k; sy=shy+4*k
        ex=sx-math.sin(a)*92*k; ey=sy+math.cos(a)*92*k
        c.line([(sx,sy),(ex,ey)],sk,17*k); c.ell(ex,ey,10*k,fill=sk); hands.append((ex,ey))
    c.ell(x+tilt,hy,r,fill=sk)
    face(c,x+tilt,hy,r,fc,t)
    if acc!='cap': c.d.pieslice([c.sx(x+tilt-r*1.0),c.sx(hy-r*1.08),c.sx(x+tilt+r*1.0),c.sx(hy+r*0.3)],185,355,fill=(35,25,20,255))
    if acc=="glasses":
        for s in(-1,1): c.ell(x+tilt+s*r*0.36,hy-r*0.05,r*0.27,fill=(255,255,255,90),outline=(30,30,30),w=2.5*k/1.2)
        c.line([(x+tilt-r*0.1,hy-r*0.05),(x+tilt+r*0.1,hy-r*0.05)],(30,30,30),2.5)
    if acc=="shades":
        c.rect(x+tilt-r*0.75,hy-r*0.22,x+tilt+r*0.75,hy+r*0.12,(15,15,20),6)
    if acc in("cap","capoff") and acc=="cap":
        c.d.pieslice([c.sx(x+tilt-r*1.02),c.sx(hy-r*1.15),c.sx(x+tilt+r*1.02),c.sx(hy+r*0.7)],180,360,fill=(200,50,50,255)); c.rect(x+tilt-r*0.2,hy-r*0.55,x+tilt+r*1.3,hy-r*0.4,(160,30,30),6)
    return hands,(x+tilt,hy-r)
def bubble(c,x,y,text,t,t0,t1,tail=None,w=620):
    if not(t0<=t<t1): return
    pop=ease((t-t0)/0.15); sc_=0.6+0.4*pop
    fnt=F(FB,44)
    words=text.split(); lines=[]; cur=""
    for wd in words:
        tt=(cur+" "+wd).strip()
        if c.d.textlength(tt,font=fnt)/S>w-60 and cur: lines.append(cur); cur=wd
        else: cur=tt
    lines.append(cur)
    h=len(lines)*62+44; ww=w*sc_; hh=h*sc_
    x0,y0=x-ww/2,y-hh
    c.rect(x0-4,y0-4,x0+ww+4,y0+hh+4,(40,40,40),34*sc_); c.rect(x0,y0,x0+ww,y0+hh,(255,255,255),30*sc_)
    if tail:
        tx,ty=tail; bx=max(x0+50,min(x0+ww-50,tx))
        c.poly([(bx-26,y0+hh-4),(bx+26,y0+hh-4),(tx,ty)],(40,40,40)); c.poly([(bx-20,y0+hh-8),(bx+20,y0+hh-8),(tx,ty-8)],(255,255,255))
    if pop>=1:
        for i,l in enumerate(lines): c.text(x,y0+22+i*62,l,fnt,(30,30,40))
def banner(c,t,t0,t1,text,sz=78):
    if t0<=t<t1:
        a=ease((t-t0)/0.4)*(1-ease((t-t1+0.4)/0.4)); c.rect(60,150,1020,320,(0,0,0,int(150*a)),50)
        c.text(540,172,text,F(FB,sz if len(text)<20 else 62),(255,230,90),a)
def brand(c):
    c.text(540,1560,"DASHX",F(FB,210),(255,255,255),0.10)
    c.rect(300,50,780,118,(0,0,0,110),34); c.text(540,62,"DASHX Cricket Tennis Ball",F(FM,30),(255,255,255))
def endcard(c,im,t,t0,line1,line2):
    if t<t0: return
    a=ease((t-t0)/0.5)
    im.alpha_composite(Image.new("RGBA",im.size,(0,0,0,int(185*a)))); c2=Cv(im)
    c2.text(540,470,"DASHX",F(FB,230),(255,210,50),a)
    by=1000-abs(math.sin((t-t0)*4))*150*a
    c2.ell(540,by+8,60*(0.7+0.3*(by/1000)),14,fill=(0,0,0,90))
    ball_(c2,540,by,(t-t0)*14,r=64)
    c2.text(540,1150,line1,F(FB,58),(255,255,255),a); c2.text(540,1240,line2,F(FM,48),(255,230,120),a)
def stumps(c,x,fall):
    for i,dx in enumerate((-32,0,32)):
        if fall<=0: c.line([(x+dx,GY),(x+dx,GY-225)],(250,250,250),15)
        else:
            ang=fall*(0.5+0.4*i)*(1 if i!=1 else -1.4); x0=x+dx+fall*30*i
            c.line([(x0,GY),(x0+math.sin(ang)*225,GY-math.cos(ang)*225)],(250,250,250),15)
def haha(c,t,t0,t1):
    if t0<=t<t1:
        u=t-t0
        for i in range(4): c.text(200+i*220+math.sin(u*8+i)*20,980-u*60-(i%2)*70,"HA HA",F(FB,64),(255,90,60),1-u/(t1-t0))
def R1(c,im,t,bg):
    B=dict(x=300,sh=(60,110,220)); U=dict(x=560); V=dict(x=860)
    stumps(c,150,ease((t-3.45)/0.5)) 
    fcB="happy"; hopB=0; aRB=-0.35
    if 3.45<=t<4.2: fcB="shock"
    elif 4.2<=t<10.6: fcB="angry"; hopB=abs(math.sin(t*9))*22; aRB=2.6; 
    elif t>=10.6: fcB="laugh"; hopB=abs(math.sin(t*10))*14
    kid(c,300,GY,(60,110,220),fcB,0.35,aRB,hop=hopB,acc=None,skin=0,t=t)
    thr=2.0<=t<2.4
    kid(c,860,GY,(40,170,90),"happy" if t<10.6 else "laugh",0.3,(-2.4 if 2.0<=t<2.5 else -0.35),hop=(abs(math.sin(t*10))*14 if t>=10.6 else 0),skin=1,t=t)
    fu=ease((t-3.4)/0.4)
    kid(c,560,GY-30,(250,200,50),"serious" if t<10.6 else "laugh",0.35,(-0.35+fu*(-2.6) if t<10.6 else -0.35),k=1.4,acc="glasses",hop=(abs(math.sin(t*10))*12 if t>=10.6 else 0),skin=2,t=t)
    if 2.0<=t<3.45:
        q=(t-2.0)/1.45; bx=800-(800-160)*q; by=1180+(GY-60-1180)*q*q-math.sin(q*math.pi)*60; ball_(c,bx,by,t*20)
    elif 3.45<=t<6.0:
        q=(t-3.45); ball_(c,160-q*30,GY-30+abs(math.sin(q*4))*-40*max(0,1-q/1.0),t*10)
    banner(c,t,0.2,2.2,"GALI KA UMPIRE")
    bubble(c,300,860,"Ye no ball thi!",t,4.4,6.6,tail=(300,1000))
    bubble(c,560,860,"Ball DASHX ki thi,",t,6.8,8.5,tail=(560,1000))
    bubble(c,560,860,"galti ball ki nahi, teri hai.",t,8.5,10.8,tail=(560,1000))
    haha(c,t,10.8,13.0)
    brand(c); endcard(c,im,t,13.0,"DASHX ball - Meerut se.","COD aur UPI.")
R1.cues=[("tock",3.45),("pop",4.4),("pop",6.8),("pop",8.5),("laugh",10.8),("tada",13.0)]
def R2(c,im,t,bg):
    wx,wy=860,780
    c.rect(wx-70,wy-20,wx+70,wy+130,(255,255,255)); c.rect(wx-62,wy-12,wx+62,wy+122,(60,40,50))
    aun=6.5<=t<12.4
    if aun:
        a=ease((t-6.5)/0.3); c.ell(wx,wy+70,46,fill=(235,185,140)); c.ell(wx,wy+22,44,30,fill=(40,25,25)); c.ell(wx,wy-10,22,fill=(40,25,25))
        c.ell(wx-16,wy+68,6,fill=(30,30,30)); c.ell(wx+16,wy+68,6,fill=(30,30,30)); c.line([(wx-26,wy+54),(wx-8,wy+58)],(30,20,20),5); c.line([(wx+26,wy+54),(wx+8,wy+58)],(30,20,20),5)
        c.ell(wx,wy+50,5,fill=(220,40,60)); c.line([(wx-14,wy+98),(wx+14,wy+98)],(120,40,50),5)
    sw=ease((t-2.8)/0.3)
    frz=4.4<=t<6.5; sh="shock" if (frz or 6.5<=t<12.0) else "happy"
    kid(c,300,GY,(60,110,220),"happy" if t<4.2 else sh,0.35,0.35,hop=0,t=t,skin=0)
    kid(c,560,GY,(250,120,60),"happy" if t<4.2 else sh,0.35,-0.35,hop=0,t=t,skin=1)
    kid(c,860,GY,(40,170,90),"happy" if t<4.2 else sh,0.3,(-2.4 if 1.8<=t<2.3 else -0.35),hop=0,t=t,skin=2)
    if 1.8<=t<3.0:
        q=(t-1.8)/1.2; ball_(c,820-(820-340)*q,1190+(1210-1190)*q-math.sin(q*math.pi)*60,t*20)
    elif 3.0<=t<4.4:
        q=(t-3.0)/1.4; ball_(c,340+(wx-80-340)*ease(q),1210+(wy+160-1210)*ease(q),t*18)
    elif 4.4<=t<9.0: ball_(c,wx-80+math.sin(t*30)*2,wy+160+math.cos(t*27)*2,0)
    elif 9.0<=t<12.4:
        q=(t-9.0)/3.4
        if q<0.4: ball_(c,wx-80,wy+160,0)
    if 11.0<=t<12.4:
        q=(t-11.0)/1.4; ball_(c,wx-80-(wx-80-560)*q,wy+160+(GY-60-wy-160)*q+(-math.sin(q*math.pi)*120),t*16)
    if frz:
        for x in(300,560,860): c.text(x,780,"!!!",F(FB,80),(230,50,50),ease((t-4.4)/0.2))
    banner(c,t,0.2,2.2,"PADOSI AUNTY KI KHIDKI",72)
    bubble(c,520,520,"Ye DASHX wali hai na?",t,6.8,8.9,tail=(wx,wy+10))
    bubble(c,520,520,"Rakh lo, gali ki jaan hai.",t,9.0,11.4,tail=(wx,wy+10))
    bubble(c,440,860,"Kya?!",t,12.0,13.4,w=360,tail=(560,1000))
    brand(c); endcard(c,im,t,13.4,"DASHX - gali cricket ka asli saathi","Meerut se. COD aur UPI.")
R2.cues=[("tock",3.0),("pop",6.8),("pop",9.0),("pop",12.0),("tada",13.4)]
def R3(c,im,t,bg):
    stumps(c,150,ease((t-8.0)/0.5))
    bw="shock" if 8.0<=t<9.0 else ("cry" if t>=9.0 else "sad")
    kid(c,330,GY,(60,110,220),bw if t>=2.5 else "serious",0.35,-0.35,hop=0,t=t,skin=0)
    if 6.4<=t<7.9:
        a=ease((t-6.4)/1.5)*3.5-1.2
    kid(c,560,GY,(250,120,60),"cry" if t>=9.0 else "sad",0.55,-0.55,hop=(abs(math.sin(t*10))*10 if t>=9 else 0),t=t,skin=1)
    kid(c,740,GY,(180,80,200),"cry" if t>=9.0 else "sad",0.55,-0.55,hop=(abs(math.sin(t*12))*10 if t>=9 else 0),t=t,skin=2,k=1.7)
    bx_=1000-ease((t-2.5)/2.5)*160 if t<5.0 else 840
    if t<6.5: bx_=1000-ease((t-2.5)/3.0)*160
    kid(c,bx_,GY,(40,170,90),"smug" if t>=6.4 and t<9.0 else "happy",0.3,(-2.4 if 6.5<=t<6.9 else -0.35),t=t,skin=1)
    if 6.5<=t<8.0:
        q=(t-6.5)/1.5; ball_(c,bx_-(bx_-160)*q,1180+(GY-60-1180)*q*q,t*20)
    elif 8.0<=t<9.5: ball_(c,160-(t-8.0)*40,GY-30,t*8)
    if 2.5<=t<6.0 and int(t*3)%2==0: c.text(540,430,"SLOW MOTION",F(FB,64),(255,255,255),0.9)
    banner(c,t,0.2,2.4,"LAST BALL. 6 RUN CHAHIYE.",64)
    bubble(c,bx_,880,"Aaj to DASHX hi bachayegi",t,5.0,7.0,tail=(bx_,1000),w=660)
    if t>=9.0:
        c.text(540+math.sin(t*30)*8,650,"HAAAAI!",F(FB,120),(230,50,50),min(1,(t-9.0)/0.3)*(1-ease((t-11.4)/0.6)))
    brand(c); endcard(c,im,t,11.8,"Ball DASHX, drama free.","Meerut se. COD aur UPI.")
R3.cues=[("pop",5.0),("tock",8.0),("pop",9.0),("tada",11.8)]
def R4(c,im,t,bg):
    for i in range(6): c.ell(70+i*40,1400-(i%2)*18,70,fill=(40,130,60))
    c.ell(130,1350,85,fill=(30,110,50))
    shake=math.sin(t*40)*6 if 6.4<=t<8.0 else 0
    if 6.4<=t<8.0:
        for i in range(6): c.ell(70+i*40+shake,1400-(i%2)*18,70,fill=(40,130,60))
    f1=("angry" if 3.2<=t<7.0 else "happy"); 
    kid(c,420,GY,(60,110,220),f1 if t<8.0 else "shock",0.35,(-2.2 if 3.2<=t<6.4 else -0.35),hop=0,t=t,skin=0)
    kid(c,700,GY,(250,120,60),("angry" if 3.2<=t<7.0 else "happy") if t<8.0 else "shock",(2.2 if 3.2<=t<6.4 else 0.35),-0.35,hop=0,t=t,skin=1)
    kid(c,900,GY,(180,80,200),"shock" if t>=8.0 else "sad",0.35,-0.35,k=1.7,t=t,skin=2)
    if t<2.8:
        q=ease((t-1.0)/1.8) if t>1.0 else 0; ball_(c,640-(640-130)*q,GY-30-q*0,t*14+q*10)
    sx=520-ease((t-6.4)/1.3)*360 if 6.4<=t<7.7 else (160 if 7.7<=t<8.0 else None)
    if t>=6.4:
        if t<8.0: kid(c,520-ease((t-6.4)/1.3)*330 if t<7.7 else 190,GY+10,(220,50,60),"happy",0.35,-0.35,k=1.5,acc="cap",t=t,skin=1)
        else:
            bow=ease((t-11.0)/0.5)*0.5 if 11.0<=t<12.2 else 0
            kid(c,300,GY+10,(220,50,60),"happy",-2.6,2.4,k=1.6,acc=None if t>=11.0 else "cap",tilt=bow*60,t=t,skin=1)
            if t<11.0: ball_(c,300-14,GY-390,0)
            for i in range(12):
                a=i/12*2*math.pi+t; c.line([(300,GY-420),(300+math.cos(a)*420,GY-420+math.sin(a)*420)],(255,240,150),6)
    if 2.8<=t<3.2: c.text(540,860,"BALL KAHAN GAYI?!",F(FB,60),(220,50,50),1)
    banner(c,t,0.2,2.2,"BALL KHO GAYI")
    bubble(c,420,880,"Tune maari thi!",t,3.2,4.9,tail=(420,1000),w=500)
    bubble(c,700,880,"Nahi, tune!",t,4.9,6.4,tail=(700,1000),w=420)
    bubble(c,500,800,"Dhundhne wale ko DASHX mil hi jaati hai.",t,8.4,11.0,tail=(300,GY-600),w=720)
    brand(c); endcard(c,im,t,12.6,"Dhundhne wale ko DASHX mil hi jaati hai.","Meerut se. COD aur UPI.")
R4.cues=[("pop",3.2),("pop",4.9),("tada",8.0),("pop",8.4),("tada",12.6)]
def R5(c,im,t,bg):
    for i in range(14):
        a=i/14*2*math.pi+t*0.25; c.poly([(540,1100),(540+math.cos(a)*1500,1100+math.sin(a)*1500),(540+math.cos(a+0.12)*1500,1100+math.sin(a+0.12)*1500)],(255,225,120,120) if False else (255,214,110))
    cols=[(60,110,220),(220,60,70),(40,170,90),(250,150,40)]
    for i,col in enumerate(cols):
        tgt=170+i*240; st=-300-i*150
        x=st+(tgt-st)*ease((t-0.8)/5.4)
        step=abs(math.sin(t*3+i))*10 if t<6.4 else 0
        hands,_=kid(c,x,GY-step,col,"smug",0.35 if i%2 else 0.15,-0.35,k=1.75,acc="shades",t=t,skin=i,hop=0)
        if True: ball_(c,hands[1][0],hands[1][1],t*6,r=32)
    if t<6.4 and int(t*2)%2==0: c.text(540,470,"SLOW MOTION",F(FB,60),(255,255,255),0.95)
    banner(c,t,0.2,2.4,"MEERUT BOYS ENTRY")
    bubble(c,540,830,"Team ka naam? Kuch nahi.",t,6.6,9.4,tail=(170+240*1,1000),w=720)
    bubble(c,540,830,"Ball ka naam? DASHX.",t,9.4,12.0,tail=(170+240*1,1000),w=720)
    brand(c); endcard(c,im,t,12.4,"Made in Meerut.","COD aur UPI.")
R5.cues=[("pop",6.6),("pop",9.4),("tada",12.4)]
REELS=[R1,R2,R3,R4,R5]
NAMES=["umpire","aunty","lastball","lost","entry"]
def audio_expr(cues):
    terms=[]
    for k,T in cues:
        d=f"(t-{T})"
        if k=="pop": terms.append(f"if(between(t,{T},{T+0.2}),0.5*sin(2*PI*(500+3000*{d})*{d})*exp(-16*{d}),0)")
        if k=="tock": terms.append(f"if(gte(t,{T}),0.9*sin(2*PI*210*{d})*exp(-28*{d}),0)")
        if k=="laugh": terms.append(f"if(between(t,{T},{T+2.2}),0.28*sin(2*PI*(320+40*sin(2*PI*7*{d}))*t)*gt(sin(2*PI*6*{d}),0),0)")
        if k=="tada":
            for f,o in((523,0),(659,0.12),(784,0.24),(1046,0.4)): terms.append(f"if(gte(t,{T+o}),0.35*sin(2*PI*{f}*(t-{T+o}))*exp(-5*(t-{T+o})),0)")
    return "+".join(terms)
def main(i,out):
    fn=REELS[i]; DUR=16; bg=bgs()
    tmp=out+".silent.mp4"
    p=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","image2pipe","-framerate",str(FPS),"-i","-","-c:v","libx264","-pix_fmt","yuv420p","-crf","19","-t",str(DUR),tmp],stdin=subprocess.PIPE)
    for n in range(FPS*DUR):
        im=bg.copy(); c=Cv(im); t=n/FPS
        fn(c,im,t,bg)
        im.convert("RGB").resize((W,H),Image.LANCZOS).save(p.stdin,"JPEG",quality=92)
    p.stdin.close(); p.wait()
    ex=audio_expr(fn.cues)
    fc=f"aevalsrc='{ex}':s=44100:d={DUR}[cue];anoisesrc=c=pink:r=44100:a=0.05:d={DUR},lowpass=f=900[amb];[cue][amb]amix=inputs=2:normalize=0,afade=t=out:st={DUR-0.6}:d=0.6"
    a=out+".m4a"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-filter_complex",fc,"-t",str(DUR),"-c:a","aac","-b:a","128k",a],check=True)
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",tmp,"-i",a,"-c:v","copy","-c:a","copy","-shortest",out],check=True)
if __name__=="__main__": main(int(sys.argv[1]),sys.argv[2])
