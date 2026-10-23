"""One-click Seal helper for the user's full-screen AnyDesk layout."""
import ctypes
from ctypes import wintypes
import os,sys,json,time,re,hashlib,zipfile,threading,queue,io,subprocess
import urllib.request,urllib.parse,base64
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

VERSION='1.6'
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

RETRY_PANEL=base64.b64decode('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')
def detect_retry(rgb):
    # Match the complete supplied Session Closed dialog, including its labels
    # and all three buttons. Never click based on a red rectangle alone.
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    gray=cv2.resize(gray,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
    reference=cv2.imdecode(np.frombuffer(RETRY_PANEL,np.uint8),cv2.IMREAD_GRAYSCALE)
    best=None
    for scale in (.65,.75,.8,.9,1.,1.1,1.25,1.5):
        template=cv2.resize(reference,None,fx=scale*.5,fy=scale*.5,interpolation=cv2.INTER_AREA)
        th,tw=template.shape
        if th>gray.shape[0] or tw>gray.shape[1]:continue
        _,score,_,point=cv2.minMaxLoc(cv2.matchTemplate(gray,template,cv2.TM_CCOEFF_NORMED))
        if score>=.90 and (best is None or score>best[0]):
            # Retry centre relative to the complete 625 x 262 dialog.
            best=(score,round(point[0]*2+370*scale),round(point[1]*2+230*scale))
    return best

SETTINGS_TITLE=base64.b64decode('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')
def detect_settings_minimize(rgb):
    # Only the generic title strip is stored, never the security settings.
    # Require the AnyDesk / Global Settings title AND window controls to match.
    gray=cv2.resize(cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY),None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
    reference=cv2.imdecode(np.frombuffer(SETTINGS_TITLE,np.uint8),0)
    best=None
    for scale in (.65,.75,.8,.9,1.,1.1,1.25,1.5):
        template=cv2.resize(reference,None,fx=scale*.5,fy=scale*.5,interpolation=cv2.INTER_AREA)
        th,tw=template.shape
        if th>gray.shape[0] or tw>gray.shape[1]:continue
        _,score,_,point=cv2.minMaxLoc(cv2.matchTemplate(gray,template,cv2.TM_CCOEFF_NORMED))
        if score<.90:continue
        x,y=point;patch=gray[y:y+th,x:x+tw]
        left=max(5,round(220*scale*.5));right=max(5,round(110*scale*.5))
        title=float(cv2.matchTemplate(patch[:,:left],template[:,:left],cv2.TM_CCOEFF_NORMED)[0,0])
        controls=float(cv2.matchTemplate(patch[:,-right:],template[:,-right:],cv2.TM_CCOEFF_NORMED)[0,0])
        if title>=.90 and controls>=.90 and (best is None or score>best[0]):
            best=(score,round(x*2+649*scale),round(y*2+14*scale))
    return best

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
        self.root=tk.Tk();self.root.title('Seal Vision • อัตโนมัติ');self.root.geometry('660x740')
        self.running=False;self.arming=False;self.bound=None;self.seq=0;self.last_submit=0
        self.update_queue=queue.Queue();self.update_busy=False;self.release=None
        self.reader=Reader();self.status=tk.StringVar(value='เปิด AnyDesk เต็มจอให้เห็นเกม แล้วกดเริ่ม')
        self.ap_status=tk.StringVar(value='AP: กำลังเตรียมตัวอ่านตัวเลข')
        self.round_status=tk.StringVar(value='ทดสอบครบ 0 / 3 รอบ')
        self.test=tk.BooleanVar(value=True);self.hotkeys={}
        try:address=json.loads((ROOT/'connection.json').read_text(encoding='utf-8'))['address']
        except Exception:address=''
        self.address=tk.StringVar(value=address)
        self.last_connect=0;self.monitor=False;self.retry_hits=0;self.retry_at=-100;self.retry_check=0;self.settings_hits=0;self.settings_at=-100
        self.bag=cv2.imread(str(ROOT/'bag.png'))
        if self.bag is not None:self.bag=cv2.cvtColor(self.bag,cv2.COLOR_BGR2RGB)
        self.reset()
        tk.Label(self.root,text='Seal Vision',font=('Segoe UI',24,'bold')).pack(pady=14)
        tk.Label(self.root,text='AnyDesk เต็มจอแบบภาพอ้างอิง • ไม่ต้องตั้งข้อ 1–6').pack()
        tk.Label(self.root,text='Tab หาเป้าหมาย → 1 / 2 ใช้สกิล → Space เก็บถุงแดง').pack(pady=7)
        tk.Label(self.root,text='อ่านตัวเลข AP • ต่ำกว่า 50% กด 3 • ใช้เลขแถวบน').pack()
        connection=tk.Frame(self.root);connection.pack(pady=8)
        tk.Label(connection,text='AnyDesk ID').pack(side='left')
        tk.Entry(connection,textvariable=self.address,width=18).pack(side='left',padx=8)
        tk.Button(connection,text='เชื่อม AnyDesk',command=self.connect_anydesk).pack(side='left')
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
    def connect_anydesk(self):
        address=re.sub(r'\s+','',self.address.get())
        if not re.fullmatch(r'[0-9]{6,12}',address):
            self.status.set('กรอก AnyDesk ID ของเครื่องเกมก่อน');return
        if time.monotonic()-self.last_connect<15:
            self.status.set('ส่งคำขอแล้ว กรุณารอเครื่องเกมยอมรับ');return
        paths=[Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'AnyDesk/AnyDesk.exe',
               Path(os.environ.get('ProgramFiles','C:/Program Files'))/'AnyDesk/AnyDesk.exe',
               Path.home()/'Downloads/AnyDesk.exe']
        executable=next((p for p in paths if p.is_file()),None)
        if executable is None:
            selected=filedialog.askopenfilename(title='เลือก AnyDesk.exe',filetypes=[('AnyDesk','AnyDesk.exe')])
            if not selected:return
            executable=Path(selected)
        try:
            # Official session CLI; no passwords or permission changes.
            subprocess.Popen([str(executable),address],cwd=str(executable.parent))
            (ROOT/'connection.json').write_text(json.dumps({'address':address}),encoding='utf-8')
            self.last_connect=time.monotonic();self.monitor=True
            self.status.set('ส่งคำขอเชื่อม AnyDesk แล้ว • เมื่อเห็นเกมให้กดเริ่ม (F8)')
        except Exception as ex:self.status.set('เชื่อมไม่ได้: '+str(ex))
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
        self.reset();self.arming=True;self.monitor=True
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
        was=self.running or self.arming;self.running=False;self.arming=False;self.monitor=False
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
    def retry_session(self):
        now=time.monotonic()
        title,_=foreground()
        if 'anydesk' not in title.lower():self.retry_hits=0;return False
        hwnd=u.GetForegroundWindow()
        if now-self.retry_check<.8:return getattr(self,'retry_visible',False)
        self.retry_check=now
        image=np.asarray(ImageGrab.grab())
        settings=detect_settings_minimize(image)
        if settings:
            self.settings_hits+=1;self.retry_visible=True
            self.good_ap=0;self.low=0;self.reader.result=None
            self.last_change=now;self.last_frame=None
            self.status.set('พบ Global Settings บังเกม • กำลังย่อหน้าต่าง')
            if self.settings_hits>=2 and now-self.settings_at>=5 and u.GetForegroundWindow()==hwnd:
                _,x,y=settings
                u.SetCursorPos(x,y);u.mouse_event(2,0,0,0,0);u.mouse_event(4,0,0,0,0)
                self.settings_at=now;self.settings_hits=0
                self.event('anydesk_settings_minimized')
            return True
        self.settings_hits=0
        found=detect_retry(image);self.retry_visible=bool(found)
        if not found:self.retry_hits=0;return False
        self.retry_hits+=1;self.good_ap=0;self.low=0;self.reader.result=None
        self.last_change=now;self.last_frame=None
        self.status.set('Session หมด • รอกด Retry อัตโนมัติ • F9 หยุด')
        if self.retry_hits>=2 and now-self.retry_at>=30 and u.GetForegroundWindow()==hwnd:
            _,x,y=found
            # Same foreground window and a freshly matched complete dialog.
            u.SetCursorPos(x,y);u.mouse_event(2,0,0,0,0);u.mouse_event(4,0,0,0,0)
            self.retry_at=now;self.retry_hits=0
            self.phase='seek';self.baseline=None;self.combat=False
            self.bag_observed=False;self.loot_sent=False;self.bag_hits=0;self.bag_absent=0
            self.last.pop('loot_start',None);self.last_max=None
            if self.running:self.target_hwnd=hwnd
            self.event('anydesk_retry')
            self.status.set('กด Retry แล้ว • รอเชื่อมต่อและยืนยันภาพเกม')
        return True
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
        retry_wait=False
        if self.monitor:
            try:retry_wait=self.retry_session()
            except Exception as ex:self.status.set('ตรวจ Retry ไม่ได้: '+str(ex))
        if self.running and not retry_wait:
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
