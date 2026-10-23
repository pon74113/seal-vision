"""One-click Seal helper for the user's full-screen AnyDesk layout."""
import ctypes
from ctypes import wintypes
import os,sys,json,time,re,hashlib,zipfile,threading,queue,io,subprocess
import urllib.request,urllib.parse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import cv2
import numpy as np
from PIL import Image,ImageGrab
from vision_tracker import match_red_bag

try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError,OSError): pass
ROOT=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'SealVision'
ROOT.mkdir(parents=True,exist_ok=True)
sys.path.append(str(ROOT/'ocr_deps'))
u=ctypes.windll.user32
u.GetForegroundWindow.restype=wintypes.HWND
u.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
u.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
u.SetCursorPos.argtypes=[ctypes.c_int,ctypes.c_int]
u.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
u.SetForegroundWindow.argtypes=[wintypes.HWND]

def find_anydesk():
    found=[]
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def inspect(hwnd,param):
        title=ctypes.create_unicode_buffer(1024);u.GetWindowTextW(hwnd,title,1024)
        if 'anydesk' in title.value.lower() and u.IsWindowVisible(hwnd):
            rect=wintypes.RECT();u.GetWindowRect(hwnd,ctypes.byref(rect))
            found.append(((rect.right-rect.left)*(rect.bottom-rect.top),hwnd))
        return True
    u.EnumWindows(callback(inspect),0)
    return max(found)[1] if found else None

def foreground():
    h=u.GetForegroundWindow(); t=ctypes.create_unicode_buffer(1024)
    u.GetWindowTextW(h,t,1024);r=wintypes.RECT();u.GetWindowRect(h,ctypes.byref(r))
    return t.value,[r.left,r.top,r.right,r.bottom]

def parse_ap(text):
    m=re.search(r'(\d{1,6})\s*/\s*(\d{1,6})',text)
    if not m:return None
    current,total=map(int,m.groups())
    return (current,total) if 0<=current<=total and 0<total<1_000_000 else None

def recognize_ap(engine,rgb):
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    votes={}
    for threshold in (100,150,210):
        image=np.where(gray>threshold,0,255).astype(np.uint8)
        image=cv2.resize(image,None,fx=6,fy=6,interpolation=cv2.INTER_NEAREST)
        image=cv2.copyMakeBorder(image,12,12,12,12,cv2.BORDER_CONSTANT,value=255)
        result,_=engine(cv2.cvtColor(image,cv2.COLOR_GRAY2BGR),use_det=False,use_cls=False)
        for text,confidence,*_ in result or []:
            value=parse_ap(text)
            if value and confidence>=.88:votes[value]=votes.get(value,0)+1
    valid=[value for value,count in votes.items() if count>=2]
    return valid[0] if len(valid)==1 else None

VERSION='1.3'
def stage_update(blob,home=ROOT):
    if len(blob)>5_000_000:raise ValueError('ไฟล์อัปเดตใหญ่เกินกำหนด')
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        if len(z.infolist())!=3 or sum(i.file_size for i in z.infolist())>5_000_000:raise ValueError('ขนาดหรือรายการไฟล์ไม่ถูกต้อง')
        m=json.loads(z.read('version.json'))
        if m.get('product')!='SealVision' or m.get('launcher_min',999)>1:raise ValueError('รุ่นอัปเดตไม่รองรับโปรแกรมนี้')
        if set(m['sha256'])!={'seal_app.py','vision_tracker.py'}:raise ValueError('รายการไฟล์ไม่ถูกต้อง')
        data={n:z.read(n) for n in m['sha256']}
        for name,body in data.items():
            if hashlib.sha256(body).hexdigest()!=m['sha256'][name]:raise ValueError('ไฟล์เสียหาย')
            compile(body,name,'exec')
    pending=home/'pending_update';pending.mkdir(parents=True,exist_ok=True)
    # Manifest is the commit marker: an interrupted write cannot be installed.
    (pending/'version.json').unlink(missing_ok=True)
    for name,body in data.items():(pending/name).write_bytes(body)
    temp=pending/'version.tmp';temp.write_text(json.dumps(m),encoding='utf-8');temp.replace(pending/'version.json')
    return m

def version_tuple(value):
    return tuple(int(n) for n in value.lstrip('v').split('.'))

def fetch_https(url,limit):
    if urllib.parse.urlparse(url).scheme!='https':raise ValueError('ต้องใช้ HTTPS')
    req=urllib.request.Request(url,headers={'User-Agent':'SealVision/'+VERSION,'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=25) as response:
        if urllib.parse.urlparse(response.url).scheme!='https':raise ValueError('ลิงก์ดาวน์โหลดไม่ปลอดภัย')
        data=response.read(limit+1)
    if len(data)>limit:raise ValueError('ไฟล์ใหญ่เกินกำหนด')
    return data

class Reader:
    def __init__(self):
        self.request=None;self.result=None;self.error='กำลังเตรียมตัวอ่าน AP';self.ready=False
        self.event=threading.Event();self.closed=False
        threading.Thread(target=self.work,daemon=True).start()
    def work(self):
        try:
            # The stable EXE carries Pillow's core. OCR needs additional Pillow
            # modules from the installed update, using the same Pillow version.
            import PIL
            extra_pil=str(ROOT/'ocr_deps'/'PIL')
            if extra_pil not in PIL.__path__:PIL.__path__.append(extra_pil)
            from rapidocr_onnxruntime import RapidOCR
            engine=RapidOCR(intra_op_num_threads=1,inter_op_num_threads=1)
            self.ready=True;self.error=''
            while not self.closed:
                self.event.wait(.5);self.event.clear()
                request=self.request;self.request=None
                if request is None:continue
                seq,image=request
                try:self.result=(seq,time.monotonic(),recognize_ap(engine,image))
                except Exception as ex:self.error=str(ex);self.result=(seq,time.monotonic(),None)
        except Exception as ex:
            self.error='เปิดตัวอ่าน AP ไม่ได้: '+str(ex)
            import traceback
            (ROOT/'ocr_error.log').write_text(traceback.format_exc(),encoding='utf-8')
    def submit(self,seq,image):
        self.request=(seq,image.copy());self.event.set()

class App:
    def __init__(self):
        self.root=tk.Tk();self.root.title('Seal Vision • อัตโนมัติ');self.root.geometry('660x650')
        self.running=False;self.arming=False;self.bound=None;self.seq=0;self.last_submit=0
        self.update_queue=queue.Queue();self.update_busy=False;self.release=None
        self.reader=Reader();self.status=tk.StringVar(value='เปิด AnyDesk เต็มจอให้เห็นเกม แล้วกดเริ่ม')
        self.ap_status=tk.StringVar(value='AP: กำลังเตรียมตัวอ่านตัวเลข')
        self.round_status=tk.StringVar(value='ทดสอบครบ 0 / 3 รอบ')
        self.test=tk.BooleanVar(value=True);self.hotkeys={}
        self.bag=cv2.imread(str(ROOT/'bag.png'))
        if self.bag is not None:self.bag=cv2.cvtColor(self.bag,cv2.COLOR_BGR2RGB)
        self.reset()
        tk.Label(self.root,text='Seal Vision',font=('Segoe UI',24,'bold')).pack(pady=14)
        tk.Label(self.root,text='AnyDesk เต็มจอแบบภาพอ้างอิง • ไม่ต้องตั้งข้อ 1–6').pack()
        tk.Label(self.root,text='Tab หาเป้าหมาย → 1 / 2 ใช้สกิล → Space เก็บถุงแดง').pack(pady=7)
        tk.Label(self.root,text='อ่านตัวเลข AP • ต่ำกว่า 50% กด 3 • ใช้เลขแถวบน').pack()
        tk.Checkbutton(self.root,text='ทดสอบ 3 รอบแล้วหยุดอัตโนมัติ',variable=self.test).pack(pady=8)
        tk.Button(self.root,text='เริ่ม (F8)',font=('Segoe UI',15,'bold'),bg='#b8e1c3',command=self.start).pack(fill='x',padx=30,pady=5)
        tk.Button(self.root,text='หยุด (F9)',font=('Segoe UI',13),command=self.stop).pack(fill='x',padx=30)
        tk.Label(self.root,textvariable=self.ap_status,fg='#006e87').pack(pady=8)
        tk.Label(self.root,textvariable=self.round_status).pack()
        tk.Label(self.root,textvariable=self.status,wraplength=610,justify='center').pack(padx=20,pady=8)
        self.update_button=tk.Button(self.root,text='ตรวจหาอัปเดต',command=self.online_update)
        self.update_button.pack(fill='x',padx=30,pady=5)
        tk.Label(self.root,text='รุ่น '+VERSION).pack()
        tk.Button(self.root,text='อัปเดตจากไฟล์ ZIP (สำรอง)',command=self.install_update).pack()
        self.root.protocol('WM_DELETE_WINDOW',self.close);self.root.after(150,self.tick)
        if '--test3' in sys.argv:self.root.after(1500,self.auto_start)
    def auto_start(self):
        if not self.reader.ready:
            if self.reader.error.startswith('เปิดตัวอ่าน'):
                self.status.set(self.reader.error);return
            self.root.after(1000,self.auto_start);return
        self.start()
    def event(self,event,**data):
        with (ROOT/'run_events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps({'time':time.time(),'event':event,**data},ensure_ascii=False)+'\n')
    def reset(self):
        self.last={};self.cycles=0;self.phase='seek';self.phase_at=time.monotonic()
        self.ap=None;self.last_ap_seq=-1;self.good_ap=0;self.low=0;self.bag_hits=0;self.bag_absent=0
        self.baseline=None;self.combat=False;self.loot_sent=False;self.bag_observed=False
        self.last_frame=None;self.last_change=time.monotonic();self.last_max=None
        self.round_status.set('ทดสอบครบ 0 / 3 รอบ') if hasattr(self,'round_status') else None
    def start(self):
        if self.running or self.arming:return
        if self.bag is None:self.status.set('ยังไม่พบภาพอ้างอิงถุงแดง');return
        if not self.reader.ready:self.status.set(self.reader.error or 'กำลังเตรียมตัวอ่าน AP กรุณารอสักครู่');return
        self.reset();self.arming=True
        hwnd=find_anydesk()
        if hwnd is None:self.arming=False;self.status.set('ยังไม่พบ AnyDesk กรุณาเปิดการเชื่อมต่อเกมก่อน');return
        self.status.set('กำลังเปิด AnyDesk และตรวจ AP • F9 หยุด')
        self.target_hwnd=hwnd
        self.root.iconify();u.ShowWindow(hwnd,3);u.SetForegroundWindow(hwnd)
        self.root.after(1500,self.bind)
    def bind(self):
        if not self.arming:return
        title,rect=foreground();self.arming=False
        if 'anydesk' not in title.lower():
            self.root.deiconify();self.status.set('ยังไม่เริ่ม: เปิด AnyDesk เต็มจอไว้ด้านหน้า แล้วกดเริ่มใหม่');return
        sw,sh=u.GetSystemMetrics(0),u.GetSystemMetrics(1)
        if rect[2]-rect[0]<sw*.92 or rect[3]-rect[1]<sh*.85:
            self.root.deiconify();self.status.set('ยังไม่เริ่ม: ขยาย AnyDesk ให้เต็มหน้าจอตามภาพอ้างอิง');return
        self.bound=(title,rect);self.running=True;self.event('start',test3=self.test.get(),window=rect)
        self.status.set('เริ่มแล้ว • รอยืนยัน AP จากภาพก่อนส่งปุ่ม')
    def stop(self):
        was=self.running or self.arming;self.running=False;self.arming=False
        self.status.set('หยุดแล้ว');self.root.deiconify()
        if was:self.event('stop',cycles=self.cycles)
    def allowed(self):
        if not self.running or self.bound is None:return False
        title,rect=foreground()
        # The caption changes when AnyDesk reconnects. Bind to the actual
        # window handle so a reconnect does not leave the bot permanently paused.
        return u.GetForegroundWindow()==getattr(self,'target_hwnd',None) and 'anydesk' in title.lower()
    def key(self,code,now):
        if not self.allowed():return False
        u.keybd_event(code,0,0,0);time.sleep(.07);u.keybd_event(code,0,2,0)
        self.event('key',key=chr(code) if code in (49,50,51) else 'Space' if code==32 else 'Tab',ap=self.ap)
        return True
    def ground(self,image,now):
        # Fixed reference layout; reject points whose small patch contains UI,
        # bright objects or strong texture, rather than click a random pixel.
        h,w=image.shape[:2]
        for fx,fy in ((.60,.67),(.56,.70),(.59,.53)):
            x,y=round(w*fx),round(h*fy);patch=image[y-8:y+8,x-8:x+8]
            hsv=cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)
            grass=((hsv[:,:,0]>=15)&(hsv[:,:,0]<=55)&(hsv[:,:,1]>35)&(hsv[:,:,2]>40)&(hsv[:,:,2]<230)).mean()
            if grass>.85 and patch.std()<65 and self.allowed():
                u.SetCursorPos(x,y);u.mouse_event(2,0,0,0,0);u.mouse_event(4,0,0,0,0)
                self.event('walk',point=[x,y]);self.last['walk']=now;return True
        return False
    def tick(self):
        try:
            kind,value=self.update_queue.get_nowait()
            self.update_busy=False;self.update_button.config(state='normal')
            if kind=='release':
                self.release=value;self.update_button.config(text='อัปเดตเลย • '+value['tag_name'])
                self.status.set('พบรุ่นใหม่ กดอัปเดตเลยเพื่อติดตั้ง')
            elif kind=='installed':
                launcher=os.environ.get('SEAL_VISION_LAUNCHER')
                if launcher:
                    subprocess.Popen([launcher]);self.close();return
                self.status.set('ติดตั้งพร้อมแล้ว ปิดและเปิดโปรแกรมเดิมอีกครั้ง')
            else:self.status.set(value)
        except queue.Empty:pass
        for vk,action in ((0x77,self.start),(0x78,self.stop)):
            value=u.GetAsyncKeyState(vk);held=bool(value&0x8000)
            if (value&1) or (held and not self.hotkeys.get(vk)):action()
            self.hotkeys[vk]=held
        if self.running:
            try:self.step()
            except Exception as ex:
                self.stop();self.status.set('หยุดเพราะตรวจภาพไม่ได้: '+str(ex));self.event('error',message=str(ex))
        elif not self.reader.ready:self.ap_status.set(self.reader.error)
        self.root.after(250,self.tick)
    def step(self):
        now=time.monotonic()
        if not self.allowed():self.status.set('พัก: AnyDesk ต้องอยู่ด้านหน้าและเต็มจอขนาดเดิม');return
        image=np.asarray(ImageGrab.grab());h,w=image.shape[:2]
        # Pixel fractions from the user's full-screen 1917 x 1078 reference.
        def crop(box):
            x1,y1,x2,y2=box
            return image[round(y1*h/1078):round(y2*h/1078),round(x1*w/1917):round(x2*w/1917)]
        if now-self.last_submit>.65:
            self.seq+=1;self.reader.submit(self.seq,crop((345,171,429,188)));self.last_submit=now
        result=self.reader.result
        if result is None or now-result[1]>2 or result[2] is None:
            self.good_ap=0;self.low=0;self.status.set('รออ่าน AP ให้ตรงกัน • ไม่ส่งปุ่มขณะอ่านไม่ได้');return
        if result[0]!=self.last_ap_seq:
            self.last_ap_seq=result[0];self.ap=result[2]
            current,total=self.ap
            if self.last_max is not None and total!=self.last_max:
                self.stop();self.status.set('AP สูงสุดเปลี่ยนกะทันหัน กรุณาตรวจภาพก่อนเริ่มใหม่');return
            self.last_max=total;self.good_ap+=1;self.low=self.low+1 if current*2<total else 0
            self.event('ap',current=current,total=total)
            if self.baseline is not None and current<self.baseline-10:self.combat=True
        if self.good_ap<2:return
        current,total=self.ap
        self.ap_status.set(f'AP {current} / {total} = {current/total:.1%}')
        field=crop((175,200,1520,840))
        small=cv2.resize(field,(96,64))
        if self.last_frame is None or np.abs(small.astype(float)-self.last_frame.astype(float)).mean()>.8:self.last_change=now
        self.last_frame=small
        if now-self.last_change>18:
            self.stop();self.status.set('หยุด: ภาพเกมนิ่งเกิน 18 วินาที กรุณาตรวจการเชื่อมต่อ');return
        bag=match_red_bag(crop((700,430,1230,825)),self.bag)
        self.bag_hits=min(3,self.bag_hits+1) if bag>=.82 else 0
        self.bag_absent=min(4,self.bag_absent+1) if bag<.76 else 0
        if self.bag_hits==1:self.event('bag_seen',score=bag)
        if self.low>=2 and now-self.last.get('mana',0)>3:
            if self.key(51,now):self.last['mana']=now
            return
        if self.bag_hits>=2:
            self.phase='loot';self.bag_observed=True
            if now-self.last.get('loot',0)>1:
                if self.key(32,now):self.last['loot']=now;self.loot_sent=True
            self.status.set(f'พบถุงแดง {bag:.2f} • กด Space เก็บของ')
            if now-self.last.setdefault('loot_start',now)>10:
                self.stop();self.status.set('หยุด: ยังเห็นถุงหลังเก็บ 10 วินาที ต้องตรวจระยะเก็บ');return
            return
        if self.phase=='loot':
            if self.bag_absent<3:return
            if self.combat and self.bag_observed and self.loot_sent:
                self.cycles+=1;self.event('cycle_complete',cycle=self.cycles,ap=self.ap)
                self.round_status.set(f'ทดสอบครบ {self.cycles} / 3 รอบ')
                if self.test.get() and self.cycles>=3:
                    self.stop();self.status.set('ผ่าน: ตรวจภาพครบ ค้นหา → สกิล → ถุง → เก็บ 3 รอบ');return
            self.phase='seek';self.phase_at=now;self.baseline=None;self.combat=False;self.bag_observed=False;self.loot_sent=False
            self.last.pop('loot_start',None)
        self.status.set(f'ทำงาน: {self.phase} • AP {current}/{total} • ถุง {bag:.2f} • F9 หยุด')
        if self.phase=='seek':
            if now-self.last.get('walk',now)>8:self.ground(image,now)
            if self.key(9,now):self.phase='one';self.phase_at=now
        elif self.phase=='one' and now-self.phase_at>.8:
            if self.key(49,now):self.phase='two';self.phase_at=now
        elif self.phase=='two' and now-self.phase_at>.8:
            self.baseline=current
            if self.key(50,now):self.phase='wait';self.phase_at=now
        elif self.phase=='wait' and now-self.phase_at>3:
            if not self.combat and now-self.last.get('walk',0)>5:self.ground(image,now)
            if now-self.phase_at>5:self.phase='seek';self.phase_at=now
    def online_update(self):
        if self.update_busy:return
        try:
            config=json.loads((ROOT/'updates.json').read_text(encoding='utf-8'))
            repo=config['repository']
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError()
        except Exception:
            self.status.set('ยังไม่ได้เชื่อมแหล่งอัปเดต GitHub • ต้องเผยแพร่รุ่นแรกก่อน');return
        release=self.release
        if release:self.stop()
        self.update_busy=True;self.update_button.config(state='disabled')
        self.status.set('กำลังดาวน์โหลดและตรวจไฟล์...' if release else 'กำลังตรวจหารุ่นใหม่...')
        def worker():
            try:
                if release:
                    assets=[a for a in release.get('assets',[]) if re.fullmatch(r'SealVision-update-[0-9.]+\.zip',a['name'])]
                    if len(assets)!=1:raise ValueError('ไม่พบไฟล์อัปเดตที่ตรงรุ่น')
                    asset=assets[0];blob=fetch_https(asset['browser_download_url'],5_000_000)
                    digest=asset.get('digest')
                    if not digest or digest!='sha256:'+hashlib.sha256(blob).hexdigest():raise ValueError('ตรวจความถูกต้องของไฟล์ไม่ผ่าน')
                    # Check version before staging executable code.
                    with zipfile.ZipFile(io.BytesIO(blob)) as z:manifest=json.loads(z.read('version.json'))
                    if version_tuple(manifest['version'])!=version_tuple(release['tag_name']):raise ValueError('เลขรุ่นในไฟล์ไม่ตรงกัน')
                    stage_update(blob);self.update_queue.put(('installed',None))
                else:
                    value=json.loads(fetch_https('https://api.github.com/repos/'+repo+'/releases/latest',1_000_000))
                    if version_tuple(value['tag_name'])>version_tuple(VERSION):self.update_queue.put(('release',value))
                    else:self.update_queue.put(('status','ใช้รุ่นล่าสุดแล้ว ('+VERSION+')'))
            except Exception as ex:self.update_queue.put(('error','อัปเดตไม่สำเร็จ: '+str(ex)))
        threading.Thread(target=worker,daemon=True).start()
    def install_update(self):
        self.stop();path=filedialog.askopenfilename(title='เลือกไฟล์อัปเดต',filetypes=[('SealVision update','*.zip')])
        if not path:return
        try:
            stage_update(Path(path).read_bytes())
            self.status.set('อัปเดตพร้อมแล้ว ปิดและเปิดโปรแกรมเดิมอีกครั้ง')
        except Exception as ex:self.status.set('อัปเดตไม่สำเร็จ: '+str(ex))
    def close(self):
        self.running=False;self.arming=False;self.reader.closed=True;self.reader.event.set();self.root.destroy()

if __name__=='__main__':App().root.mainloop()
